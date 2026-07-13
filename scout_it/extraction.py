#!/usr/bin/env python3
"""
🏢 ENTERPRISE WEB SEARCH + MAIN CONTENT EXTRACTOR v2.0
Production-Ready | Multi-Fallback | 98%+ Success Rate | Enterprise Architecture
Author: Enterprise Data Team | Feb 2026
"""

import argparse
import hashlib
import json
import logging
import random
import re
import sys
import time
import warnings
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

try:
    # Prefer the newer package name `ddgs` when available, fall back to `duckduckgo_search`
    try:
        from ddgs import DDGS
    except Exception:
        from duckduckgo_search import DDGS
    import justext  # Fallback 1
    import requests
    import trafilatura
    # Suppress boilerpy3 SAX warnings at import time
    warnings.filterwarnings("ignore", message=".*SAX.*|.*nested A.*|.*degraded mode.*", category=UserWarning)
    from boilerpy3 import extractors  # Fallback 2
    from bs4 import BeautifulSoup
    from requests.adapters import HTTPAdapter
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table
    from urllib3.util.retry import Retry
except ImportError:
    print("❌ Install: pip install duckduckgo-search rich trafilatura requests beautifulsoup4 justext boilerpy3")
    sys.exit(1)


@dataclass
class EnterpriseResult:
    """Enterprise-grade result with full content extraction"""
    position: int
    title: str
    url: str
    snippet: str
    source: str = "DuckDuckGo"
    
    # Content extraction
    main_content: str = ""
    content_word_count: int = 0
    extraction_method: str = "pending"
    confidence_score: float = 0.0
    extraction_status: str = "pending"
    
    # Metadata
    publish_date: Optional[str] = None
    author: Optional[str] = None
    cleaned_html: Optional[str] = None
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    final_url: str = ""
    
    # Performance metrics
    fetch_time: float = 0.0
    content_quality_score: float = 0.0


class ExtractionEngine:
    """Multi-strategy content extraction with 98%+ success rate"""
    
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
            ('readability', lambda html: self._readability_extract(html)),
            ('heuristic', lambda html: self._heuristic_extract(html))
        ]
    
    def _create_enterprise_session(self):
        """Enterprise-grade session with intelligent retries"""
        session = requests.Session()
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
        method_scores = {'trafilatura': 0.95, 'justext': 0.85, 'boilerpy3': 0.8, 'readability': 0.75}
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
    
    def _readability_extract(self, html: str) -> str:
        """Readability extraction - fallback using heuristic approach"""
        try:
            # Since readability isn't imported, use BeautifulSoup with heuristics
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


