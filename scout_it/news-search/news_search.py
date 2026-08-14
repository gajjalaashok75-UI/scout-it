"""
News Search Module - Extracted from cli.py

This module contains the news_search function and its related logic,
extracted from cli.py for better code organization and maintainability.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from rich.console import Console

# Import from parent package
from ..extraction import _ddgs_list_search_with_retry
from ..cleaner import process_results
from ..google_news_source import google_news_search
from ..category_providers import fetch_category_news, get_available_categories
from ..staged_ranker import rank_candidates_initial

# Initialize logger
logger = logging.getLogger(__name__)

# Shared Rich console so [cyan]/[green]/[yellow] markup in print() calls
# below renders as actual colors instead of literal bracket text.
console = Console()


def news_search(
    query: str,
    max_results: int = 10,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    workers: int = 5,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
    enable_alternate_source: bool = False,
    enable_dns_fallback: bool = False,
    enable_tls_impersonate: bool = False,
    enable_persistent_profile: bool = False,
    browser_profile_name: Optional[str] = None,
    enable_bandit: bool = True,
    source: Optional[str] = None,
    locations: Optional[List[str]] = None,
    max_chars: Optional[int] = None,
    max_size: Optional[str] = None,
    categories: Optional[List[str]] = None,
    research_mode: bool = False,
    snippets_only: bool = False,
):
    """News search with optimized discovery-first pipeline.
    
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
    - DDGS News (always) → 20 snippets
    - Google News RSS (if --sources google-news) → ALL entries
    - ToI RSS (if --location) → ALL entries per location
    - Category RSS (if --category) → ALL entries from feeds
    
    Args:
        query: Search query
        max_results: Final number of results to extract and return (default: 10)
        
    Returns:
        Structured results with full extracted content
    """
    start_time = time.time()
    
    # Discovery limits
    DDGS_SNIPPET_LIMIT = 20  # Get top 20 snippets from DDGS (lightweight)
    RSS_NO_LIMIT = 500       # RSS feeds: get ALL entries (or large limit)
    
    # Extraction limit
    EXTRACTION_COUNT = max_results  # Extract content for this many results after ranking
    
    all_raw_results: List[Dict[str, Any]] = []
    search_stats: Dict[str, Any] = {}
    seen_urls: set = set()

    use_gn_source = source == 'google-news'

    # Augment query with location names for geographic relevance
    ddgs_query = query
    if locations:
        location_str = " ".join(locations)
        ddgs_query = f"{query} {location_str}"
        console.print(f"[blue]Augmenting query with location:[/blue] '{query}' → '{ddgs_query}'")

    def _dedup_append(results: List[Dict[str, Any]]) -> int:
        """Append results with URL-level dedup. Returns count added."""
        count = 0
        for r in results:
            url = r.get('url', '') or r.get('href', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_raw_results.append(r)
                count += 1
        return count

    # ── Stream 1: DDGS → Playwright HTML → Google News RSS (always runs) ──
    def _run_ddgs_chain():
        """DDGS news search - get 20 snippets only (NO content extraction).

        Returns lightweight metadata: title, description, url, date
        """
        results, stats = _ddgs_list_search_with_retry(
            'news', query=ddgs_query, max_results=DDGS_SNIPPET_LIMIT,
            options={'region': region, 'safesearch': safesearch, 'timelimit': timelimit},
            retry_on_zero_success=retry_on_zero_success,
            max_zero_success_retries=retry_attempts,
            retry_backoff_seconds=retry_backoff,
        )

        if not results and not use_gn_source:
            # Tier 3: Google News RSS (only when not a parallel source)
            console.print(f"[yellow]DDGS chain returned 0 results, falling back to Google News RSS[/yellow]")
            gn = google_news_search(ddgs_query, max_results=RSS_NO_LIMIT)
            for r in gn:
                item_url = r.get('url', '') or r.get('href', '')
                results.append({
                    'title': r.get('title', ''),
                    'url': item_url,
                    'href': item_url,
                    'body': r.get('body', ''),
                    'source': r.get('source', 'google-news'),
                    'publish_date': r.get('date', ''),
                })

        return results, stats

    # ── Stream 2: Google News (parallel, when --sources google-news) ──
    def _run_google_news():
        """Get ALL Google News RSS entries (NO limit)."""
        gn = google_news_search(ddgs_query, max_results=RSS_NO_LIMIT)
        results = []
        for r in gn:
            item_url = r.get('url', '') or r.get('href', '')
            results.append({
                'title': r.get('title', ''),
                'url': item_url,
                'href': item_url,
                'body': r.get('body', ''),
                'source': r.get('source', 'google-news'),
                'publish_date': r.get('date', ''),
            })
        return results

    # ── Stream 3: ToI RSS (parallel, when --location) ──
    def _run_toi(locs: List[str]):
        """Get ALL ToI RSS entries for locations (NO limit per location)."""
        from ..toi_rss_source import fetch_toi_news
        results = fetch_toi_news(locs, max_per_location=RSS_NO_LIMIT)
        for r in results:
            if 'date' in r and 'publish_date' not in r:
                r['publish_date'] = r['date']
        return results

    # ── Stream 4: Category RSS providers (parallel, when --category) ──
    def _run_category_providers(cats: List[str]):
        """Get ALL TechCrunch RSS entries for categories (NO limit)."""
        return fetch_category_news(cats, query, max_results=RSS_NO_LIMIT)

    # ── Determine which streams to run ──
    streams: List[Tuple[str, Any]] = [('ddgs_chain', _run_ddgs_chain)]
    if use_gn_source:
        streams.append(('google_news', _run_google_news))
    if locations:
        streams.append(('toi_rss', lambda locs=locations: _run_toi(locs)))
    if categories:
        streams.append(('category_rss', lambda cats=categories: _run_category_providers(cats)))
        console.print(f"[blue]Category RSS providers enabled:[/blue] {', '.join(categories)}")
        console.print(f"[dim]Available categories: {', '.join(get_available_categories())}[/dim]")

    # ── Execute all streams in parallel ──
    stream_outputs: Dict[str, Any] = {}

    if len(streams) > 1:
        with ThreadPoolExecutor(max_workers=min(len(streams), 4)) as executor:
            fut_map = {executor.submit(fn): label for label, fn in streams}
            for fut in as_completed(fut_map):
                label = fut_map[fut]
                try:
                    stream_outputs[label] = fut.result()
                except Exception as exc:
                    console.print(f"[red]Stream '{label}' failed:[/red] {type(exc).__name__}: {exc}")
                    stream_outputs[label] = [] if label != 'ddgs_chain' else ([], {})
    else:
        result = streams[0][1]()
        stream_outputs[streams[0][0]] = result

    # ── Merge results ──
    if 'ddgs_chain' in stream_outputs:
        ddgs_results, ddgs_stats = stream_outputs['ddgs_chain']
        if ddgs_results:
            _dedup_append(ddgs_results)
        search_stats.update(ddgs_stats)

    if 'google_news' in stream_outputs:
        gn_results = stream_outputs['google_news']
        gn_added = _dedup_append(gn_results) if gn_results else 0
        search_stats['google_news_source'] = True
        search_stats['google_news_count'] = gn_added

    if 'toi_rss' in stream_outputs:
        toi_results = stream_outputs['toi_rss']
        toi_added = _dedup_append(toi_results) if toi_results else 0
        search_stats['toi_locations'] = locations
        search_stats['toi_count'] = toi_added

    if 'category_rss' in stream_outputs:
        category_results = stream_outputs['category_rss']
        category_added = _dedup_append(category_results) if category_results else 0
        search_stats['category_providers'] = categories
        search_stats['category_rss_count'] = category_added
        console.print(f"[green]Category RSS providers returned {category_added} unique results[/green]")

    search_stats['total'] = len(all_raw_results)
    search_stats['count'] = len(all_raw_results)
    search_stats['candidates_collected'] = len(all_raw_results)
    collection_time = round(time.time() - start_time, 3)
    search_stats['collection_time'] = collection_time

    if not all_raw_results:
        return [], {
            'search_engine': search_stats,
            'cleaner': {'total_input': 0, 'successful': 0, 'failed': 0, 'processed': 0},
            'ranking': {
                'ranking_time_ms': 0,
                'extraction_time_ms': 0,
            }
        }

    console.print(f"\n[cyan]Phase 1: Lightweight Discovery[/cyan]")
    print(f"  • Total candidates: {len(all_raw_results)}")
    print(f"  • Collection time: {collection_time:.2f}s")
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
        
        for candidate in all_raw_results[:]:
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
                        all_raw_results.remove(candidate)
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
                    all_raw_results.remove(candidate)
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
    
    # ══════════════════════════════════════════════════════════════════
    # PHASE 2: RANK CANDIDATES (Metadata-Only, Fast)
    # ══════════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 2: Ranking Candidates[/cyan]")
    print(f"  • Ranking {len(all_raw_results)} candidates by relevance")
    print(f"  • Using: title, summary, source quality, recency")
    
    if snippets_only:
        print(f"  • Selecting top {EXTRACTION_COUNT} snippets (--snippets mode)")
    else:
        print(f"  • Selecting top {EXTRACTION_COUNT} for content extraction")
    
    ranking_start = time.perf_counter()
    ranked_candidates = rank_candidates_initial(
        all_raw_results, 
        query, 
        top_k=EXTRACTION_COUNT
    )
    ranking_time_ms = (time.perf_counter() - ranking_start) * 1000
    
    print(f"  ✓ Ranked in {ranking_time_ms:.0f}ms")
    
    if snippets_only:
        print(f"  ✓ Selected top {len(ranked_candidates)} snippets")
    else:
        print(f"  ✓ Selected top {len(ranked_candidates)} for extraction")
    
    # ══════════════════════════════════════════════════════════════════
    # SNIPPETS MODE: Skip extraction and return ranked snippets
    # ══════════════════════════════════════════════════════════════════
    
    if snippets_only:
        total_execution_time = round(time.time() - start_time, 3)
        
        console.print(f"\n[green]✓ Snippet search complete![/green]")
        print(f"  • Total execution time: {total_execution_time:.2f}s")
        print(f"  • Discovery: {collection_time:.2f}s")
        print(f"  • Ranking: {ranking_time_ms/1000:.2f}s")
        print(f"  • Mode: snippets (extraction skipped)")
        print(f"  • Results: {len(ranked_candidates)}")
        
        snippets_output = []
        for idx, candidate in enumerate(ranked_candidates, start=1):
            snippet = {
                'rank': idx,
                'title': candidate.get('title', ''),
                'summary': candidate.get('body', '') or candidate.get('description', ''),
                'url': candidate.get('url', '') or candidate.get('href', ''),
                'source': candidate.get('source', ''),
                'publish_date': candidate.get('publish_date', '') or candidate.get('date', ''),
                'score': candidate.get('initial_rank_score', 0.0),
            }
            snippets_output.append(snippet)
        
        combined_stats = {
            'search_engine': {
                **search_stats,
                'execution_time': total_execution_time,
            },
            'ranking': {
                'ranking_time_ms': round(ranking_time_ms, 2),
                'candidates_total': len(all_raw_results),
                'candidates_selected': len(ranked_candidates),
            },
            'cleaner': {
                'total_input': 0,
                'successful': 0,
                'failed': 0,
                'processed': 0,
            }
        }
        
        return snippets_output, combined_stats
    
    # ══════════════════════════════════════════════════════════════════
    # PHASE 3: CONTENT EXTRACTION (Only Top Ranked)
    # ══════════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 3: Content Extraction[/cyan]")
    print(f"  • Extracting full page content for {len(ranked_candidates)} URLs")
    print(f"  • Using: requests → Playwright fallback")
    
    extraction_start = time.perf_counter()
    
    # ═══════════════════════════════════════════════════════════════════
    # USE ENTERPRISE SEARCH ENGINE (same as web-search)
    # ═══════════════════════════════════════════════════════════════════
    from ..extraction import EnterpriseSearchEngine
    from dataclasses import asdict
    
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
    
    raw_results = engine.execute_search_from_urls(ranked_candidates)
    enriched_results = [asdict(r) for r in raw_results]
    
    extraction_time_ms = (time.perf_counter() - extraction_start) * 1000
    
    # ══════════════════════════════════════════════════════════════════
    # EXTRACTION STATISTICS
    # ══════════════════════════════════════════════════════════════════
    requests_count = 0
    playwright_count = 0
    failed_count = 0
    
    console.print(f"\n[cyan]Extraction Breakdown:[/cyan]")
    for idx, result in enumerate(enriched_results, 1):
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
    print(f"  • Requests tier: {requests_count}/{len(enriched_results)}")
    print(f"  • Playwright tier: {playwright_count}/{len(enriched_results)}")
    print(f"  • Failed/Low quality: {failed_count}/{len(enriched_results)}")
    print(f"  • Total time: {extraction_time_ms/1000:.2f}s")
    if enriched_results:
        print(f"  • Average per URL: {extraction_time_ms/len(enriched_results)/1000:.2f}s")
    
    if playwright_count > 0:
        console.print(f"  [yellow]⚠️  {playwright_count} URLs used Playwright (3-8s browser launch overhead each)[/yellow]")
    
    print(f"  ✓ Extracted in {extraction_time_ms/1000:.2f}s")
    
    # ══════════════════════════════════════════════════════════════════
    # PHASE 4: CLEAN & STRUCTURE
    # ══════════════════════════════════════════════════════════════════
    
    console.print(f"\n[cyan]Phase 4: Cleaning & Structuring[/cyan]")
    structured_results, cleaner_stats = process_results(enriched_results)

    # Phase 5: Apply max_chars / max_size truncation on each result
    if max_chars is not None and max_chars > 0:
        for r in structured_results:
            content = r.get("cleaned_content", "") or r.get("main_content", "")
            if isinstance(content, list):
                content = " ".join(content)
            if len(content) > max_chars:
                truncated = content[:max_chars]
                r["cleaned_content"] = truncated
                r["main_content"] = truncated

    if max_size is not None:
        from ..output import parse_size_string as _parse_size
        size_bytes = _parse_size(max_size)
        if size_bytes:
            for r in structured_results:
                for key in ("raw_html", "html"):
                    val = r.get(key)
                    if isinstance(val, str) and len(val.encode("utf-8")) > size_bytes:
                        r[key] = val[:size_bytes]

    # Combine stats
    total_execution_time = round(time.time() - start_time, 3)
    search_stats['execution_time'] = total_execution_time
    
    combined_stats = {
        'search_engine': search_stats,
        'ranking': {
            'ranking_time_ms': round(ranking_time_ms, 2),
            'extraction_time_ms': round(extraction_time_ms, 2),
            'candidates_total': len(all_raw_results),
            'candidates_selected': len(ranked_candidates),
            'results_extracted': len(enriched_results),
        },
        'cleaner': cleaner_stats,
    }
    
    console.print(f"\n[green]✓ News search complete![/green]")
    print(f"  • Total execution time: {total_execution_time:.2f}s")
    print(f"  • Discovery: {collection_time:.2f}s")
    print(f"  • Ranking: {ranking_time_ms/1000:.2f}s")
    print(f"  • Extraction: {extraction_time_ms/1000:.2f}s")
    print(f"  • Final results: {len(structured_results)}")
    
    return structured_results, combined_stats
