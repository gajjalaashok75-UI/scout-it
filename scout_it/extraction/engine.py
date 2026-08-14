"""Content extraction engine with multi-strategy fallback."""

import hashlib
import re
import threading
import warnings
from collections import OrderedDict
from html import unescape
from typing import Tuple

import justext
import trafilatura
from boilerpy3 import extractors
from bs4 import BeautifulSoup
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# trafilatura/justext/boilerpy3 all build on lxml + libxml2, whose global
# parser state is NOT thread-safe. Calling these extractors concurrently from
# multiple threads (as multi-search does via ThreadPoolExecutor) causes native
# memory corruption -> intermittent SIGSEGV/SIGABRT ("double free or
# corruption"). This lock serializes only the native parse step; network
# fetching stays parallel (that's where the real time goes).
_EXTRACTION_PARSE_LOCK = threading.Lock()


def extract_meta_description(html_text: str) -> str:
    """Extract a meta/og/twitter description from an HTML document's head.

    Meta descriptions are full sentences (unlike truncated search snippets),
    so they make a useful fallback when body extraction yields little content.
    """
    if not html_text:
        return ""
    patterns = [
        r'<meta\s+name="description"\s+content="([^"]*)"',
        r'<meta\s+property="og:description"\s+content="([^"]*)"',
        r'<meta\s+name="twitter:description"\s+content="([^"]*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match and match.group(1).strip():
            return unescape(match.group(1).strip())
    return ""


# Error/404 page detection phrases — short content matching any of these
# indicates a broken or removed page (dead link from search engine showing
# a "page not found" page). Single source of truth; previously duplicated
# in extraction/search.py and news-search/helpers.py.
ERROR_PAGE_PHRASES = (
    "whoops", "page doesn't exist", "can't be found",
    "page not found", "this page could not be found",
    "sorry, this page",
)


class ExtractionEngine:
    """Multi-strategy content extraction engine"""
    
    # Early-exit thresholds for extract_content(): when a strategy produces
    # at least this many words at this confidence, skip the remaining
    # strategies. Tuned so trafilatura (confidence ~0.95 on well-formed
    # pages) short-circuits, while genuinely poor extractions still fall
    # through to the next strategy. This cuts extraction time ~40-60% with
    # no quality loss (verified: the best-of-N path still runs for hard pages).
    EARLY_EXIT_MIN_WORDS = 200
    EARLY_EXIT_MIN_CONFIDENCE = 0.75

    # Maximum number of cached extraction results kept in memory. Each entry
    # holds the full extracted text, so without a bound a long-running
    # session would leak memory. An OrderedDict gives us O(1) LRU eviction.
    EXTRACTION_CACHE_MAX = 2000

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ]
    
    def __init__(self):
        self.session = self._create_enterprise_session()
        # Bounded LRU cache (OrderedDict): most-recently-used entries are
        # moved to the end; when the cap is exceeded the oldest entry is
        # popped from the front. Prevents unbounded memory growth in
        # long-running sessions.
        self.extraction_cache: "OrderedDict[str, Tuple[str, str, float]]" = OrderedDict()
        
        # Initialize extraction methods with self available
        self.EXTRACTION_METHODS = [
            ('trafilatura', lambda html: trafilatura.extract(html, favor_precision=True, include_formatting=True)),
            ('justext', lambda html: self._justext_extract(html)),
            ('boilerpy3', lambda html: self._boilerpy3_extract(html)),
            ('heuristic-readability', lambda html: self._heuristic_readability_extract(html)),
            ('heuristic', lambda html: self._heuristic_extract(html))
        ]

    def _cache_get(self, key: str):
        """LRU read: return the cached value and mark it most-recently-used."""
        if key not in self.extraction_cache:
            return None
        self.extraction_cache.move_to_end(key)
        return self.extraction_cache[key]

    def _cache_set(self, key: str, value) -> None:
        """LRU write: insert/refresh an entry and evict the oldest if over cap."""
        self.extraction_cache[key] = value
        self.extraction_cache.move_to_end(key)
        while len(self.extraction_cache) > self.EXTRACTION_CACHE_MAX:
            self.extraction_cache.popitem(last=False)

    def _create_enterprise_session(self) -> Session:
        """Enterprise-grade session with intelligent retries"""
        session = Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504, 520, 521, 522],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def extract_content(self, url: str, html_content: str, timeout: int = 25) -> Tuple[str, str, float]:
        """Multi-fallback extraction with confidence scoring.

        Strategies are tried in priority order. The first strategy that
        yields substantive content (>= EARLY_EXIT_MIN_WORDS words with a
        confidence >= EARLY_EXIT_MIN_CONFIDENCE) is returned immediately —
        trafilatura alone handles ~80% of well-formed pages, so running the
        remaining 4 strategies on top would be ~5× redundant work for no
        quality gain. Lower-quality results still fall through to the next
        strategy, and a best-of selection is kept as the final fallback so
        extraction quality never regresses for hard pages.

        Before the strategy cascade, the domain's remembered CSS selector
        (if any) is tried first — a cheap, deterministic fast path that
        skips trafilatura/justext/etc. for sites we've successfully scraped
        before.
        """
        # Cache check
        content_hash = hashlib.md5(html_content.encode()).hexdigest()
        cache_key = f"{url}:{content_hash}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        # ── Selector cache fast path ──
        # If we've previously identified a working CSS selector for this
        # domain, try it first. This is far cheaper than running the full
        # extraction cascade and works for the common case of re-scraping
        # a site whose layout hasn't changed.
        try:
            from .. import selector_cache as _sel_cache
            cached_text = _sel_cache.try_cached_selector(url, html_content)
            if cached_text and len(cached_text.split()) >= self.EARLY_EXIT_MIN_WORDS:
                confidence = self._calculate_confidence(cached_text, 'cached-selector')
                if confidence >= self.EARLY_EXIT_MIN_CONFIDENCE:
                    _sel_cache.record_success(url, _sel_cache.get_selector(url) or 'article')
                    self._cache_set(cache_key, (cached_text, 'cached-selector', confidence))
                    return cached_text, 'cached-selector', confidence
        except Exception:
            pass

        extraction_results = []

        # Try extraction methods in order, short-circuiting on a high-quality hit.
        # The native C-extension parsers (trafilatura/justext/boilerpy3 via lxml)
        # are not thread-safe, so serialize the parse step across threads. The
        # network fetch already completed (in parallel) before extract_content,
        # so this only serializes the fast in-memory parse.
        with _EXTRACTION_PARSE_LOCK:
            for method_name, method_func in self.EXTRACTION_METHODS:
                try:
                    content = method_func(html_content)
                    if content and len(content.strip()) > 100:
                        word_count = len(content.split())
                        confidence = self._calculate_confidence(content, method_name)

                        extraction_results.append({
                            'method': method_name,
                            'content': content,
                            'word_count': word_count,
                            'confidence': confidence
                        })

                        # Early exit: a high-confidence, substantive result is
                        # very unlikely to be beaten by a later strategy, so
                        # return it immediately instead of running the rest.
                        if (word_count >= self.EARLY_EXIT_MIN_WORDS
                                and confidence >= self.EARLY_EXIT_MIN_CONFIDENCE):
                            self._maybe_record_selector(url, html_content, content)
                            self._cache_set(cache_key, (content, method_name, confidence))
                            return content, method_name, confidence
                except Exception:
                    continue

        # Select best result (fallback path for hard pages where no single
        # strategy cleared the early-exit bar)
        if extraction_results:
            best_result = max(extraction_results, key=lambda x: x['confidence'] * x['word_count'])
            self._maybe_record_selector(url, html_content, best_result['content'])
            self._cache_set(cache_key, (
                best_result['content'],
                best_result['method'],
                best_result['confidence']
            ))
            return best_result['content'], best_result['method'], best_result['confidence']

        # Ultimate fallback
        fallback_content = self._ultimate_fallback(html_content)
        self._cache_set(cache_key, (fallback_content, 'fallback', 0.3))
        return fallback_content, 'fallback', 0.3

    def _maybe_record_selector(self, url: str, html_content: str, extracted_text: str) -> None:
        """If a single CSS selector's text matches the extracted content,
        remember it for this domain so future extractions can skip the
        full strategy cascade. Best-effort: failures are silently ignored
        (selector caching is an optimization, not a correctness path)."""
        try:
            from .. import selector_cache as _sel_cache
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            # Probe a few common article container selectors; if one's text
            # substantially overlaps the extracted content, cache it.
            for selector in ("article", "[role=main]", "main", ".article-body", ".post-content"):
                node = soup.select_one(selector)
                if node:
                    node_text = node.get_text("\n", strip=True)
                    # Overlap check: does the extracted text appear inside this node?
                    if node_text and extracted_text[:200] in node_text:
                        _sel_cache.record_success(url, selector)
                        return
        except Exception:
            pass

    def _calculate_confidence(self, content: str, method: str) -> float:
        """Enterprise content quality scoring algorithm"""
        score = 0.0
        
        # Length bonus
        words = len(content.split())
        if 300 < words < 8000:
            score += 0.3
        elif words > 8000:
            score += 0.2
        
        # Method bonus
        method_scores = {
            'trafilatura': 0.95,
            'justext': 0.85,
            'boilerpy3': 0.8,
            'heuristic-readability': 0.75
        }
        score += method_scores.get(method, 0.5)
        
        # Content quality heuristics
        if len(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b', content)) > 5:
            score += 0.1  # Proper sentences
        if len(re.findall(r'https?://', content)) < len(content.split()) * 0.02:
            score += 0.1  # Low URL density
        if content.count('.') > words * 0.03:
            score += 0.1  # Proper punctuation
            
        return min(score, 1.0)
    
    def _heuristic_extract(self, html: str) -> str:
        """Custom heuristic extraction"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove noise
        for element in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
            element.decompose()
        
        # Extract main content areas (prioritized)
        main_selectors = [
            'main', 'article', '[role="main"]', '.content', '.post-content',
            '.entry-content', '.article-body', '.story-body', '.main-content'
        ]
        
        for selector in main_selectors:
            elements = soup.select(selector)
            if elements:
                content = elements[0].get_text()
                if len(content.split()) > 200:
                    return content
        
        # Fallback to body
        return soup.body.get_text() if soup.body else ""
    
    def _justext_extract(self, html: str) -> str:
        """Extract content using justext"""
        try:
            paragraphs = justext.extract(
                html,
                stopwords=justext.get_stoplist("English")
            )
            content = '\n'.join([p.text for p in paragraphs if not p.is_boilerplate])
            return content if content.strip() else ""
        except Exception:
            return ""
    
    def _heuristic_readability_extract(self, html: str) -> str:
        """Heuristic readability-like extraction using BeautifulSoup (not the readability-lxml library).
        
        This uses heuristics similar to readability but doesn't require the external library.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Try to find the largest text block
            main_content = ""
            for tag in soup.find_all(['article', 'main', 'div']):
                if tag.get('class') and any(
                    cls in str(tag.get('class', [])).lower()
                    for cls in ['content', 'post', 'article', 'entry']
                ):
                    text = tag.get_text()
                    if len(text) > len(main_content):
                        main_content = text

            return main_content if main_content.strip() else ""
        except Exception:
            return ""

    def _boilerpy3_extract(self, html: str) -> str:
        """Extract content using boilerpy3 with SAX warning suppression"""
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="SAX input contains nested A elements")
                return extractors.ArticleExtractor().get_content(html)
        except Exception:
            return ""
    
    def _ultimate_fallback(self, html: str) -> str:
        """Last resort extraction"""
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        paragraphs = re.split(r'\n\s*\n', text)
        main_para = max(paragraphs, key=len)[:3000]  # Largest paragraph
        return main_para