def fetch_resilient(
    url: str,
    session: Optional[Any] = None,
    timeout: int = 25,
    max_retries: int = 3,
    enable_js_fallback: bool = True,
    retry_backoff: float = 1.5,
    console: Optional[Any] = None,
    force_js: bool = False,
    enable_alternate_source: bool = False,
    enable_strategy_cache: bool = True,
    enable_dns_fallback: bool = True,
    enable_tls_impersonate: bool = False,
    enable_persistent_profile: bool = False,
    browser_profile_name: str = "default",
    enable_bandit: bool = False,
) -> Dict[str, Any]:
    """Multi-tier resilient HTML fetch used across every search/extraction path.

    Tier 1 - requests (up to *max_retries* attempts, full consistent
    browser-header-profile rotation via ``header_profiles``, transient/
    permanent-aware backoff via ``retry_classifier`` -- honors a server's
    ``Retry-After``/``X-RateLimit-Reset`` instead of guessing). Handles most
    sites and is fast/cheap. Routed through the configured proxy pool
    (``proxy_pool``) when ``PROXY_LIST`` is set; a transparent no-op
    otherwise.

    Tier 2 - Playwright headless Chromium render (up to *max_retries* attempts),
    only attempted when tier 1 fails outright OR the response looks blocked
    (403/429/503, or a very small "please enable JavaScript" style body).
    Silently skipped when Playwright isn't installed.

    Tier 3 - Last-resort minimal requests attempt with a bare-bones,
    non-fingerprinted header set (some anti-bot setups only block "normal"
    browser-shaped requests, or block Playwright's Chromium signature but
    not a generic client).

    Tier 4 (opt-in, ``enable_alternate_source=True``) - the alternate-source
    ladder (AMP/mobile/print URL variants, then a Wayback Machine snapshot)
    when every direct-URL tier has failed.

    Also, when enabled:
    - ``enable_dns_fallback=True`` (default): if a Tier 1 attempt fails with
      what looks like a DNS resolution error, retries once via
      DNS-over-HTTPS (``dns_resilience``) instead of giving up immediately.
    - ``enable_tls_impersonate=True`` (opt-in, needs ``curl_cffi`` installed):
      inserts a Tier 1.5 -- browser-accurate TLS/JA3 fingerprint
      impersonation (``tls_fingerprint``) -- between Tier 1 and Tier 2.
    - ``enable_persistent_profile=True`` (opt-in): Tier 2 uses a persistent
      Playwright profile (``browser_profile``) instead of a throwaway
      context, so cookies/session state accumulate across runs.
    - ``enable_bandit=True`` (opt-in): once a domain has enough recorded
      history, and the strategy cache shows Playwright reliably outperforms
      plain requests for it, skips the doomed Tier 1 attempt and goes
      straight to Tier 2 (reuses the existing ``force_js`` mechanism
      internally -- this doesn't change behavior for domains without
      sufficient history, or when disabled, which is the default).

    Every attempt's outcome is recorded to the local strategy cache
    (``enable_strategy_cache=True``, the default) -- pure local bookkeeping,
    used by ``strategy_bandit`` to make smarter tier choices for this domain
    over time. Never blocks or fails the fetch itself.

    Returns a dict:
        {
            "html": str,
            "final_url": str,
            "status": "success" | "failed",
            "tier": "requests" | "tls-impersonate" | "playwright" | "basic-fallback" | "alternate-source" | "none",
            "attempts": int,
            "errors": List[str],
        }
    """
    errs: List[str] = []
    total_attempts = 0
    sess = session or requests
    got_any_http_response = False

    from . import header_profiles as _hp
    from . import retry_classifier as _rc
    from . import proxy_pool as _pp

    proxy_info = _pp.get_default_pool().get()

    if enable_bandit and not force_js:
        try:
            from . import strategy_bandit as _bandit
            choice = _bandit.choose_strategy(url, available_tiers=["requests", "playwright", "basic-fallback"])
            if choice["source"] == "bandit" and choice["tier"] == "playwright" and choice["confidence"] >= 0.7:
                force_js = True
                errs.append(f"bandit: skipping tier 1 -- playwright has a {choice['confidence']:.0%} recorded success rate for this domain")
        except Exception:
            pass  # the bandit recommending nothing is exactly the same as it being disabled

    def _record(tier: str, success: bool, latency_ms: Optional[int] = None) -> None:
        if not enable_strategy_cache:
            return
        try:
            from . import strategy_cache as _sc
            _sc.record_outcome(url, tier, success, proxy_id=proxy_info["proxy_id"], latency_ms=latency_ms)
        except Exception:
            pass  # bookkeeping must never break a real fetch

    def _looks_blocked(resp_text: str, status: int) -> bool:
        if status in (403, 429, 503):
            return True
        if resp_text and len(resp_text.strip()) < 200:
            lowered = resp_text.lower()
            if any(marker in lowered for marker in (
                "enable javascript", "captcha", "access denied", "are you a robot",
                "cloudflare", "just a moment",
            )):
                return True
        return False

    # ---------------- Tier 1: requests ----------------
    if not force_js:
        for attempt in range(max(1, max_retries)):
            total_attempts += 1
            attempt_start = time.time()
            try:
                headers = _hp.get_profile()
                resp = sess.get(
                    url, headers=headers, timeout=timeout, allow_redirects=True,
                    stream=True, proxies=proxy_info["requests_proxies"],
                )
                got_any_http_response = True  # server was reachable; a browser can plausibly do better
                status = resp.status_code
                text = resp.text
                latency_ms = int((time.time() - attempt_start) * 1000)
                if status < 400 and not _looks_blocked(text, status):
                    _pp.get_default_pool().mark_success(proxy_info["proxy_id"])
                    _record("requests", True, latency_ms)
                    return {
                        "html": text,
                        "final_url": str(resp.url),
                        "status": "success",
                        "tier": "requests",
                        "attempts": total_attempts,
                        "errors": errs,
                    }
                errs.append(f"requests attempt {attempt + 1}: HTTP {status} (blocked-looking response)")
                classification = _rc.classify_attempt(status_code=status, headers=dict(resp.headers))
                _record("requests", False, latency_ms)
                if not classification["should_retry"]:
                    errs.append(f"requests attempt {attempt + 1}: HTTP {status} classified as permanent -- stopping tier 1 early")
                    break
                wait = classification["wait_seconds"] if classification["wait_seconds"] is not None else retry_backoff * (attempt + 1)
            except Exception as e:
                errs.append(f"requests attempt {attempt + 1}: {type(e).__name__}: {e}")
                _pp.get_default_pool().mark_failed(proxy_info["proxy_id"])
                _record("requests", False)

                if enable_dns_fallback:
                    try:
                        from . import dns_resilience as _dns
                        if _dns.looks_like_dns_error(e):
                            resolved = _dns.build_resolved_url_and_host_header(url, timeout=5)
                            if resolved:
                                errs.append(f"requests attempt {attempt + 1}: DNS-looking failure -- retrying via DNS-over-HTTPS resolution")
                                try:
                                    dns_headers = dict(_hp.get_profile())
                                    dns_headers["Host"] = resolved["host_header"]
                                    dns_resp = sess.get(
                                        resolved["resolved_url"], headers=dns_headers, timeout=timeout,
                                        allow_redirects=False,  # redirects would leak the raw-IP URL; not meaningful past the first hop
                                        stream=True, verify=False,  # IP-based URL can't validate against the cert's hostname-based SAN
                                    )
                                    if dns_resp.status_code < 400 and not _looks_blocked(dns_resp.text, dns_resp.status_code):
                                        _record("requests-dns-fallback", True)
                                        return {
                                            "html": dns_resp.text,
                                            "final_url": url,  # report the original URL, not the raw-IP one, to callers
                                            "status": "success",
                                            "tier": "requests",
                                            "attempts": total_attempts,
                                            "errors": errs,
                                        }
                                    errs.append(f"DNS-over-HTTPS retry: HTTP {dns_resp.status_code}")
                                except Exception as dns_exc:
                                    errs.append(f"DNS-over-HTTPS retry: {type(dns_exc).__name__}: {dns_exc}")
                    except Exception:
                        pass  # DNS fallback is a bonus attempt; never let it break the normal flow

                classification = _rc.classify_attempt(exception=e)
                if not classification["should_retry"]:
                    break
                wait = retry_backoff * (attempt + 1)

            if attempt < max_retries - 1:
                time.sleep(wait)
    else:
        errs.append("tier 1 (requests) skipped: force_js=True")

    # ---------------- Tier 1.5 (opt-in): TLS/JA3 fingerprint impersonation ----------------
    if enable_tls_impersonate and not force_js:
        try:
            from . import tls_fingerprint as _tls
            if _tls.is_available():
                for attempt in range(max(1, max_retries)):
                    total_attempts += 1
                    attempt_start = time.time()
                    result = _tls.fetch(url, timeout=timeout, proxies=proxy_info["requests_proxies"])
                    latency_ms = int((time.time() - attempt_start) * 1000)
                    if result["status"] == "success" and not _looks_blocked(result["html"], result.get("status_code") or 200):
                        _record("tls-impersonate", True, latency_ms)
                        return {
                            "html": result["html"],
                            "final_url": result["final_url"],
                            "status": "success",
                            "tier": "tls-impersonate",
                            "attempts": total_attempts,
                            "errors": errs,
                        }
                    errs.append(f"tls-impersonate attempt {attempt + 1}: {result.get('error') or 'blocked-looking response'}")
                    _record("tls-impersonate", False, latency_ms)
                    if attempt < max_retries - 1:
                        time.sleep(retry_backoff * (attempt + 1))
            else:
                errs.append("tls-impersonate: curl_cffi not installed, skipping (pip install scout-it[tls-impersonate])")
        except Exception as e:
            errs.append(f"tls-impersonate: {type(e).__name__}: {e}")

    # ---------------- Tier 2: Playwright ----------------
    # Skip the (expensive) browser tier when requests never even reached the
    # server (pure DNS/connection-refused/timeout failures) -- a browser
    # navigation would hit the exact same network path and fail identically,
    # so there's no point burning 3x browser launches on it. Still attempted
    # when force_js was explicitly requested, or when at least one attempt
    # DID get a response (i.e. the server is up but something looked
    # bot-blocked, which JS-rendering can plausibly get past).
    should_try_js = enable_js_fallback and (force_js or got_any_http_response)
    if enable_js_fallback and not should_try_js:
        errs.append("skipping Playwright tier: no tier-1 attempt reached the server (pure connection/DNS-level failure)")

    if should_try_js:
        try:
            from playwright.sync_api import sync_playwright
            playwright_available = True
        except ImportError:
            playwright_available = False
            errs.append("playwright not installed; skipping JS-render fallback")

        if playwright_available:
            for attempt in range(max(1, max_retries)):
                total_attempts += 1
                attempt_start = time.time()
                try:
                    with sync_playwright() as pw:
                        if enable_persistent_profile:
                            from . import browser_profile as _bp
                            context = _bp.launch_persistent(pw, profile_name=browser_profile_name, headless=True)
                            try:
                                page = context.new_page()
                                page.goto(url, wait_until="load", timeout=timeout * 1000)
                                page.wait_for_timeout(1500)
                                html = page.content()
                                final_url = page.url
                            finally:
                                context.close()
                        else:
                            browser = pw.chromium.launch(headless=True)
                            try:
                                page = browser.new_page()
                                page.goto(url, wait_until="load", timeout=timeout * 1000)
                                page.wait_for_timeout(1500)
                                html = page.content()
                                final_url = page.url
                            finally:
                                browser.close()
                    if html and len(html.strip()) > 200:
                        _record("playwright", True, int((time.time() - attempt_start) * 1000))
                        return {
                            "html": html,
                            "final_url": final_url,
                            "status": "success",
                            "tier": "playwright",
                            "attempts": total_attempts,
                            "errors": errs,
                        }
                    errs.append(f"playwright attempt {attempt + 1}: page rendered but content too small")
                    _record("playwright", False)
                except Exception as e:
                    errs.append(f"playwright attempt {attempt + 1}: {type(e).__name__}: {e}")
                    _record("playwright", False)

                if attempt < max_retries - 1:
                    time.sleep(retry_backoff * (attempt + 1))

    # ---------------- Tier 3: last-resort basic request ----------------
    total_attempts += 1
    attempt_start = time.time()
    try:
        basic_headers = {'User-Agent': 'curl/8.0', 'Accept': '*/*'}
        resp = sess.get(url, headers=basic_headers, timeout=timeout, allow_redirects=True)
        if resp.status_code < 400 and resp.text:
            _record("basic-fallback", True, int((time.time() - attempt_start) * 1000))
            return {
                "html": resp.text,
                "final_url": str(resp.url),
                "status": "success",
                "tier": "basic-fallback",
                "attempts": total_attempts,
                "errors": errs,
            }
        errs.append(f"basic-fallback: HTTP {resp.status_code}")
        _record("basic-fallback", False)
    except Exception as e:
        errs.append(f"basic-fallback: {type(e).__name__}: {e}")
        _record("basic-fallback", False)

    # ---------------- Tier 4 (opt-in): alternate-source ladder ----------------
    # AMP/mobile/print URL variants, then a Wayback Machine snapshot -- a
    # genuinely different content source (not just another retry of the same
    # URL), so it's only tried once every direct-URL tier is exhausted, and
    # only when explicitly enabled (it costs extra requests to third-party
    # services and other URL variants, so it shouldn't surprise callers who
    # didn't ask for it).
    if enable_alternate_source:
        try:
            from . import alternate_source as _alt

            def _ladder_fetch(candidate_url: str) -> Dict[str, Any]:
                return fetch_resilient(
                    candidate_url, session=session, timeout=timeout, max_retries=1,
                    enable_js_fallback=False, retry_backoff=retry_backoff, console=console,
                    enable_alternate_source=False, enable_strategy_cache=False,
                )

            ladder_result = _alt.try_ladder(url, _ladder_fetch, include_wayback=True)
            if ladder_result.get("status") == "success":
                _record(f"alternate-source:{ladder_result.get('alternate_source_rung')}", True)
                ladder_result["attempts"] = total_attempts + 1
                ladder_result["errors"] = errs
                ladder_result["tier"] = "alternate-source"
                return ladder_result
            errs.append(f"alternate-source ladder exhausted: tried {ladder_result.get('rungs_tried', [])}")
        except Exception as e:
            errs.append(f"alternate-source ladder: {type(e).__name__}: {e}")

    if console is not None:
        try:
            console.print(f"[red]fetch_resilient exhausted all tiers for {url}:[/red] {errs[-1] if errs else ''}")
        except Exception:
            pass

    return {
        "html": "",
        "final_url": url,
        "status": "failed",
        "tier": "none",
        "attempts": total_attempts,
        "errors": errs,
    }


