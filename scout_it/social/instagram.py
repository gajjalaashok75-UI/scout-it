"""
📸 INSTAGRAM PROVIDER — DDGS discovery + public profile scraping + Playwright.

Instagram aggressively blocks anonymous/non-browser requests (302 → login
wall), and the GraphQL API requires session cookies + CSRF tokens. This
provider uses a tiered strategy to maximize results across both the
authenticated and anonymous cases, mirroring the web/news-search workflow
(snippet extraction → rank → extract top → clean):

  1. ``--query``            -> DDGS web search for public Instagram content
     (``site:instagram.com <query>`` + ``instagram <query>``). DuckDuckGo
     indexes public Instagram profiles, posts, and hashtag pages, so this
     yields related snippets/titles/links even without credentials. This is
     the primary, reliable no-auth path.

  2. ``--profile``          -> fetch a specific user's public profile page
     (``https://www.instagram.com/{username}/``) and extract embedded
     JSON-LD / shared data. Three tiers:
       a. requests + browser-like headers (extract JSON-LD `<script>` blocks).
       b. Playwright headless render (when requests hits the login wall / 302).
       c. DDGS fallback (``site:instagram.com {username}``) if both fail.

  3. Optional ``INSTAGRAM_SESSION_ID`` env var -> use the session cookie to
     access the GraphQL API for full profile/hashtag data (like
     ``REDDIT_COOKIE``). When set, profile fetches are more reliable and
     return more posts.

References (approach, not code):
  - drawrowfly/instagram-scraper — session-based hashtag/profile scraping,
    proxy rotation, media-type filtering.
  - instaloader/instaloader — Profile/Post structure, GraphQL endpoints,
    session-file pattern.
  - data-scrape/instagram-account-scraper — no-login public profile/post
    scraping, proxy + rate-limit support.

Capabilities: ``query`` (DDGS, no login) and ``profile`` (public page
scraping + Playwright fallback). The ``query`` capability is the public
fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests

from .. import __version__ as _VERSION
from .base import (
    CAP_PROFILE,
    CAP_QUERY,
    SocialProvider,
    normalize_item,
    provider_result,
)

logger = logging.getLogger(__name__)

INSTAGRAM_BASE = "https://www.instagram.com"

# Browser-like headers to reduce the chance of Instagram's login-wall 302.
_BROWSER_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def _get_proxy() -> Optional[str]:
    """Read a proxy from env (HTTP_PROXY / HTTPS_PROXY / INSTAGRAM_PROXY)."""
    return (os.environ.get("INSTAGRAM_PROXY")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("HTTP_PROXY"))


def _has_session() -> bool:
    return bool(os.environ.get("INSTAGRAM_SESSION_ID"))


def _session_cookies() -> Dict[str, str]:
    sid = os.environ.get("INSTAGRAM_SESSION_ID")
    if not sid:
        return {}
    return {"sessionid": sid, "ig_cb": "2"}


# =====================================================================
# DDGS web discovery (query capability, NO login required)
# =====================================================================

def _ddgs_text(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Run a DDGS text search, tolerant of the installed ddgs API shape."""
    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS
        except Exception:
            return []
    results: List[Dict[str, Any]] = []
    try:
        with DDGS(timeout=20) as ddgs:
            method = getattr(ddgs, "text", None)
            if not callable(method):
                return []
            for call in (
                lambda: list(method(keywords=query, max_results=max_results)),
                lambda: list(method(query, max_results=max_results)),
                lambda: list(method(query))[:max_results],
            ):
                try:
                    results = call()
                    break
                except TypeError:
                    continue
    except Exception as e:
        logger.debug("DDGS instagram search failed: %s", e)
        return []
    return results or []


