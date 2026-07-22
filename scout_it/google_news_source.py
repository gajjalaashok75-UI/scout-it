#!/usr/bin/env python3
"""
📰 GOOGLE NEWS SEARCH SOURCE — Google News RSS feed search
=============================================================

Provides a drop-in news search source compatible with the DDGS news result format,
so it can be used as a fallback or primary source for ``news-search``.

Ported from ``references/google_news_extractor_version_2.py``:

Features:
- ``urllib3.Retry`` adapter with exponential backoff
- Thread-safe ``SimpleRateLimiter``
- Disk-backed response cache via existing ``response_cache``
- Session connection pooling
- RSS namespace-aware XML parsing
- Google News redirect URL stripping
- **Publisher-aware title cleaning** with cleanup profiles
- **HTML description part extraction** (link, source, text)
- Rich per-item fields: publisher, description_link, guid, pub_date
- **Deduplicator** — content-hash deduplication
- Locale-aware URL builder (hl / gl / ceid params)

Usage:
    from scout_it.google_news_source import google_news_search, Deduplicator

    results = google_news_search("AI technology", max_results=10)
    # Returns List[Dict] with keys: title, url, body, source, date,
    # publisher, description_link, guid, rank
"""

import hashlib
import json
import logging
import random
import re
import time
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, unquote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import header_profiles as _hp
from . import proxy_pool as _pp
from . import response_cache as _rc
from ._utils import SimpleRateLimiter, prune_empty, build_retry_session

logger = logging.getLogger(__name__)

# Google News RSS feed URL
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

TIMEOUT = 25
MAX_RETRIES = 3
RATE_PER_SEC = 1.5

# Publisher-specific title cleanup patterns (ported from reference)
PUBLISHER_CLEANUP_PATTERNS: Dict[str, List[str]] = {
    "times of india": [
        r"\s*-\s*Times of India\s*$",
        r"\s*-\s*TOI\s*$",
    ],
    "google news": [
        r"\s*-\s*[^-]+$",
    ],
}

__all__ = ["google_news_search", "Deduplicator"]


# ── HTTP client ─────────────────────────────────────────────────────────────


class _NewsHttpClient:
    """Reusable HTTP client with Retry adapter + rate limiting."""

    def __init__(self):
        self.rate_limiter = SimpleRateLimiter(RATE_PER_SEC)
        self.session = build_retry_session(retries=MAX_RETRIES)

    def request_text(self, url: str, timeout: int = TIMEOUT) -> Optional[str]:
        """Make a rate-limited, retried request for raw text (RSS XML)."""
        cache_key = hashlib.sha256(f"rss::{url}".encode("utf-8")).hexdigest()[:32]

        cached = _rc.get(cache_key, cache_dir=None)
        if cached and cached.get("content"):
            return cached["content"]

        proxy_info = _pp.get_default_pool().get()
        headers = _hp.get_profile()

        self.rate_limiter.wait()

        try:
            resp = self.session.get(
                url,
                headers=headers,
                timeout=timeout,
                proxies=proxy_info["requests_proxies"],
            )
            resp.raise_for_status()
            text = resp.text

            _rc.set(
                cache_key,
                text,
                content_type="news",
                ttl_seconds=60 * 30,  # 30 min for news
                extra={"url": url},
            )

            return text
        except requests.exceptions.RequestException as e:
            logger.debug(f"Google News RSS request failed: {e}")
            return None


_client = _NewsHttpClient()


# ── URL builder ──────────────────────────────────────────────────────────────


def build_google_news_url(
    query: str,
    hl: str = "en-IN",
    gl: str = "IN",
    ceid: Optional[str] = None,
) -> str:
    """Build a Google News RSS search URL with locale parameters.

    Ported from ``NewsPipeline.build_google_news_url`` in the reference.
    """
    if ceid is None:
        ceid = f"{gl}:{hl}"
    return (
        f"{GOOGLE_NEWS_RSS}?q={quote_plus(query)}"
        f"&hl={hl}&gl={gl}&ceid={ceid}"
    )


