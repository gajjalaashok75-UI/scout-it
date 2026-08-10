"""Image search command module — unified discovery -> rank -> output pipeline.

Mirrors the web-search/news-search unified flow: discover candidate images
from multiple sources (DuckDuckGo Images + image RSS category feeds), rank
them with the shared ``rank_candidates_initial`` scorer, and return the top
results. RSS feeds are fetched in parallel and only add sources when
``categories`` are requested (or ``include_rss=True``).
"""

import logging
from dataclasses import asdict
from typing import Optional, Dict, Any, List, Sequence, Tuple

from ..extraction import ImageSearchEngine, _compact_options
from ..staged_ranker import rank_candidates_initial
from .image_category_providers import fetch_image_category_feeds, flickr_query_feed
from .image_rss import fetch_image_feed_entries

logger = logging.getLogger(__name__)


def _passes_dimensions(
    width: Optional[int],
    height: Optional[int],
    min_width: Optional[int],
    max_width: Optional[int],
    min_height: Optional[int],
    max_height: Optional[int],
) -> bool:
    if not any(v is not None for v in (min_width, max_width, min_height, max_height)):
        return True
    if width is None or height is None:
        return False
    if min_width is not None and width < min_width:
        return False
    if max_width is not None and width > max_width:
        return False
    if min_height is not None and height < min_height:
        return False
    if max_height is not None and height > max_height:
        return False
    return True


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        parsed = int(value)
        return parsed if parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def image_search(
    query: str,
    max_results: int = 50,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    type_image: Optional[str] = None,
    layout: Optional[str] = None,
    license_image: Optional[str] = None,
    min_width: Optional[int] = None,
    max_width: Optional[int] = None,
    min_height: Optional[int] = None,
    max_height: Optional[int] = None,
    categories: Optional[Sequence[str]] = None,
    include_rss: bool = False,
    top_k: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Execute the unified image search pipeline: discover -> rank -> output.

    Discovery sources (merged before ranking):
      1. DuckDuckGo Images (always).
      2. Image RSS category feeds (when ``categories`` given or
         ``include_rss=True``). A Flickr tag feed derived from ``query`` is
         also fetched when no explicit categories are provided.

    Ranking uses the shared lightweight ``rank_candidates_initial`` scorer
    (title/body relevance, source quality, recency) - the same one used by
    web-search/news-search - so image results are ordered consistently.

    Args:
        query: Search query string.
        max_results: Max images to fetch from DuckDuckGo.
        categories: Image RSS categories to include (e.g. ``["nature","space"]``).
        include_rss: Force RSS discovery even without ``categories``.
        top_k: Number of ranked results to return (defaults to ``max_results``).

    Returns:
        ``(image_results, stats)`` tuple with ranked image metadata.
    """
    if min_width is not None and max_width is not None and min_width > max_width:
        raise ValueError("min_width cannot be greater than max_width")
    if min_height is not None and max_height is not None and min_height > max_height:
        raise ValueError("min_height cannot be greater than max_height")

    engine = ImageSearchEngine()
    image_options = _compact_options({
        'region': region,
        'safesearch': safesearch,
        'timelimit': timelimit,
        'size': size,
        'color': color,
        'type_image': type_image,
        'layout': layout,
        'license_image': license_image,
    })

    # ---- Discovery stream 1: DuckDuckGo Images ----
    raw_results = engine.execute_image_search(
        query,
        max_results,
        search_options=image_options,
        retry_on_zero_success=retry_on_zero_success,
        max_zero_success_retries=retry_attempts,
        retry_backoff_seconds=retry_backoff,
        min_width=min_width,
        max_width=max_width,
        min_height=min_height,
        max_height=max_height,
    )
    ddgs_dicts = [asdict(r) for r in raw_results]

    # Normalize DDGS results into ranking candidate shape.
    candidates: List[Dict[str, Any]] = []
    for r in ddgs_dicts:
        candidates.append({
            "title": r.get("title", ""),
            "image_url": r.get("image_url", ""),
            "source_url": r.get("source_url", ""),
            "thumbnail_url": r.get("thumbnail_url", ""),
            "width": r.get("width", 0),
            "height": r.get("height", 0),
            "image_size": r.get("image_size", ""),
            "body": r.get("title", ""),
            "source": "DuckDuckGo",
            "publish_date": "",
        })

    rss_count = 0
    # ---- Discovery stream 2: image RSS feeds ----
    rss_categories = list(categories) if categories else []
    if rss_categories:
        rss_entries = fetch_image_category_feeds(rss_categories, query, max_results=max_results)
        candidates.extend(rss_entries)
        rss_count += len(rss_entries)
    elif include_rss:
        flickr_url = flickr_query_feed(query)
        if flickr_url:
            rss_entries = fetch_image_feed_entries([flickr_url], limit=max_results)
            candidates.extend(rss_entries)
            rss_count += len(rss_entries)

    # ---- Rank (shared scorer) ----
    limit = int(top_k) if top_k is not None else int(max_results)
    ranked = rank_candidates_initial(candidates, query, top_k=max(limit, len(candidates)))

    # Re-apply dimension filters on ranked output and dedupe by image_url.
    seen: set = set()
    output: List[Dict[str, Any]] = []
    for entry in ranked:
        image_url = entry.get("image_url", "")
        # Keep image-less entries too (e.g. stub DDGS results in tests) by
        # falling back to a title-based key so they are not silently dropped.
        key = image_url or f"title:{entry.get('title', '')}"
        if not key or key in seen:
            continue
        width = _coerce_int(entry.get("width"))
        height = _coerce_int(entry.get("height"))
        if not _passes_dimensions(width, height, min_width, max_width, min_height, max_height):
            continue
        seen.add(key)
        output.append({
            "position": len(output) + 1,
            "title": entry.get("title", ""),
            "image_url": image_url,
            "source_url": entry.get("source_url", image_url),
            "thumbnail_url": entry.get("thumbnail_url", image_url),
            "width": width or 0,
            "height": height or 0,
            "image_size": entry.get("image_size", ""),
            "source": entry.get("source", "DuckDuckGo"),
            "initial_rank_score": entry.get("initial_rank_score", 0.0),
            "rank_breakdown": entry.get("rank_breakdown", {}),
        })
        if len(output) >= limit:
            break

    stats = {
        'search_engine': engine.stats,
        'pipeline': 'unified',
        'ddgs_candidates': len(ddgs_dicts),
        'rss_candidates': rss_count,
        'total_candidates': len(candidates),
        'ranked_output': len(output),
        'rss_categories': rss_categories,
    }

    print(f"📈 Found {len(output)} ranked images for query: {query} "
          f"(DDGS: {len(ddgs_dicts)}, RSS: {rss_count})")
    return output, stats