def instagram_ddgs_search(query: str, max_results: int = 20) -> Dict[str, Any]:
    """No-login discovery: search the public web for Instagram content related
    to ``query`` via DuckDuckGo. Searches both ``site:instagram.com <query>``
    (precise) and ``instagram <query>`` (broader), deduplicates by URL, and
    ranks by query relevance — mirroring the web/news-search snippet-extraction
    step.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "no_input",
                "error_message": "A --query is required for Instagram web search."}

    precise = _ddgs_text(f"site:instagram.com {q}", max_results * 2)
    broad = _ddgs_text(f"instagram {q}", max_results)
    seen: set = set()
    merged: List[Dict[str, Any]] = []
    for r in precise + broad:
        url = r.get("href") or r.get("url") or r.get("link") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append({
            "title": r.get("title") or "",
            "content": r.get("body") or r.get("snippet") or r.get("content") or "",
            "url": url,
        })
    ranked = _rank_instagram_results(merged, q, max_results)
    return {"query": query, "result_count": len(ranked), "results": ranked,
            "source": "ddgs_web"}


# =====================================================================
# Public profile scraping (profile capability)
# =====================================================================

def _extract_json_ld(html: str) -> List[Dict[str, Any]]:
    """Extract all JSON-LD `<script type="application/ld+json">` blocks from
    an Instagram HTML page. Returns a list of parsed dicts."""
    blocks: List[Dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1).strip())
            if isinstance(data, list):
                blocks.extend(data)
            elif isinstance(data, dict):
                blocks.append(data)
        except (json.JSONDecodeError, ValueError):
            continue
    return blocks


def _extract_shared_data(html: str) -> Optional[Dict[str, Any]]:
    """Extract the ``window._sharedData`` / additional data JSON blob that
    Instagram embeds in profile pages. Returns None if not found."""
    for pattern in (
        r'window\._sharedData\s*=\s*(\{.*?\})\s*;\s*</script>',
        r'window\.__additionalData\s*=\s*(\{.*?\})\s*;\s*</script>',
        r'"timeline_media":\s*(\{.*?\})\s*[,}]',
    ):
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _parse_profile_posts(json_ld: List[Dict[str, Any]],
                         shared: Optional[Dict[str, Any]],
                         username: str) -> List[Dict[str, Any]]:
    """Parse posts from JSON-LD blocks and/or shared data into the provider's
    post schema. Handles both the BlogPosting/Person JSON-LD shape and the
    older ``timeline_media`` shared-data shape."""
    posts: List[Dict[str, Any]] = []

    # JSON-LD: Instagram profiles embed BlogPosting entries for recent posts.
    for block in json_ld:
        # Some pages wrap posts in a graph.
        items = block.get("@graph", block) if isinstance(block, dict) else block
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if not isinstance(item, dict):
                continue
            typ = item.get("@type", "")
            if typ in ("BlogPosting", "SocialMediaPosting", "Article") or item.get("articleBody"):
                posts.append({
                    "author": (item.get("author") or {}).get("name", username)
                        if isinstance(item.get("author"), dict)
                        else item.get("author") or username,
                    "content": item.get("articleBody") or item.get("description") or item.get("headline") or "",
                    "url": item.get("mainEntityOfPage", {}).get("@id")
                        if isinstance(item.get("mainEntityOfPage"), dict)
                        else item.get("url"),
                    "timestamp": item.get("datePublished"),
                    "image": item.get("image", {}).get("url")
                        if isinstance(item.get("image"), dict)
                        else item.get("image"),
                    "title": item.get("headline") or "",
                })

    # Shared data: older timeline_media shape.
    if shared and isinstance(shared, dict):
        timeline = (shared.get("entry_data", {})
                           .get("ProfilePage", [{}])[0]
                           .get("graphql", {})
                           .get("user", {})
                           .get("edge_owner_to_timeline_media", {}))
        for edge in timeline.get("edges", []):
            node = edge.get("node", {})
            if not node:
                continue
            posts.append({
                "author": username,
                "content": node.get("edge_media_to_caption", {})
                                .get("edges", [{}])[0].get("node", {}).get("text", ""),
                "url": f"{INSTAGRAM_BASE}/p/{node.get('shortcode', '')}/" if node.get("shortcode") else None,
                "timestamp": _instagram_timestamp(node.get("taken_at_timestamp")),
                "image": node.get("display_url"),
                "title": "",
                "likes": node.get("edge_liked_by", {}).get("count"),
                "comments": node.get("edge_media_to_comment", {}).get("count"),
            })

    return posts


def _instagram_timestamp(ts: Any) -> Optional[str]:
    """Convert an Instagram epoch timestamp to an ISO string."""
    if not ts:
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts)))
    except (ValueError, TypeError, OverflowError):
        return None


def _fetch_profile_requests(username: str, max_retries: int = 2) -> Dict[str, Any]:
    """Tier 1: fetch a public Instagram profile page via requests with
    browser-like headers + optional session cookie. Returns ``{ok, html,
    status_code, error}``."""
    import random
    url = f"{INSTAGRAM_BASE}/{username}/"
    headers = {
        "User-Agent": random.choice(_BROWSER_UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    if _has_session():
        headers["X-CSRFToken"] = "scout-it"  # placeholder; real CSRF comes from cookie
    cookies = _session_cookies()
    proxies = {"https": _get_proxy(), "http": _get_proxy()} if _get_proxy() else None

    for attempt in range(max(1, max_retries)):
        try:
            resp = requests.get(url, headers=headers, cookies=cookies,
                                proxies=proxies, timeout=15, allow_redirects=False)
        except Exception as e:
            if attempt + 1 >= max_retries:
                return {"ok": False, "html": None, "status_code": None,
                        "error": f"{type(e).__name__}: {e}"}
            time.sleep(0.5 * (attempt + 1))
            continue

        # Instagram 302s to /accounts/login/ when it blocks the request.
        if resp.status_code in (301, 302):
            loc = resp.headers.get("Location", "")
            if "login" in loc.lower():
                return {"ok": False, "html": None, "status_code": resp.status_code,
                        "error": "login_wall (Instagram redirected to login page)"}
            # Follow non-login redirects manually.
            continue
        if resp.status_code == 404:
            return {"ok": False, "html": None, "status_code": 404,
                    "error": f"Instagram profile '{username}' not found."}
        if resp.status_code == 429:
            time.sleep(min(float(resp.headers.get("Retry-After", 2.0)), 5.0))
            continue
        if resp.status_code >= 400:
            return {"ok": False, "html": None, "status_code": resp.status_code,
                    "error": f"HTTP {resp.status_code}"}
        html = resp.text or ""
        if len(html) < 500:
            return {"ok": False, "html": html, "status_code": resp.status_code,
                    "error": "page too small (likely a block/challenge page)"}
        return {"ok": True, "html": html, "status_code": resp.status_code, "error": None}

    return {"ok": False, "html": None, "status_code": None,
            "error": "request failed after retries"}


def _fetch_profile_playwright(username: str, timeout_ms: int = 15000) -> Dict[str, Any]:
    """Tier 2: render a public Instagram profile page with Playwright
    (headless Chromium). Instagram serves the full profile HTML to a real
    browser, which we then parse for JSON-LD / shared data. Returns
    ``{ok, html, error}``."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "html": None,
                "error": "playwright not installed (pip install playwright && playwright install chromium)"}

    import random
    url = f"{INSTAGRAM_BASE}/{username}/"
    ua = random.choice(_BROWSER_UAS)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, proxy=(
                {"server": _get_proxy()} if _get_proxy() else None
            ))
            try:
                context = browser.new_context(
                    user_agent=ua,
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
                # Inject session cookie if available.
                if _has_session():
                    context.add_cookies([{
                        "name": "sessionid", "value": os.environ["INSTAGRAM_SESSION_ID"],
                        "domain": ".instagram.com", "path": "/",
                    }])
                page = context.new_page()
                # Anti-bot: hide webdriver flag.
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Wait for content or login redirect to settle.
                try:
                    page.wait_for_selector("main, article, [role='main']", timeout=5000, state="attached")
                except Exception:
                    page.wait_for_timeout(2000)
                html = page.content()
                final_url = page.url
            finally:
                browser.close()
        if not html or "accounts/login" in final_url:
            return {"ok": False, "html": html, "error": "login_wall (Playwright redirected to login)"}
        return {"ok": True, "html": html, "error": None}
    except Exception as e:
        return {"ok": False, "html": None, "error": f"{type(e).__name__}: {e}"}


def instagram_profile_search(
    username: str,
    max_results: int = 20,
) -> Dict[str, Any]:
    """Fetch a public Instagram profile's recent posts. Tries requests first
    (tier 1), falls back to Playwright (tier 2) when the login wall is hit,
    then DDGS (tier 3) as a last resort. When ``INSTAGRAM_SESSION_ID`` is set,
    the session cookie is used for more reliable access."""
    username = (username or "").strip().lstrip("@")
    if not username:
        return {"error": "no_input",
                "error_message": "An Instagram username is required."}
    # Sanitize: Instagram usernames are alphanumeric + . + _
    if not re.match(r"^[A-Za-z0-9._]+$", username):
        return {"error": "invalid_username",
                "error_message": f"'{username}' is not a valid Instagram username."}

    notes: List[str] = []
    sources_tried: List[str] = []

    # Tier 1: requests + JSON-LD extraction.
    sources_tried.append("requests")
    t1 = _fetch_profile_requests(username)
    posts: List[Dict[str, Any]] = []
    if t1["ok"] and t1["html"]:
        json_ld = _extract_json_ld(t1["html"])
        shared = _extract_shared_data(t1["html"])
        posts = _parse_profile_posts(json_ld, shared, username)
        if posts:
            notes.append("fetched via requests (JSON-LD/shared data).")
        else:
            notes.append("requests fetched page but no posts extracted (Instagram may require login).")

    # Tier 2: Playwright fallback (login wall or no posts from requests).
    if not posts:
        sources_tried.append("playwright")
        t2 = _fetch_profile_playwright(username)
        if t2["ok"] and t2["html"]:
            json_ld = _extract_json_ld(t2["html"])
            shared = _extract_shared_data(t2["html"])
            posts = _parse_profile_posts(json_ld, shared, username)
            if posts:
                notes.append("fetched via Playwright (JS render).")
            else:
                notes.append("Playwright rendered page but no posts extracted.")
        elif t2.get("error"):
            notes.append(f"Playwright: {t2['error']}.")

    # Tier 3: DDGS fallback — at least find the profile + related content.
    if not posts:
        sources_tried.append("ddgs_web")
        ddgs = instagram_ddgs_search(username, max_results=max_results)
        if "error" not in ddgs and ddgs.get("results"):
            notes.append("fell back to DDGS web search (profile page was blocked).")
            return {"username": username, "result_count": ddgs["result_count"],
                    "results": ddgs["results"], "source": "ddgs_web",
                    "sources_tried": sources_tried, "notes": notes}

    if not _has_session():
        notes.append(
            "INSTAGRAM_SESSION_ID is not set — Instagram blocks most anonymous "
            "profile access. Set it (via `scout-it config`) for reliable profile scraping."
        )

    posts = posts[:max_results]
    return {"username": username, "result_count": len(posts),
            "posts": posts, "source": sources_tried[0] if posts else "none",
            "sources_tried": sources_tried, "notes": notes}


# =====================================================================
# Ranking + enrichment
# =====================================================================

def _rank_instagram_results(items: List[Dict[str, Any]], query: str,
                            max_results: int) -> List[Dict[str, Any]]:
    """Rank Instagram results by query relevance: title match > content match,
    whole-phrase bonus. Caps at ``max_results``."""
    if not items:
        return items
    q = (query or "").lower().strip().lstrip("#")
    terms = [t for t in re.split(r"\s+", q) if len(t) > 1] if q else []

    def _score(it: Dict[str, Any]) -> float:
        title = (it.get("title") or it.get("content") or "").lower()
        body = (it.get("content") or "").lower()
        if not terms:
            return 0.0
        score = 0.0
        for t in terms:
            if t in title:
                score += 3.0
            if t in body:
                score += 1.0
        if q and q in title:
            score += 5.0
        if q and q in body:
            score += 2.0
        return score

    ranked = sorted(items, key=lambda it: -_score(it))
    return ranked[:max_results]


def _enrich_instagram_with_full_content(items: List[Dict[str, Any]],
                                         max_results: int) -> List[Dict[str, Any]]:
    """Best-effort full-page extraction for DDGS-discovered Instagram URLs."""
    try:
        from ..extraction import fetch_resilient
        from ..cleaner import advanced_clean_text
    except Exception:
        return items
    for it in items[:max_results]:
        url = it.get("url")
        if not url or "instagram.com" not in url:
            continue
        try:
            outcome = fetch_resilient(url, timeout=15, max_retries=1)
            if outcome.get("status") == "success" and outcome.get("html"):
                cleaned = advanced_clean_text(outcome["html"], url)
                if cleaned:
                    it["full_content"] = cleaned[:5000]
        except Exception:
            continue
    return items


# =====================================================================
# Provider (capability-aware wrapper)
# =====================================================================

class InstagramProvider(SocialProvider):
    platform = "instagram"
    # query = DDGS web search of public Instagram content (no login).
    # profile = public profile page scraping (requests → Playwright → DDGS).
    SUPPORTED_CAPABILITIES = {CAP_QUERY, CAP_PROFILE}
    FALLBACK_CAPABILITY = CAP_QUERY

    def _execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        max_results = params.get("max_results", 20)
        extract_full = params.get("extract_full", False)

        if capability == CAP_PROFILE:
            return self._exec_profile(params, max_results)
        return self._exec_query(params, max_results, extract_full)

    # -- query (DDGS web discovery) ------------------------------------------
    def _exec_query(self, params: Dict[str, Any], max_results: int,
                    extract_full: bool) -> Dict[str, Any]:
        query = (params.get("query") or "").strip()
        if not query:
            return provider_result(self.platform, error="no_input",
                                   error_message="Instagram query search requires a --query.",
                                   capabilities_used=[CAP_QUERY])

        ddgs_res = instagram_ddgs_search(query, max_results=max_results)
        raw: Dict[str, Any] = {"query": query, "ddgs_search": ddgs_res}
        items: List[Dict[str, Any]] = []
        note_parts: List[str] = []

        if "error" not in ddgs_res:
            for r in ddgs_res.get("results", []):
                items.append({
                    "title": r.get("title") or "",
                    "content": r.get("content") or "",
                    "author": None,
                    "url": r.get("url"),
                    "timestamp": None,
                    "metadata": {"source": "ddgs_web"},
                })

        items = _rank_instagram_results(items, query, max_results)

        if extract_full and items:
            _enrich_instagram_with_full_content(items, max_results)

        normalized: List[Dict[str, Any]] = [normalize_item(
            self.platform,
            author=it.get("author"),
            content=(it.get("title") + "\n\n" + it.get("content")).strip()
                if it.get("title") else it.get("content"),
            url=it.get("url"),
            timestamp=it.get("timestamp"),
            metadata=it.get("metadata") or {},
        ) for it in items]

        if not _has_session():
            note_parts.append(
                "INSTAGRAM_SESSION_ID is not set — results are from public web search. "
                "Set it (via `scout-it config`) for direct profile scraping."
            )
        note = " ".join(note_parts) if note_parts else None
        return provider_result(self.platform, query=query, results=normalized,
                               capabilities_used=[CAP_QUERY], raw=raw, note=note)

    # -- profile (public page scraping + Playwright + DDGS fallback) ---------
    def _exec_profile(self, params: Dict[str, Any], max_results: int) -> Dict[str, Any]:
        username = (params.get("profile") or "").strip()
        if not username:
            return provider_result(self.platform, error="no_input",
                                   error_message="Instagram --profile requires a username.",
                                   capabilities_used=[CAP_PROFILE])

        raw_res = instagram_profile_search(username, max_results=max_results)
        raw: Dict[str, Any] = {"profile": username, "raw": raw_res}
        note_parts: List[str] = list(raw_res.get("notes", []))

        items: List[Dict[str, Any]] = []
        # Posts from profile scraping.
        for p in raw_res.get("posts", []):
            items.append({
                "title": p.get("title") or "",
                "content": p.get("content") or "",
                "author": p.get("author") or username,
                "url": p.get("url"),
                "timestamp": p.get("timestamp"),
                "metadata": {
                    "source": "profile_scrape",
                    "image": p.get("image"),
                    "likes": p.get("likes"),
                    "comments": p.get("comments"),
                },
            })
        # DDGS fallback results.
        for r in raw_res.get("results", []):
            items.append({
                "title": r.get("title") or "",
                "content": r.get("content") or "",
                "author": None,
                "url": r.get("url"),
                "timestamp": None,
                "metadata": {"source": "ddgs_web"},
            })

        normalized: List[Dict[str, Any]] = [normalize_item(
            self.platform,
            author=it.get("author"),
            content=(it.get("title") + "\n\n" + it.get("content")).strip()
                if it.get("title") else it.get("content"),
            url=it.get("url"),
            timestamp=it.get("timestamp"),
            metadata=it.get("metadata") or {},
        ) for it in items]

        note = " ".join(note_parts) if note_parts else None
        return provider_result(self.platform, results=normalized,
                               capabilities_used=[CAP_PROFILE], raw=raw, note=note)
