#!/usr/bin/env python3
"""
🌍 TIMES OF INDIA RSS NEWS SOURCE — Location-based RSS news search
==================================================================

Provides location-aware RSS news feeds from Times of India, allowing
``news-search --location india`` to fetch the latest news for a given
country or city.

Location codes follow a ``country-city`` pattern:
    ``india``          — Top India news
    ``world``          — International news
    ``US``, ``UK``     — Country-specific feeds
    ``india-delhi``    — City-specific feeds

Usage:
    from scout_it.toi_rss_source import fetch_toi_news, LOCATION_FEEDS

    results = fetch_toi_news(["india", "india-delhi"], max_per_location=5)
    # Returns List[Dict] with keys: title, url, href, body, source, date
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests

from scout_it.response_cache import get as _cache_get, set as _cache_set

_logger = logging.getLogger(__name__)

# ── Location → RSS URL mapping ───────────────────────────────────
# Sourced from references/rss-codes.md
# fmt: off
LOCATION_FEEDS: Dict[str, List[str]] = {
    "india":           ["https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"],
    "world":           ["https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"],
    "US":              ["https://timesofindia.indiatimes.com/rssfeeds_us/72258322.cms",
                        "https://timesofindia.indiatimes.com/rssfeeds/30359486.cms"],  # fallback
    "pakistan":        ["https://timesofindia.indiatimes.com/rssfeeds/30359534.cms"],
    "UK":              ["https://timesofindia.indiatimes.com/rssfeeds/2177298.cms"],
    "europe":          ["https://timesofindia.indiatimes.com/rssfeeds/1898274.cms"],
    "china":           ["https://timesofindia.indiatimes.com/rssfeeds/1898184.cms"],
    "india-delhi":     ["https://timesofindia.indiatimes.com/rssfeeds/-2128839596.cms"],
    "india-bangalore": ["https://timesofindia.indiatimes.com/rssfeeds/-2128833038.cms"],
    "india-hyderabad": ["https://timesofindia.indiatimes.com/rssfeeds/-2128816011.cms"],
}
# fmt: on


def _parse_toi_rss(xml_text: str, source_label: str) -> List[Dict[str, Any]]:
    """Parse a ToI RSS XML string into a list of result dicts."""
    results: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        _logger.warning("ToI RSS parse error for %s: %s", source_label, exc)
        return results

    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        date_el = item.find("pubDate")
        creator_el = item.find("{http://purl.org/dc/elements/1.1/}creator")

        title = title_el.text.strip() if title_el is not None and title_el.text else ""
        link = link_el.text.strip() if link_el is not None and link_el.text else ""
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
        pub_date = date_el.text.strip() if date_el is not None and date_el.text else ""
        author = creator_el.text.strip() if creator_el is not None and creator_el.text else ""

        if not title or not link:
            continue

        results.append({
            "title": title,
            "url": link,
            "href": link,
            "body": description,
            "source": f"toi-{source_label}",
            "date": pub_date,
            "author": author,
        })

    return results


def _fetch_feed(feed_url: str, session: requests.Session, timeout: int = 15) -> str:
    """Fetch a single RSS feed, checking cache first."""
    cached = _cache_get(feed_url)
    if cached is not None:
        content = cached.get("content") or cached.get("response")
        if content:
            return content

    try:
        resp = session.get(feed_url, timeout=timeout)
        resp.raise_for_status()
        text = resp.text
        _cache_set(feed_url, text, content_type="xml", ttl_seconds=300)
        return text
    except requests.RequestException as exc:
        _logger.warning("Failed to fetch ToI feed %s: %s", feed_url, exc)
        return ""


def fetch_toi_news(
    locations: List[str],
    max_per_location: int = 5,
    timeout: int = 15,
) -> List[Dict[str, Any]]:
    """Fetch news from Times of India RSS feeds for the given locations.

    Args:
        locations: Location keys from ``LOCATION_FEEDS`` (e.g. ``"india"``,
            ``"india-delhi"``, ``"US"``).
        max_per_location: Max items to keep per location feed.
        timeout: HTTP request timeout.

    Returns:
        List of result dicts with keys *title*, *url*, *href*, *body*,
        *source*, *date*, *author* — compatible with the ``news_search``
        pipeline.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    session = requests.Session()
    seen_urls: set = set()
    all_results: List[Dict[str, Any]] = []

    # Collect all feed URLs to fetch
    feed_tasks: List[str] = []
    feed_labels: List[str] = []
    for loc in locations:
        normalized = loc.strip().lower().replace(" ", "-")
        feed_urls = LOCATION_FEEDS.get(normalized)
        if not feed_urls:
            _logger.warning("Unknown location '%s', skipping", loc)
            continue
        for url in feed_urls:
            feed_tasks.append(url)
            feed_labels.append(normalized)

    # Fetch in parallel
    def _fetch(label: str, url: str) -> List[Dict]:
        xml_text = _fetch_feed(url, session, timeout=timeout)
        if not xml_text:
            return []
        items = _parse_toi_rss(xml_text, label)
        # De-duplicate within this batch
        unique = []
        for item in items:
            u = item.get("url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                unique.append(item)
        # Use the last processed items (most recent from RSS order)
        return unique[-max_per_location:] if len(unique) > max_per_location else unique

    with ThreadPoolExecutor(max_workers=min(len(feed_tasks), 8)) as pool:
        fut_map = {pool.submit(_fetch, label, url): (label, url)
                   for label, url in zip(feed_labels, feed_tasks)}
        for fut in as_completed(fut_map):
            try:
                items = fut.result()
                all_results.extend(items)
            except Exception as exc:
                label, url = fut_map[fut]
                _logger.warning("Error fetching %s (%s): %s", label, url, exc)

    return all_results
