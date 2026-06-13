#!/usr/bin/env python3
"""
Complete search pipeline wrapper.
Runs extraction.py → cleaner.py
Outputs: structured JSON with filtered results

Usage (CLI):
  gakr-ddgs web-search --query "today hot news" --max 50 --workers 6 --out results.json
  gakr-ddgs image-search --query "sunset" --max 20 --out images.json

This imports `EnterpriseSearchEngine`, `ImageSearchEngine` from `extraction.py` 
and `process_results` from `cleaner.py`
"""
import argparse
import sys

# Ensure Unicode output works on Windows terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass  # Fallback: ignore if not supported
import json
import random
import re
import time
from dataclasses import asdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:
    from .cleaner import process_results
    from .extraction import (
        DDGS,
        EnterpriseSearchEngine,
        ExtractionEngine,
        ImageSearchEngine,
        _compact_options,
    )
except Exception as e:
    raise ImportError("Could not import from gakr_ddgs modules: " + str(e))


def _ddgs_list_search(
    method_name: str,
    query: str,
    max_results: int,
    options: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run DDGS method with compatibility fallbacks across package versions."""
    start_time = time.time()
    params = _compact_options(options or {})
    params['max_results'] = max_results

    try:
        with DDGS(timeout=timeout) as ddgs:
            method = getattr(ddgs, method_name, None)
            if not callable(method):
                return [], {
                    'total': 0,
                    'success': 0,
                    'execution_time': time.time() - start_time,
                    'error': f"DDGS method '{method_name}' is unavailable in this installed version",
                }

            call_patterns = [
                lambda: list(method(keywords=query, **params)),
                lambda: list(method(query, **params)),
                lambda: list(method(query, max_results=max_results)),
                lambda: list(method(keywords=query, max_results=max_results)),
                lambda: list(method(query, max_results)),
                lambda: list(method(query))[:max_results],
            ]

            for call in call_patterns:
                try:
                    results = call()
                    return results, {
                        'total': len(results),
                        'success': len(results),
                        'execution_time': time.time() - start_time,
                    }
                except TypeError:
                    continue

            return [], {
                'total': 0,
                'success': 0,
                'execution_time': time.time() - start_time,
                'error': f"No compatible DDGS call signature worked for '{method_name}'",
            }
    except Exception as exc:
        return [], {
            'total': 0,
            'success': 0,
            'execution_time': time.time() - start_time,
            'error': 'DuckDuckGo request failed',
        }


def web_search(
    query: str,
    max_results: int = 100,
    workers: int = 8,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: Optional[str] = None,
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    backend: str = 'auto',
):
    """
    Execute web search pipeline: search → extract → clean → filter.
    
    Args:
        query: Search query string
        max_results: Max results to fetch
        workers: Parallel workers
    
    Returns:
        (structured_results, stats) tuple with cleaned and structured content
    """
    # Phase 1: Search and extract
    engine = EnterpriseSearchEngine(max_workers=workers)
    search_options = _compact_options({
        'region': region,
        'safesearch': safesearch,
        'timelimit': timelimit,
        'backend': backend,
    })

    raw_results = engine.execute_search(
        query,
        max_results,
        search_options=search_options,
        retry_on_zero_success=retry_on_zero_success,
        max_zero_success_retries=retry_attempts,
        retry_backoff_seconds=retry_backoff,
    )
    
    # Convert dataclass results to plain dicts
    results_dicts = [asdict(r) for r in raw_results]
    
    # Phase 2: Clean and filter by extraction_status == "success"
    structured_results, cleaner_stats = process_results(results_dicts)
    
    # Combine stats
    combined_stats = {
        'search_engine': engine.stats,
        'cleaner': cleaner_stats
    }
    return structured_results, combined_stats


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
): 
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


def news_search(
    query: str,
    max_results: int = 50,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
):
    """DuckDuckGo news search wrapper with retry support."""
    results, stats = _ddgs_list_search(
        'news',
        query=query,
        max_results=max_results,
        options={
            'region': region,
            'safesearch': safesearch,
            'timelimit': timelimit,
        },
    )
    return results, {'search_engine': stats}


def video_search(
    query: str,
    max_results: int = 50,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    resolution: Optional[str] = None,
    duration: Optional[str] = None,
    license_videos: Optional[str] = None,
):
    """DuckDuckGo video search wrapper."""
    results, stats = _ddgs_list_search(
        'videos',
        query=query,
        max_results=max_results,
        options={
            'region': region,
            'safesearch': safesearch,
            'timelimit': timelimit,
            'resolution': resolution,
            'duration': duration,
            'license_videos': license_videos,
        },
    )
    return results, {'search_engine': stats}


def _extract_html_title(html_text: str) -> str:
    """Extract page title from HTML text."""
    if not html_text:
        return ""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    return unescape(re.sub(r"\s+", " ", title)).strip()


def _parse_size_string(size_str: Optional[str]) -> Optional[int]:
    """Parse size string like '100kb', '1mb' to bytes. Returns None if invalid."""
    if not size_str:
        return None
    
    size_str = size_str.strip().lower()
    
    # Mapping of units to bytes
    units = {
        'b': 1,
        'kb': 1024,
        'mb': 1024 ** 2,
        'gb': 1024 ** 3,
    }
    
    # Try to parse the string
    match = re.match(r'^([0-9.]+)\s*([a-z]+)$', size_str)
    if not match:
        return None
    
    try:
        value = float(match.group(1))
        unit = match.group(2)
        
        if unit not in units:
            return None
        
        return int(value * units[unit])
    except (ValueError, TypeError):
        return None


def _check_max_size_warning(max_size: Optional[str], main_content: Any) -> Optional[str]:
    """Check if max_size truncation produced suspiciously short content."""
    if max_size and main_content:
        words = len(str(main_content).split())
        if words < 50:
            return f"Content very short ({words} words) after --max-size {max_size} truncation. Consider a larger limit."
    return None


def fetch_url(
    url: str,
    timeout: int = 25,
    max_chars: Optional[int] = None,
    max_size: Optional[str] = None,
    raw_html: bool = False,
):
    """
    Fetch a single URL and extract/clean its content.
    
    Enhanced version of fatchurl with better naming.

    Returns a dict containing a single structured result.
    """
    # Validation: Only one of max_chars or max_size is allowed
    if max_chars is not None and max_size is not None:
        return {
            "error": "Cannot use both --max-chars and --max-size together. Use only ONE parameter:\n"
                    "   • --max-chars 10000 (to limit extracted content by character count)\n"
                    "   • --max-size 5mb (to limit response size by file size)\n"
                    "   Use either one, not both."
        }
    
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"error": "Invalid URL. Provide a working http/https URL."}

    start_time = time.time()
    try:
        headers = {
            "User-Agent": random.choice(ExtractionEngine.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        response.raise_for_status()
        final_url = str(response.url)

        # Truncate HTML response if max_size is specified
        response_text = response.text
        max_size_bytes = _parse_size_string(max_size)
        if max_size_bytes and len(response.content) > max_size_bytes:
            # Truncate HTML content to max_size bytes
            response_text = response.content[:max_size_bytes].decode('utf-8', errors='ignore')

        extractor = ExtractionEngine()
        main_content, method, confidence = extractor.extract_content(
            final_url,
            response_text,
            timeout=timeout,
        )
        
        # Apply max_chars constraint if specified
        if max_chars and main_content and len(main_content) > max_chars:
            main_content = main_content[:max_chars]
        
        elapsed = time.time() - start_time
        title = _extract_html_title(response_text) or final_url

        raw_record = {
            "position": 1,
            "title": title,
            "url": str(url),
            "final_url": final_url,
            "publish_date": None,
            "author": None,
            "fetch_time": elapsed,
            "extraction_status": "success" if str(main_content).strip() else "failed",
            "confidence_score": float(confidence or 0.0),
            "content_word_count": len(str(main_content or "").split()),
            "content_type": "unknown",
            "main_content": main_content or "",
            "snippet": "",
            "extraction_method": method or "unknown",
        }

        if raw_html:
            # Skip the cleaner pipeline — return raw extracted content
            structured = {
                "position": 1,
                "title": title,
                "url": str(url),
                "final_url": final_url,
                "extraction_status": "success" if str(main_content).strip() else "failed",
                "confidence_score": float(confidence or 0.0),
                "content_word_count": len(str(main_content or "").split()),
                "extraction_method": method or "unknown",
                "raw_content": str(main_content or "").strip(),
            }
            cleaner_stats = {"mode": "raw-html", "cleaning_skipped": True}
        else:
            structured_results, cleaner_stats = process_results([raw_record])
            if structured_results:
                structured = structured_results[0]
            else:
                structured = raw_record
                structured["cleaned_content"] = str(main_content or "").strip()
                structured["content_sections"] = {}
                structured["top_keywords"] = []
                structured["paragraphs"] = []
                structured["sentences_count"] = 0
                structured["sample_sentences"] = []

        return {
            "result": structured,
            "stats": {
                "fetch_time_seconds": round(elapsed, 3),
                "raw_html_mode": raw_html,
                "cleaner": cleaner_stats,
                "extraction_method": method,
                "confidence_score": confidence,
                "extraction_max_size_warning": _check_max_size_warning(max_size, main_content),
            },
        }
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        status_hints = {
            301: "The page has permanently moved. Try the updated URL.",
            302: "The page has temporarily moved. The final destination may be blocked.",
            403: "Access forbidden. The site may be blocking automated requests.",
            404: "Page not found. The URL may be incorrect or the page was removed.",
            410: "The page has been permanently removed from the server.",
            429: "Rate-limited by the server. Try again later with a lower request rate.",
            500: "Internal server error on the target site. Try again later.",
            502: "Bad gateway from the target server. Temporarily unavailable.",
            503: "Service unavailable. The target site may be temporarily overloaded.",
        }
        hint = status_hints.get(status_code,
                                "The server returned an unexpected status code.")
        return {
            "error": (
                f"fetch_url failed: HTTP {status_code} — {hint}\n"
                f"       URL: {url}"
            )
        }
    except requests.ConnectionError:
        return {"error": f"fetch_url failed: Connection refused — the server at {url} may be unreachable or blocking requests"}
    except requests.Timeout:
        return {"error": f"fetch_url failed: Request timed out after {timeout}s — {url} may be too slow or unresponsive"}
    except Exception as exc:
        exc_name = type(exc).__name__
        return {"error": f"fetch_url failed: [{exc_name}] {exc}"}


# Legacy function name for backward compatibility
def fatchurl(url: str, timeout: int = 25):
    """Deprecated: Use fetch_url() instead"""
    return fetch_url(url, timeout)


def main():
    parser = argparse.ArgumentParser(
        description='Complete search pipeline: web, image, news, video search + URL fetch'
    )
    
    # Subcommands for different search types
    subparsers = parser.add_subparsers(dest='command', help='Search commands')
    
    # Web search subcommand
    web_parser = subparsers.add_parser(
        'web-search',
        help='Web search',
        description='Web search with content extraction.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after retries,\n'
                    'try: (1) Using a different search query, (2) Adjusting --retry-attempts and --retry-backoff,\n'
                    '(3) Waiting and trying again later, or (4) Checking your internet connection.'
    )
    web_parser.add_argument('--query', '-q', required=True, help='Search query')
    web_parser.add_argument('--max', '-m', type=int, default=5, help='Max results (1-100)')
    web_parser.add_argument('--workers', '-w', type=int, default=8, help='Parallel workers')
    web_parser.add_argument('--out', '-o', default='struct_format_results.json', help='Output file')
    web_parser.add_argument('--region', default=None, help='DuckDuckGo region (example: us-en, wt-wt)')
    web_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    web_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    web_parser.add_argument('--backend', default='auto', choices=['auto', 'html', 'lite'], help='DDGS backend')
    web_parser.set_defaults(retry_on_zero=True)
    web_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 successful extractions')
    web_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 successful extractions')
    web_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    
    # Image search subcommand
    img_parser = subparsers.add_parser(
        'image-search',
        help='Image search',
        description='Image search with dimension and property filtering.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Using different query keywords, (2) Removing dimension filters temporarily,\n'
                    '(3) Reducing --max parameter, or (4) Trying again later.'
    )
    img_parser.add_argument('--query', '-q', required=True, help='Search query')
    img_parser.add_argument('--max', '-m', type=int, default=5, help='Max images (1-50)')
    img_parser.add_argument('--out', '-o', default='image_search_results.json', help='Output file')
    img_parser.add_argument('--download', '-d', action='store_true', help='Download images')
    img_parser.add_argument('--download-dir', default='downloaded_images', help='Download directory')
    img_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    img_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    img_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    img_parser.add_argument('--size', default=None, help='Image size filter (Small, Medium, Large, Wallpaper)')
    img_parser.add_argument('--color', default=None, help='Image color filter')
    img_parser.add_argument('--type-image', default=None, help='Image type filter (photo, clipart, gif, transparent, line)')
    img_parser.add_argument('--layout', default=None, help='Image layout filter (Square, Tall, Wide)')
    img_parser.add_argument('--license-image', default=None, help='Image license filter')
    img_parser.add_argument('--min-width', type=int, default=None, help='Minimum image width in pixels')
    img_parser.add_argument('--max-width', type=int, default=None, help='Maximum image width in pixels')
    img_parser.add_argument('--min-height', type=int, default=None, help='Minimum image height in pixels')
    img_parser.add_argument('--max-height', type=int, default=None, help='Maximum image height in pixels')
    img_parser.set_defaults(retry_on_zero=True)
    img_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 valid images are found')
    img_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 valid images are found')
    img_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')

    # News search subcommand
    news_parser = subparsers.add_parser(
        'news-search',
        help='DuckDuckGo news search',
        description='News search with regional and temporal filtering.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Broadening your query, (2) Removing --timelimit filter,\n'
                    '(3) Changing --region, or (4) Waiting and retrying.'
    )
    news_parser.add_argument('--query', '-q', required=True, help='Search query')
    news_parser.add_argument('--max', '-m', type=int, default=5, help='Max news items (1-50)')
    news_parser.add_argument('--out', '-o', default='news_search_results.json', help='Output file')
    news_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    news_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    news_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    news_parser.set_defaults(retry_on_zero=True)
    news_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries on zero results')
    news_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts on zero results')
    news_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')

    # Video search subcommand
    video_parser = subparsers.add_parser(
        'video-search',
        help='DuckDuckGo video search',
        description='Video search with duration and resolution filtering.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Using broader search terms, (2) Removing --duration filter,\n'
                    '(3) Changing --region, or (4) Trying again later.'
    )
    video_parser.add_argument('--query', '-q', required=True, help='Search query')
    video_parser.add_argument('--max', '-m', type=int, default=5, help='Max videos (1-50)')
    video_parser.add_argument('--out', '-o', default='video_search_results.json', help='Output file')
    video_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    video_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    video_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    video_parser.add_argument('--resolution', default=None, help='Video resolution filter (high, standard)')
    video_parser.add_argument('--duration', default=None, help='Video duration filter (short, medium, long)')
    video_parser.add_argument('--license-videos', default=None, help='Video license filter')
    
    # URL fetch subcommand
    url_parser = subparsers.add_parser(
        'fetch-url',
        help='Fetch and extract single URL',
        description='Fetch a URL and extract main content.\n\n'
                    '⚠️  NOTE: Content extraction depends on website structure. If extraction fails,\n'
                    'try: (1) Checking if the URL is valid, (2) Using --max-chars or --max-size to adjust output,\n'
                    '(3) Verifying the website is accessible, or (4) Using --timeout to increase wait time.'
    )
    url_parser.add_argument('--url', '-u', required=True, help='URL to fetch')
    url_parser.add_argument('--timeout', type=int, default=5, help='Extraction timeout in seconds')
    url_parser.add_argument('--max-chars', type=int, default=None, help='Maximum characters to extract (e.g., 10000)')
    url_parser.add_argument('--max-size', type=str, default=None, help='Maximum response size (e.g., 100kb, 1mb, 500mb)')
    url_parser.add_argument('--out', '-o', default='url_fetch_result.json', help='Output file')
    url_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    url_parser.add_argument('--raw-html', action='store_true', help='Skip cleaner pipeline, return raw extracted content')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    if args.command == 'image-search':
        if args.min_width is not None and args.max_width is not None and args.min_width > args.max_width:
            parser.error('--min-width cannot be greater than --max-width')
        if args.min_height is not None and args.max_height is not None and args.min_height > args.max_height:
            parser.error('--min-height cannot be greater than --max-height')
    
    # Web search
    if args.command == 'web-search':
        print(f"\n🔍 Starting web search: '{args.query}'\n")
        structured_results, stats = web_search(
            args.query,
            max_results=args.max,
            workers=args.workers,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            backend=args.backend,
        )
        
        output = {
            'query': args.query,
            'search_type': 'web',
            'parameters': {
                'max_results': args.max,
                'workers': args.workers,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'backend': args.backend,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
            },
            'stats': stats,
            'structured_results': structured_results
        }
        
        out_path = Path(args.out)
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print(f'\n✅ WEB SEARCH COMPLETE!')
        print(f'   🔍 Query: {args.query}')
        print(f'   📊 Total results from search: {stats["search_engine"]["total"]}')
        print(f'   ✅ Successfully extracted: {stats["cleaner"]["successful"]}')
        print(f'   ❌ Failed (ignored): {stats["cleaner"]["failed"]}')
        print(f'   📄 Structured JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"]["execution_time"]:.1f}s\n')
    
    # Image search
    elif args.command == 'image-search':
        print(f"\n🖼️  Starting image search: '{args.query}'\n")
        image_results, stats = image_search(
            args.query,
            max_results=args.max,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            size=args.size,
            color=args.color,
            type_image=args.type_image,
            layout=args.layout,
            license_image=args.license_image,
            min_width=args.min_width,
            max_width=args.max_width,
            min_height=args.min_height,
            max_height=args.max_height,
        )
        
        output = {
            'query': args.query,
            'search_type': 'image',
            'parameters': {
                'max_results': args.max,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'size': args.size,
                'color': args.color,
                'type_image': args.type_image,
                'layout': args.layout,
                'license_image': args.license_image,
                'min_width': args.min_width,
                'max_width': args.max_width,
                'min_height': args.min_height,
                'max_height': args.max_height,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
            },
            'stats': stats,
            'image_results': image_results
        }
        
        out_path = Path(args.out)
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print(f'\n✅ IMAGE SEARCH COMPLETE!')
        print(f'   🖼️  Query: {args.query}')
        print(f'   📊 Total images found: {stats["search_engine"]["total"]}')
        print(f'   ✅ Valid URLs: {stats["search_engine"]["success"]}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"]["execution_time"]:.2f}s')
        
        # Download images if requested
        if args.download and image_results:
            from references.quick_scrape import ImageSearchEngine
            engine = ImageSearchEngine()
            engine.results = [type('obj', (object,), r)() for r in image_results]
            engine.download_images(args.download_dir, min(10, len(image_results)))
        
        print()

    # News search
    elif args.command == 'news-search':
        print(f"\n📰 Starting news search: '{args.query}'\n")
        news_results, stats = news_search(
            args.query,
            max_results=args.max,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
        )

        output = {
            'query': args.query,
            'search_type': 'news',
            'parameters': {
                'max_results': args.max,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
            },
            'stats': stats,
            'news_results': news_results,
        }

        out_path = Path(args.out)
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f'\n✅ NEWS SEARCH COMPLETE!')
        print(f'   📰 Query: {args.query}')
        print(f'   📊 Total news found: {stats["search_engine"].get("total", 0)}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"].get("execution_time", 0.0):.2f}s\n')

    # Video search
    elif args.command == 'video-search':
        print(f"\n🎬 Starting video search: '{args.query}'\n")
        video_results, stats = video_search(
            args.query,
            max_results=args.max,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            resolution=args.resolution,
            duration=args.duration,
            license_videos=args.license_videos,
        )

        output = {
            'query': args.query,
            'search_type': 'video',
            'parameters': {
                'max_results': args.max,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'resolution': args.resolution,
                'duration': args.duration,
                'license_videos': args.license_videos,
            },
            'stats': stats,
            'video_results': video_results,
        }

        out_path = Path(args.out)
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f'\n✅ VIDEO SEARCH COMPLETE!')
        print(f'   🎬 Query: {args.query}')
        print(f'   📊 Total videos found: {stats["search_engine"].get("total", 0)}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"].get("execution_time", 0.0):.2f}s\n')
    
    # Fetch URL
    elif args.command == 'fetch-url':
        # Validate: Only one of --max-chars or --max-size is allowed
        if args.max_chars is not None and args.max_size is not None:
            parser.error('❌ ERROR: Cannot use both --max-chars and --max-size together. Use only ONE parameter at a time:\n'
                        '   • --max-chars 10000 (to limit extracted content by character count)\n'
                        '   • --max-size 5mb (to limit response size by file size)\n'
                        '   Use either one, not both.')
        
        print(f"\n📥 Fetching: {args.url}\n")
        result = fetch_url(
            args.url,
            timeout=args.timeout,
            max_chars=args.max_chars,
            max_size=args.max_size,
            raw_html=args.raw_html,
        )

        output = {
            'url': args.url,
            'search_type': 'fetch',
            'parameters': {
                'timeout': args.timeout,
                'max_chars': args.max_chars,
                'max_size': args.max_size,
                'raw_html': args.raw_html,
            },
            'result': result
        }

        out_path = Path(args.out)
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

        if "error" in result:
            print(f"❌ Error: {result['error']}\n")
        else:
            mode_tag = " RAW" if args.raw_html else ""
            print(f'✅ FETCH COMPLETE{mode_tag}!')
            print(f'   📝 Title: {result["result"]["title"]}')
            print(f'   📊 Words: {result["result"]["content_word_count"]}')
            print(f'   ✅ Status: {result["stats"]["extraction_method"]}')
            print(f'   ⏱️  Fetch time: {result["stats"]["fetch_time_seconds"]}s')
            print(f'   📄 Result JSON: {out_path}')
            if args.raw_html:
                print(f'   🔧 Mode: raw-html (cleaner pipeline skipped)')
            print(f'   📂 Results saved to: {out_path.resolve()}\n')


if __name__ == '__main__':
    main()
