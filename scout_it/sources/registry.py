"""Plugin registry — discovers, registers, and dispatches to source plugins.

Plugins register themselves via ``@register`` or are auto-discovered from
the ``scout_it.sources`` package. The registry provides:

  - ``list_plugins()`` — all registered source names + metadata
  - ``list_available()`` — sources that are enabled and have required keys
  - ``search_source(name, query)`` — search one source
  - ``search_all(query, sources)`` — search multiple sources concurrently
  - ``source_search(query, sources)`` — gather all → semantic rank → output
"""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any, Dict, List, Optional, Sequence

from .base import SourcePlugin, SearchResult, make_result
from .source_config import is_source_enabled, get_source_config, SOURCE_BY_NAME

logger = logging.getLogger(__name__)

# ─── Registry ────────────────────────────────────────────────────────────────

_plugins: Dict[str, SourcePlugin] = {}
_discovered = False


def register(plugin: SourcePlugin) -> SourcePlugin:
    """Register a source plugin instance."""
    if not plugin.name:
        raise ValueError(f"Plugin {plugin} has no name")
    _plugins[plugin.name] = plugin
    logger.debug("Registered source plugin: %s", plugin.name)
    return plugin


def _discover() -> None:
    """Auto-discover and import all source plugin modules.

    Each module in ``scout_it.sources`` that defines a ``PLUGIN`` or
    ``get_plugin()`` is registered. Modules are imported lazily on first use.
    """
    global _discovered
    if _discovered:
        return
    _discovered = True

    # List of plugin modules to import (each registers itself via @register).
    plugin_modules = [
        "openalex",
        "semantic_scholar",
        "arxiv",
        "crossref",
        "unpaywall",
        "core_ac",
        "europe_pmc",
        "huggingface",
        "zenodo",
        "data_gov",
        "wikidata",
        "open_library",
        "gutenberg",
        "gdelt",
        "internet_archive",
        "listennotes",
        "openstreetmap",
        # New no-auth sources (from public-apis/public-apis)
        "hackernews",
        "stackexchange",
        "open_fda",
        "open_meteo",
        "usgs_earthquakes",
        "musicbrainz",
        "open_food_facts",
        "spaceflight_news",
        "art_institute_chicago",
        "met_museum",
        "jikan",
        "doaj",
        "gitlab",
        "bitbucket",
    ]

    for mod_name in plugin_modules:
        try:
            importlib.import_module(f"scout_it.sources.plugins.{mod_name}")
        except ImportError as exc:
            logger.debug("Source plugin %s not available: %s", mod_name, exc)
        except Exception as exc:
            logger.warning("Failed to load source plugin %s: %s", mod_name, exc)


def get_plugin(name: str) -> Optional[SourcePlugin]:
    """Get a registered plugin by name, discovering if needed."""
    _discover()
    return _plugins.get(name)


def list_plugins() -> List[Dict[str, Any]]:
    """List all registered plugins with their metadata and status."""
    _discover()
    out = []
    for name, plugin in sorted(_plugins.items()):
        cfg = get_source_config(name)
        meta = SOURCE_BY_NAME.get(name, {})
        out.append({
            "name": name,
            "display_name": getattr(plugin, "display_name", name),
            "content_type": getattr(plugin, "content_type", "academic"),
            "requires_key": meta.get("requires_key", False),
            "available": plugin.is_available(),
            "enabled": cfg.get("enabled", True),
            "configured": True if not meta.get("requires_key") else bool(cfg.get("api_key")),
            "description": meta.get("description", ""),
        })
    return out


def list_available() -> List[str]:
    """Return names of plugins that are enabled and available."""
    _discover()
    out = []
    for name, plugin in _plugins.items():
        cfg = get_source_config(name)
        if cfg.get("enabled", True) and plugin.is_available():
            out.append(name)
    return out


# ─── Search ──────────────────────────────────────────────────────────────────


async def _search_source_async(
    plugin: SourcePlugin,
    query: str,
    max_results: int,
) -> List[Dict[str, Any]]:
    """Search one source, catching errors so one failure doesn't affect others."""
    try:
        results = plugin.search(query, max_results=max_results)
        # Ensure every result has the source field set.
        for r in results:
            if not r.get("source"):
                r["source"] = plugin.name
        return results
    except Exception as exc:
        logger.warning("Source %s search failed: %s", plugin.name, exc)
        return []