# ── Text / metadata helpers ─────────────────────────────────────────────────


def _normalize_text(text: str) -> str:
    """Clean and normalize text — strip HTML tags, unescape, collapse whitespace."""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_google_news_url(raw_url: str, description_link: str = "") -> str:
    """Extract the real article URL from Google News' redirect wrapper.

    Google News RSS items have two link sources:
    * The ``<link>`` element — usually a tracking/redirect URL (``/articles/``
      format or old ``?q=`` format).
    * The ``<a href="...">`` inside the ``<description>`` HTML — often the
      actual article URL directly.

    Args:
        raw_url: Value from the RSS ``<link>`` element.
        description_link: Optional ``href`` from the RSS description HTML.

    Returns:
        The resolved article URL, or *raw_url* as-is if no resolution is
        available.
    """
    # Old ?q= format (e.g. ?q=https://example.com/article)
    match = re.search(r"[?&]q=(https?://[^&]+)", raw_url)
    if match:
        return unquote(match.group(1))
    # New /articles/ format — the RSS description <a href> usually contains
    # the actual article URL (not another Google redirect).
    if description_link and "news.google.com" not in description_link:
        return description_link
    return raw_url


def _resolve_google_news_articles_url(url: str, timeout: int = 10) -> str:
    """Resolve a Google News ``/articles/`` URL via HTTP redirect following.

    Google News ``/articles/`` URLs sometimes issue an HTTP 302 redirect to
    the real article when accessed with a browser-grade User-Agent.  This
    function follows the redirect chain and returns the final URL.

    Args:
        url: A Google News article URL (``/articles/`` format).
        timeout: Request timeout in seconds.

    Returns:
        The resolved article URL, or *url* unchanged if resolution fails.
    """
    if "/articles/" not in url:
        return url
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(
            url, headers=headers, timeout=timeout,
            allow_redirects=True, stream=True,
        )
        final = str(resp.url)
        if final != url and "news.google.com" not in final:
            return final
    except Exception:
        pass
    return url


def _parse_rss_date(date_str: str) -> str:
    """Parse RSS date string into ISO format, or return as-is."""
    try:
        from datetime import datetime
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(date_str)
        return dt.isoformat() if dt else date_str
    except Exception:
        return date_str



# ── Title cleaning ──────────────────────────────────────────────────────────


def _clean_title(
    title: str,
    publisher: str = "",
    cleanup_profile: str = "generic",
) -> str:
    """Clean a news title: normalize, strip publisher suffixes.

    Ported from ``FeedParser.clean_title`` in the reference.

    Args:
        title: Raw title text.
        publisher: Detected publisher name (used for exact pattern match).
        cleanup_profile: Named profile (``"google_news"``, ``"generic"``).

    Returns:
        Cleaned title string.
    """
    title = _normalize_text(title)

    # Google News titles often have trailing " - PublisherName"
    if cleanup_profile == "google_news":
        if " - " in title:
            title = title.rsplit(" - ", 1)[0].strip()

    # Apply publisher-specific and profile patterns
    patterns = (
        PUBLISHER_CLEANUP_PATTERNS.get(publisher.lower(), [])
        + PUBLISHER_CLEANUP_PATTERNS.get(cleanup_profile.lower(), [])
    )
    for pat in patterns:
        title = re.sub(pat, "", title, flags=re.I).strip()

    return title


# ── Description part extraction ─────────────────────────────────────────────


