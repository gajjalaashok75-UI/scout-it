"""Web search command module."""

from dataclasses import asdict
from typing import Optional, List, Dict, Any, Tuple

from ..extraction import EnterpriseSearchEngine
from ..cleaner import process_results
from .. import engines as search_engines


def multi_search(
    query: str,
    engines: Optional[List[str]] = None,
    max_results: int = 10,
    workers: int = 5,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
    dedupe: bool = True,
    sources: Optional[List[str]] = None,
    **engine_kwargs,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Query multiple search engines in parallel, merge/dedupe the results,
    then run them through the same content-extraction + cleaning pipeline as
    ``web_search``.

    See ``scout_it.engines`` for what each engine needs (DuckDuckGo works
    out of the box; Brave/Bing/Google/SerpAPI each need an API key set as an
    environment variable). Unconfigured engines are skipped, not errored —
    check the returned ``stats['discovery']['skipped']`` list to see why.

    When ``sources`` includes ``'wikimedia'``, the Wikimedia engine is
    added to the engine list (zero-config, no API key needed).
    """
    engines = engines or ['duckduckgo']
    if sources:
        for s in sources:
            if s == 'wikimedia':
                if 'wikimedia' not in engines:
                    engines.append('wikimedia')

    discovery = search_engines.multi_engine_search(
        query, engines=engines, max_results=max_results, max_workers=min(workers, 5), **engine_kwargs
    )

    if not discovery['merged_results']:
        return [], {
            'discovery': discovery['stats'],
            'search_engine': {'total': 0, 'success': 0, 'execution_time': discovery['stats']['execution_time']},
            'cleaner': {'total_input': 0, 'successful': 0, 'failed': 0, 'processed': 0},
        }

    engine = EnterpriseSearchEngine(
        max_workers=workers,
        max_fetch_retries=max_fetch_retries,
        enable_js_fallback=enable_js_fallback,
    )
    raw_results = engine.execute_search_from_urls(discovery['merged_results'][:max_results])

    results_dicts = [asdict(r) for r in raw_results]
    structured_results, cleaner_stats = process_results(results_dicts)

    combined_stats = {
        'discovery': discovery['stats'],
        'search_engine': engine.stats,
        'cleaner': cleaner_stats,
    }
    return structured_results, combined_stats
