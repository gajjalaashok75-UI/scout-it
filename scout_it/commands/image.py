"""Image search command module."""

from dataclasses import asdict
from typing import Optional, Dict, Any, List, Tuple

from ..extraction import ImageSearchEngine, _compact_options


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
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute image search pipeline: search → extract metadata.

    Args:
        query: Search query string
        max_results: Max images to fetch

    Returns:
        (image_results, stats) tuple with image metadata
    """
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
    
    # Convert to dicts for JSON serialization
    results_dicts = [asdict(r) for r in raw_results]
    
    stats = {
        'search_engine': engine.stats
    }
    
    print(f"📈 Found {len(raw_results)} images for query: {query}")
    return results_dicts, stats
