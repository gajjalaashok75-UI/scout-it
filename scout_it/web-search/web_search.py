"""
Web Search Module - Extracted from cli.py

This module contains the web_search function and its related helpers,
extracted from cli.py for better code organization and maintainability.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from rich.console import Console

# Import from parent package
from ..extraction import (
    EnterpriseSearchEngine,
    _ddgs_list_search_with_retry,
)
from ..cleaner import process_results

# Initialize logger
logger = logging.getLogger(__name__)

# Shared Rich console so [cyan]/[green]/[yellow] markup in print() calls
# below renders as actual colors instead of literal bracket text.
console = Console()


def web_search(
    query: str,
    max_results: int = 10,
    workers: int = 5,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: Optional[str] = None,
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    backend: str = 'auto',
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
    enable_alternate_source: bool = False,
    enable_dns_fallback: bool = True,
    enable_tls_impersonate: bool = False,
    enable_persistent_profile: bool = False,
    browser_profile_name: str = 'default',
    enable_bandit: bool = False,
    source: Optional[str] = None,
    categories: Optional[List[str]] = None,
    snippets_only: bool = False,
):
    """Web search with optimized discovery-first pipeline (matches news-search).
    
    Correct Pipeline:
    1. Lightweight Discovery Phase
       - DDGS: 20 snippets (title, description, url, date)
       - RSS feeds: ALL entries (no limit)
       - NO content extraction yet
    
    2. Deduplicate & Rank (metadata-only, fast)
       - Deduplicate by URL
       - Rank by relevance using titles/descriptions
       - Select top N where N = max_results (default: 10)
    
    3. Content Extraction (only top N)
       - Extract full page content ONLY for top ranked URLs
       - Use requests → Playwright fallback
    
    4. Clean & Output
       - Process extracted content
       - Return final results
    
    Providers:
    - DDGS Text Search (always) → 20 snippets
    - Category RSS (if --category) → ALL entries from feeds
    
    Args:
        query: Search query
        max_results: Final number of results to extract and return (default: 10)
        categories: RSS feed categories (e.g., ['ai', 'cloud', 'engineering'])
        
    Returns:
        Structured results with full extracted content
    """
    start_time = time.time()
    
    # Discovery limits - MATCH NEWS_SEARCH EXACTLY
    DDGS_SNIPPET_LIMIT = 20      # Get top 20 snippets from DDGS (lightweight)
    RSS_NO_LIMIT = 500           # RSS feeds: get ALL entries (or large limit)
    
    # Extraction limit
    EXTRACTION_COUNT = max_results  # Extract content for this many results after ranking
    
    all_candidates: List[Dict[str, Any]] = []
    search_stats: Dict[str, Any] = {}
    seen_urls: set = set()
    
    def _dedup_append(results: List[Dict[str, Any]]) -> int:
        """Append results with URL-level dedup. Returns count added."""
        count = 0
        for r in results:
            url = r.get('url', '') or r.get('href', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_candidates.append(r)
                count += 1
        return count
    
    # ══════════════════════════════════════════════════════════════
    # Phase 1: Lightweight Discovery (Snippets Only, NO Extraction)
    # ══════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 1: Lightweight Discovery[/cyan]")
    discovery_start = time.time()
    
    # Stream 1: DDGS Search (20 snippets only - MATCH NEWS_SEARCH)
    def _run_ddgs_discovery():
        """Get DDGS snippets (NO content extraction)."""
        results, stats = _ddgs_list_search_with_retry(
            'text',
            query=query,
            max_results=DDGS_SNIPPET_LIMIT,
            options={'region': region, 'safesearch': safesearch, 'timelimit': timelimit, 'backend': backend},
            retry_on_zero_success=retry_on_zero_success,
            max_zero_success_retries=retry_attempts,
            retry_backoff_seconds=retry_backoff,
        )
        return results, stats
    
    # Stream 2: Category RSS Feeds (ALL entries - MATCH NEWS_SEARCH)
    def _run_category_rss(cats: List[str]):
        """Get ALL RSS entries from web categories (NO extraction)."""
        from ..web_category_providers import fetch_web_category_feeds, get_available_web_categories
        console.print(f"[blue]Web category RSS providers enabled:[/blue] {', '.join(cats)}")
        console.print(f"[dim]Available categories: {', '.join(get_available_web_categories())}[/dim]")
        return fetch_web_category_feeds(cats, query, max_results=RSS_NO_LIMIT)
    
    # Stream 3: Wikimedia (if --sources wikimedia)
    def _run_wikimedia_discovery():
        """Get Wikimedia results (NO extraction)."""
        from ..wikimedia_source import wikimedia_search
        console.print(f"[blue]Wikimedia source enabled[/blue]")
        results = wikimedia_search(query, max_results=RSS_NO_LIMIT)
        # Normalize to search format
        normalized = []
        for r in results:
            normalized.append({
                'title': r.get('title', ''),
                'url': r.get('url', ''),
                'href': r.get('url', ''),
                'body': r.get('body', ''),
                'snippet': r.get('snippet', ''),
                'source': 'wikimedia',
            })
        return normalized
    
    # ── API search sources (Tavily/Exa/Firecrawl) as parallel discovery ──
    # ``source`` may be a comma-separated list like "wikimedia,tavily,exa".
    api_source_names: List[str] = []
    if source:
        api_source_names = [
            s.strip() for s in source.split(',')
            if s.strip() and s.strip() != 'wikimedia'
        ]

    # Pre-discover plugins in the main thread to avoid a race condition where
    # concurrent ThreadPoolExecutor workers call get_plugin() before
    # _discover() has finished registering all plugins.
    if api_source_names:
        from ..sources.registry import _discover as _discover_plugins
        _discover_plugins()

    def _run_api_source(name: str) -> List[Dict[str, Any]]:
        """Query one API search source (Tavily/Exa/Firecrawl) directly.

        Runs as a parallel discovery stream alongside DDGS, exactly like the
        Wikimedia stream. Results are normalized into the search-candidate
        shape (title/url/href/body/snippet/source) so the ranker treats them
        the same as DDGS/Wikimedia candidates. Skip/error messages are
        collected for the CLI to print after discovery.
        """
        from ..sources.registry import get_plugin
        plugin = get_plugin(name)
        if plugin is None:
            console.print(f"[yellow]Unknown --source '{name}' — ignored[/yellow]")
            return []
        results = plugin.search(query, max_results=RSS_NO_LIMIT, search_type='web')
        normalized = []
        for r in results:
            url = r.get('url', '') or r.get('id', '')
            if not url:
                continue
            normalized.append({
                'title': r.get('title', ''),
                'url': url,
                'href': url,
                'body': r.get('snippet', '') or r.get('content', ''),
                'snippet': r.get('snippet', ''),
                'source': name,
                'content': r.get('content', ''),
            })
        return normalized

    # Execute discovery streams in parallel
    streams: List[Tuple[str, Any]] = [('ddgs', _run_ddgs_discovery)]
    if categories:
        streams.append(('category_rss', lambda cats=categories: _run_category_rss(cats)))
    if source and 'wikimedia' in source:
        streams.append(('wikimedia', _run_wikimedia_discovery))
    for name in api_source_names:
        streams.append((f'api_{name}', lambda n=name: _run_api_source(n)))
    
    stream_outputs: Dict[str, Any] = {}
    
    if len(streams) > 1:
        with ThreadPoolExecutor(max_workers=min(len(streams), 6)) as executor:
            fut_map = {executor.submit(fn): label for label, fn in streams}
            for fut in as_completed(fut_map):
                label = fut_map[fut]
                try:
                    stream_outputs[label] = fut.result()
                except Exception as exc:
                    console.print(f"[red]Stream '{label}' failed:[/red] {exc}")
                    stream_outputs[label] = [] if label != 'ddgs' else ([], {})
    else:
        result = streams[0][1]()
        stream_outputs[streams[0][0]] = result
    
    # Merge results
    if 'ddgs' in stream_outputs:
        ddgs_results, ddgs_stats = stream_outputs['ddgs']
        if ddgs_results:
            _dedup_append(ddgs_results)
        search_stats.update(ddgs_stats)
    
    if 'category_rss' in stream_outputs:
        rss_results = stream_outputs['category_rss']
        rss_added = _dedup_append(rss_results) if rss_results else 0
        search_stats['category_rss_providers'] = categories
        search_stats['category_rss_count'] = rss_added
        console.print(f"[green]Category RSS providers returned {rss_added} unique results[/green]")
    
    if 'wikimedia' in stream_outputs:
        wiki_results = stream_outputs['wikimedia']
        wiki_added = _dedup_append(wiki_results) if wiki_results else 0
        search_stats['wikimedia_count'] = wiki_added
        console.print(f"[green]Wikimedia returned {wiki_added} unique results[/green]")

    # Merge API search-source streams (tavily/exa/firecrawl).
    api_added_total = 0
    for label in [k for k in stream_outputs if k.startswith('api_')]:
        name = label[4:]
        api_results = stream_outputs[label]
        api_added = _dedup_append(api_results) if api_results else 0
        search_stats[f'{name}_count'] = api_added
        api_added_total += api_added
        console.print(f"[green]{name} returned {api_added} unique results[/green]")
    if api_added_total:
        search_stats['api_sources'] = api_source_names
    # Print any skip/error messages collected by API sources.
    from ..sources.api_search_base import source_messages as _src_msgs
    if _src_msgs.has_messages():
        for msg in _src_msgs.drain():
            if msg['type'] == 'skip':
                console.print(f"[yellow]⏭️  Source '{msg['source']}' skipped: {msg['reason']}[/yellow]")
            else:
                console.print(f"[yellow]⚠️  Source '{msg['source']}': {msg['reason']}[/yellow]")
    
    discovery_time = time.time() - discovery_start
    candidate_count = len(all_candidates)
    
    print(f"  • Total candidates: {candidate_count}")
    print(f"  • Collection time: {discovery_time:.2f}s")
    print(f"  • Ready for ranking (NO content extracted yet)")
    
    # ══════════════════════════════════════════════════════════════════
    # PHASE 1.5: RESOLVE WRAPPER URLs (MSN, Yahoo, AOL) - URL PARAMETERS ONLY
    # ══════════════════════════════════════════════════════════════════
    
    if not snippets_only:
        from ..source_resolvers import is_wrapper_domain, resolve_source_url
        
        wrapper_resolution_start = time.perf_counter()
        resolved_count = 0
        dropped_count = 0
        resolved_urls = set()
        
        wrapper_stats = {
            'msn': 0,
            'yahoo': 0,
            'aol': 0,
            'google_news': 0,
        }
        
        for candidate in all_candidates[:]:
            url = candidate.get('url') or candidate.get('href', '')
            if not url:
                continue
            
            if is_wrapper_domain(url):
                resolved = resolve_source_url(url, html=None)
                
                if resolved and resolved != url:
                    if resolved not in resolved_urls and resolved not in seen_urls:
                        candidate['original_wrapper_url'] = url
                        candidate['url'] = resolved
                        candidate['href'] = resolved
                        candidate['was_resolved'] = True
                        resolved_urls.add(resolved)
                        resolved_count += 1
                        logger.info(f"Resolved wrapper: {urlparse(url).netloc} → {urlparse(resolved).netloc}")
                    else:
                        all_candidates.remove(candidate)
                        dropped_count += 1
                        domain = urlparse(url).netloc.lower()
                        if 'msn.com' in domain:
                            wrapper_stats['msn'] += 1
                        elif 'yahoo.com' in domain:
                            wrapper_stats['yahoo'] += 1
                        elif 'aol.com' in domain:
                            wrapper_stats['aol'] += 1
                        elif 'google.com' in domain:
                            wrapper_stats['google_news'] += 1
                else:
                    logger.info(f"Dropping unresolved wrapper: {url[:80]}")
                    all_candidates.remove(candidate)
                    dropped_count += 1
                    domain = urlparse(url).netloc.lower()
                    if 'msn.com' in domain:
                        wrapper_stats['msn'] += 1
                    elif 'yahoo.com' in domain:
                        wrapper_stats['yahoo'] += 1
                    elif 'aol.com' in domain:
                        wrapper_stats['aol'] += 1
                    elif 'google.com' in domain:
                        wrapper_stats['google_news'] += 1
        
        wrapper_resolution_time_ms = (time.perf_counter() - wrapper_resolution_start) * 1000
        
        if resolved_count > 0 or dropped_count > 0:
            print(f"  • Wrapper resolution: {resolved_count} resolved, {dropped_count} dropped ({wrapper_resolution_time_ms:.0f}ms)")
            if dropped_count > 0:
                dropped_details = []
                if wrapper_stats['msn'] > 0:
                    dropped_details.append(f"MSN: {wrapper_stats['msn']}")
                if wrapper_stats['yahoo'] > 0:
                    dropped_details.append(f"Yahoo: {wrapper_stats['yahoo']}")
                if wrapper_stats['aol'] > 0:
                    dropped_details.append(f"AOL: {wrapper_stats['aol']}")
                if wrapper_stats['google_news'] > 0:
                    dropped_details.append(f"Google News: {wrapper_stats['google_news']}")
                if dropped_details:
                    console.print(f"    [dim]└─ {', '.join(dropped_details)}[/dim]")
    else:
        print(f"  • Wrapper resolution: skipped (snippets mode keeps all sources)")
    
    if candidate_count == 0:
        console.print(f"[red]✗ No candidates discovered[/red]")
        return [], {
            'search_engine': {**search_stats, 'total': 0, 'success': 0},
            'cleaner': {'total_input': 0, 'successful': 0, 'failed': 0, 'processed': 0}
        }
    
    candidate_count = len(all_candidates)
    
    # ══════════════════════════════════════════════════════════════
    # Phase 2: Ranking Candidates (Metadata Only)
    # ══════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 2: Ranking Candidates[/cyan]")
    ranking_start = time.time()
    
    print(f"  • Ranking {len(all_candidates)} candidates by relevance")
    print(f"  • Using: title, snippet, domain quality, authority")
    
    if snippets_only:
        print(f"  • Selecting top {EXTRACTION_COUNT} snippets (--snippets mode)")
    else:
        print(f"  • Selecting top {EXTRACTION_COUNT} for content extraction")
    
    try:
        from ..staged_ranker import rank_candidates_initial
        ranked = rank_candidates_initial(all_candidates, query, top_k=EXTRACTION_COUNT)
    except Exception as e:
        logger.warning(f"staged_ranker not available, using simple ranking: {e}")
        ranked = sorted(all_candidates, key=lambda x: x.get('position', 999))[:EXTRACTION_COUNT]
    
    ranking_time = (time.time() - ranking_start) * 1000
    
    print(f"  ✓ Ranked in {ranking_time:.0f}ms")
    
    if snippets_only:
        print(f"  ✓ Selected top {min(EXTRACTION_COUNT, len(ranked))} snippets")
    else:
        print(f"  ✓ Selected top {EXTRACTION_COUNT} for extraction")
    
    # ══════════════════════════════════════════════════════════════════
    # SNIPPETS MODE: Skip extraction and return ranked snippets
    # ══════════════════════════════════════════════════════════════════
    
    if snippets_only:
        total_execution_time = round(time.time() - start_time, 3)
        top_snippets = ranked[:EXTRACTION_COUNT]
        
        console.print(f"\n[green]✓ Snippet search complete![/green]")
        print(f"  • Total execution time: {total_execution_time:.2f}s")
        print(f"  • Discovery: {discovery_time:.2f}s")
        print(f"  • Ranking: {ranking_time/1000:.2f}s")
        print(f"  • Mode: snippets (extraction skipped)")
        print(f"  • Results: {len(top_snippets)}")
        
        snippets_output = []
        for idx, candidate in enumerate(top_snippets, start=1):
            snippet = {
                'rank': idx,
                'title': candidate.get('title', ''),
                'summary': candidate.get('body', '') or candidate.get('description', '') or candidate.get('snippet', ''),
                'url': candidate.get('url', '') or candidate.get('href', ''),
                'source': candidate.get('source', ''),
                'score': candidate.get('initial_rank_score', 0.0),
            }
            snippets_output.append(snippet)
        
        print(f"\n✅ WEB SEARCH COMPLETE!")
        print(f"   🔍 Query: {query}")
        print(f"   📊 Total candidates discovered: {search_stats.get('candidates_collected', candidate_count)}")
        print(f"   ✅ Snippets returned: {len(snippets_output)}")
        print(f"   🎯 Snippets requested: {EXTRACTION_COUNT}")
        print(f"   📋 Mode: snippets (no extraction)")
        
        combined_stats = {
            'search_engine': {
                **search_stats,
                **{'execution_time': total_execution_time},
                'candidates_collected': candidate_count,
                'collection_time': discovery_time,
                'ranking_time_ms': ranking_time,
            },
            'ranking': {
                'ranking_time_ms': round(ranking_time, 2),
                'candidates_total': candidate_count,
                'candidates_selected': len(top_snippets),
            },
            'cleaner': {
                'total_input': 0,
                'successful': 0,
                'failed': 0,
                'processed': 0,
            }
        }
        
        return snippets_output, combined_stats
    
    # ══════════════════════════════════════════════════════════════
    # Phase 3: Select Top N
    # ══════════════════════════════════════════════════════════════
    
    top_n = ranked[:EXTRACTION_COUNT]
    
    # ══════════════════════════════════════════════════════════════
    # Phase 4: Content Extraction (Only Top N)
    # ══════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 3: Content Extraction[/cyan]")
    print(f"  • Extracting full page content for {len(top_n)} URLs")
    print(f"  • Using: requests → Playwright fallback")
    extraction_start = time.time()
    
    engine = EnterpriseSearchEngine(
        max_workers=workers,
        max_fetch_retries=max_fetch_retries,
        enable_js_fallback=enable_js_fallback,
        enable_alternate_source=enable_alternate_source,
        enable_dns_fallback=enable_dns_fallback,
        enable_tls_impersonate=enable_tls_impersonate,
        enable_persistent_profile=enable_persistent_profile,
        browser_profile_name=browser_profile_name,
        enable_bandit=enable_bandit,
        source=source,
    )
    
    raw_results = engine.execute_search_from_urls(top_n)
    results_dicts = [asdict(r) for r in raw_results]
    
    extraction_time = time.time() - extraction_start
    
    # ══════════════════════════════════════════════════════════════════
    # EXTRACTION STATISTICS
    # ══════════════════════════════════════════════════════════════════
    requests_count = 0
    playwright_count = 0
    failed_count = 0
    
    console.print(f"\n[cyan]Extraction Breakdown:[/cyan]")
    for idx, result in enumerate(results_dicts, 1):
        url = result.get('url', '')
        domain = urlparse(url).netloc if url else 'unknown'
        method = result.get('extraction_method', 'unknown')
        word_count = result.get('content_word_count', 0)
        status = result.get('extraction_status', 'unknown')
        
        tier = 'unknown'
        if 'requests' in method.lower() or 'basic-fallback' in method.lower() or 'tls-impersonate' in method.lower():
            tier = 'requests'
            requests_count += 1
        elif 'playwright' in method.lower():
            tier = 'playwright'
            playwright_count += 1
        
        tier_display = f"[green]{tier:10s}[/green]" if tier == 'requests' else f"[yellow]{tier:10s}[/yellow]"
        status_icon = "✓" if status == 'success' and word_count >= 200 else "✗"
        
        console.print(f"  {status_icon} URL {idx:2d} ({domain[:25]:25s}) {tier_display} {word_count:4d} words")
        
        if status != 'success' or word_count < 100:
            failed_count += 1
    
    console.print(f"\n[cyan]Extraction Stats:[/cyan]")
    print(f"  • Requests tier: {requests_count}/{len(results_dicts)}")
    print(f"  • Playwright tier: {playwright_count}/{len(results_dicts)}")
    print(f"  • Failed/Low quality: {failed_count}/{len(results_dicts)}")
    print(f"  • Total time: {extraction_time:.2f}s")
    if results_dicts:
        print(f"  • Average per URL: {extraction_time/len(results_dicts):.2f}s")
    
    if playwright_count > 0:
        console.print(f"  [yellow]⚠️  {playwright_count} URLs used Playwright (3-8s browser launch overhead each)[/yellow]")
    
    print(f"  ✓ Extracted in {extraction_time:.2f}s")
    
    # ══════════════════════════════════════════════════════════════
    # Phase 5: Cleaning & Structuring
    # ══════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 4: Cleaning & Structuring[/cyan]")
    structured_results, cleaner_stats = process_results(results_dicts)
    
    total_time = time.time() - start_time
    
    console.print(f"\n[green]✓ Web search complete![/green]")
    print(f"  • Total execution time: {total_time:.2f}s")
    print(f"  • Discovery: {discovery_time:.2f}s")
    print(f"  • Ranking: {ranking_time/1000:.2f}s")
    print(f"  • Extraction: {extraction_time:.2f}s")
    print(f"  • Final results: {len(structured_results)}")
    
    print(f"\n✅ WEB SEARCH COMPLETE!")
    print(f"   🔍 Query: {query}")
    print(f"   📊 Total candidates discovered: {search_stats.get('candidates_collected', candidate_count)}")
    print(f"   ✅ Successfully extracted: {len(structured_results)}")
    print(f"   ❌ Failed (ignored): {failed_count}")
    
    combined_stats = {
        'search_engine': {
            **search_stats,
            **engine.stats,
            'candidates_collected': candidate_count,
            'collection_time': discovery_time,
            'ranking_time_ms': ranking_time,
            'extraction_time': extraction_time,
            'total_time': total_time,
        },
        'cleaner': cleaner_stats
    }
    
    return structured_results, combined_stats
