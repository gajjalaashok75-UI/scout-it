"""
Helper functions for news search - Extracted from cli.py

This module contains helper functions used by news_search,
extracted from cli.py for better code organization.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any, Dict, List

# Import from parent package
from ..extraction import ExtractionEngine, fetch_resilient

# Initialize logger
logger = logging.getLogger(__name__)

# Error/404 page detection phrases — short content matching any of these
# indicates a broken or removed page (dead link from search engine).
_ERROR_PAGE_PHRASES = [
    "whoops", "page doesn't exist", "can't be found",
    "page not found", "this page could not be found",
    "sorry, this page",
]


def _extract_meta_description(html_text: str) -> str:
    """Extract meta description / og:description / twitter:description from HTML
    head. These are always full sentences (never truncated like search snippets).
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


def _extract_news_content(
    results: List[Dict[str, Any]],
    max_workers: int = 5,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch and extract full article content for news results in parallel.

    Takes raw DDGS news result dicts, fetches each URL through the shared
    ``fetch_resilient`` fallback chain (requests-retries -> Playwright
    JS-render -> last-resort basic request), runs the HTML through
    ``ExtractionEngine``, and returns enriched dicts compatible with
    ``process_results()`` (i.e. containing ``main_content``,
    ``extraction_status``, ``confidence_score``, etc.).
    
    Uses browser pool to reuse Playwright browser across all URLs,
    reducing browser launch overhead from 3-8s per URL to ~0.5s per page.
    """
    if not results:
        return results

    shared_engine = ExtractionEngine()
    
    # ═══════════════════════════════════════════════════════════════════
    # BROWSER POOL: Launch browser ONCE for all URLs
    # ═══════════════════════════════════════════════════════════════════
    browser_pool = None
    if enable_js_fallback:
        try:
            from ..browser_pool import PlaywrightBrowserPool
            browser_pool = PlaywrightBrowserPool.get_instance()
            browser_pool.start()
            logger.info("Browser pool started - will reuse browser for all URLs")
        except Exception as e:
            logger.warning(f"Failed to start browser pool: {e}")
            browser_pool = None

    def _extract_one(r):
        url = r.get("url", "")
        if not url:
            r["extraction_status"] = "failed"
            r["main_content"] = ""
            return r
        try:
            # Google News /articles/ URLs are JS-rendered SPAs — force
            # Playwright Tier 2 to execute the JS redirect / render the
            # article content (requests-only gets the interstitial shell).
            force_js = "/articles/" in url and "news.google.com" in url
            
            # ═══════════════════════════════════════════════════════════
            # DOMAIN LEARNING: Check learned strategy
            # ═══════════════════════════════════════════════════════════
            if not force_js and enable_js_fallback:
                from ..domain_routing import get_domain_learning
                learning = get_domain_learning()
                strategy, confidence = learning.get_strategy(url)
                
                if strategy == "banned":
                    r["extraction_status"] = "failed"
                    r["main_content"] = ""
                    r["errors"] = ["Domain is banned (never returns valid content)"]
                    logger.info(f"Domain learning: Skipping banned domain - {url[:80]}")
                    return r
                elif strategy == "playwright" and confidence >= 0.80:
                    force_js = True
                    logger.info(f"Domain learning: Using Playwright (strategy={strategy}, conf={confidence:.0%}) - {url[:80]}")
            
            # ═══════════════════════════════════════════════════════════
            # SOURCE RESOLUTION: Check if this is a wrapper site (MSN, Yahoo, etc.)
            # ═══════════════════════════════════════════════════════════
            original_url = url
            from ..source_resolvers import is_wrapper_domain, resolve_source_url
            
            if is_wrapper_domain(url):
                logger.info(f"Wrapper domain detected: {url[:80]}")
                # First attempt: Try to resolve from URL alone
                resolved = resolve_source_url(url, html=None)
                if resolved:
                    url = resolved
                    r["url"] = resolved
                    r["href"] = resolved
                    r["original_wrapper_url"] = original_url
                    logger.info(f"Resolved to publisher: {url[:80]}")
            
            outcome = fetch_resilient(
                url,
                session=shared_engine.session,
                timeout=25,  # Increased from 15s for problematic sites
                max_retries=max_fetch_retries,
                enable_js_fallback=enable_js_fallback,
                force_js=force_js,
                browser_pool=browser_pool,  # Pass browser pool
            )
            if outcome["status"] != "success":
                r["extraction_status"] = "failed"
                r["main_content"] = ""
                r["errors"] = outcome["errors"][-3:]
                logger.warning(f"Failed to fetch {url[:80]}: {outcome['errors'][-1] if outcome['errors'] else 'unknown error'}")
                return r
            
            def _update_url(outcome):
                nonlocal url
                fetched_url = outcome.get("final_url", url)
                if fetched_url != url and fetched_url:
                    r["url"] = fetched_url
                    r["href"] = fetched_url
                    url = fetched_url

            _update_url(outcome)
            content, method, confidence = shared_engine.extract_content(url, outcome["html"])
            
            # ═══════════════════════════════════════════════════════════
            # WRAPPER RE-RESOLUTION: If this is still a wrapper and we have HTML,
            # try to resolve again with the HTML content
            # ═══════════════════════════════════════════════════════════
            if is_wrapper_domain(url) and not r.get("original_wrapper_url"):
                resolved_from_html = resolve_source_url(url, html=outcome.get("html", ""))
                if resolved_from_html and resolved_from_html != url:
                    logger.info(f"Re-resolved wrapper from HTML: {resolved_from_html[:80]}")
                    r["original_wrapper_url"] = url
                    url = resolved_from_html
                    r["url"] = resolved_from_html
                    r["href"] = resolved_from_html
                    # Re-fetch the resolved URL
                    outcome = fetch_resilient(
                        url,
                        session=shared_engine.session,
                        timeout=15,
                        max_retries=max_fetch_retries,
                        enable_js_fallback=enable_js_fallback,
                        force_js=force_js,
                        browser_pool=browser_pool,  # Pass browser pool
                    )
                    if outcome["status"] == "success":
                        content, method, confidence = shared_engine.extract_content(url, outcome["html"])
                        _update_url(outcome)
            
            # ═══════════════════════════════════════════════════════════
            # QUALITY VALIDATION & AUTOMATIC PLAYWRIGHT ESCALATION
            # ═══════════════════════════════════════════════════════════
            # Check if extraction quality is sufficient
            from ..extraction_quality import should_escalate_to_playwright
            
            should_escalate, escalation_reason = should_escalate_to_playwright(
                content=content,
                expected_title=r.get("title", ""),
                html=outcome.get("html", ""),
                extraction_tier=outcome.get("tier", "requests"),
            )
            
            # Automatic escalation to Playwright if quality is poor
            if should_escalate and enable_js_fallback and outcome.get("tier") != "playwright":
                logger.info(f"Escalating to Playwright: {escalation_reason} - {url[:80]}")
                _jr = fetch_resilient(
                    url,
                    session=shared_engine.session,
                    timeout=25,  # Increased from 15s
                    max_retries=max_fetch_retries,
                    enable_js_fallback=True,
                    force_js=True,
                    browser_pool=browser_pool,  # Pass browser pool
                )
                if _jr["status"] == "success":
                    outcome = _jr
                    content, method, confidence = shared_engine.extract_content(url, outcome["html"])
                    _update_url(outcome)
            
            # ═══════════════════════════════════════════════════════════
            # DOMAIN LEARNING: Record extraction outcome
            # ═══════════════════════════════════════════════════════════
            word_count = len(content.split())
            from ..domain_routing import get_domain_learning
            learning = get_domain_learning()
            learning.record_extraction(
                url=url,
                tier=outcome.get("tier", "unknown"),
                success=(word_count >= 200),
                word_count=word_count,
            )
            
            # Detect error / 404 pages (dead links from search engines).
            # Short content matching error phrases indicates a broken URL.
            if content and any(p in content.lower() for p in _ERROR_PAGE_PHRASES) and len(content.strip()) < 500:
                content = ""
                method = "error-page"
                confidence = 0.0
            # Before falling back to the (often truncated) search snippet,
            # extract the full meta description from the page HTML itself.
            if len(content.strip()) < 30:
                meta_desc = _extract_meta_description(outcome.get("html", ""))
                if meta_desc and len(meta_desc) > len(content.strip()):
                    content = meta_desc
                    method = "meta-description"
                    confidence = 0.4
            # If article extraction yields no real content (e.g. "Google News"
            # page title from Google News redirect pages), fall back to the
            # RSS snippet body — that is more useful than a page title.
            rss_body = r.get("body", "")
            if len(content.strip()) < 30 and rss_body.strip() and len(rss_body) > len(content.strip()):
                content = rss_body
                method = "rss-fallback"
                confidence = 0.5
            # If still no content and Playwright rendered visible text from a
            # JS-heavy page (e.g. Google News AMP syndication), use that instead.
            if len(content.strip()) < 30:
                rendered_text = outcome.get("rendered_text", "")
                if rendered_text.strip() and len(rendered_text.strip()) > len(content.strip()):
                    content = rendered_text
                    method = "rendered-text"
                    confidence = 0.6
            r["main_content"] = content
            r["extraction_method"] = f"{method} ({outcome['tier']})"
            r["confidence_score"] = confidence
            r["extraction_status"] = "success" if content.strip() else "failed"
            r["content_word_count"] = len(content.split())
        except Exception as exc:
            r["extraction_status"] = "failed"
            r["main_content"] = ""
            r["errors"] = [str(exc)]
        return r

    # Display progress with Rich
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, MofNCompleteColumn, TimeElapsedColumn
    from rich.panel import Panel
    
    console = Console()
    console.print(Panel("[bold yellow]⚡ PARALLEL CONTENT EXTRACTION[/bold yellow]", padding=(1, 2)))
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_extract_one, r): idx for idx, r in enumerate(results)}
        enriched = [None] * len(results)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("  Extracting content...", total=len(futures))
            
            for future in as_completed(futures):
                idx = futures[future]
                enriched[idx] = future.result()
                progress.advance(task)
    
    # ═══════════════════════════════════════════════════════════════════
    # BROWSER POOL CLEANUP: Close browser after all URLs are processed
    # ═══════════════════════════════════════════════════════════════════
    if browser_pool:
        try:
            browser_pool.stop()
            logger.info("Browser pool stopped")
        except Exception as e:
            logger.warning(f"Error stopping browser pool: {e}")
    
    # ═══════════════════════════════════════════════════════════════════
    # DOMAIN LEARNING: Save learned strategies to disk
    # ═══════════════════════════════════════════════════════════════════
    try:
        from ..domain_routing import get_domain_learning
        learning = get_domain_learning()
        learning.force_save()
    except Exception as e:
        logger.warning(f"Error saving domain learning data: {e}")
    
    return enriched
