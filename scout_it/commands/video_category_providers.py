"""Category-aware RSS provider registry for video-search.

Mirrors the news/web image provider registries but drives YouTube channel
feeds from ``video_search_feed.py``. Each provider returns normalized video
entries (with ``content``/``url``/``description``/``thumbnail``) that the
unified video-search pipeline ranks alongside DuckDuckGo results.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Sequence
import logging

from .video_search_feed import VIDEO_SEARCH_FEEDS
from .video_rss import fetch_video_feed_entries

logger = logging.getLogger(__name__)

__all__ = [
    "VIDEO_CATEGORY_PROVIDERS",
    "get_available_video_categories",
    "get_video_category_feeds",
    "fetch_video_category_feeds",
]


def _feed_urls_for_category(category: str) -> List[str]:
    return [entry["url"] for entry in VIDEO_SEARCH_FEEDS.get(category, []) if entry.get("url")]


def _make_video_provider(category: str):
    def _provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
        urls = _feed_urls_for_category(category)
        if not urls:
            return []
        logger.info("video RSS %s: fetching %d feeds", category, len(urls))
        entries = fetch_video_feed_entries(urls, limit=max_results)
        for e in entries:
            e.setdefault("source", f"rss:{category}")
        logger.info("video RSS %s: returning %d entries", category, len(entries))
        return entries

    _provider.__name__ = f"video_{category}_provider"
    return _provider


VIDEO_CATEGORY_PROVIDERS: Dict[str, List[Any]] = {
    category: [_make_video_provider(category)] for category in VIDEO_SEARCH_FEEDS
}


def get_available_video_categories() -> List[str]:
    """Return supported video RSS category names."""
    return sorted(VIDEO_CATEGORY_PROVIDERS.keys())


def get_video_category_feeds(category: str) -> List[Any]:
    """Return provider functions for a video category."""
    return VIDEO_CATEGORY_PROVIDERS.get(category.lower(), [])


def fetch_video_category_feeds(
    categories: Sequence[str],
    query: str,
    max_results: int = 500,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Fetch video entries from all RSS providers for the given categories."""
    providers_to_run: List[tuple] = []
    for category in categories:
        funcs = get_video_category_feeds(category.lower())
        if not funcs:
            logger.warning("no video RSS providers for category: %s", category)
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
                    key = entry.get("url") or entry.get("content")
                    if key and key not in seen:
                        seen.add(key)
                        all_results.append(entry)
            except Exception as exc:
                logger.error("video provider %s (%s) failed: %s", name, cat, exc)

    logger.info("video RSS total after dedup: %d", len(all_results))
    return all_results