def _extract_description_parts(html_desc: str) -> Dict[str, Any]:
    """Parse the ``<description>`` HTML content of an RSS item for structured fields.

    Ported from ``FeedParser.extract_description_parts`` in the reference.
    Google News RSS descriptions contain HTML like::

        <a href="...">snippet text</a><font size="-1">source</font>

    Returns:
        Dict with keys ``description_link``, ``description_text``,
        ``description_source``, ``description_source_url``.
    """
    if not html_desc:
        return {}

    # Anchor tag → link + display text
    match_anchor = re.search(
        r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_desc, flags=re.I | re.S
    )
    # <source> tag (non-standard but some feeds use it)
    match_source_tag = re.search(
        r'<source[^>]*url="([^"]+)"[^>]*>(.*?)</source>',
        html_desc,
        flags=re.I | re.S,
    )
    # <font> tag (Google News uses this for publisher name)
    match_font = re.search(
        r"<font[^>]*>(.*?)</font>", html_desc, flags=re.I | re.S
    )

    return {
        "description_link": match_anchor.group(1) if match_anchor else None,
        "description_text": _normalize_text(
            match_anchor.group(2) if match_anchor else html_desc
        ),
        "description_source": _normalize_text(
            match_source_tag.group(2)
            if match_source_tag
            else (match_font.group(1) if match_font else "")
        ),
        "description_source_url": match_source_tag.group(1)
        if match_source_tag
        else None,
    }


# ── RSS parsing ─────────────────────────────────────────────────────────────


def _parse_rss_items(
    xml_text: str,
    max_results: int,
    cleanup_profile: str = "google_news",
) -> List[Dict[str, Any]]:
    """Parse Google News RSS XML into structured result dicts.

    Enhanced version of the basic parser with:
    - Publisher extraction from ``<source>`` tag and description HTML
    - Title cleaning with publisher-specific cleanup profiles
    - HTML description part extraction
    - GUID tracking
    - Rank ordering

    Args:
        xml_text: Raw RSS XML text.
        max_results: Maximum items to return.
        cleanup_profile: Title cleanup profile (``"google_news"``, ``"generic"``).

    Returns:
        List of result dicts.  Each result includes DDGS-compatible fields
        (``title``, ``url``, ``href``, ``body``, ``source``, ``date``) plus
        richer news-specific fields (``publisher``, ``description_link``,
        ``guid``, ``rank``).
    """
    items: List[Dict[str, Any]] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning(f"Google News RSS parse error: {e}")
        return items

    for item_elem in root.iter("item"):
        if len(items) >= max_results:
            break

        result: Dict[str, Any] = {}

        # ── title ────────────────────────────────────────────────────────
        title_el = item_elem.find("title")
        raw_title = title_el.text if title_el is not None else ""

        # ── source (publisher) from <source> tag ─────────────────────────
        source_tag = item_elem.find("source")
        source_name = (
            _normalize_text(source_tag.text)
            if source_tag is not None and source_tag.text
            else ""
        )
        source_url = source_tag.attrib.get("url") if source_tag is not None else None

        # ── description (HTML) ───────────────────────────────────────────
        desc_el = item_elem.find("description")
        description_html = desc_el.text if desc_el is not None else ""
        desc_parts = _extract_description_parts(description_html)

        # Use source from <source> tag; fall back to description source
        publisher = source_name or desc_parts.get("description_source") or ""

        # Clean title with publisher profile
        cleaned_title = _clean_title(
            raw_title, publisher=publisher, cleanup_profile=cleanup_profile
        )

        # ── link ─────────────────────────────────────────────────────────
        link_el = item_elem.find("link")
        raw_url = link_el.text if link_el is not None else ""
        desc_link = desc_parts.get("description_link") or ""
        clean_url = _clean_google_news_url(raw_url, description_link=desc_link)

        # ── GUID ─────────────────────────────────────────────────────────
        guid_el = item_elem.find("guid")
        guid = guid_el.text if guid_el is not None and guid_el.text else ""

        # ── pubDate ──────────────────────────────────────────────────────
        pub_date_el = item_elem.find("pubDate")
        pub_date = (
            _parse_rss_date(pub_date_el.text)
            if pub_date_el is not None and pub_date_el.text
            else ""
        )

        # ── enclosure / image ────────────────────────────────────────────
        enclosure = item_elem.find("enclosure")
        image_url = enclosure.get("url", "") if enclosure is not None else ""

        # Build result — DDGS-compatible + richer fields
        result["title"] = cleaned_title or _normalize_text(raw_title)
        result["url"] = clean_url
        result["href"] = clean_url
        result["body"] = desc_parts.get("description_text", "")
        result["source"] = f"google-news:{publisher}" if publisher else "google-news"
        result["publisher"] = publisher
        result["publisher_url"] = source_url or ""
        result["description_link"] = desc_parts.get("description_link") or ""
        result["guid"] = guid
        result["date"] = pub_date
        result["rank"] = len(items) + 1
        if image_url:
            result["image_url"] = image_url

        items.append(prune_empty(result))

    return items


