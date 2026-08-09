"""Wikipedia search command module."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

from ..extraction import ExtractionEngine, fetch_resilient


def _wiki_do_bundle(
    ex: Any, query: str, clean_text: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Bundle mode: search all 12 Wikimedia projects for a topic."""
    from ..wikimedia_source import SITE_MAP, SITE_HOME, clean_noise_text

    rr = ex.bundle_topic(query)
    if not rr.ok:
        return [], {"errors": [rr.error or "bundle failed"]}

    bundle_data = rr.data.get("data", rr.data)
    raw_results: List[Dict[str, Any]] = []
    for proj_key in SITE_MAP:
        proj_results = bundle_data.get(f"{proj_key}_search", [])
        if not proj_results:
            continue
        base_url = SITE_HOME.get(proj_key, "")
        items = proj_results if isinstance(proj_results, list) else [proj_results]
        for item in items:
            title = item.get("title") if isinstance(item, dict) else ""
            if not title:
                continue
            snippet = item.get("snippet") or item.get("extract") or ""
            raw_results.append({
                "title": title,
                "href": f"{base_url}wiki/{quote(title.replace(' ', '_'))}",
                "body": clean_noise_text(snippet) if clean_text else snippet,
                "source": f"wikimedia:{proj_key}",
                "pageid": item.get("pageid") if isinstance(item, dict) else None,
            })
    if clean_text:
        for r in raw_results:
            r["body"] = clean_noise_text(r["body"])
    return raw_results, {"bundle": True, "total_results": len(raw_results)}


