"""Category-aware RSS provider registry for wiki-search.

Mirrors the image/video category-provider registries but drives MediaWiki
RecentChanges feeds from ``wiki_search_feed.py``. Each provider returns
normalized wiki entries (with ``href``/``url``/``body``/``title``) that the
unified wiki-search pipeline ranks alongside the MediaWiki Action API
search results.

Here a "category" is a Wikimedia project key (wikipedia, commons, wiktionary,
...) rather than a topical grouping, since the RecentChanges feed is
project-scoped, not topic-scoped.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Sequence
import logging

from .wiki_search_feed import WIKI_SEARCH_FEEDS, WIKI_FEED_CATEGORIES
from .wiki_rss import fetch_wiki_feed_entries

logger = logging.getLogger(__name__)

__all__ = [
    "WIKI_CATEGORY_PROVIDERS",
    "get_available_wiki_categories",
    "get_wiki_category_feeds",
    "fetch_wiki_category_feeds",
]


def _feed_urls_for_category(category: str) -> List[str]:
    return [entry["url"] for entry in WIKI_SEARCH_FEEDS.get(category, []) if entry.get("url")]


def _make_wiki_provider(category: str):
    def _provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
        urls = _feed_urls_for_category(category)
        if not urls:
            return []
        logger.info("wiki RSS %s: fetching %d feeds", category, len(urls))
        entries = fetch_wiki_feed_entries(urls, limit=max_results)
        for e in entries:
            e.setdefault("source", f"rss:{category}")
            e.setdefault("project", category)
        logger.info("wiki RSS %s: returning %d entries", category, len(entries))
        return entries

    _provider.__name__ = f"wiki_{category}_provider"
    return _provider


WIKI_CATEGORY_PROVIDERS: Dict[str, List[Any]] = {
    category: [_make_wiki_provider(category)] for category in WIKI_SEARCH_FEEDS
}


def get_available_wiki_categories() -> List[str]:
    """Return supported wiki RSS category (project) names."""
    return sorted(WIKI_CATEGORY_PROVIDERS.keys())


def get_wiki_category_feeds(category: str) -> List[Any]:
    """Return provider functions for a wiki category (project)."""
    return WIKI_CATEGORY_PROVIDERS.get(category.lower(), [])


def fetch_wiki_category_feeds(
    categories: Sequence[str],
    query: str,
    max_results: int = 500,
    **kwargs,
) -> List[Dict[str, Any]]:
    """Fetch wiki entries from all RSS providers for the given categories (projects)."""
    providers_to_run: List[tuple] = []
    for category in categories:
        funcs = get_wiki_category_feeds(category.lower())
        if not funcs:
            logger.warning("no wiki RSS providers for category: %s", category)
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
                    key = entry.get("href") or entry.get("url")
                    if key and key not in seen:
                        seen.add(key)
                        all_results.append(entry)
            except Exception as exc:
                logger.error("wiki provider %s (%s) failed: %s", name, cat, exc)

    logger.info("wiki RSS total after dedup: %d", len(all_results))
    return all_results