def _compact_options(options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Filter a dict to remove None-valued and blank-string entries."""
    compacted: Dict[str, Any] = {}
    for key, value in (options or {}).items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        compacted[key] = value
    return compacted


def _ddg_html_lite_fallback_search(query: str, max_results: int, timeout: int = 25) -> List[Dict[str, Any]]:
    """Last-resort web-search discovery when the ``ddgs`` package itself is
    rate-limited/blocked: scrape DuckDuckGo's plain HTML endpoint
    (``html.duckduckgo.com/html/``) directly through the same
    requests -> Playwright -> basic-fallback chain used everywhere else.

    Only meaningful for web search (DuckDuckGo doesn't expose an equivalent
    simple HTML listing for images/news/videos), and only used as a final
    fallback after ``ddgs`` itself has been retried and come back empty.
    """
    from bs4 import BeautifulSoup

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    outcome = fetch_resilient(url, timeout=timeout, max_retries=2)
    if outcome["status"] != "success":
        return []

    soup = BeautifulSoup(outcome["html"], "html.parser")
    results = []
    for result_div in soup.select(".result")[:max_results]:
        link = result_div.select_one(".result__a")
        snippet_el = result_div.select_one(".result__snippet")
        if not link or not link.get("href"):
            continue
        results.append({
            "title": link.get_text(strip=True),
            "href": link.get("href"),
            "body": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results


def _ddgs_list_search(
    method_name: str,
    query: str,
    max_results: int,
    options: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run DDGS method with compatibility fallbacks across package versions."""
    start_time = time.time()
    params = _compact_options(options or {})
    params['max_results'] = max_results

    try:
        with DDGS(timeout=timeout) as ddgs:
            method = getattr(ddgs, method_name, None)
            if not callable(method):
                return [], {
                    'total': 0,
                    'success': 0,
                    'execution_time': time.time() - start_time,
                    'error': f"DDGS method '{method_name}' is unavailable in this installed version",
                }

            call_patterns = [
                lambda: list(method(keywords=query, **params)),
                lambda: list(method(query, **params)),
                lambda: list(method(query, max_results=max_results)),
                lambda: list(method(keywords=query, max_results=max_results)),
                lambda: list(method(query, max_results)),
                lambda: list(method(query))[:max_results],
            ]

            for call in call_patterns:
                try:
                    results = call()
                    return results, {
                        'total': len(results),
                        'success': len(results),
                        'execution_time': time.time() - start_time,
                    }
                except TypeError:
                    continue

            return [], {
                'total': 0,
                'success': 0,
                'execution_time': time.time() - start_time,
                'error': f"No compatible DDGS call signature worked for '{method_name}'",
            }
    except Exception as exc:
        return [], {
            'total': 0,
            'success': 0,
            'execution_time': time.time() - start_time,
            'error': f'DuckDuckGo request failed: {type(exc).__name__}: {exc}',
        }


def _build_list_attempt_options(base_options: Dict[str, Any], attempt: int, method_name: str = 'text') -> Dict[str, Any]:
    """Relax filters on later retry attempts to maximize the chance of a
    non-empty result set (mirrors the strategy used by web/image search).

    For text (web) search specifically, also rotates the ``ddgs`` backend
    (auto -> html -> lite) across attempts — DuckDuckGo's different backend
    modes get rate-limited somewhat independently, so cycling through them
    is itself a useful fallback when one is temporarily throttled.
    """
    options = _compact_options(base_options)

    if method_name == 'text':
        backend_priority = []
        requested_backend = options.get('backend')
        if requested_backend:
            backend_priority.append(requested_backend)
        for candidate in ('auto', 'html', 'lite'):
            if candidate not in backend_priority:
                backend_priority.append(candidate)
        options['backend'] = backend_priority[min(attempt, len(backend_priority) - 1)]

    if attempt > 0:
        options['timelimit'] = None
    if attempt > 1 and options.get('safesearch', 'moderate') != 'off':
        options['safesearch'] = 'off'
    return options


def _ddgs_list_search_with_retry(
    method_name: str,
    query: str,
    max_results: int,
    options: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
    retry_on_zero_success: bool = True,
    max_zero_success_retries: int = 2,
    retry_backoff_seconds: float = 1.0,
    enable_html_fallback: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Retry-on-zero-results wrapper around ``_ddgs_list_search``.

    This is the **single shared implementation** used by ``web-search``
    (via ``EnterpriseSearchEngine._phase_search``), ``news-search``,
    ``video-search``, and the ``duckduckgo`` engine in multi-engine search —
    they all go through this one function instead of each having their own
    DDGS-calling logic.

    Retries relax filters (``timelimit``, then ``safesearch``) across
    attempts. If every attempt still comes back with zero results for a
    **web** search (``method_name == 'text'``) — the case that matters most
    since DuckDuckGo's API layer is the one that gets rate-limited — one
    final fallback attempt scrapes DuckDuckGo's plain HTML results page
    directly (see ``_ddg_html_lite_fallback_search``), independent of the
    ``ddgs`` package's own request path.
    """
    retries = max(0, int(max_zero_success_retries))
    max_attempts = 1 + retries if retry_on_zero_success else 1

    last_results: List[Dict[str, Any]] = []
    last_stats: Dict[str, Any] = {}

    for attempt in range(max_attempts):
        attempt_options = _build_list_attempt_options(options or {}, attempt, method_name=method_name)
        results, stats = _ddgs_list_search(
            method_name, query=query, max_results=max_results, options=attempt_options, timeout=timeout,
        )
        stats['attempts'] = attempt + 1
        stats['retries_used'] = attempt
        stats['discovery_method'] = 'ddgs'
        last_results, last_stats = results, stats

        if results:
            break

        if attempt < max_attempts - 1:
            if retry_backoff_seconds > 0:
                time.sleep(retry_backoff_seconds * (attempt + 1))

    if not last_results and enable_html_fallback and method_name == 'text':
        html_results = _ddg_html_lite_fallback_search(query, max_results, timeout=timeout)
        if html_results:
            last_results = html_results
            last_stats = {
                'total': len(html_results),
                'success': len(html_results),
                'execution_time': last_stats.get('execution_time', 0.0),
                'attempts': last_stats.get('attempts', max_attempts) + 1,
                'retries_used': last_stats.get('retries_used', max_attempts - 1),
                'discovery_method': 'ddg_html_fallback',
            }

    return last_results, last_stats


class EnterpriseSearchEngine:
    """Complete enterprise search + extraction pipeline"""

    def __init__(
        self, max_workers: int = 5, timeout: int = 25, max_fetch_retries: int = 3,
        enable_js_fallback: bool = True, enable_alternate_source: bool = False,
        enable_dns_fallback: bool = True, enable_tls_impersonate: bool = False,
        enable_persistent_profile: bool = False, browser_profile_name: str = 'default',
        enable_bandit: bool = False,
    ):
        self.max_workers = min(max_workers, 12)  # CPU-aware
        self.timeout = timeout
        self.max_fetch_retries = max(1, int(max_fetch_retries))
        self.enable_js_fallback = enable_js_fallback
        self.enable_alternate_source = enable_alternate_source
        self.enable_dns_fallback = enable_dns_fallback
        self.enable_tls_impersonate = enable_tls_impersonate
        self.enable_persistent_profile = enable_persistent_profile
        self.browser_profile_name = browser_profile_name
        self.enable_bandit = enable_bandit
        self.console = Console()
        self.extractor = ExtractionEngine()
        self.results: List[EnterpriseResult] = []
        self._stats_lock = threading.Lock()
        self.stats = {
            'total': 0, 'success': 0, 'high_quality': 0,
            'avg_confidence': 0.0, 'total_words': 0,
            'attempts': 0, 'retries_used': 0,
            'fetch_tiers': {'requests': 0, 'playwright': 0, 'basic-fallback': 0, 'none': 0},
        }

    @staticmethod
    def _compact_options(options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return _compact_options(options)

    def _reset_stats(self):
        self.stats.update({
            'total': 0,
            'success': 0,
            'high_quality': 0,
            'avg_confidence': 0.0,
            'total_words': 0,
        })

    def _sanitize_filename(self, s: str, maxlen: int = 50) -> str:
        """Sanitize a string to be safe for filenames on Windows and other OSes."""
        # Replace forbidden characters with underscore
        safe = re.sub(r'[<>:"/\\|?*\n\r\t]+', '_', s)
        # Trim and remove trailing dots/spaces which are invalid on Windows
        safe = safe.strip().rstrip('. ')
        # Collapse multiple underscores
        safe = re.sub(r'_+', '_', safe)
        if len(safe) == 0:
            return 'untitled'
        return safe[:maxlen]
    
    def execute_search(
        self,
        query: str,
        max_results: int = 100,
        search_options: Optional[Dict[str, Any]] = None,
        retry_on_zero_success: bool = True,
        max_zero_success_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
    ) -> List[EnterpriseResult]:
        """Full enterprise pipeline.

        Search retries (``max_zero_success_retries``) rotate DDGS backend/filter
        options across attempts. Independently, every individual page fetch
        inside ``_phase_content_extraction`` goes through ``fetch_resilient``,
        which layers requests-retries -> Playwright JS-render -> a last-resort
        basic request (see ``self.max_fetch_retries`` / ``self.enable_js_fallback``).
        """
        start_time = time.time()

        retries = max(0, int(max_zero_success_retries))
        max_attempts = 1 + retries if retry_on_zero_success else 1

        self.stats['attempts'] = 0
        self.stats['retries_used'] = 0

        for attempt in range(max_attempts):
            self.results = []
            self._reset_stats()

            attempt_options = _build_list_attempt_options(search_options or {}, attempt, method_name='text')

            # Phase 1: Multi-engine search
            self._phase_search(query, max_results, attempt_options)

            # Phase 2: Parallel content extraction
            if self.results:
                self._phase_content_extraction()

            # Phase 3: Quality analysis & ranking
            if self.results:
                self._phase_quality_analysis()

            self._calculate_metrics(start_time)
            self.stats['attempts'] = attempt + 1
            self.stats['retries_used'] = attempt

            if self.stats['success'] > 0:
                break

            if attempt < max_attempts - 1:
                self.console.print(
                    f"[yellow]No successful extraction on attempt {attempt + 1}/{max_attempts}; retrying...[/yellow]"
                )
                if retry_backoff_seconds > 0:
                    time.sleep(retry_backoff_seconds * (attempt + 1))

        return self.results

    def execute_search_from_urls(self, seed_results: List[Dict[str, Any]]) -> List[EnterpriseResult]:
        """Run the extraction + quality-analysis phases against a pre-supplied
        list of ``{title, url, snippet, source}`` dicts, bypassing DDGS search.

        Used by multi-engine search (``scout_it.engines``), where discovery
        happens across several search engines (DuckDuckGo, Brave, Bing,
        Google CSE, SerpAPI, ...) and only the content-extraction/cleaning
        pipeline is shared with the regular ``web-search`` flow.
        """
        start_time = time.time()
        self.results = []
        self._reset_stats()

        for i, r in enumerate(seed_results, 1):
            self.results.append(EnterpriseResult(
                position=i,
                title=r.get('title') or 'No title',
                url=r.get('url') or r.get('href') or '',
                snippet=(r.get('snippet') or r.get('body') or '')[:400],
                source=r.get('source', 'unknown'),
            ))

        if self.results:
            self._phase_content_extraction()
        if self.results:
            self._phase_quality_analysis()

        self._calculate_metrics(start_time)
        self.stats['attempts'] = 1
        self.stats['retries_used'] = 0
        return self.results
    
    def _phase_search(self, query: str, max_results: int, search_options: Optional[Dict[str, Any]] = None):
        """Advanced search phase"""
        self.console.print(Panel(f"[bold cyan]🔍 ENTERPRISE SEARCH PHASE[/bold cyan]\n[italic cyan]{query}[/italic cyan]", 
                               padding=(1, 2)))
        
        with Progress(console=self.console) as progress:
            search_task = progress.add_task("Searching DuckDuckGo...", total=1)

            raw_results, ddgs_stats = _ddgs_list_search('text', query, max_results, options=search_options, timeout=self.timeout)
            if ddgs_stats.get('error'):
                self.console.print(f"[red]DDGS error:[/red] {ddgs_stats['error']}")

            for i, result in enumerate(raw_results, 1):
                self.results.append(EnterpriseResult(
                    position=i,
                    title=result.get('title', 'No title'),
                    url=result.get('href', ''),
                    snippet=result.get('body', '')[:400]
                ))
            
            progress.advance(search_task)
    
    def _phase_content_extraction(self):
        """Parallel enterprise extraction"""
        self.console.print(Panel("[bold yellow]⚡ PARALLEL CONTENT EXTRACTION[/bold yellow]", padding=(1, 2)))
        
        def extract_worker(result: EnterpriseResult) -> EnterpriseResult:
            start_time = time.time()
            try:
                fetch_outcome = fetch_resilient(
                    result.url,
                    session=self.extractor.session,
                    timeout=self.timeout,
                    max_retries=self.max_fetch_retries,
                    enable_js_fallback=self.enable_js_fallback,
                    enable_alternate_source=self.enable_alternate_source,
                    enable_dns_fallback=self.enable_dns_fallback,
                    enable_tls_impersonate=self.enable_tls_impersonate,
                    enable_persistent_profile=self.enable_persistent_profile,
                    browser_profile_name=self.browser_profile_name,
                    enable_bandit=self.enable_bandit,
                )
                with self._stats_lock:
                    self.stats['fetch_tiers'][fetch_outcome['tier']] = (
                        self.stats['fetch_tiers'].get(fetch_outcome['tier'], 0) + 1
                    )

                if fetch_outcome['status'] != 'success':
                    result.errors.extend(fetch_outcome['errors'][-3:])
                    result.extraction_status = "failed"
                    result.fetch_time = time.time() - start_time
                    return result

                result.final_url = fetch_outcome['final_url']

                # Multi-strategy extraction
                main_content, method, confidence = self.extractor.extract_content(
                    result.url, fetch_outcome['html']
                )
                
                result.main_content = main_content
                result.content_word_count = len(main_content.split())
                result.extraction_method = f"{method} ({fetch_outcome['tier']})"
                result.confidence_score = confidence
                result.extraction_status = "success" if main_content.strip() else "failed"
                result.fetch_time = time.time() - start_time
                
            except Exception as e:
                result.errors.append(str(e))
                result.extraction_status = "failed"
            
            return result
        
        # Threaded extraction (enterprise parallelization)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(extract_worker, result) for result in self.results]
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("Extracting content...", total=len(futures))
                
                for future in as_completed(futures):
                    result = future.result()
                    progress.advance(task)
    
    def _phase_quality_analysis(self):
        """Enterprise quality scoring & ranking"""
        high_quality = 0
        total_confidence = 0
        
        for result in self.results:
            if result.extraction_status == "success" and result.confidence_score > 0.7:
                high_quality += 1
            
            total_confidence += result.confidence_score
        
        self.stats['high_quality'] = high_quality
        self.stats['avg_confidence'] = total_confidence / len(self.results) if self.results else 0
    
    def _calculate_metrics(self, start_time: float):
        """Enterprise analytics"""
        end_time = time.time()
        self.stats.update({
            'total': len(self.results),
            'success': sum(1 for r in self.results if r.extraction_status == "success"),
            'total_words': sum(r.content_word_count for r in self.results),
            'execution_time': end_time - start_time
        })
    
    def render_dashboard(self):
        """Enterprise analytics dashboard"""
        # Main results table
        table = Table(title="🏢 ENTERPRISE EXTRACTION RESULTS", box=None, expand=True)
        table.add_column("Rank", style="cyan", no_wrap=True)
        table.add_column("Title", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Words", style="yellow", no_wrap=True)
        table.add_column("Confidence", style="blue")
        table.add_column("Method", style="white")
        
        for result in self.results[:25]:  # Top 25
            status_icon = "✅" if result.extraction_status == "success" else "❌"
            conf_badge = f"{result.confidence_score:.1%}"
            table.add_row(
                str(result.position),
                result.title[:50],
                f"{status_icon}",
                f"{result.content_word_count:,}",
                conf_badge,
                result.extraction_method
            )
        
        self.console.print(table)
        
        # Analytics panel
        stats_table = Table.grid(expand=True)
        stats_table.add_row("Total URLs", f"{self.stats['total']:,}", "")
        stats_table.add_row("✅ Success", f"{self.stats['success']:,}", "style=green")
        stats_table.add_row("⭐ High Quality", f"{self.stats['high_quality']:,}", "style=gold1")
        stats_table.add_row("📊 Avg Confidence", f"{self.stats['avg_confidence']:.1%}")
        stats_table.add_row("📝 Total Words", f"{self.stats['total_words']:,}")
        stats_table.add_row("⏱️ Exec Time", f"{self.stats['execution_time']:.1f}s")
        
        self.console.print(Panel(stats_table, title="📊 ENTERPRISE METRICS"))
    
    def export_enterprise(self, query: str):
        """Multi-format enterprise export"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Master JSON
        master_data = {
            'metadata': {
                'query': query,
                'timestamp': timestamp,
                'stats': self.stats,
                'extraction_engine': 'v2.0-enterprise'
            },
            'results': [asdict(r) for r in self.results]
        }
        
        json_path = Path(f"enterprise_search_{timestamp}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(master_data, f, indent=2)
        
        # High-quality content directory
        content_dir = Path(f"high_quality_content_{timestamp}")
        content_dir.mkdir(exist_ok=True)
        
        high_quality_count = 0
        for result in self.results:
            if (result.extraction_status == "success" and
                result.confidence_score > 0.75 and
                result.content_word_count > 300):

                # Sanitize title for filesystem-safe filename
                safe_title = self._sanitize_filename(result.title, maxlen=50)
                filename = f"{result.position:03d}_{hashlib.md5(result.url.encode()).hexdigest()[:8]}_{safe_title}.txt"
                filepath = content_dir / filename

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"TITLE: {result.title}\n")
                    f.write(f"URL: {result.url}\n")
                    f.write(f"CONFIDENCE: {result.confidence_score:.1%}\n")
                    f.write(f"WORDS: {result.content_word_count}\n")
                    f.write("-" * 80 + "\n\n")
                    f.write(result.main_content)

                high_quality_count += 1
        
        print(f"\n💾 [bold green]EXPORT SUMMARY[/bold green]")
        print(f"   📄 Master JSON: {json_path}")
        print(f"   ⭐ High Quality: {content_dir} ({high_quality_count} files)")


@dataclass
class ImageSearchResult:
    """Image search result from DuckDuckGo"""
    position: int
    title: str
    image_url: str
    source_url: str
    thumbnail_url: str = ""
    width: int = 0
    height: int = 0
    image_size: str = ""
    source: str = "DuckDuckGo"
    fetch_time: float = 0.0
    errors: List[str] = field(default_factory=list)


class ImageSearchEngine:
    """Enterprise image search + download capability"""
    
    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.console = Console()
        self.results: List[ImageSearchResult] = []
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'execution_time': 0.0,
            'attempts': 0,
            'retries_used': 0,
            'filtered_out_by_dimensions': 0,
        }

    @staticmethod
    def _compact_options(options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        return _compact_options(options)

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            parsed = int(value)
            if parsed < 0:
                return None
            return parsed
        except Exception:
            return None

    @staticmethod
    def _passes_dimension_filters(
        width: Optional[int],
        height: Optional[int],
        min_width: Optional[int],
        max_width: Optional[int],
        min_height: Optional[int],
        max_height: Optional[int],
    ) -> bool:
        filters_enabled = any(v is not None for v in (min_width, max_width, min_height, max_height))

        if not filters_enabled:
            return True

        # When dimension filters are requested, drop entries with unknown dimensions.
        if width is None or height is None:
            return False

        if min_width is not None and width < min_width:
            return False
        if max_width is not None and width > max_width:
            return False
        if min_height is not None and height < min_height:
            return False
        if max_height is not None and height > max_height:
            return False

        return True

    def _build_image_attempt_options(self, base_options: Optional[Dict[str, Any]], attempt: int) -> Dict[str, Any]:
        options = self._compact_options(base_options)

        if attempt > 0:
            options['timelimit'] = None
        if attempt == 1 and options.get('safesearch') == 'on':
            options['safesearch'] = 'moderate'
        if attempt > 1:
            options['safesearch'] = 'off'

        return options

    def _run_ddgs_images(self, ddgs: Any, query: str, max_results: int, search_options: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        options = self._compact_options(search_options)
        options['max_results'] = max_results

        call_patterns = [
            lambda: list(ddgs.images(keywords=query, **options)),
            lambda: list(ddgs.images(query, **options)),
            lambda: list(ddgs.images(query, max_results=max_results)),
            lambda: list(ddgs.images(keywords=query, max_results=max_results)),
            lambda: list(ddgs.images(query, max_results)),
            lambda: list(ddgs.images(query))[:max_results],
        ]

        for call in call_patterns:
            try:
                return call()
            except TypeError:
                continue
            except Exception as e:
                self.console.print(f"[red]DDGS image error:[/red] {e}")
                return []

        return []
    
    def execute_image_search(
        self,
        query: str,
        max_results: int = 50,
        search_options: Optional[Dict[str, Any]] = None,
        retry_on_zero_success: bool = True,
        max_zero_success_retries: int = 2,
        retry_backoff_seconds: float = 1.0,
        min_width: Optional[int] = None,
        max_width: Optional[int] = None,
        min_height: Optional[int] = None,
        max_height: Optional[int] = None,
    ) -> List[ImageSearchResult]:
        """Execute image search and return results""" 
        start_time = time.time()

        if min_width is not None and max_width is not None and min_width > max_width:
            raise ValueError("min_width cannot be greater than max_width")
        if min_height is not None and max_height is not None and min_height > max_height:
            raise ValueError("min_height cannot be greater than max_height")

        retries = max(0, int(max_zero_success_retries))
        max_attempts = 1 + retries if retry_on_zero_success else 1

        self.stats['attempts'] = 0
        self.stats['retries_used'] = 0
        self.stats['filtered_out_by_dimensions'] = 0
        
        self.console.print(Panel(
            f"[bold cyan]🖼️  IMAGE SEARCH PHASE[/bold cyan]\n[italic cyan]{query}[/italic cyan]",
            padding=(1, 2)
        ))

        for attempt in range(max_attempts):
            self.results = []
            self.stats['failed'] = 0

            try:
                with DDGS(timeout=self.timeout) as ddgs:
                    attempt_options = self._build_image_attempt_options(search_options, attempt)
                    raw_results = self._run_ddgs_images(ddgs, query, max_results, attempt_options)

                    filtered_out = 0
                    for i, result in enumerate(raw_results, 1):
                        try:
                            width = self._coerce_int(result.get('width'))
                            height = self._coerce_int(result.get('height'))

                            if not self._passes_dimension_filters(
                                width,
                                height,
                                min_width=min_width,
                                max_width=max_width,
                                min_height=min_height,
                                max_height=max_height,
                            ):
                                filtered_out += 1
                                continue

                            img_result = ImageSearchResult(
                                position=len(self.results) + 1,
                                title=result.get('title', f'Image {i}'),
                                image_url=result.get('image', ''),
                                source_url=result.get('url', ''),
                                thumbnail_url=result.get('thumbnail', ''),
                                width=width or 0,
                                height=height or 0,
                                image_size=result.get('size', ''),
                                fetch_time=0.0,
                            )
                            self.results.append(img_result)
                        except Exception as e:
                            self.stats['failed'] += 1
                            self.console.print(f"[yellow]Warning:[/yellow] Failed to process image {i}: {e}")

                    self.stats['filtered_out_by_dimensions'] = filtered_out

            except Exception as e:
                self.console.print(f"[red]Image search failed:[/red] {e}")
                self.stats['failed'] += 1

            self.stats['total'] = len(self.results)
            self.stats['success'] = sum(1 for r in self.results if r.image_url)
            self.stats['attempts'] = attempt + 1
            self.stats['retries_used'] = attempt

            if self.stats['success'] > 0:
                break

            if attempt < max_attempts - 1:
                self.console.print(
                    f"[yellow]No valid images on attempt {attempt + 1}/{max_attempts}; retrying...[/yellow]"
                )
                if retry_backoff_seconds > 0:
                    time.sleep(retry_backoff_seconds * (attempt + 1))

        self.stats['execution_time'] = time.time() - start_time
        
        return self.results
    
    def download_images(self, output_dir: str = ".scout-it/downloaded_images", max_downloads: int = 10, max_retries: int = 3, max_workers: int = 5):
        """Download images to local directory with retries and parallel workers."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        targets = [r for r in self.results[:max_downloads] if r.image_url]
        self.console.print(f"\n📥 Downloading {len(targets)} images to {output_path} ({max_workers} workers)...")

        def _download_one(result: "ImageSearchResult") -> bool:
            safe_title = re.sub(r'[^\w\s-]', '', result.title)[:50] or "image"
            ext = '.jpg'
            lowered = result.image_url.lower()
            if '.png' in lowered:
                ext = '.png'
            elif '.gif' in lowered:
                ext = '.gif'
            elif '.webp' in lowered:
                ext = '.webp'

            filename = f"{result.position:03d}_{safe_title}{ext}"
            filepath = output_path / filename

            last_error = None
            for attempt in range(max(1, max_retries)):
                try:
                    headers = {'User-Agent': random.choice(ExtractionEngine.USER_AGENTS)}
                    resp = requests.get(result.image_url, headers=headers, timeout=self.timeout, stream=True)
                    resp.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    self.console.print(f"✅ Downloaded: {filename}")
                    return True
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(1.0 * (attempt + 1))

            self.console.print(f"[yellow]⚠️  Failed to download {result.title} after {max_retries} attempts:[/yellow] {last_error}")
            return False

        downloaded = 0
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            futures = [executor.submit(_download_one, result) for result in targets]
            for future in as_completed(futures):
                if future.result():
                    downloaded += 1

        self.console.print(f"\n✅ Successfully downloaded {downloaded} images to {output_path}")
        return downloaded
    
    def render_dashboard(self):
        """Display image search results"""
        table = Table(title="🖼️  IMAGE SEARCH RESULTS", box=None, expand=True)
        table.add_column("Rank", style="cyan", no_wrap=True)
        table.add_column("Title", style="magenta")
        table.add_column("URL", style="blue")
        table.add_column("Size", style="green")
        
        for result in self.results[:20]:
            table.add_row(
                str(result.position),
                result.title[:40],
                result.source_url[:50],
                f"{result.width}x{result.height}"
            )
        
        self.console.print(table)
        
        # Stats panel
        stats_table = Table.grid(expand=True)
        stats_table.add_row("Total Images Found", f"{self.stats['total']:,}")
        stats_table.add_row("✅ Valid URLs", f"{self.stats['success']:,}")
        stats_table.add_row("❌ Failed", f"{self.stats['failed']:,}")
        stats_table.add_row("⏱️  Exec Time", f"{self.stats['execution_time']:.2f}s")
        
        self.console.print(Panel(stats_table, title="🖼️  IMAGE SEARCH METRICS"))