def _wiki_do_summary(
    ex: Any, query: str, language: str, clean_text: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Summary mode: fetch REST API summary for a page."""
    from ..wikimedia_source import clean_noise_text

    rr = ex.wikipedia_summary(query)
    if not rr.ok or not rr.data:
        return [], {"errors": [rr.error or "summary fetch failed"]}

    d = rr.data
    result = {
        "title": d.get("title", query),
        "href": f"https://{language}.wikipedia.org/wiki/{quote(query.replace(' ', '_'))}",
        "body": clean_noise_text(d.get("extract", "")) if clean_text else d.get("extract", ""),
        "source": "wikimedia:wikipedia",
        "description": d.get("description"),
        "thumbnail": d.get("thumbnail"),
    }
    return [result], {"mode": "summary"}


def _wiki_do_extract(
    ex: Any, project: str, query: str, clean_text: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Extract mode: fetch full-page Action API extract."""
    from ..wikimedia_source import SITE_HOME, clean_noise_text

    rr = ex.action_query_extract(project, query)
    if not rr.ok or not rr.data:
        return [], {"errors": [rr.error or "extract fetch failed"]}

    d = rr.data
    base_url = SITE_HOME.get(project, "https://en.wikipedia.org/")
    result = {
        "title": d.get("title", query),
        "href": d.get("fullurl") or f"{base_url}wiki/{quote(query.replace(' ', '_'))}",
        "body": clean_noise_text(d.get("extract", "")) if clean_text else d.get("extract", ""),
        "source": f"wikimedia:{project}",
        "pageid": d.get("pageid"),
        "links": d.get("links"),
        "categories": d.get("categories"),
    }
    return [result], {"mode": "extract"}


def _wiki_do_sections(
    ex: Any, project: str, query: str, clean_text: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Sections mode: export section-by-section text."""
    from ..wikimedia_source import SITE_HOME, clean_noise_text

    rr = ex.export_sections(project, query)
    if not rr.ok or not rr.data:
        return [], {"errors": [rr.error or "sections fetch failed"]}

    raw_results = []
    for sec in rr.data:
        raw_results.append({
            "section_index": sec.get("section_index"),
            "section_title": sec.get("section_title"),
            "title": sec.get("title", query),
            "href": f"{SITE_HOME.get(project, '')}wiki/{quote(query.replace(' ', '_'))}#{quote(sec.get('section_anchor', ''))}",
            "body": clean_noise_text(sec.get("text", "")) if clean_text else sec.get("text", ""),
            "source": f"wikimedia:{project}:sections",
        })
    return raw_results, {"mode": "sections"}


def _wiki_do_crawl(
    ex: Any, project: str, query: str,
    max_results: int, crawl_depth: int, clean_text: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Crawl mode: recursive spider from search seed."""
    from ..wikimedia_source import SITE_HOME, clean_noise_text

    rr = ex.spider_from_search(
        project, query,
        seed_limit=max_results,
        depth=crawl_depth,
        per_page_links=15,
        max_pages=max_results * 5,
    )
    if not rr.ok:
        return [], {"errors": [rr.error or "crawl failed"]}

    raw_results = []
    base_url = SITE_HOME.get(project, "https://en.wikipedia.org/")
    for item in rr.data.get("results", []):
        title = item.get("title", "")
        raw_results.append({
            "title": title,
            "href": item.get("fullurl") or f"{base_url}wiki/{quote(title.replace(' ', '_'))}",
            "body": clean_noise_text(item.get("extract", "")) if clean_text else item.get("extract", ""),
            "source": f"wikimedia:{project}:crawl",
            "pageid": item.get("pageid"),
        })
    return raw_results, {"mode": "crawl", "crawl_edges": len(rr.data.get("edges", [])), "visited_count": rr.data.get("visited_count", 0)}


def _wiki_do_search(
    ex: Any, project: str, query: str, max_results: int, clean_text: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Default mode: search pages via Action API."""
    from ..wikimedia_source import SITE_HOME, clean_noise_text

    rr = ex.search_pages(project, query, limit=max_results)
    if not rr.ok or not rr.data:
        return [], {"errors": [rr.error or "search failed"]}

    base_url = SITE_HOME.get(project, "https://en.wikipedia.org/")
    raw_results = []
    for item in rr.data:
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        raw_results.append({
            "title": title,
            "href": f"{base_url}wiki/{quote(title.replace(' ', '_'))}",
            "body": clean_noise_text(snippet) if clean_text else snippet,
            "source": f"wikimedia:{project}",
            "pageid": item.get("pageid"),
        })
    if clean_text:
        for r in raw_results:
            r["body"] = clean_noise_text(r["body"])
    return raw_results, {"mode": "search"}


def _wiki_enrich_results(
    raw_results: List[Dict[str, Any]],
    timeout: int, workers: int, clean_text: bool, max_results: int,
) -> Dict[str, Any]:
    """Parallel page content extraction via fetch_resilient (same pipeline as fetch-url)."""
    if not raw_results:
        return {}
    from ..wikimedia_source import clean_noise_text

    _wiki_engine = ExtractionEngine()

    def _fetch(item: dict) -> None:
        url = item.get("href", "")
        if not url:
            item["extraction_status"] = "failed"
            item["main_content"] = item.get("body", "")
            return
        try:
            outcome = fetch_resilient(url, session=_wiki_engine.session, timeout=timeout, max_retries=1)
            if outcome["status"] != "success":
                item["extraction_status"] = "failed"
                item["main_content"] = item.get("body", "")
                return
            content, method, confidence = _wiki_engine.extract_content(url, outcome["html"])
            if clean_text:
                content = clean_noise_text(content)
            item["main_content"] = content
            item["extraction_method"] = f"{method} ({outcome.get('tier', '?')})"
            item["confidence_score"] = confidence
            item["extraction_status"] = "success" if content.strip() else "failed"
        except Exception:
            item["extraction_status"] = "failed"
            item["main_content"] = item.get("body", "")

    with ThreadPoolExecutor(max_workers=min(workers, max_results or 1)) as executor:
        list(executor.map(_fetch, raw_results))

    successes = sum(1 for r in raw_results if r.get("extraction_status") == "success")
    return {"extraction": {"total": len(raw_results), "successful": successes, "failed": len(raw_results) - successes}}


def wikipedia_search(
    query: str,
    max_results: int = 10,
    project: str = "wikipedia",
    language: str = "en",
    timeout: int = 25,
    workers: int = 5,
    summary: bool = False,
    extract: bool = False,
    sections: bool = False,
    crawl: bool = False,
    crawl_depth: int = 2,
    bundle: bool = False,
    robots: bool = False,
    clean_text: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Search Wikimedia projects via the MediaWiki Action API.

    This is the backend for the ``wikipedia-search`` CLI command.

    Args:
        query: Search query or page title
        max_results: Maximum results (1-50)
        project: Wikimedia project key (any SITE_MAP key)
        language: Project language for language-scoped wikis
        timeout: HTTP timeout
        workers: Parallel workers
        summary: Fetch Wikipedia REST summary instead of search
        extract: Fetch full-page Action API extract
        sections: Export section-by-section text
        crawl: Enable recursive crawl
        crawl_depth: Crawl depth
        bundle: Run multi-project topic bundle (searches all 12 projects)
        robots: Check robots.txt
        clean_text: Apply text cleaning

    Returns:
        (results_list, stats_dict) — same pattern as web_search / news_search.
    """
    from ..wikimedia_source import WikimediaExtractor

    ex = WikimediaExtractor(language=language, timeout=timeout, max_workers=workers)
    stats: Dict[str, Any] = {"source": f"wikimedia:{project}", "project": project, "language": language}

    # robots.txt check
    if robots:
        rr = ex.check_robots(project)
        if rr.ok:
            stats["robots"] = rr.data
        else:
            stats["robots_error"] = rr.error

    # Dispatch to mode handler
    if bundle:
        results, mode_stats = _wiki_do_bundle(ex, query, clean_text)
        stats.update(mode_stats)
        return results, stats

    if summary:
        results, mode_stats = _wiki_do_summary(ex, query, language, clean_text)
    elif extract:
        results, mode_stats = _wiki_do_extract(ex, project, query, clean_text)
    elif sections:
        results, mode_stats = _wiki_do_sections(ex, project, query, clean_text)
    elif crawl:
        results, mode_stats = _wiki_do_crawl(ex, project, query, max_results, crawl_depth, clean_text)
    else:
        results, mode_stats = _wiki_do_search(ex, project, query, max_results, clean_text)

    errors = mode_stats.get("errors", [])
    stats.update(mode_stats)
    stats["results_count"] = len(results)

    # Parallel content enrichment for search results
    enrich_stats = _wiki_enrich_results(results, timeout, workers, clean_text, max_results)
    if enrich_stats:
        stats.update(enrich_stats)

    return results, {**stats, "errors": errors or None}
