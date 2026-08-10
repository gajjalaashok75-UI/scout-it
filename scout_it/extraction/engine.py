"""Content extraction engine with multi-strategy fallback."""

import hashlib
import re
import warnings
from html import unescape
from typing import Tuple

import justext
import trafilatura
from boilerpy3 import extractors
from bs4 import BeautifulSoup
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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


class ExtractionEngine:
    """Multi-strategy content extraction engine"""
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ]
    
    def __init__(self):
        self.session = self._create_enterprise_session()
        self.extraction_cache = {}
        
        # Initialize extraction methods with self available
        self.EXTRACTION_METHODS = [
            ('trafilatura', lambda html: trafilatura.extract(html, favor_precision=True, include_formatting=True)),
            ('justext', lambda html: self._justext_extract(html)),
            ('boilerpy3', lambda html: self._boilerpy3_extract(html)),
            ('heuristic-readability', lambda html: self._heuristic_readability_extract(html)),
            ('heuristic', lambda html: self._heuristic_extract(html))
        ]
    
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
        """Multi-fallback extraction with confidence scoring"""
        # Cache check
        content_hash = hashlib.md5(html_content.encode()).hexdigest()
        cache_key = f"{url}:{content_hash}"
        if cache_key in self.extraction_cache:
            return self.extraction_cache[cache_key]
        
        extraction_results = []
        
        # Try all extraction methods in order
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
            except Exception as e:
                continue
        
        # Select best result
        if extraction_results:
            best_result = max(extraction_results, key=lambda x: x['confidence'] * x['word_count'])
            self.extraction_cache[cache_key] = (
                best_result['content'],
                best_result['method'],
                best_result['confidence']
            )
            return best_result['content'], best_result['method'], best_result['confidence']
        
        # Ultimate fallback
        fallback_content = self._ultimate_fallback(html_content)
        self.extraction_cache[cache_key] = (fallback_content, 'fallback', 0.3)
        return fallback_content, 'fallback', 0.3
    
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
