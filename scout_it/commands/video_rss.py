"""Media-aware RSS fetcher for video-search.

Parses YouTube channel Atom feeds (and generic Media RSS) to extract video
URLs, thumbnails, descriptions, and publish dates. Reuses the parallel HTTP
transport from ``tech_crunch_rss``.

Public entry point: ``fetch_video_feed_entries(urls, limit)``.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

__all__ = ["fetch_video_feed_entries", "parse_video_feed"]


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _attr_int(el: ET.Element, name: str) -> Optional[int]:
    raw = el.attrib.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _first_text(parent: ET.Element, names: Sequence[str]) -> str:
    target = {_strip_ns(n) for n in names}
    for child in parent.iter():
        if _strip_ns(child.tag) in target and child.text:
            return child.text.strip()
    return ""


def _media_thumbnail(item: ET.Element) -> str:
    for child in item.iter():
        if _strip_ns(child.tag) == "thumbnail" and child.attrib.get("url"):
            return child.attrib["url"]
    return ""


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str) -> str:
    if not value:
        return ""
    value = _HTML_TAG_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_video_feed(xml_text: str, feed_url: str = "") -> List[Dict[str, Any]]:
    """Parse a YouTube Atom / Media RSS feed into video-search entries."""
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("video feed parse failed for %s: %s", feed_url or "<inline>", exc)
        return []

    feed_name = feed_url.split("//")[-1].split("/")[0] if feed_url else "rss"

    items: List[ET.Element] = []
    channel = root.find("channel")
    if channel is not None:
        items = channel.findall("item")
    if not items:
        items = root.findall(".//{*}entry")

    results: List[Dict[str, Any]] = []
    for item in items:
        link = ""
        for lnk in item.findall("{*}link"):
            href = lnk.attrib.get("href", "")
            rel = lnk.attrib.get("rel", "alternate")
            if href and rel in {"alternate", ""}:
                link = href
                break
        if not link:
            link = _first_text(item, ["link"])

        title = _clean_text(_first_text(item, ["title"]))
        published = _first_text(item, ["published", "pubDate", "updated", "created"])
        author = _first_text(item, ["author", "{*}author/{*}name"]) or _first_text(item, ["creator"])
        description = _clean_text(_first_text(item, ["description", "summary", "content", "{*}group/{*}description"]))

        thumbnail = _media_thumbnail(item)

        # Skip entries without a usable video link.
        if not link:
            continue

        results.append({
            "title": title or f"Video from {feed_name}",
            "content": link,
            "url": link,
            "description": description,
            "body": description,
            "snippet": description,
            "thumbnail": thumbnail,
            "image": thumbnail,
            "source": f"rss:{feed_name}",
            "publish_date": published,
            "author": author,
            "rss_metadata": {
                "feed_url": feed_url,
                "feed_name": feed_name,
            },
        })
    return results


def fetch_video_feed_entries(
    urls: Sequence[str],
    limit: int = 500,
    timeout: float = 15.0,
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    """Fetch and parse multiple video RSS feeds in parallel."""
    if not urls:
        return []

    try:
        import importlib
        _tcr = importlib.import_module(".tech_crunch_rss", "scout_it.news-search")
        # RSSProvider is abstract; use the concrete TechCrunchRSSProvider for
        # the parallel HTTP transport.
        provider_cls = getattr(_tcr, "TechCrunchRSSProvider", None) or _tcr.RSSProvider
        provider = provider_cls()
        fetched = provider.fetch_multiple_feeds(list(urls), timeout=timeout, max_workers=max_workers)
    except Exception as exc:
        logger.error("video RSS transport unavailable: %s", exc)
        return []

    all_entries: List[Dict[str, Any]] = []
    seen: set = set()
    for feed_url, content in fetched:
        if not content:
            continue
        parsed = parse_video_feed(content, feed_url=feed_url)
        for entry in parsed:
            key = entry.get("url") or entry.get("content")
            if key and key not in seen:
                seen.add(key)
                all_entries.append(entry)
        if len(all_entries) >= limit:
            break

    logger.info("video RSS: fetched %d entries from %d feeds", len(all_entries), len(urls))
    return all_entries[:limit]
