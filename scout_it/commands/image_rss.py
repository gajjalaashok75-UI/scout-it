"""Media-aware RSS fetcher for image-search.

Reuses the parallel HTTP transport from ``tech_crunch_rss`` (RSSProvider) but
parses Media RSS / RSS-with-enclosure feeds itself, extracting the actual
image URLs, thumbnails, and dimensions that the news parser discards.

Public entry point: ``fetch_image_feed_entries(urls, limit)``.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Sequence
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

__all__ = ["fetch_image_feed_entries", "parse_image_feed"]


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


def _media_images(item: ET.Element) -> List[Dict[str, Any]]:
    """Collect media:content / media:thumbnail / enclosure image entries."""
    images: List[Dict[str, Any]] = []
    seen: set = set()
    for child in item.iter():
        local = _strip_ns(child.tag)
        if local in {"content", "thumbnail"} and child.attrib.get("url"):
            url = child.attrib["url"]
            if url in seen:
                continue
            seen.add(url)
            images.append({
                "url": url,
                "width": _attr_int(child, "width"),
                "height": _attr_int(child, "height"),
                "medium": child.attrib.get("medium", ""),
            })
    # RSS <enclosure url="..." type="image/..."/>
    for enc in item.findall("{*}enclosure"):
        etype = enc.attrib.get("type", "")
        url = enc.attrib.get("url", "")
        if url and ("image" in etype or not etype) and url not in seen:
            seen.add(url)
            images.append({
                "url": url,
                "width": _attr_int(enc, "width"),
                "height": _attr_int(enc, "height"),
                "medium": etype,
            })
    return images


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(value: str) -> str:
    if not value:
        return ""
    value = _HTML_TAG_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_image_feed(xml_text: str, feed_url: str = "") -> List[Dict[str, Any]]:
    """Parse a Media RSS / Atom feed into image-search entries.

    Each returned dict carries both ranking fields (title, body, source,
    publish_date) and image-specific fields (image_url, source_url,
    thumbnail_url, width, height).
    """
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("image feed parse failed for %s: %s", feed_url or "<inline>", exc)
        return []

    feed_name = feed_url.split("//")[-1].split("/")[0] if feed_url else "rss"

    # Determine item container (RSS <item> or Atom <entry>).
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
        published = _first_text(item, ["pubDate", "published", "updated", "created"])
        author = _first_text(item, ["author", "{*}author/{*}name"]) or _first_text(item, ["creator"])
        body = _clean_text(_first_text(item, ["description", "summary", "content"]))

        media = _media_images(item)
        if not media:
            continue  # no usable image — skip non-image entries

        primary = media[0]
        thumbnail = ""
        for m in media:
            if m.get("medium") == "image" or m["url"]:
                if m is not primary:
                    thumbnail = m["url"]
                    break
        if not thumbnail and len(media) > 1:
            thumbnail = media[-1]["url"]

        results.append({
            "title": title or f"Image from {feed_name}",
            "image_url": primary["url"],
            "source_url": link or primary["url"],
            "thumbnail_url": thumbnail or primary["url"],
            "width": primary.get("width") or 0,
            "height": primary.get("height") or 0,
            "image_size": "",
            "body": body,
            "snippet": body,
            "source": f"rss:{feed_name}",
            "publish_date": published,
            "author": author,
            "rss_metadata": {
                "feed_url": feed_url,
                "feed_name": feed_name,
                "media_count": len(media),
            },
        })
    return results


def fetch_image_feed_entries(
    urls: Sequence[str],
    limit: int = 500,
    timeout: float = 15.0,
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    """Fetch and parse multiple image RSS feeds in parallel.

    Returns ALL image entries (no query filtering) for downstream ranking.
    """
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
        logger.error("image RSS transport unavailable: %s", exc)
        return []

    all_entries: List[Dict[str, Any]] = []
    seen: set = set()
    for feed_url, content in fetched:
        if not content:
            continue
        parsed = parse_image_feed(content, feed_url=feed_url)
        for entry in parsed:
            img_url = entry.get("image_url", "")
            if img_url and img_url not in seen:
                seen.add(img_url)
                all_entries.append(entry)
        if len(all_entries) >= limit:
            break

    logger.info("image RSS: fetched %d entries from %d feeds", len(all_entries), len(urls))
    return all_entries[:limit]
