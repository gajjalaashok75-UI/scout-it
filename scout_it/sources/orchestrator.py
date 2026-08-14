"""Orchestration: merge source plugin results with regular search results.

When a --sources flag is passed to web-search, news-search, etc., this module:
  1. Searches the specified source plugins in parallel (async)
  2. Normalizes regular search results into the SearchResult schema
  3. Merges both pools
  4. Deduplicates by URL
  5. Runs BM25F + vector semantic re-ranking on the combined set
  6. Returns the ranked results

The regular search results and source results are fetched concurrently,
so the total time is max(regular_search, source_searches) — not the sum.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


def normalize_regular_result(
    result: Dict[str, Any],
    default_source: str = "web",
) -> Dict[str, Any]:
    """Convert a regular search result (DDGS, RSS, etc.) into SearchResult schema.

    Regular results have fields like {title, href, snippet, body, url, source, ...}.
    This normalizes them to the unified schema so they can be merged with source
    plugin results and ranked together.
    """
    url = result.get("href") or result.get("url") or result.get("link") or ""
    title = result.get("title") or ""
    snippet = result.get("snippet") or result.get("body") or result.get("summary") or result.get("description") or ""
    content = result.get("main_content") or result.get("content") or ""

    # Source: use the existing source field, or the default.
    source = result.get("source") or result.get("engine") or default_source

    # Authority: use score if present, else 0.
    score = result.get("score") or 0
    try:
        authority = min(float(score) / 100.0, 1.0) if score else 0.0
    except (ValueError, TypeError):
        authority = 0.0

    # Timestamp.
    timestamp = result.get("publish_date") or result.get("date") or result.get("timestamp") or ""

    return {
        "id": url or title,
        "source": source,
        "url": url,
        "title": title,
        "snippet": snippet,
        "content": content,
        "content_type": result.get("content_type", "web"),
        "timestamp": timestamp,
        "authority_score": authority,
        "relevance_score": 0.0,
        "lang": result.get("lang", "en"),
        "metadata": {k: v for k, v in result.items() if k not in {
            "title", "href", "url", "link", "snippet", "body", "summary",
            "description", "main_content", "content", "source", "engine",
            "score", "publish_date", "date", "timestamp", "lang", "content_type",
        }},
    }


def merge_and_rank(
    query: str,
    regular_results: List[Dict[str, Any]],
    source_results: Dict[str, List[Dict[str, Any]]],
    max_final: int = 20,
    default_source: str = "web",
    *,
    semantic_rerank: bool = True,
    composite_rerank: bool = True,
    content_type_hint: str = "web",
) -> List[Dict[str, Any]]:
    """Merge regular results with source plugin results, then rank.

    Pipeline:
      1. Normalize + merge regular + source results
      2. Deduplicate by URL
      3. Semantic re-rank (BM25F + vector + RRF + cross-encoder)
      4. Composite re-rank (relevance + authority + freshness + diversity)

    Args:
        query: the search query.
        regular_results: results from DDGS/RSS/etc. (will be normalized).
        source_results: results from source plugins (already in SearchResult schema).
        max_final: max results to return after ranking.
        default_source: source label for regular results.
        semantic_rerank: if True, apply BM25F+vector re-ranking.
        composite_rerank: if True, apply composite (Phase 3) re-ranking after semantic.
        content_type_hint: dominant content type for composite weighting.

    Returns:
        List of SearchResult dicts, ranked by composite score.
    """
    # 1. Normalize regular results.
    all_results: List[Dict[str, Any]] = [
        normalize_regular_result(r, default_source=default_source)
        for r in regular_results
        if r  # skip empties
    ]

    # 2. Add source plugin results (already normalized).
    for source_name, results in source_results.items():
        all_results.extend(results)

    if not all_results:
        return []

    # 3. Deduplicate by URL.
    seen_urls = set()
    deduped = []
    for r in all_results:
        url = r.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped.append(r)
    all_results = deduped

    # 4. Semantic re-rank (BM25F + vector hybrid).
    ranked = all_results
    if semantic_rerank:
        try:
            from ..semantic import semantic_rerank as _rerank
            ranked = _rerank(all_results, query)
        except Exception as exc:
            logger.warning("Semantic rerank failed, falling back to authority sort: %s", exc)
            ranked = all_results

    # 5. Composite re-rank (Phase 3: relevance + authority + freshness + diversity).
    if composite_rerank:
        try:
            from ..semantic import composite_rerank as _composite
            ranked = _composite(ranked, query, content_type_hint=content_type_hint,
                                 max_final=max_final)
        except Exception as exc:
            logger.warning("Composite rerank failed, using semantic order: %s", exc)
            ranked = ranked[:max_final]
    else:
        ranked = ranked[:max_final]

    return ranked


def search_sources_parallel(
    query: str,
    sources: Sequence[str],
    max_per_source: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """Search multiple source plugins in parallel (async).

    Returns a dict mapping source name → list of SearchResult dicts.
    Failed sources return an empty list (errors are isolated).
    """
    from .registry import search_all
    return search_all(query, sources=sources, max_results_per_source=max_per_source)


def augment_search_with_sources(
    query: str,
    regular_results: List[Dict[str, Any]],
    sources: Optional[str],
    max_final: int = 20,
    max_per_source: int = 10,
    default_source: str = "web",
    *,
    semantic_rerank: bool = True,
    composite_rerank: bool = True,
    content_type_hint: str = "web",
    use_source_bandit: bool = False,
    bandit_top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Augment regular search results with source plugin results.

    This is the main entry point called by CLI commands when --sources is given.
    It:
    1. Resolves which sources to query (explicit list, or bandit-selected)
    2. Searches those sources in parallel (async)
    3. Merges with the regular results
    4. Deduplicates and semantic-ranks the combined pool
    5. Applies composite re-ranking (relevance + authority + freshness + diversity)
    6. Records outcomes to the source-selection bandit (for future learning)

    Args:
        query: search query.
        regular_results: results from the main search (DDGS, RSS, etc.).
        sources: comma-separated source names, or None.
        max_final: max results to return after ranking.
        max_per_source: max results per source plugin.
        default_source: source label for regular results.
        semantic_rerank: if True, apply BM25F+vector re-ranking.
        composite_rerank: if True, apply composite (Phase 3) re-ranking.
        content_type_hint: dominant content type for composite weighting.
        use_source_bandit: if True and sources is None, use the source-selection
            bandit to pick the best sources for the query type.
        bandit_top_k: how many sources the bandit should select.

    Returns:
        List of SearchResult dicts, ranked by composite score. If --sources is not
        given (and bandit is disabled), returns the regular results as-is.
    """
    # Determine which sources to query.
    source_names: List[str] = []
    bandit_info: Optional[Dict[str, Any]] = None

    if sources:
        # Explicit --sources flag: use the user-specified sources.
        source_names = [s.strip() for s in sources.split(",") if s.strip()]
    elif use_source_bandit:
        # No explicit sources — let the bandit pick.
        from .source_bandit import choose_sources as _choose
        from .registry import list_available
        available = list_available()
        if available:
            bandit_info = _choose(query, available, top_k=bandit_top_k)
            source_names = bandit_info["sources"]
            logger.info("Source bandit selected %d sources for query type '%s': %s",
                        len(source_names), bandit_info["query_type"], source_names)

    if not source_names:
        return regular_results

    # Search sources in parallel.
    source_results = search_sources_parallel(query, source_names, max_per_source)

    # Check if we got any source results.
    total_source = sum(len(v) for v in source_results.values())
    if total_source == 0:
        logger.info("No source results from %s, returning regular results only", source_names)
        return regular_results

    # Determine content_type_hint from the bandit classification or the explicit hint.
    effective_hint = content_type_hint
    if bandit_info and bandit_info.get("query_type") and content_type_hint == "web":
        effective_hint = bandit_info["query_type"]

    # Merge and rank (semantic + composite).
    ranked = merge_and_rank(
        query=query,
        regular_results=regular_results,
        source_results=source_results,
        max_final=max_final,
        default_source=default_source,
        semantic_rerank=semantic_rerank,
        composite_rerank=composite_rerank,
        content_type_hint=effective_hint,
    )

    # Record outcomes to the source-selection bandit (learns for next time).
    try:
        from .source_bandit import record_source_outcomes as _record
        _record(query, source_results)
    except Exception as exc:
        logger.debug("Could not record source bandit outcomes: %s", exc)

    return ranked
