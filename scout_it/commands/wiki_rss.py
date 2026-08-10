"""MediaWiki RecentChanges RSS fetcher for wiki-search.

Reuses the parallel HTTP transport from ``tech_crunch_rss`` (RSSProvider) but
parses MediaWiki RecentChanges RSS feeds itself, converting each recently
edited page into a ranking candidate with a clean article title, canonical
``wiki/Title`` URL, de-diffed snippet, and timestamp.

Public entry point: ``fetch_wiki_feed_entries(urls, limit)``.
"""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any, Dict, List, Optional, Sequence
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

__all__ = ["fetch_wiki_feed_entries", "parse_wiki_feed"]


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _first_text(parent: ET.Element, names: Sequence[str]) -> str:
    target = {_strip_ns(n) for n in names}
    for child in parent.iter():
        if _strip_ns(child.tag) in target and child.text:
            return child.text.strip()
    return ""


# Blocked page namespaces — mirror wikimedia_source.BLOCKED_PREFIXES so we
# skip user sandboxes, file/category/template pages, and other non-article
# entries that pollute RecentChanges.
_BLOCKED_PREFIXES = (
    "file:", "category:", "template:", "help:", "portal:",
    "special:", "talk:", "user:", "module:", "draft:", "user talk:",
    "wikipedia talk:", "media:", "mediawiki:",
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DIFF_TABLE_RE = re.compile(r"<table[^>]*data-mw-interface[^>]*>.*?</table>", re.DOTALL | re.IGNORECASE)


def _clean_diff_html(value: str) -> str:
    """Strip the MediaWiki diff table and surrounding HTML from an RC description.

    RecentChanges ``<description>`` carries an HTML diff table plus an
    autocomment summary. We keep the human-readable autocomment (if any) and
    drop the raw diff markup so the snippet feeds the ranker as plain text.
    """
    if not value:
        return ""
    text = _DIFF_TABLE_RE.sub(" ", value)
    # Pull out the autocomment span ("Summary: actual summary") when present.
    m = re.search(
        r"autocomment[^>]*>([^<]*)</span>", text, re.IGNORECASE,
    )
    if m and m.group(1).strip():
        summary = m.group(1).strip()
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        # If the cleaned text is mostly diff noise, prefer the autocomment.
        return summary if len(text) < len(summary) * 3 else text
    text = _HTML_TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_to_slug(title: str) -> str:
    """Normalize a wiki page title for use in a canonical URL path."""
    return title.replace(" ", "_").replace("&amp;", "%26")


def parse_wiki_feed(
    xml_text: str,
    feed_url: str = "",
    base_url: str = "",
) -> List[Dict[str, Any]]:
    """Parse a MediaWiki RecentChanges RSS feed into wiki-search entries.

    Each returned dict carries both ranking fields (title, body, source,
    publish_date) and wiki-specific fields (href = canonical article URL,
    project, pageid placeholder).
    """
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("wiki feed parse failed for %s: %s", feed_url or "<inline>", exc)
        return []

    feed_name = feed_url.split("//")[-1].split("/")[0] if feed_url else "wikimedia"
    # Derive a project key + canonical base URL from the feed host when the
    # caller did not supply one.
    if not base_url:
        if "en.wikipedia.org" in feed_url or "wikipedia.org" in feed_url:
            project = "wikipedia"
        elif "commons.wikimedia.org" in feed_url:
            project = "commons"
        elif "wikidata.org" in feed_url:
            project = "wikidata"
        elif "mediawiki.org" in feed_url:
            project = "mediawiki"
        elif "species.wikimedia.org" in feed_url:
            project = "wikispecies"
        elif "wikifunctions.org" in feed_url:
            project = "wikifunctions"
        elif "wikivoyage.org" in feed_url:
            project = "wikivoyage"
        elif "wiktionary.org" in feed_url:
            project = "wiktionary"
        elif "wikibooks.org" in feed_url:
            project = "wikibooks"
        elif "wikiversity.org" in feed_url:
            project = "wikiversity"
        elif "wikiquote.org" in feed_url:
            project = "wikiquote"
        elif "wikisource.org" in feed_url:
            project = "wikisource"
        else:
            project = "wikipedia"
        base_url = f"https://{feed_name}/"
    else:
        project = base_url.split("//")[-1].split("/")[0] if "://" in base_url else "wikipedia"

    # Determine item container (RSS <item> or Atom <entry>).
    items: List[ET.Element] = []
    channel = root.find("channel")
    if channel is not None:
        items = channel.findall("item")
    if not items:
        items = root.findall(".//{*}entry")

    results: List[Dict[str, Any]] = []
    seen_titles: set = set()
    for item in items:
        title = _first_text(item, ["title"])
        if not title:
            continue
        title = unescape(title).strip()
        # Skip blocked namespaces (User:, File:, Talk:, etc.).
        if title.split(":", 1)[0].lower() in {p.rstrip(":") for p in _BLOCKED_PREFIXES}:
            continue
        if title in seen_titles:
            continue
        seen_titles.add(title)

        link = _first_text(item, ["link"])
        # The RSS <link> is a diff URL; build a clean canonical article URL.
        href = f"{base_url}wiki/{_title_to_slug(title)}"

        description = _first_text(item, ["description", "summary", "content"])
        body = _clean_diff_html(description) if description else ""
        if not body:
            body = title
        published = _first_text(item, ["pubDate", "published", "updated"])
        author = _first_text(item, ["author", "creator", "{*}author/{*}name"])

        results.append({
            "title": title,
            "href": href,
            "url": href,
            "body": body,
            "snippet": body,
            "description": body,
            "source": f"rss:{feed_name}",
            "project": project,
            "publish_date": published,
            "author": author,
            "pageid": None,
            "rss_metadata": {
                "feed_url": feed_url,
                "feed_name": feed_name,
                "diff_link": link,
            },
        })
    return results


def fetch_wiki_feed_entries(
    urls: Sequence[str],
    limit: int = 500,
    timeout: float = 15.0,
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    """Fetch and parse multiple MediaWiki RecentChanges feeds in parallel.

    Returns ALL entries (no query filtering) for downstream ranking - the
    same contract as the image/video RSS fetchers.
    """
    if not urls:
        return []

    try:
        import importlib
        _tcr = importlib.import_module(".tech_crunch_rss", "scout_it.news-search")
        # RSSProvider is abstract; use the concrete TechCrunchRSSProvider
        # for the parallel HTTP transport (mirrors image_rss / video_rss).
        provider_cls = getattr(_tcr, "TechCrunchRSSProvider", None) or _tcr.RSSProvider
        provider = provider_cls()
        fetched = provider.fetch_multiple_feeds(list(urls), timeout=timeout, max_workers=max_workers)
    except Exception as exc:
        logger.error("wiki RSS transport unavailable: %s", exc)
        return []

    all_entries: List[Dict[str, Any]] = []
    seen: set = set()
    for feed_url, content in fetched:
        if not content:
            continue
        parsed = parse_wiki_feed(content, feed_url=feed_url)
        for entry in parsed:
            href = entry.get("href", "")
            if href and href not in seen:
                seen.add(href)
                all_entries.append(entry)
        if len(all_entries) >= limit:
            break

    logger.info("wiki RSS: fetched %d entries from %d feeds", len(all_entries), len(urls))
    return all_entries[:limit]