# ── Deduplicator ────────────────────────────────────────────────────────────


class Deduplicator:
    """Content-hash deduplication for news items.

    Ported from the reference ``Deduplicator`` class.

    Usage:
        dedup = Deduplicator()
        unique = dedup.dedupe_items(items_with_article_pages)
    """

    @staticmethod
    def content_hash(text: str) -> Optional[str]:
        """SHA-256 hash of the first 5000 chars (whitespace-normalised)."""
        if not text:
            return None
        text = re.sub(r"\s+", " ", text.strip().lower())
        if not text:
            return None
        return hashlib.sha256(text[:5000].encode("utf-8")).hexdigest()

    @staticmethod
    def item_hash(item: Dict[str, Any]) -> Optional[str]:
        """Derive a dedup hash for a single item.

        Prefers an ``article_page.article_extraction.content_hash`` if present
        (from deep extraction), otherwise falls back to URL + title.
        """
        # Check for deep-article hash
        article_page = item.get("article_page") or {}
        art = article_page.get("article_extraction") or {}
        if art.get("content_hash"):
            return art["content_hash"]

        # Fall back to URL or title
        base = (
            item.get("url")
            or item.get("href")
            or item.get("google_news_link")
            or item.get("title")
            or ""
        )
        return Deduplicator.content_hash(base)

    @staticmethod
    def dedupe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate items from a list, preserving order."""
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for item in items:
            h = Deduplicator.item_hash(item)
            if h and h in seen:
                continue
            if h:
                seen.add(h)
            out.append(item)
        return out


# ── Main search entry point ────────────────────────────────────────────────


def google_news_search(
    query: str,
    max_results: int = 10,
    language: str = "en-IN",
    country: str = "IN",
    timeout: int = TIMEOUT,
    hl: Optional[str] = None,
    gl: Optional[str] = None,
    ceid: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search Google News RSS feed and return results.

    Drop-in source for ``news-search``. Returns results compatible with
    the DDGS news result format (``title``, ``url``, ``href``, ``body``,
    ``source``, ``date``) plus richer news-specific fields (``publisher``,
    ``description_link``, ``guid``, ``rank``).

    Ported features from ``references/google_news_extractor_version_2.py``:
    - Publisher-aware title cleaning
    - HTML description part extraction
    - Locale-aware URL building (hl / gl / ceid)
    - Rich per-item fields

    Args:
        query: Search query string.
        max_results: Maximum results.
        language: Language/region code (e.g. ``en-IN``, ``en-US``).
            Used for ``hl`` and ``ceid`` defaults when ``hl``/``ceid`` are
            not explicitly passed.
        country: Country code (e.g. ``IN``, ``US``).
            Used for ``gl`` and ``ceid`` defaults when ``gl``/``ceid`` are
            not explicitly passed.
        timeout: HTTP request timeout.
        hl: Explicit Google News ``hl`` parameter. Overrides *language*.
        gl: Explicit Google News ``gl`` parameter. Overrides *country*.
        ceid: Explicit Google News ``ceid`` parameter.
            Defaults to ``{gl}:{hl}``.

    Returns:
        List of news result dicts. Empty list on failure (never raises).
    """
    try:
        # Resolve locale params with explicit overrides
        hl_param = hl or language
        gl_param = (gl or country).upper()
        ceid_param = ceid or f"{gl_param}:{hl_param}"

        url = build_google_news_url(query, hl=hl_param, gl=gl_param, ceid=ceid_param)
        xml_text = _client.request_text(url, timeout=timeout)
        if not xml_text:
            return []
        return _parse_rss_items(xml_text, max_results)
    except Exception as e:
        logger.warning(f"google_news_search failed: {e}")
        return []
