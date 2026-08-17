"""Web search command module."""

import logging
from dataclasses import asdict
from typing import Optional, List, Dict, Any, Tuple

from ..extraction import EnterpriseSearchEngine
from ..cleaner import process_results
from .. import engines as search_engines

logger = logging.getLogger(__name__)


def multi_search(
    query: str,
    engines: Optional[List[str]] = None,
    max_results: int = 10,
    workers: int = 5,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
    dedupe: bool = True,
    sources: Optional[List[str]] = None,
    source: Optional[str] = None,
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

    When ``source`` is given (comma-separated), the listed API search
    providers (``tavily``, ``exa``, ``firecrawl``) and ``wikimedia`` are
    added as parallel discovery streams alongside the engines. ``wikimedia``
    is appended to the engine list; API sources are queried directly and
    their URL candidates are merged into the discovery results before
    content extraction — exactly like the ``--source`` flag on
    ``web-search``.
    """
    engines = engines or ['duckduckgo']
    if sources:
        for s in sources:
            if s == 'wikimedia':
                if 'wikimedia' not in engines:
                    engines.append('wikimedia')

    # --source (singular): comma-separated parallel discovery sources.
    api_source_names: List[str] = []
    if source:
        for s in source.split(','):
            s = s.strip()
            if not s:
                continue
            if s == 'wikimedia' and 'wikimedia' not in engines:
                engines.append('wikimedia')
            elif s not in ('duckduckgo', 'brave', 'bing', 'google', 'serpapi', 'wikimedia'):
                api_source_names.append(s)

    discovery = search_engines.multi_engine_search(
        query, engines=engines, max_results=max_results, max_workers=min(workers, 5), **engine_kwargs
    )

    # ── API search sources: query in parallel, merge URL candidates ──
    api_candidates: List[Dict[str, Any]] = []
    if api_source_names:
        from ..sources.registry import get_plugin, _discover as _discover_plugins
        from ..sources.api_search_base import source_messages as _src_msgs
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Pre-discover in main thread to avoid race condition in workers.
        _discover_plugins()

        def _query_api(name: str) -> List[Dict[str, Any]]:
            plugin = get_plugin(name)
            if plugin is None:
                return []
            return plugin.search(query, max_results=max_results, search_type='multi')

        with ThreadPoolExecutor(max_workers=min(len(api_source_names), 3)) as ex:
            futs = {ex.submit(_query_api, n): n for n in api_source_names}
            for fut in as_completed(futs):
                name = futs[fut]
                try:
                    for r in fut.result():
                        url = r.get('url', '') or r.get('id', '')
                        if url:
                            api_candidates.append({
                                'title': r.get('title', ''),
                                'url': url,
                                'href': url,
                                'body': r.get('snippet', '') or r.get('content', ''),
                                'source': name,
                            })
                except Exception as exc:
                    logger.warning("API source %s failed: %s", name, exc)

        # Print skip/error messages collected by API sources.
        if _src_msgs.has_messages():
            for msg in _src_msgs.drain():
                if msg['type'] == 'skip':
                    print(f"⏭️  Source '{msg['source']}' skipped: {msg['reason']}")
                else:
                    print(f"⚠️  Source '{msg['source']}': {msg['reason']}")

    # Merge API candidates into the discovery results (dedupe by URL).
    if api_candidates:
        seen_urls = {r.get('url', '') or r.get('href', '') for r in discovery['merged_results']}
        for c in api_candidates:
            url = c.get('url', '') or c.get('href', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                discovery['merged_results'].append(c)
        discovery['stats']['api_sources'] = api_source_names
        discovery['stats']['api_candidates'] = len(api_candidates)

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