async def _search_all_async(
    query: str,
    sources: Sequence[str],
    max_results_per_source: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """Search multiple sources concurrently."""
    _discover()
    coros = []
    active_sources = []
    for name in sources:
        plugin = _plugins.get(name)
        if not plugin:
            logger.warning("Unknown source: %s", name)
            continue
        cfg = get_source_config(name)
        if not cfg.get("enabled", True):
            logger.debug("Source %s is disabled, skipping", name)
            continue
        if not plugin.is_available():
            logger.debug("Source %s not available (missing key?), skipping", name)
            continue
        coros.append(_search_source_async(plugin, query, max_results_per_source))
        active_sources.append(name)

    results_lists = await asyncio.gather(*coros, return_exceptions=True)
    out = {}
    for name, results in zip(active_sources, results_lists):
        if isinstance(results, Exception):
            logger.warning("Source %s raised: %s", name, results)
            out[name] = []
        else:
            out[name] = results
    return out


def search_source(
    source: str,
    query: str,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Search a single source and return normalized results."""
    plugin = get_plugin(source)
    if not plugin:
        raise ValueError(f"Unknown source: {source}. Use list_plugins() to see available sources.")
    results = plugin.search(query, max_results=max_results)
    for r in results:
        if not r.get("source"):
            r["source"] = plugin.name
    return results


def search_all(
    query: str,
    sources: Optional[Sequence[str]] = None,
    max_results_per_source: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """Search multiple sources concurrently, return results grouped by source.

    Args:
        query: search query.
        sources: list of source names. If None, uses all enabled & available.
        max_results_per_source: max results per source.

    Returns:
        Dict mapping source name → list of SearchResult dicts.
    """
    if sources is None:
        sources = list_available()
    if not sources:
        return {}
    return run_async_helper(_search_all_async(query, sources, max_results_per_source))


def source_search(
    query: str,
    sources: Optional[Sequence[str]] = None,
    max_results_per_source: int = 10,
    max_final_results: int = 20,
    *,
    semantic_rerank: bool = True,
    enable_reranker: bool = False,
) -> List[Dict[str, Any]]:
    """Search across multiple sources, gather all results, then semantic-rank.

    This is the main entry point for multi-source semantic search. It:
    1. Searches all specified sources concurrently (async)
    2. Gathers all results into one pool
    3. Runs BM25F + vector hybrid semantic re-ranking (if semantic_rerank=True)
    4. Returns the top results sorted by relevance

    Args:
        query: search query string.
        sources: source names to search. If None, searches all enabled sources.
        max_results_per_source: max results to fetch from each source.
        max_final_results: max results to return after ranking.
        semantic_rerank: if True, apply BM25F+vector re-ranking.
        enable_reranker: if True, use cross-encoder reranker (needs ML deps).

    Returns:
        List of SearchResult dicts, ranked by relevance.
    """
    # 1. Gather all results from all sources.
    grouped = search_all(query, sources, max_results_per_source)
    all_results: List[Dict[str, Any]] = []
    for source_name, results in grouped.items():
        all_results.extend(results)

    if not all_results:
        return []

    # 2. Deduplicate by URL.
    seen_urls = set()
    deduped = []
    for r in all_results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(r)
    all_results = deduped

    # 3. Semantic re-rank (BM25F + vector hybrid).
    if semantic_rerank:
        try:
            from ..semantic import semantic_rerank as _rerank
            ranked = _rerank(all_results, query, enable_reranker=enable_reranker)

            # 3b. Composite re-rank (Phase 3: relevance + authority + freshness + diversity).
            from ..semantic import composite_rerank as _composite
            ranked = _composite(ranked, query, max_final=max_final_results)

            return ranked
        except Exception as exc:
            logger.warning("Semantic rerank failed, returning unranked: %s", exc)

    # Fallback: sort by authority score, then snippet length.
    all_results.sort(
        key=lambda r: (r.get("authority_score", 0), len(r.get("snippet", ""))),
        reverse=True,
    )
    return all_results[:max_final_results]


def run_async_helper(coro):
    """Run an async coroutine from sync code."""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)
