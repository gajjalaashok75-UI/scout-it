"""Category-aware RSS provider registry for image-search.

Mirrors ``category_providers.py`` (news) and ``web_category_providers.py``
(web) but drives image RSS feeds from ``image_search_feed.py``. Each provider
returns normalized image entries (with ``image_url``/``thumbnail_url``) that
the unified image-search pipeline ranks alongside DuckDuckGo results.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Sequence
import logging

from .image_search_feed import IMAGE_SEARCH_FEEDS, flickr_tag_feed, deviantart_query_feeds
from .image_rss import fetch_image_feed_entries

logger = logging.getLogger(__name__)

__all__ = [
    "IMAGE_CATEGORY_PROVIDERS",
    "get_available_image_categories",
    "get_image_category_feeds",
    "fetch_image_category_feeds",
    "flickr_query_feed",
    "deviantart_query_feed",
]


def _feed_urls_for_category(category: str) -> List[str]:
    return [entry["url"] for entry in IMAGE_SEARCH_FEEDS.get(category, []) if entry.get("url")]


def _make_image_provider(category: str):
    def _provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
        urls = _feed_urls_for_category(category)
        if not urls:
            return []
        logger.info("image RSS %s: fetching %d feeds", category, len(urls))
        entries = fetch_image_feed_entries(urls, limit=max_results)
        for e in entries:
            e.setdefault("source", f"rss:{category}")
        logger.info("image RSS %s: returning %d entries", category, len(entries))
        return entries

    _provider.__name__ = f"image_{category}_provider"
    return _provider


IMAGE_CATEGORY_PROVIDERS: Dict[str, List[Any]] = {
    category: [_make_image_provider(category)] for category in IMAGE_SEARCH_FEEDS
}


def get_available_image_categories() -> List[str]:
    """Return supported image RSS category names."""
    return sorted(IMAGE_CATEGORY_PROVIDERS.keys())


def get_image_category_feeds(category: str) -> List[Any]:
    """Return provider functions for an image category."""
    return IMAGE_CATEGORY_PROVIDERS.get(category.lower(), [])


def fetch_image_category_feeds(
    categories: Sequence[str],
    query: str,
    max_results: int = 500,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Fetch image entries from all RSS providers for the given categories.

    Returns ALL matching entries (no artificial limit) for ranking.
    """
    providers_to_run: List[tuple] = []
    for category in categories:
        funcs = get_image_category_feeds(category.lower())
        if not funcs:
            logger.warning("no image RSS providers for category: %s", category)
            continue
        for func in funcs:
            providers_to_run.append((category.lower(), func))

    if not providers_to_run:
        return []

    all_results: List[Dict[str, Any]] = []
    seen: set = set()

    with ThreadPoolExecutor(max_workers=min(len(providers_to_run), 4)) as executor:
        futures = {
            executor.submit(func, query, max_results, **kwargs): (cat, func.__name__)
            for cat, func in providers_to_run
        }
        for future in as_completed(futures):
            cat, name = futures[future]
            try:
                for entry in future.result():
                    key = entry.get("image_url") or entry.get("source_url")
                    if key and key not in seen:
                        seen.add(key)
                        all_results.append(entry)
            except Exception as exc:
                logger.error("image provider %s (%s) failed: %s", name, cat, exc)

    logger.info("image RSS total after dedup: %d", len(all_results))
    return all_results


def flickr_query_feed(query: str) -> str:
    """Build a Flickr tag feed from an arbitrary search query."""
    tag = query.strip().lower().replace(" ", ",")
    return flickr_tag_feed(tag) if tag else ""


def deviantart_query_feed(query: str) -> List[str]:
    """Build DeviantArt RSS feed URLs from an arbitrary search query.

    Uses ``deviantart_query_feeds`` to map query keywords to the best
    DeviantArt tag feeds. Returns a list of feed URLs (may be empty if the
    query is blank).
    """
    return deviantart_query_feeds(query)
