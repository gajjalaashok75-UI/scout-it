"""Resilient fetching with multi-tier fallback strategy."""

import random
import time
from typing import Any, Dict, List, Optional

import requests


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
    browser_pool: Optional[Any] = None,
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
    from .. import header_profiles as _hp
    from .. import retry_classifier as _rc
    from .. import proxy_pool as _pp
    from ..extraction.engine import ExtractionEngine

    errs: List[str] = []
    total_attempts = 0
    sess = session or requests
    got_any_http_response = False

    proxy_info = _pp.get_default_pool().get()

    def _record(tier: str, success: bool, latency_ms: Optional[int] = None) -> None:
        if not enable_strategy_cache:
            return
        try:
            from .. import strategy_cache as _sc
            _sc.record_outcome(url, tier, success, proxy_id=proxy_info["proxy_id"], latency_ms=latency_ms)
        except Exception:
            pass

    # ── Disk response cache: short-circuit a re-fetch of a page we already
    # successfully fetched recently. Skipped for force_js (JS-rendered pages
    # are non-deterministic) and when explicitly disabled by the caller.
    # This is the single biggest fetch-path optimization: every search
    # command goes through fetch_resilient, so caching here eliminates
    # redundant network round-trips for repeated URLs across a session.
    _use_response_cache = (
        enable_strategy_cache
        and not force_js
        and not browser_pool
    )
    if _use_response_cache:
        try:
            from .. import response_cache as _resp_cache
            cached = _resp_cache.get(url)
            if cached and cached.get("content"):
                # A cache hit means the *original* fetch succeeded with the
                # "requests" tier — record that outcome so the strategy cache
                # keeps learning even when serving from cache.
                _record("requests", True)
                return {
                    "html": cached["content"],
                    "final_url": url,
                    "status": "success",
                    "tier": "cache",
                    "attempts": 0,
                    "errors": [],
                    "cached": True,
                    "age_seconds": cached.get("age_seconds"),
                }
        except Exception:
            _use_response_cache = False

    def _cache_set(html: str, tier: str) -> None:
        """Persist a successful fetch to the response cache."""
        if not _use_response_cache or not html:
            return
        try:
            _resp_cache.set(url, html, content_type="web")
        except Exception:
            pass

    if enable_bandit and not force_js:
        try:
            from .. import strategy_bandit as _bandit
            choice = _bandit.choose_strategy(url, available_tiers=["requests", "playwright", "basic-fallback"])
            if choice["source"] == "bandit" and choice["tier"] == "playwright" and choice["confidence"] >= 0.7:
                force_js = True
                errs.append(f"bandit: skipping tier 1 -- playwright has a {choice['confidence']:.0%} recorded success rate for this domain")
        except Exception:
            pass

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
                got_any_http_response = True
                status = resp.status_code
                text = resp.text
                latency_ms = int((time.time() - attempt_start) * 1000)
                if status < 400 and not _looks_blocked(text, status):
                    _pp.get_default_pool().mark_success(proxy_info["proxy_id"])
                    _record("requests", True, latency_ms)
                    _cache_set(text, "requests")
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
                        from .. import dns_resilience as _dns
                        if _dns.looks_like_dns_error(e):
                            resolved = _dns.build_resolved_url_and_host_header(url, timeout=5)
                            if resolved:
                                errs.append(f"requests attempt {attempt + 1}: DNS-looking failure -- retrying via DNS-over-HTTPS resolution")
                                try:
                                    dns_headers = dict(_hp.get_profile())
                                    dns_headers["Host"] = resolved["host_header"]
                                    dns_resp = sess.get(
                                        resolved["resolved_url"], headers=dns_headers, timeout=timeout,
                                        allow_redirects=False,
                                        stream=True, verify=False,
                                    )
                                    if dns_resp.status_code < 400 and not _looks_blocked(dns_resp.text, dns_resp.status_code):
                                        _record("requests-dns-fallback", True)
                                        return {
                                            "html": dns_resp.text,
                                            "final_url": url,
                                            "status": "success",
                                            "tier": "requests",
                                            "attempts": total_attempts,
                                            "errors": errs,
                                        }
                                    errs.append(f"DNS-over-HTTPS retry: HTTP {dns_resp.status_code}")
                                except Exception as dns_exc:
                                    errs.append(f"DNS-over-HTTPS retry: {type(dns_exc).__name__}: {dns_exc}")
                    except Exception:
                        pass

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
            from .. import tls_fingerprint as _tls
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
            def _playwright_navigate(page, url, timeout, force_js):
                """Navigate page with optimized wait strategy for news sites."""
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                """)
                
                page.goto(url, wait_until="domcontentloaded", timeout=10000)
                
                if not force_js:
                    article_selectors = [
                        "article", "[role='main']", ".article-body",
                        ".story-body", ".entry-content", "main",
                    ]
                    
                    article_found = False
                    for selector in article_selectors:
                        try:
                            page.wait_for_selector(selector, timeout=3000, state="attached")
                            article_found = True
                            break
                        except Exception:
                            continue
                    
                    if not article_found:
                        try:
                            page.wait_for_timeout(2000)
                        except Exception:
                            pass
                else:
                    _orig_url = page.url
                    try:
                        page.wait_for_function(f"window.location.href !== '{_orig_url}'", timeout=10000)
                    except Exception:
                        pass
                    
                    try:
                        page.wait_for_selector("article, [role='main'], main", timeout=5000, state="attached")
                    except Exception:
                        try:
                            page.wait_for_timeout(2000)
                        except Exception:
                            pass
                
                html = page.content()
                final_url = page.url
                rendered_text = page.evaluate("document.body.innerText") or ""
                return html, final_url, rendered_text

            for attempt in range(max(1, max_retries)):
                total_attempts += 1
                attempt_start = time.time()
                try:
                    if browser_pool and browser_pool.is_available():
                        with browser_pool.get_page() as page:
                            html, final_url, rendered_text = _playwright_navigate(page, url, timeout, force_js)
                    else:
                        with sync_playwright() as pw:
                            if enable_persistent_profile:
                                _ua = random.choice(ExtractionEngine.USER_AGENTS)
                                from .. import browser_profile as _bp
                                context = _bp.launch_persistent(pw, profile_name=browser_profile_name, headless=True, user_agent=_ua)
                                try:
                                    page = context.new_page()
                                    html, final_url, rendered_text = _playwright_navigate(page, url, timeout, force_js)
                                finally:
                                    context.close()
                            else:
                                _ua = random.choice(ExtractionEngine.USER_AGENTS)
                                browser = pw.chromium.launch(headless=True)
                                try:
                                    page = browser.new_page(user_agent=_ua)
                                    html, final_url, rendered_text = _playwright_navigate(page, url, timeout, force_js)
                                finally:
                                    browser.close()
                    if html and len(html.strip()) > 200:
                        _record("playwright", True, int((time.time() - attempt_start) * 1000))
                        return {
                            "html": html,
                            "final_url": final_url,
                            "rendered_text": rendered_text,
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
            _cache_set(resp.text, "basic-fallback")
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
    if enable_alternate_source:
        try:
            from .. import alternate_source as _alt

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
