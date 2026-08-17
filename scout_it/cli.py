#!/usr/bin/env python3
"""
Complete search pipeline wrapper.
Runs extraction.py → cleaner.py
Outputs: structured JSON with filtered results

Usage (CLI):
  scout-it web-search --query "today hot news" --max 50 --workers 6 --out results.json
  scout-it image-search --query "sunset" --max 20 --out images.json

This imports `EnterpriseSearchEngine`, `ImageSearchEngine` from `extraction.py` 
and `process_results` from `cleaner.py`
"""
import argparse
import logging
import sys

# Ensure Unicode output works on Windows terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass  # Fallback: ignore if not supported
import importlib.metadata
import json
import random
import re
import socket
import time
from dataclasses import asdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

# Local imports
from .wikimedia_source import SITE_MAP

# Initialize logger
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# LIGHTWEIGHT NETWORK CONNECTIVITY CHECKER (TCP Socket-Based)
# ══════════════════════════════════════════════════════════════════════════
# Moved to scout_it/utils/net.py
# Functions: check_internet_connection(), ensure_internet_connection()
# ══════════════════════════════════════════════════════════════════════════


try:
    from .cleaner import process_results
    from .extraction import (
        DDGS,
        EnterpriseSearchEngine,
        ExtractionEngine,
        ImageSearchEngine,
        _compact_options,
        _ddg_html_lite_fallback_search,
        _ddgs_list_search,
        _ddgs_list_search_with_retry,
        fetch_resilient,
    )
    from . import github_extract as gh
    from . import engines as search_engines
    from . import social
    from . import config as ds_config
    from . import output as output_mod
    from . import strategy_cache
    from . import proxy_pool
    from . import response_cache
    from . import canary_probe
    
    # Import refactored search modules
    # Note: Using importlib for folders with hyphens in their names
    import importlib
    web_search_module = importlib.import_module('.web-search.web_search', package='scout_it')
    news_search_module = importlib.import_module('.news-search.news_search', package='scout_it')
    web_search = web_search_module.web_search
    news_search = news_search_module.news_search
    
    # Import command modules
    from .commands import (
        image_search,
        video_search,
        video_extract,
        fetch_url,
        fatchurl,
        multi_search,
        wikipedia_search,
    )
    # Backward-compatibility: these helpers were originally defined in cli.py
    # before the refactor split them into commands/video.py. Re-export them so
    # `from scout_it.cli import ...` and
    # `mock.patch('scout_it.cli._fetch_youtube_metadata')` keep working.
    from .commands.video import (
        _enhance_video_descriptions,
        _fetch_youtube_metadata,
    )
    from .utils import (
        check_internet_connection,
        ensure_internet_connection,
        _log_phase,
        _PhaseTimer,
        _write_output,
    )
except Exception as e:
    raise ImportError("Could not import from scout_it modules: " + str(e))


# Error/404 page detection phrases — short content matching any of these
# indicates a broken or removed page (dead link from search engine).

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR_PAGE_PHRASES is defined once in scout_it/extraction/engine.py and
# imported from there wherever needed (extraction/search.py, etc.).
# ═══════════════════════════════════════════════════════════════════════════════



# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
# Moved to scout_it/utils/output.py
# Functions: _log_phase(), _PhaseTimer, _write_output()
# ---------------------------------------------------------------------------


# Maps each command to the base filename (no extension, no directory) its
# --out default is built from, e.g. 'web-search' -> '.scout-it/struct_format_results.json'.
# Centralizes --out/--markdown resolution in one place instead of duplicating
# it in every dispatch block.
COMMAND_OUTPUT_STUBS: Dict[str, str] = {
    'web-search': 'struct_format_results',
    'image-search': 'image_search_results',
    'news-search': 'news_search_results',
    'video-search': 'video_search_results',
    'fetch-url': 'url_fetch_result',
    'video-extract': 'video_extract_results',
    'multi-search': 'multi_search_results',
    'github-repo': 'github_repo_results',
    'wikipedia-search': 'wikipedia_search_results',
    'github-commits': 'github_commits_results',
    'github-commit': 'github_commit_results',
    'github-pr': 'github_pr_results',
    'github-prs': 'github_prs_results',
    'github-folder': 'github_folder_results',
    'github-issues': 'github_issues_results',
    'github-issue': 'github_issue_results',
    'github-file': 'github_file_results',
    'github-search-code': 'github_search_code_results',
    'github-search-repos': 'github_search_repos_results',
    'github-discussions': 'github_discussions_results',
    'social-search': 'social_search_results',
}


def _print_source_messages() -> None:
    """Print and clear any leftover skip/error messages from source plugins.

    API search sources (Tavily/Exa/Firecrawl) now run via ``--source`` (singular)
    and drain their own messages inside the search functions. This helper is
    kept as a safety net to flush any stray messages after ``--sources`` (plural)
    augmentation. It is a no-op when there are no messages.
    """
    try:
        from .sources import source_messages
    except ImportError:
        return
    messages = source_messages.drain()
    if not messages:
        return
    for msg in messages:
        src = msg.get("source", "unknown")
        reason = msg.get("reason", "")
        if msg.get("type") == "skip":
            print(f"   ⏭️  Source '{src}' skipped: {reason}")
        else:
            print(f"   ⚠️  Source '{src}' error: {reason}")



# ═══════════════════════════════════════════════════════════════════════════════
# web_search has been moved to scout_it/web-search/
# It is imported at the top of this file via importlib
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# multi_search has been moved to scout_it/commands/web.py
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# image_search has been moved to scout_it/commands/image.py
# ═══════════════════════════════════════════════════════════════════════════════



# ═══════════════════════════════════════════════════════════════════════════════
# news_search has been moved to scout_it/news-search/
# It is imported at the top of this file via importlib
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# Wikipedia search functions have been moved to scout_it/commands/wikipedia.py
# Functions: wikipedia_search(), _wiki_do_bundle(), _wiki_do_summary(), 
#            _wiki_do_extract(), _wiki_do_sections(), _wiki_do_crawl(),
#            _wiki_do_search(), _wiki_enrich_results()
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# Video search functions have been moved to scout_it/commands/video.py
# Functions: video_search(), video_extract(), _enhance_video_descriptions(),
#            _fetch_youtube_metadata(), _fetch_youtube_subtitles()
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# URL fetch functions have been moved to scout_it/commands/url.py
# Functions: fetch_url(), fatchurl(), _extract_html_title(), _check_max_size_warning()
# ═══════════════════════════════════════════════════════════════════════════════


def build_parser():
    """Build and return the argparse parser for the scout-it CLI.

    Extracted from ``main()`` so tests can parse args without running the CLI.
    """
    parser = argparse.ArgumentParser(
        description='Complete search pipeline: web, image, news, video search + URL fetch'
    )
    try:
        ver = importlib.metadata.version("scout-it")
    except Exception:
        ver = "unknown"
    parser.add_argument('-v', '--version', action='version', version=f'scout-it {ver}')
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
    web_parser.add_argument('--max', '-m', type=int, default=None, 
                             help='Number of results to return. Default: 10 (full extraction), 30 (--snippets mode). '
                                  'Pipeline: Collect snippets from all sources → Rank by relevance → '
                                  'Extract full content for top N (or return snippets only with --snippets). '
                                  'Example: -m 20 will rank all candidates and extract top 20.')
    web_parser.add_argument('--snippets', action='store_true',
                             help='Return ranked snippets only. Skips content extraction for ~10x faster results (~2-4s vs 20-70s). '
                                  'Perfect for quickly browsing large numbers of candidates. Default limit: 30 snippets.')
    web_parser.add_argument('--workers', '-w', type=int, default=5, help='Parallel workers')
    web_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/struct_format_results.json)')
    web_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    web_parser.add_argument('--sources', default=None, help='Also search these source plugins (comma-separated, e.g. openalex,arxiv,wikidata) and merge results with BM25F+vector re-ranking. Run `scout-it sources` for available sources.')
    web_parser.add_argument('--auto-sources', action='store_true', help='Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.')
    web_parser.add_argument('--region', default=None, help='DuckDuckGo region (example: us-en, wt-wt)')
    web_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    web_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    web_parser.add_argument('--backend', default='auto', choices=['auto', 'html', 'lite'], help='DDGS backend')
    web_parser.add_argument('--source', default=None,
                            help='Search source override(s) running as parallel discovery streams alongside DuckDuckGo. '
                                 'Comma-separated: "wikimedia" (Wikimedia), "tavily", "exa", "firecrawl" (API search providers, '
                                 'need API keys via `scout-it config`). Example: --source wikimedia,tavily. '
                                 'If the primary source returns zero results, falls back to the other source.')
    web_parser.add_argument('--category', nargs='+', default=None,
                            help='Category-specific RSS feeds to include (ai, engineering, cloud, devops, research, etc.). '
                                 'Multiple categories can be specified, e.g. --category ai cloud devops. '
                                 'Results from category feeds are merged with DuckDuckGo search.')
    web_parser.set_defaults(retry_on_zero=True)
    web_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 successful extractions')
    web_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 successful extractions')
    web_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    web_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright) when fetching each result page')
    web_parser.add_argument('--enable-alternate-source', action='store_true', help='If every fetch tier fails, try AMP/mobile/print URL variants and a Wayback Machine snapshot before giving up (extra requests, opt-in)')
    web_parser.add_argument('--no-dns-fallback', dest='enable_dns_fallback', action='store_false', help='Disable the DNS-over-HTTPS retry when a fetch fails with a DNS-looking error (on by default)')
    web_parser.set_defaults(enable_dns_fallback=True)
    web_parser.add_argument('--tls-impersonate', dest='enable_tls_impersonate', action='store_true', help='Insert a browser-accurate TLS/JA3 fingerprint tier between requests and Playwright (needs: pip install scout-it[tls-impersonate])')
    web_parser.add_argument('--persistent-profile', dest='enable_persistent_profile', action='store_true', help='Use a persistent Playwright profile (cookies/session survive across runs) instead of a throwaway context for the JS-render tier')
    web_parser.add_argument('--profile-name', dest='browser_profile_name', default='default', help='Persistent profile name (only with --persistent-profile)')
    web_parser.add_argument('--use-bandit', dest='enable_bandit', action='store_true', help="Once a domain has enough recorded history, skip straight to whichever fetch tier has actually worked best for it instead of always starting with plain requests (see 'scout-it stats')")
    web_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback when a page fetch fails or looks blocked')
    web_parser.add_argument('--semantic', dest='enable_semantic', action='store_true', help='Re-rank results by semantic relevance (hybrid BM25+dense-vector + cross-encoder). Needs: pip install sentence-transformers torch')
    web_parser.set_defaults(enable_js_fallback=True)

    # Wikimedia search subcommand
    wiki_parser = subparsers.add_parser(
        'wikipedia-search',
        help='Search any Wikimedia project (Wikipedia, Wikidata, Commons, Wiktionary, etc.)',
        description='Search Wikimedia projects via the MediaWiki Action API.\n\n'
                    'Supports all 12 Wikimedia projects: wikipedia, commons, wikivoyage, wiktionary,\n'
                    'wikibooks, wikidata, wikiversity, wikiquote, mediawiki, wikisource, wikispecies,\n'
                    'wikifunctions.\n\n'
                    'Use --project to choose which project (default: wikipedia).\n'
                    'Use --summary / --extract / --sections / --crawl for different data modes.',
    )
    wiki_parser.add_argument('--query', '-q', required=True, help='Search query or page title')
    wiki_parser.add_argument('--max', '-m', type=int, default=10, help='Max results (1-50)')
    wiki_parser.add_argument('--project', default='wikipedia', choices=sorted(SITE_MAP.keys()),
                             help='Wikimedia project to search (default: wikipedia)')
    wiki_parser.add_argument('--language', '-l', default='en',
                             help='Project language for language-scoped wikis (default: en)')
    wiki_parser.add_argument('--timeout', type=int, default=25, help='HTTP timeout in seconds')
    wiki_parser.add_argument('--workers', '-w', type=int, default=5, help='Parallel workers')
    wiki_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/wikimedia_results.json)')
    wiki_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    wiki_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    # Mode options
    wiki_parser.add_argument('--summary', action='store_true',
                             help='Fetch a Wikipedia REST summary for the given title')
    wiki_parser.add_argument('--extract', action='store_true',
                             help='Fetch cleaned full-page extract via the Action API')
    wiki_parser.add_argument('--sections', action='store_true',
                             help='Export section-by-section cleaned text')
    wiki_parser.add_argument('--crawl', action='store_true',
                             help='Enable recursive crawl from the search results')
    wiki_parser.add_argument('--crawl-depth', type=int, default=2,
                             help='Crawl depth for --crawl mode (default: 2)')
    wiki_parser.add_argument('--bundle', action='store_true',
                             help='Run a broad multi-project topic bundle (searches all 12 projects)')
    wiki_parser.add_argument('--robots', action='store_true',
                             help='Check robots.txt allowance before searching')
    wiki_parser.add_argument('--no-clean', action='store_false', dest='clean_text',
                             help='Disable text cleaning')
    # Unified pipeline flags (discover -> rank -> output), mirroring image/video/news search.
    wiki_parser.add_argument('--rss', action='store_true', dest='rss',
                             help='Include MediaWiki RecentChanges RSS feeds in discovery (uses --project as default category)')
    wiki_parser.add_argument('--category', '-c', dest='category', action='append', default=None,
                             choices=None,
                             help='Wikimedia project RSS category to include (repeatable): wikipedia, commons, wiktionary, wikivoyage, wikibooks, wikidata, wikiversity, wikiquote, mediawiki, wikisource, wikispecies, wikifunctions. Adds recently-changed pages to the candidate pool before ranking.')
    wiki_parser.set_defaults(clean_text=True)

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
    img_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/image_search_results.json)')
    img_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    img_parser.add_argument('--sources', default=None, help='Also search source plugins (comma-separated, e.g. internet_archive,openstreetmap) and merge with BM25F+vector re-ranking. Run `scout-it sources` for available sources.')
    img_parser.add_argument('--auto-sources', action='store_true', help='Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.')
    img_parser.add_argument('--download', '-d', action='store_true', help='Download images')
    img_parser.add_argument('--download-dir', default='.scout-it/downloaded_images', help='Download directory (default: .scout-it/downloaded_images)')
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
    img_parser.add_argument('--category', nargs='+', default=None, dest='category',
                            help='Image RSS categories to include (e.g. nature space travel anime_art fantasy_art). '
                                 'Fetches Media RSS feeds (Flickr/NASA/DeviantArt) alongside DuckDuckGo and ranks them together.')
    img_parser.add_argument('--rss', action='store_true',
                            help='Include image RSS discovery even without --category — fetches a Flickr tag feed '
                                 'and keyword-matched DeviantArt tag feeds from the query in parallel')
    img_parser.add_argument('--source', default=None,
                            help='Search source override(s) running as parallel discovery streams alongside DuckDuckGo Images. '
                                 'Comma-separated API search providers: "tavily", "firecrawl" (need API keys via `scout-it config`). '
                                 'Example: --source tavily,firecrawl. Results are merged and ranked together.')
    img_parser.set_defaults(retry_on_zero=True)
    img_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 valid images are found')
    img_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 valid images are found')
    img_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')

    # News search subcommand
    news_parser = subparsers.add_parser(
        'news-search',
        help='DuckDuckGo news search with full content extraction',
        description='News search with regional and temporal filtering and full article content extraction.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Broadening your query, (2) Removing --timelimit filter,\n'
                    '(3) Changing --region, or (4) Waiting and retrying.'
    )
    news_parser.add_argument('--query', '-q', required=True, help='Search query')
    news_parser.add_argument('--max', '-m', type=int, default=None, 
                             help='Number of results to return. Default: 10 (full extraction), 30 (--snippets mode). '
                                  'Pipeline: Collect snippets from all sources → Rank by relevance → '
                                  'Extract full content for top N (or return snippets only with --snippets). '
                                  'Example: -m 20 will rank all candidates and extract top 20.')
    news_parser.add_argument('--snippets', action='store_true',
                             help='Return ranked news snippets only. Skips article extraction for ~10x faster results (~2-4s vs 20-70s). '
                                  'Perfect for quickly browsing large numbers of candidates. Default limit: 30 snippets.')
    news_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/news_search_results.json)')
    news_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    news_parser.add_argument('--sources', default=None, help='Also search source plugins (comma-separated, e.g. gdelt,openalex,crossref) and merge with BM25F+vector re-ranking. Run `scout-it sources` for available sources.')
    news_parser.add_argument('--auto-sources', action='store_true', help='Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.')
    news_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    news_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    news_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    news_parser.add_argument('--workers', type=int, default=5, help='Parallel workers for content extraction')
    news_parser.add_argument('--source', default=None,
                             help='Search source override(s) running as parallel discovery streams alongside DuckDuckGo News. '
                                  'Comma-separated: "google-news" (Google News RSS), "tavily", "exa", "firecrawl" (API search providers, '
                                  'need API keys via `scout-it config`). Example: --source google-news,tavily. '
                                  'If the primary source returns zero results, falls back to the other source.')
    news_parser.add_argument('--category', nargs='+', default=None,
                             help='Category-specific RSS feeds to include (ai, startups, security, cloud). '
                                  'Multiple categories can be specified, e.g. --category ai startups. '
                                  'Results from category feeds are merged with DuckDuckGo News.')
    news_parser.set_defaults(retry_on_zero=True)
    news_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries on zero results')
    news_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts on zero results')
    news_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    news_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright) when fetching each article page')
    news_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback when an article fetch fails or looks blocked')
    news_parser.set_defaults(enable_js_fallback=True)
    news_parser.add_argument('--location', nargs='+', default=None,
                             help='Location(s) for localized news from Times of India RSS feeds. '
                                  'Pattern: country or country-city. Examples: india, world, US, '
                                  'UK, europe, china, pakistan, india-delhi, india-bangalore, '
                                  'india-hyderabad. Multiple locations can be given, e.g. '
                                  '--location india US india-delhi')
    news_parser.add_argument('--max-chars', type=int, default=None,
                             help='Maximum characters to keep in extracted article content')
    news_parser.add_argument('--max-size', type=str, default=None,
                             help='Maximum response size per article (e.g. 5mb). '
                                  'Truncates the raw HTML before extraction.')
    news_parser.add_argument('--semantic', dest='enable_semantic', action='store_true', help='Re-rank results by semantic relevance (hybrid BM25+dense-vector + cross-encoder). Needs: pip install sentence-transformers torch')

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
    video_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/video_search_results.json)')
    video_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    video_parser.add_argument('--sources', default=None, help='Also search source plugins (comma-separated, e.g. internet_archive,listennotes) and merge with BM25F+vector re-ranking. Run `scout-it sources` for available sources.')
    video_parser.add_argument('--auto-sources', action='store_true', help='Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.')
    video_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    video_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    video_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    video_parser.add_argument('--resolution', default=None, help='Video resolution filter (high, standard)')
    video_parser.add_argument('--duration', default=None, help='Video duration filter (short, medium, long)')
    video_parser.add_argument('--license-videos', default=None, help='Video license filter')
    video_parser.add_argument('--category', nargs='+', default=None, dest='category',
                               help='Video RSS categories to include (e.g. technology science news). '
                                    'Fetches YouTube channel RSS feeds alongside DuckDuckGo and ranks them together.')
    video_parser.add_argument('--rss', action='store_true',
                               help='Include video RSS discovery even without --category (pulls a default set of YouTube channels)')
    video_parser.set_defaults(retry_on_zero=True)
    video_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 results are found')
    video_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 results are found')
    video_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    
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
    url_parser.add_argument('--timeout', type=int, default=25, help='Extraction timeout in seconds (increase for JS-rendered SPAs)')
    url_parser.add_argument('--max-chars', type=int, default=None, help='Maximum characters to extract (e.g., 10000)')
    url_parser.add_argument('--max-size', type=str, default=None, help='Maximum response size (e.g., 100kb, 1mb, 500mb)')
    url_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/url_fetch_result.json)')
    url_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    url_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    url_parser.add_argument('--raw-html', action='store_true', help='Return raw HTML (prettified) instead of extracted/cleaned content')
    url_parser.add_argument('--js-render', action='store_true', help='Skip straight to Playwright rendering instead of trying requests first')
    url_parser.add_argument('--no-js-fallback', action='store_true', help='Disable automatic Playwright fallback when requests fails or looks blocked')
    url_parser.add_argument('--max-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright)')
    url_parser.add_argument('--enable-alternate-source', action='store_true', help='If every fetch tier fails, try AMP/mobile/print URL variants and a Wayback Machine snapshot before giving up (extra requests, opt-in)')
    url_parser.add_argument('--persistent-profile', dest='enable_persistent_profile', action='store_true', help='Use a persistent Playwright profile (cookies/session survive across runs) instead of a throwaway context for the JS-render tier')
    url_parser.add_argument('--profile-name', dest='browser_profile_name', default='default', help='Persistent profile name (only with --persistent-profile)')

    # ======================================================================
    # video-extract subcommand
    # ======================================================================
    video_extract_parser = subparsers.add_parser(
        'video-extract',
        help='Extract full details from a video URL (supports YouTube)',
        description=(
            'Extract full metadata, description, and subtitles from a video URL. '
            'Currently supports YouTube. Other platforms coming soon.'
        ),
        epilog=(
            'Examples:\n'
            '  scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"\n'
            '  scout-it video-extract --url "https://youtu.be/dQw4w9WgXcQ"\n'
            '  scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --subtitle-lang fr\n'
            '  scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments\n'
        '  scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    video_extract_parser.add_argument('--url', required=True, help='Video URL to extract (e.g., https://www.youtube.com/watch?v=VIDEO_ID)')
    video_extract_parser.add_argument('--subtitle-lang', default='en', help='Preferred subtitle language code (default: en)')
    video_extract_parser.add_argument('--segments', action='store_true', help='Include subtitle segments with timestamps (default: off)')
    video_extract_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/video_extract_results.json)')
    video_extract_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    video_extract_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    video_extract_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright) when fetching the video page')
    video_extract_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback when the page fetch fails or looks blocked')
    video_extract_parser.set_defaults(enable_js_fallback=True)

    # ======================================================================
    # multi-search subcommand — search across multiple engines in parallel
    # ======================================================================
    multi_parser = subparsers.add_parser(
        'multi-search',
        help='Search across multiple engines (DuckDuckGo + optional Brave/Bing/Google/SerpAPI) in parallel',
        description=(
            'Query several search engines in parallel, merge/dedupe the results, then run the '
            'same content-extraction pipeline as web-search. DuckDuckGo works with no setup. '
            'Brave/Bing/Google/SerpAPI each need an API key (env var) — see `scout-it list-engines`. '
            'Unconfigured engines are skipped, not treated as errors.'
        ),
        epilog=(
            'Examples:\n'
            '  scout-it multi-search --query "rust vs go" --engines duckduckgo\n'
            '  scout-it multi-search --query "rust vs go" --engines duckduckgo,brave,google --max 15\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    multi_parser.add_argument('--query', '-q', required=True, help='Search query')
    multi_parser.add_argument('--engines', default='duckduckgo', help='Comma-separated engine names (duckduckgo,brave,bing,google,serpapi,wikimedia)')
    multi_parser.add_argument('--source', default=None,
                              help='Search source override(s) running as parallel discovery streams alongside the engines. '
                                   'Comma-separated: "wikimedia" (added to engine list), "tavily", "exa", "firecrawl" (API search providers, '
                                   'need API keys via `scout-it config`). Example: --source wikimedia,tavily.')
    multi_parser.add_argument('--max', '-m', type=int, default=10, help='Max merged results')
    multi_parser.add_argument('--workers', '-w', type=int, default=5, help='Parallel content-extraction workers')
    multi_parser.add_argument('--serpapi-engine', default='google', help='Underlying engine for SerpAPI (google/bing/yahoo/baidu/yandex/...)')
    multi_parser.add_argument('--no-dedupe', dest='dedupe', action='store_false', help='Keep duplicate URLs across engines instead of deduping')
    multi_parser.set_defaults(dedupe=True)
    multi_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier when fetching each result page')
    multi_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback')
    multi_parser.set_defaults(enable_js_fallback=True)
    multi_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/multi_search_results.json)')
    multi_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    multi_parser.add_argument('--sources', default=None, help='Also search source plugins (comma-separated, e.g. openalex,arxiv,wikidata,huggingface) in parallel and merge with BM25F+vector re-ranking. Run `scout-it sources` for available sources.')
    multi_parser.add_argument('--auto-sources', action='store_true', help='Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.')
    multi_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    # list-engines subcommand — show configuration status of every engine
    subparsers.add_parser('list-engines', help='List available search engines and whether each is configured')

    # config subcommand — interactive credential setup, stored at ~/.scout-it/
    config_parser = subparsers.add_parser(
        'config',
        help='Set up API keys/tokens (GitHub, Brave, Bing, Google, SerpAPI, Discord, Reddit) -- stored at ~/.scout-it/',
        description=(
            "Run with no flags for an interactive wizard that asks for each supported API key/token "
            "one at a time (Enter to skip). Values are stored at ~/.scout-it/credentials.json "
            "(owner-only file permissions) and loaded automatically on every future run -- a real "
            "environment variable always takes precedence over a stored value."
        ),
    )
    config_parser.add_argument('--show', action='store_true', help='Show configuration status for every known key (no secrets printed) instead of running the wizard')
    config_parser.add_argument('--clear', default=None, metavar='KEY', help='Remove one stored key, e.g. --clear GITHUB_TOKEN')
    config_parser.add_argument('--clear-all', action='store_true', help='Remove all stored keys')

    # stats -- introspection into the local strategy cache
    stats_parser = subparsers.add_parser(
        'stats',
        help='Show per-domain fetch-strategy statistics learned by the strategy cache',
        description=(
            "Reports what scout-it has learned about each domain it's fetched from: which "
            "{tier, proxy, fingerprint} combination works best, overall success rate, and attempt "
            "counts. Backed by a local SQLite file at ~/.scout-it/strategy_cache.db -- no network "
            "calls, pure local bookkeeping accumulated across every fetch_resilient() call."
        ),
    )
    stats_parser.add_argument('--domain', default=None, help='Show stats for one domain only (default: all known domains)')
    stats_parser.add_argument('--export', default=None, metavar='PATH', help='Write the full stats dump to a JSON file instead of printing a summary')
    stats_parser.add_argument('--reset', default=None, metavar='DOMAIN', help='Forget all recorded strategy history for one domain')
    stats_parser.add_argument('--reset-all', action='store_true', help='Forget all recorded strategy history for every domain')
    stats_parser.add_argument('--sources', action='store_true', help='Show source-selection bandit stats (which sources work best per query type)')

    # doctor -- environment/connectivity self-check
    subparsers.add_parser(
        'doctor',
        help='Run a self-check: Playwright availability, proxy config, cache health, credentials, DNS/connectivity',
        description=(
            "Diagnoses common setup issues before you hit them mid-command: whether Playwright's "
            "browser is actually installed (not just the pip package), whether PROXY_LIST is set and "
            "reachable, response-cache disk usage, which credentials are configured, and basic "
            "internet connectivity. Every check is independent and failures are reported clearly "
            "rather than raising."
        ),
    )

    # ======================================================================
    # GitHub extraction subcommands
    # ======================================================================
    gh_repo_parser = subparsers.add_parser(
        'github-repo',
        help='Get comprehensive GitHub repository details (metadata + branches + commit/PR/issue counts + contributors + releases + languages + file tree)',
        description=(
            "By default this aggregates a full overview: base metadata, all branches, an "
            "approximate commit count, accurately split open-issue/open-PR counts, top "
            "contributors, latest release, per-language byte breakdown, and a file-tree "
            "preview -- everything several separate github-* commands would otherwise need. "
            "That costs ~7 API calls instead of 1; pass --quick for just the fast base metadata "
            "if you're conserving rate limit (60/hr unauthenticated, 5,000/hr with GITHUB_TOKEN)."
        ),
    )
    gh_repo_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_repo_parser.add_argument('--quick', dest='full', action='store_false', help='Fast single-call basic metadata only (skip branches/contributors/releases/etc.)')
    gh_repo_parser.set_defaults(full=True)
    gh_repo_parser.add_argument('--file-tree', action='store_true', help='Include the FULL, untruncated file tree (not included by default -- can be huge)')
    gh_repo_parser.add_argument('--max-chars', type=int, default=None, help='(--file-tree only) cap the tree output by character count -- mutually exclusive with --max-size')
    gh_repo_parser.add_argument('--max-size', default=None, help='(--file-tree only) cap the tree output by size, e.g. 5mb -- mutually exclusive with --max-chars')
    gh_repo_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_repo_results.json)')
    gh_repo_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_repo_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_commits_parser = subparsers.add_parser('github-commits', help='List commits in a GitHub repo')
    gh_commits_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_commits_parser.add_argument('--branch', default=None, help='Branch/tag/SHA to list commits from (default: repo default branch)')
    gh_commits_parser.add_argument('--path', default=None, help='Only commits touching this file/path')
    gh_commits_parser.add_argument('--author', default=None, help='Filter by author username or email')
    gh_commits_parser.add_argument('--since', default=None, help='ISO8601 date — only commits after this')
    gh_commits_parser.add_argument('--until', default=None, help='ISO8601 date — only commits before this')
    gh_commits_parser.add_argument('--max', '-m', type=int, default=30, help='Max commits to list')
    gh_commits_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_commits_results.json)')
    gh_commits_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_commits_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_commit_parser = subparsers.add_parser('github-commit', help='Full details for ONE commit: stats, changed files, and unified diff patches')
    gh_commit_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_commit_parser.add_argument('--sha', required=True, help='Commit SHA (full or short)')
    gh_commit_parser.add_argument('--no-patch', dest='include_patch', action='store_false', help="Omit each file's unified diff patch text (metadata only)")
    gh_commit_parser.set_defaults(include_patch=True)
    gh_commit_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_commit_results.json)')
    gh_commit_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_commit_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_pr_parser = subparsers.add_parser('github-pr', help='Get a pull request, including its full diff and changed files')
    gh_pr_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_pr_parser.add_argument('--number', '-n', type=int, required=True, help='Pull request number')
    gh_pr_parser.add_argument('--no-diff', dest='include_diff', action='store_false', help='Omit the changed-files/diff list (metadata only)')
    gh_pr_parser.set_defaults(include_diff=True)
    gh_pr_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_pr_results.json)')
    gh_pr_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_pr_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_prs_parser = subparsers.add_parser('github-prs', help='List pull requests in a GitHub repo (PR-specific fields, unlike github-issues)')
    gh_prs_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_prs_parser.add_argument('--state', default='open', choices=['open', 'closed', 'all'], help='PR state filter')
    gh_prs_parser.add_argument('--sort', default='created', choices=['created', 'updated', 'popularity', 'long-running'], help='Sort order')
    gh_prs_parser.add_argument('--max', '-m', type=int, default=30, help='Max PRs to list')
    gh_prs_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_prs_results.json)')
    gh_prs_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_prs_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_folder_parser = subparsers.add_parser('github-folder', help="List (and optionally fetch) every file under a repo folder, e.g. 'src/'")
    gh_folder_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_folder_parser.add_argument('--path', default='', help="Folder path, e.g. 'src/' (default: repo root)")
    gh_folder_parser.add_argument('--ref', default=None, help='Branch/tag/SHA (default: repo default branch)')
    gh_folder_parser.add_argument('--no-recursive', dest='recursive', action='store_false', help='List only immediate children instead of walking the whole subtree')
    gh_folder_parser.set_defaults(recursive=True)
    gh_folder_parser.add_argument('--include-content', action='store_true', help="Also fetch each file's contents")
    gh_folder_parser.add_argument('--max-files', type=int, default=None, help='(--include-content only) cap how many files get their content fetched; omit to fetch ALL of them. Error if given without --include-content.')
    gh_folder_parser.add_argument('--max-chars', type=int, default=None, help="(--include-content only) cap each file's content by character count -- mutually exclusive with --max-size")
    gh_folder_parser.add_argument('--max-size', default=None, help="(--include-content only) cap each file's content by size, e.g. 500kb -- mutually exclusive with --max-chars")
    gh_folder_parser.add_argument('--save-path-dir', default=None, help='(--include-content only) also write every fetched file to disk under this directory, preserving the repo-relative path structure. Error if given without --include-content.')
    gh_folder_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_folder_results.json)')
    gh_folder_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_folder_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_issues_parser = subparsers.add_parser('github-issues', help='List issues in a GitHub repo')
    gh_issues_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_issues_parser.add_argument('--state', default='open', choices=['open', 'closed', 'all'], help='Issue state filter')
    gh_issues_parser.add_argument('--labels', default=None, help='Comma-separated label filter')
    gh_issues_parser.add_argument('--max', '-m', type=int, default=30, help='Max issues to list')
    gh_issues_parser.add_argument('--include-prs', dest='include_pull_requests', action='store_true', help="Include pull requests (GitHub's issues API returns PRs too by default)")
    gh_issues_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_issues_results.json)')
    gh_issues_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_issues_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_issue_parser = subparsers.add_parser('github-issue', help='Get one issue, including its full body and comments')
    gh_issue_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_issue_parser.add_argument('--number', '-n', type=int, required=True, help='Issue number')
    gh_issue_parser.add_argument('--no-comments', dest='include_comments', action='store_false', help='Omit comments')
    gh_issue_parser.set_defaults(include_comments=True)
    gh_issue_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_issue_results.json)')
    gh_issue_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_issue_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_file_parser = subparsers.add_parser('github-file', help='Fetch a single file\'s contents from a GitHub repo')
    gh_file_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_file_parser.add_argument('--path', required=True, help='File path within the repo, e.g. src/main.py')
    gh_file_parser.add_argument('--ref', default=None, help='Branch/tag/SHA (default: repo default branch)')
    gh_file_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_file_results.json)')
    gh_file_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_file_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_search_code_parser = subparsers.add_parser('github-search-code', help='Search code across GitHub (requires GITHUB_TOKEN)')
    gh_search_code_parser.add_argument('--query', '-q', required=True, help="GitHub code search query, e.g. 'fetch_resilient language:python'")
    gh_search_code_parser.add_argument('--max', '-m', type=int, default=20, help='Max results')
    gh_search_code_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_search_code_results.json)')
    gh_search_code_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_search_code_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_search_repos_parser = subparsers.add_parser('github-search-repos', help='Search GitHub repositories')
    gh_search_repos_parser.add_argument('--query', '-q', required=True, help="e.g. 'language:python topic:llm stars:>1000'")
    gh_search_repos_parser.add_argument('--sort', default='stars', choices=['stars', 'forks', 'help-wanted-issues', 'updated'], help='Sort order')
    gh_search_repos_parser.add_argument('--max', '-m', type=int, default=20, help='Max results')
    gh_search_repos_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_search_repos_results.json)')
    gh_search_repos_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_search_repos_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_discussions_parser = subparsers.add_parser('github-discussions', help='List GitHub Discussions for a repo (requires GITHUB_TOKEN)')
    gh_discussions_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_discussions_parser.add_argument('--max', '-m', type=int, default=20, help='Max discussions')
    gh_discussions_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/github_discussions_results.json)')
    gh_discussions_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    gh_discussions_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    # ======================================================================
    # Social/platform subcommand — unified social-search
    # ======================================================================
    # One entry point for all social platforms. --platform selects which
    # providers run (comma-separated; default = all enabled). Each provider
    # declares the capabilities it supports and falls back to public query
    # search when a requested platform-specific arg (e.g. --channel) is not
    # supported for that platform. Adding a future platform requires only a
    # new Provider + capability declaration + registry entry — no CLI change.
    social_parser = subparsers.add_parser(
        'social-search',
        help='Search one or more social platforms (Telegram, Reddit, Discord) with capability-based fallback',
        description=(
            'Unified social platform search. By default every enabled provider runs; '
            'use --platform telegram,reddit,discord to select a subset (comma-separated). '
            'Each provider decides which platform-specific source argument it supports '
            '(--channel, --channel-id, --subreddit, --profile) and, if a requested '
            'argument is unsupported, falls back to public query-based discovery rather '
            'than being skipped. Results are normalized to a common schema across '
            'platforms. Supported platforms: telegram (query, channel), reddit '
            '(query, subreddit, user), discord (channel-id, query — query works '
            'without a token via web search; set DISCORD_BOT_TOKEN for full results), '
            'instagram (query, profile — query works without login via web search; '
            'set INSTAGRAM_SESSION_ID for direct profile scraping).'
        ),
    )
    social_parser.add_argument('--query', '-q', default=None, help='Search query (used directly by query-capable platforms, and as the fallback for platforms that do not support a requested source arg)')
    social_parser.add_argument('--platform', default=None, help='Comma-separated platform list, e.g. "telegram,reddit,discord" (default: all enabled providers)')
    social_parser.add_argument('--max', '-m', type=int, default=20, help='Max results per platform (posts / messages / channels)')
    # Platform-specific source arguments — none are required; each provider
    # decides whether it supports the ones supplied.
    social_parser.add_argument('--channel', default=None, help='(Telegram) public channel username, e.g. "durov" or a t.me URL')
    social_parser.add_argument('--channel-id', default=None, help='(Discord) numeric channel ID — requires DISCORD_BOT_TOKEN')
    social_parser.add_argument('--subreddit', default=None, help='(Reddit) restrict to one subreddit (or combine with +, e.g. python+programming)')
    social_parser.add_argument('--user', default=None, help='(Reddit) fetch a user\'s posts/comments via their public RSS feed')
    social_parser.add_argument('--profile', default=None, help='(Instagram) profile username to scrape, e.g. "natgeo" — 3-tier fallback: requests → Playwright → DDGS; set INSTAGRAM_SESSION_ID for reliable access')
    # Provider tuning
    social_parser.add_argument('--posts-per-channel', type=int, default=3, help='(Telegram --query mode) posts to preview per matched channel')
    social_parser.add_argument('--max-fetch-retries', type=int, default=3, help='(Telegram) retry attempts per fetch tier')
    social_parser.add_argument('--sort', default='relevance', choices=['relevance', 'hot', 'top', 'new', 'comments'], help='(Reddit) sort order')
    social_parser.add_argument('--before', default=None, help='(Discord) only messages before this message ID (pagination)')
    social_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/social_search_results.json)')
    social_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    social_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    social_parser.add_argument('--extract-full', action='store_true', help='(Reddit) best-effort full-page extraction of each top result\'s permalink (slower)')

    # Semantic search subcommand (Phase 1 — Mode B: indexed corpus search)
    sem_parser = subparsers.add_parser(
        'semantic-search',
        help='Search the persistent semantic index (hybrid BM25+vector)',
        description=(
            'Search a persistent corpus of previously-indexed documents using hybrid '
            'BM25 + dense-vector retrieval. Use `scout-it index` to build the corpus first.\n\n'
            'Storage: ~/.scout-it/semantic/lancedb/\n'
            'Model: configurable via SCOUT_SEMANTIC_MODEL env var (default: BAAI/bge-m3)'
        ),
    )
    sem_parser.add_argument('--query', '-q', required=True, help='Search query')
    sem_parser.add_argument('--max', '-m', type=int, default=10, help='Max results')
    sem_parser.add_argument('--out', '-o', default=None, help='Output file (default: .scout-it/semantic_results.json)')
    sem_parser.add_argument('--markdown', action='store_true', help='Save results as Markdown (.md) instead of JSON')
    sem_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    # Index subcommand (Phase 1 — Mode B: build persistent corpus)
    index_parser = subparsers.add_parser(
        'index',
        help='Index search results into the persistent semantic store',
        description=(
            'Fetch, extract, chunk, and embed web-search results into the persistent '
            'LanceDB store at ~/.scout-it/semantic/lancedb/. The corpus then powers '
            '`scout-it semantic-search` and survives across runs.\n\n'
            'Needs: pip install sentence-transformers torch lancedb'
        ),
    )
    index_parser.add_argument('--query', '-q', required=True, help='Query to fetch and index')
    index_parser.add_argument('--max', '-m', type=int, default=20, help='Max results to fetch and index')
    index_parser.add_argument('--source', default='web', choices=['web', 'news'], help='Source to fetch from')

    # Source search subcommand removed — --sources flag added to web-search,
    # news-search, image-search, video-search, multi-search instead.

    # Sources subcommand — list available source plugins
    sources_parser = subparsers.add_parser(
        'sources',
        help='List available academic/dataset/knowledge source plugins',
        description=(
            'List all source plugins available via the --sources flag on '
            'web-search, news-search, image-search, video-search, and multi-search. '
            'All sources are free or have free tiers.'
        ),
    )
    sources_parser.add_argument('--json', action='store_true', help='Output as JSON')


    return parser


def main():
    ds_config.load_stored_credentials_into_env()

    parser = build_parser()

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    # Centralized --out / --markdown resolution: honors an explicit --out,
    # falls back to the command's default filename under .scout-it/, and
    # rejects the --markdown + explicit --out-ending-in-.json combination.
    if args.command in COMMAND_OUTPUT_STUBS and hasattr(args, 'out'):
        stub = COMMAND_OUTPUT_STUBS[args.command]
        out_arg = args.out if args.out is not None else f'{output_mod.DEFAULT_OUTPUT_DIR}/{stub}.json'
        resolved = output_mod.resolve_output_path(out_arg, getattr(args, 'markdown', False), stub)
        if 'error' in resolved:
            print(f"❌ Error: {resolved['error']}\n")
            return
        args.out = str(resolved['path'])

    if args.command == 'image-search':
        if args.min_width is not None and args.max_width is not None and args.min_width > args.max_width:
            parser.error('--min-width cannot be greater than --max-width')
        if args.min_height is not None and args.max_height is not None and args.min_height > args.max_height:
            parser.error('--min-height cannot be greater than --max-height')
    
    # Web search
    if args.command == 'web-search':
        print(f"\n🔍 Starting web search: '{args.query}'\n")
        
        # Adjust default max_results based on mode
        max_results = args.max
        if max_results is None:
            max_results = 30 if args.snippets else 10
        
        structured_results, stats = web_search(
            args.query,
            max_results=max_results,
            workers=args.workers,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            backend=args.backend,
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
            enable_alternate_source=args.enable_alternate_source,
            enable_dns_fallback=args.enable_dns_fallback,
            enable_tls_impersonate=args.enable_tls_impersonate,
            enable_persistent_profile=args.enable_persistent_profile,
            browser_profile_name=args.browser_profile_name,
            enable_bandit=args.enable_bandit,
            source=args.source,
            categories=args.category,
            snippets_only=args.snippets,
        )
        
        output = {
            'query': args.query,
            'search_type': 'web',
            'mode': 'snippets' if args.snippets else 'full',
            'parameters': {
                'max_results': max_results,
                'workers': args.workers,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'backend': args.backend,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
                'max_fetch_retries': args.max_fetch_retries,
                'enable_js_fallback': args.enable_js_fallback,
                'snippets_only': args.snippets,
            },
            'stats': stats,
            'structured_results': structured_results
        }

        if getattr(args, 'enable_semantic', False):
            from .semantic import semantic_rerank, is_available as _sem_ok
            print('   🧠 Semantic re-ranking: enabled' + ('' if _sem_ok() else ' (BM25-only — install sentence-transformers torch for full vector+cross-encoder reranking)'))
            structured_results = semantic_rerank(structured_results, args.query)
            output['structured_results'] = structured_results
            output['semantic_reranked'] = True
        # --sources / --auto-sources: augment with source plugin results
        if getattr(args, 'sources', None) or getattr(args, 'auto_sources', False):
            from .sources import augment_search_with_sources
            from .sources.source_bandit import classify_query as _classify
            use_bandit = getattr(args, 'auto_sources', False) and not getattr(args, 'sources', None)
            if use_bandit:
                _qt = _classify(args.query)
                print(f'   🎰 Source-selection bandit: picking best sources for query type "{_qt}"...')
            else:
                source_names = [s.strip() for s in args.sources.split(',') if s.strip()]
                print(f'   📡 Augmenting with source plugins: "{", ".join(source_names)}"')
            structured_results = augment_search_with_sources(
                args.query,
                structured_results,
                getattr(args, 'sources', None),
                max_final=max_results,
                max_per_source=max(5, max_results // 2),
                default_source='web',
                semantic_rerank=True,
                composite_rerank=True,
                use_source_bandit=use_bandit,
                search_type='web',
            )
            output['structured_results'] = structured_results
            if not use_bandit:
                output['source_plugins'] = source_names
            print(f'   📊 Merged → {len(structured_results)} ranked results')
            _print_source_messages()


        
        out_path = Path(args.out)
        _write_output(out_path, output)

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
            categories=args.category,
            include_rss=args.rss,
            source=args.source,
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
                'categories': args.category,
                'include_rss': args.rss,
                'source': args.source,
            },
            'stats': stats,
            'image_results': image_results
        }
        
        # --sources / --auto-sources: augment with source plugin results
        if getattr(args, 'sources', None) or getattr(args, 'auto_sources', False):
            from .sources import augment_search_with_sources
            from .sources.source_bandit import classify_query as _classify
            use_bandit = getattr(args, 'auto_sources', False) and not getattr(args, 'sources', None)
            if use_bandit:
                _qt = _classify(args.query)
                print(f'   🎰 Source-selection bandit: picking best sources for query type "{_qt}"...')
            else:
                source_names = [s.strip() for s in args.sources.split(',') if s.strip()]
                print(f'   📡 Augmenting with source plugins: "{", ".join(source_names)}"')
            image_results = augment_search_with_sources(
                args.query,
                image_results,
                getattr(args, 'sources', None),
                max_final=args.max or 10,
                max_per_source=max(5, (args.max or 10) // 2),
                default_source='web',
                semantic_rerank=True,
                composite_rerank=True,
                use_source_bandit=use_bandit,
                search_type='image',
            )
            output['structured_results'] = image_results
            if not use_bandit:
                output['source_plugins'] = source_names
            print(f'   📊 Merged → {len(image_results)} ranked results')
            _print_source_messages()

        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ IMAGE SEARCH COMPLETE!')
        print(f'   🖼️  Query: {args.query}')
        print(f'   📊 Total images found: {len(image_results)}')
        print(f'   ✅ Valid URLs: {stats["search_engine"]["success"]}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"]["execution_time"]:.2f}s')
        
        # Download images if requested
        if args.download and image_results:
            from .extraction import ImageSearchResult
            engine = ImageSearchEngine()
            engine.results = [ImageSearchResult(**r) for r in image_results]
            # Route bare dir name under .scout-it/
            dl_dir = args.download_dir
            dl_path = Path(dl_dir)
            if not dl_path.is_absolute() and dl_path.parent == Path("."):
                dl_dir = str(Path(output_mod.DEFAULT_OUTPUT_DIR) / dl_path)
            engine.download_images(dl_dir, min(10, len(image_results)))
        
        print()

    # News search
    elif args.command == 'news-search':
        print(f"\n📰 Starting news search: '{args.query}'\n")

        # Ensure internet connection (silent on success, only shows if problem)
        if not ensure_internet_connection(max_retries=5, silent_on_success=True):
            sys.exit(1)

        # --max-chars and --max-size are mutually exclusive
        if args.max_chars is not None and args.max_size is not None:
            print("[red]Error: Cannot use both --max-chars and --max-size together. Use only ONE parameter:[/red]")
            print("   • --max-chars 10000 (to limit extracted content by character count)")
            print("   • --max-size 5mb (to limit response size by file size)")
            sys.exit(1)
        
        # Set default for --max based on mode
        max_results = args.max
        if max_results is None:
            max_results = 30 if args.snippets else 10

        news_results, stats = news_search(
            args.query,
            max_results=max_results,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            workers=getattr(args, 'workers', 3),
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
            enable_alternate_source=getattr(args, 'enable_alternate_source', False),
            enable_dns_fallback=getattr(args, 'enable_dns_fallback', False),
            enable_tls_impersonate=getattr(args, 'enable_tls_impersonate', False),
            enable_persistent_profile=getattr(args, 'enable_persistent_profile', False),
            browser_profile_name=getattr(args, 'browser_profile_name', None),
            enable_bandit=getattr(args, 'enable_bandit', True),
            source=args.source,
            locations=args.location,
            max_chars=args.max_chars,
            max_size=args.max_size,
            categories=args.category,
            snippets_only=args.snippets,
        )

        output = {
            'query': args.query,
            'search_type': 'news',
            'mode': 'snippets' if args.snippets else 'full_extraction',
            'parameters': {
                'max_results': max_results,
                'snippets_only': args.snippets,
                'workers': args.workers if hasattr(args, 'workers') else 3,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
                'max_fetch_retries': args.max_fetch_retries,
                'enable_js_fallback': args.enable_js_fallback,
            },
            'stats': stats,
            'structured_results': news_results,
        }
        # --sources / --auto-sources: augment with source plugin results
        if getattr(args, 'sources', None) or getattr(args, 'auto_sources', False):
            from .sources import augment_search_with_sources
            from .sources.source_bandit import classify_query as _classify
            use_bandit = getattr(args, 'auto_sources', False) and not getattr(args, 'sources', None)
            if use_bandit:
                _qt = _classify(args.query)
                print(f'   🎰 Source-selection bandit: picking best sources for query type "{_qt}"...')
            else:
                source_names = [s.strip() for s in args.sources.split(',') if s.strip()]
                print(f'   📡 Augmenting with source plugins: "{", ".join(source_names)}"')
            news_results = augment_search_with_sources(
                args.query,
                news_results,
                getattr(args, 'sources', None),
                max_final=max_results,
                max_per_source=max(5, max_results // 2),
                default_source='web',
                semantic_rerank=True,
                composite_rerank=True,
                use_source_bandit=use_bandit,
                search_type='news',
            )
            output['structured_results'] = news_results
            if not use_bandit:
                output['source_plugins'] = source_names
            print(f'   📊 Merged → {len(news_results)} ranked results')
            _print_source_messages()


        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ NEWS SEARCH COMPLETE!')
        print(f'   📰 Query: {args.query}')
        print(f'   📊 Total candidates discovered: {stats["search_engine"].get("total", 0)}')
        
        # Different output for snippets vs full extraction mode
        if args.snippets:
            # Snippets mode: show snippet count
            snippets_returned = len(news_results)
            snippets_requested = max_results
            print(f'   ✅ Snippets returned: {snippets_returned}')
            print(f'   🎯 Snippets requested: {snippets_requested}')
            print(f'   📋 Mode: snippets (no extraction)')
        else:
            # Full extraction mode: show extraction stats
            print(f'   ✅ Successfully extracted: {stats.get("cleaner", {}).get("successful", 0)}')
            print(f'   ❌ Failed (ignored): {stats.get("cleaner", {}).get("failed", 0)}')
            print(f'   📋 Mode: full extraction')
        
        print(f'   📄 Structured JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"].get("execution_time", 0.0):.1f}s\n')

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
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            categories=args.category,
            include_rss=args.rss,
        )

        # Enhance truncated DDGS descriptions with full YouTube descriptions
        video_results = _enhance_video_descriptions(video_results)

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
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
                'categories': args.category,
                'include_rss': args.rss,
            },
            'stats': stats,
            'video_results': video_results,
        }
        # --sources / --auto-sources: augment with source plugin results
        if getattr(args, 'sources', None) or getattr(args, 'auto_sources', False):
            from .sources import augment_search_with_sources
            from .sources.source_bandit import classify_query as _classify
            use_bandit = getattr(args, 'auto_sources', False) and not getattr(args, 'sources', None)
            if use_bandit:
                _qt = _classify(args.query)
                print(f'   🎰 Source-selection bandit: picking best sources for query type "{_qt}"...')
            else:
                source_names = [s.strip() for s in args.sources.split(',') if s.strip()]
                print(f'   📡 Augmenting with source plugins: "{", ".join(source_names)}"')
            video_results = augment_search_with_sources(
                args.query,
                video_results,
                getattr(args, 'sources', None),
                max_final=args.max or 10,
                max_per_source=max(5, (args.max or 10) // 2),
                default_source='web',
                semantic_rerank=True,
                composite_rerank=True,
                use_source_bandit=use_bandit,
                search_type='web',
            )
            output['structured_results'] = video_results
            if not use_bandit:
                output['source_plugins'] = source_names
            print(f'   📊 Merged → {len(video_results)} ranked results')
            _print_source_messages()


        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ VIDEO SEARCH COMPLETE!')
        print(f'   🎬 Query: {args.query}')
        print(f'   📊 Total videos found: {len(video_results)}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"].get("execution_time", 0.0):.2f}s\n')

    # Video extract
    elif args.command == 'video-extract':
        print(f"\n🎥 Extracting video details: {args.url}\n")

        lang = getattr(args, 'subtitle_lang', 'en') or 'en'
        include_segments = getattr(args, 'segments', False)
        result = video_extract(
            args.url,
            subtitle_lang=lang,
            include_segments=include_segments,
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
        )

        # Handle error cases
        if "error" in result:
            err_code = result.get("error", "unknown")
            err_msg = result.get("error_message", "Unknown error")

            if err_code == "invalid_url":
                print(f'   [ERR] Invalid URL: {err_msg}')
            elif err_code == "unsupported_platform":
                print(f'   [ERR] Unsupported platform: {err_msg}')
                print(f'   [OK]  Supported platforms: {", ".join(result.get("supported_platforms", []))}')
            elif err_code in ("video_not_found", "http_error", "network_error", "timeout"):
                print(f'   [ERR] {err_msg}')
            else:
                print(f'   [ERR] {err_msg}')
            print(f'   [HINT] Provide a valid YouTube URL: scout-it video-extract --url "https://www.youtube.com/watch?v=VIDEO_ID"')
            print(f'   [HINT] Other video platforms coming soon.\n')

            # Still save error result to output for debugging
            output = result
            out_path = Path(args.out)
            _write_output(out_path, output)
        else:
            platform = result.get("platform", "unknown")
            title = result.get("title", "Unknown")
            channel = result.get("channel", "Unknown")
            views = result.get("view_count", 0)
            duration = result.get("duration_seconds", 0)
            has_subs = result.get("subtitles") is not None
            subs_error = result.get("subtitles_error")
            avail_langs = result.get("available_subtitle_languages")
            req_lang = result.get("requested_subtitle_language", "en")

            print(f'   ✅ Platform: {platform}')
            print(f'   ✅ Title: {title}')
            print(f'   📺 Channel: {channel}')
            print(f'   👁️  Views: {views:,}')
            print(f'   ⏱️  Duration: {duration}s')

            if subs_error:
                print(f'   [!]  Subtitles: {subs_error}')
                if avail_langs:
                    print(f'   [OK]  Available subtitle languages:')
                    for lang in avail_langs:
                        tag = " (auto-generated)" if lang["generated"] and "auto-generated" not in lang["name"] else ""
                        print(f'         - {lang["code"]}: {lang["name"]}{tag}')

            if has_subs:
                sub_lang = result["subtitles"].get("language_code", "?")
                print(f'   📝 Subtitles: Available ({sub_lang})')
            elif not subs_error:
                print(f'   📝 Subtitles: Not available')

            output = result

            out_path = Path(args.out)
            _write_output(out_path, output)
        if not args.json:
            if "error" in result:
                print(f'\n   [ERR] Extraction failed. Details saved to: {out_path.resolve()}\n')
            else:
                print(f'\n   ✅ VIDEO EXTRACTION COMPLETE!')
                print(f'   📄 Results saved to: {out_path.resolve()}\n')
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))

    # Wikimedia search
    elif args.command == 'wikipedia-search':
        print(f"\n🌐 Starting Wikipedia search: '{args.query}' [{args.project}]\n")

        results, stats = wikipedia_search(
            args.query,
            max_results=args.max,
            project=args.project,
            language=args.language,
            timeout=args.timeout,
            workers=args.workers,
            summary=args.summary,
            extract=args.extract,
            sections=args.sections,
            crawl=args.crawl,
            crawl_depth=args.crawl_depth,
            bundle=args.bundle,
            robots=args.robots,
            clean_text=args.clean_text,
            categories=args.category,
            include_rss=getattr(args, 'rss', False),
        )

        output = {
            'query': args.query,
            'project': args.project,
            'stats': stats,
            'results': results,
        }

        # Determine output path
        out_filename = args.out if args.out else f".scout-it/{OUTPUT_MAP.get('wikipedia-search', 'wikipedia_search_results')}.{'md' if args.markdown else 'json'}"
        out_path = Path(out_filename)

        # Write output
        if args.markdown:
            from .output import render_markdown
            md = render_markdown(output)
            out_path.write_text(md, encoding='utf-8')
        else:
            _write_output(out_path, output)

        # JSON to stdout
        if getattr(args, 'json', False):
            print(json.dumps(output, indent=2, ensure_ascii=False))

        print(f'\n✅ WIKIMEDIA SEARCH COMPLETE!')
        print(f'   🌐 Project: {args.project}')
        print(f'   📊 Total results: {len(results)}')
        ext_stats = stats.get("extraction", {})
        if ext_stats:
            print(f'   ✅ Successfully extracted: {ext_stats.get("successful", 0)}')
            print(f'   ❌ Failed (ignored): {ext_stats.get("failed", 0)}')
        print(f'   📄 Results saved to: {out_path.resolve()}')
        if args.summary:
            print(f'   📝 Mode: Summary')
        elif args.extract:
            print(f'   📝 Mode: Extract')
        elif args.sections:
            print(f'   📝 Mode: Sections')
        elif args.crawl:
            print(f'   📝 Mode: Crawl (depth: {args.crawl_depth})')
        elif args.bundle:
            print(f'   📝 Mode: Bundle (all 12 projects)')
        else:
            print(f'   📝 Mode: Search')
        if stats.get("errors"):
            print(f'   ⚠️  Errors: {stats["errors"]}')

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
            js_render=args.js_render,
            no_js_fallback=args.no_js_fallback,
            max_retries=args.max_retries,
            enable_alternate_source=args.enable_alternate_source,
            enable_persistent_profile=args.enable_persistent_profile,
            browser_profile_name=args.browser_profile_name,
        )

        output = {
            'url': args.url,
            'search_type': 'fetch',
            'parameters': {
                'timeout': args.timeout,
                'max_chars': args.max_chars,
                'max_size': args.max_size,
                'raw_html': args.raw_html,
                'js_render': args.js_render,
                'no_js_fallback': args.no_js_fallback,
                'max_retries': args.max_retries,
            },
            'result': result
        }

        out_path = Path(args.out)
        _write_output(out_path, output)

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

    # ==========================================================================
    # multi-search
    # ==========================================================================
    elif args.command == 'multi-search':
        engine_list = [e.strip() for e in args.engines.split(',') if e.strip()]
        _cmd_timer = _PhaseTimer(f"multi-search '{args.query}'", engines=engine_list)
        with _cmd_timer:
            structured_results, stats = multi_search(
                args.query,
                engines=engine_list,
                max_results=args.max,
                workers=args.workers,
                max_fetch_retries=args.max_fetch_retries,
                enable_js_fallback=args.enable_js_fallback,
                dedupe=args.dedupe,
                serpapi_engine=args.serpapi_engine,
                source=args.source,
            )
        output = {
            'query': args.query,
            'search_type': 'multi-engine',
            'parameters': {'engines': engine_list, 'max_results': args.max, 'workers': args.workers},
            'stats': stats,
            'structured_results': structured_results,
        }

        if getattr(args, 'enable_semantic', False):
            from .semantic import semantic_rerank, is_available as _sem_ok
            print('   🧠 Semantic re-ranking: enabled' + ('' if _sem_ok() else ' (BM25-only — install sentence-transformers torch for full vector+cross-encoder reranking)'))
            structured_results = semantic_rerank(structured_results, args.query)
            output['structured_results'] = structured_results
            output['semantic_reranked'] = True

        # --sources / --auto-sources: augment with source plugin results
        if getattr(args, 'sources', None) or getattr(args, 'auto_sources', False):
            from .sources import augment_search_with_sources
            from .sources.source_bandit import classify_query as _classify
            use_bandit = getattr(args, 'auto_sources', False) and not getattr(args, 'sources', None)
            if use_bandit:
                _qt = _classify(args.query)
                print(f'   🎰 Source-selection bandit: picking best sources for query type "{_qt}"...')
            else:
                source_names = [s.strip() for s in args.sources.split(',') if s.strip()]
                print(f'   📡 Augmenting with source plugins: "{", ".join(source_names)}"')
            structured_results = augment_search_with_sources(
                args.query,
                structured_results,
                getattr(args, 'sources', None),
                max_final=args.max,
                max_per_source=max(5, args.max // 2),
                default_source='web',
                semantic_rerank=True,
                composite_rerank=True,
                use_source_bandit=use_bandit,
                search_type='multi',
            )
            output['structured_results'] = structured_results
            if not use_bandit:
                output['source_plugins'] = source_names
            print(f'   📊 Merged → {len(structured_results)} ranked results')
            _print_source_messages()

        out_path = Path(args.out)
        _write_output(out_path, output)
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            skipped = stats['discovery'].get('skipped', [])
            _cmd_timer.done(engines_run=stats['discovery'].get('engines_run', []), results=len(structured_results))
            if skipped:
                print(f"   ⏭️  Skipped: {[s['engine'] for s in skipped]} (run `scout-it list-engines` for setup hints)")
            print(f'   📂 Results saved to: {out_path.resolve()}\n')

    # ==========================================================================
    # list-engines
    # ==========================================================================
    elif args.command == 'list-engines':
        print("\n🌐 SEARCH ENGINES\n")
        for info in search_engines.list_engines():
            status = "✅ configured" if info['configured'] else "⚪ not configured"
            tier_tag = "zero-config" if info['tier'] == 0 else "needs API key"
            print(f"  {info['name']:<12} [{tier_tag:<14}] {status}")
            if not info['configured']:
                print(f"      → {info['setup_hint']}")
        print(
            "\nNote: Google/Bing/Yahoo/Opera search-result *pages* can't be scraped directly "
            "(anti-bot + ToS). The engines above use each provider's official API instead — "
            "SerpAPI additionally proxies Yahoo/Baidu/Yandex/etc. via --serpapi-engine.\n"
            "Run `scout-it config` to set up API keys interactively.\n"
        )

    # ==========================================================================
    # config
    # ==========================================================================
    elif args.command == 'config':
        if args.clear_all:
            ds_config.clear_all_credentials()
            print("✅ All stored credentials cleared.\n")
        elif args.clear:
            if ds_config.clear_credential(args.clear):
                print(f"✅ Cleared stored credential: {args.clear}\n")
            else:
                print(f"⚪ No stored credential found for: {args.clear}\n")
        elif args.show:
            ds_config.print_credential_status()
        else:
            ds_config.run_config_wizard()

    # ==========================================================================
    # stats -- strategy cache introspection
    # ==========================================================================
    elif args.command == 'stats':
        if getattr(args, 'sources', False):
            from .sources.source_bandit import get_source_stats, reset_bandit
            stats = get_source_stats()
            if not stats:
                print("⚪ No source-selection history yet -- run searches with --auto-sources to start learning.\n")
            else:
                print(f"\n🎰 Source-selection bandit: {len(stats)} query type(s) learned\n")
                for qt, sources in sorted(stats.items()):
                    # Sort by success rate descending
                    ranked = sorted(sources.items(), key=lambda x: (x[1]['total'], x[1]['successes']/max(x[1]['total'],1)), reverse=True)
                    print(f"  📂 {qt} ({len(sources)} sources tried):")
                    for src, s in ranked[:8]:
                        rate = s['successes']/s['total'] if s['total'] else 0
                        print(f"     {src:<25} {s['successes']:>2}/{s['total']:<2} ({rate:.0%}) avg_rel={s['avg_relevance']:.2f}")
                    print()
        elif args.reset_all:
            domains = strategy_cache.all_known_domains()
            for d in domains:
                strategy_cache.reset_domain(d)
            print(f"✅ Cleared strategy history for {len(domains)} domain(s).\n")
        elif args.reset:
            removed = strategy_cache.reset_domain(args.reset)
            print(f"✅ Cleared {removed} recorded attempt(s) for {args.reset}.\n" if removed else f"⚪ No history found for {args.reset}.\n")
        elif args.export:
            export = strategy_cache.export_all()
            out_path = Path(args.export)
            # Bare filename lands under .scout-it/
            if not out_path.is_absolute() and out_path.parent == Path("."):
                out_path = Path(output_mod.DEFAULT_OUTPUT_DIR) / out_path
            output_mod.write_json_output(out_path, export)
            print(f"✅ Exported stats for {export['domain_count']} domain(s) to {out_path.resolve()}\n")
        elif args.domain:
            stats_result = strategy_cache.get_domain_stats(args.domain)
            if not stats_result["known"]:
                print(f"⚪ No recorded history for {args.domain} yet.\n")
            else:
                print(f"\n📊 {args.domain}")
                print(f"   Attempts: {stats_result['total_attempts']}, success rate: {stats_result['overall_success_rate']:.0%}")
                best = stats_result["best_arm"]
                print(f"   Best strategy: tier={best['tier']}, proxy={best['proxy_id']}, success_rate={best['success_rate']:.0%}")
                print(f"   {stats_result['arm_count']} strategy combination(s) tried total.\n")
        else:
            domains = strategy_cache.all_known_domains()
            if not domains:
                print("⚪ No strategy history recorded yet -- run some searches/fetches first.\n")
            else:
                print(f"\n📊 Strategy cache: {len(domains)} known domain(s)\n")
                for d in domains:
                    s = strategy_cache.get_domain_stats(d)
                    best = s["best_arm"]
                    print(f"  {d:<30} {s['total_attempts']:>4} attempts, {s['overall_success_rate']:.0%} success, best: {best['tier']}/{best['proxy_id']}")
                print()

    # ==========================================================================
    # doctor -- environment self-check
    # ==========================================================================
    elif args.command == 'doctor':
        print("\n🩺 scout-it doctor\n")

        # Playwright
        try:
            from playwright.sync_api import sync_playwright
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    browser.close()
                print("  ✅ Playwright: installed and Chromium launches successfully")
            except Exception as e:
                print(f"  ⚠️  Playwright: package installed, but Chromium failed to launch ({type(e).__name__}: {e})")
                print("      → run: playwright install chromium")
        except ImportError:
            print("  ⚪ Playwright: not installed (Tier 2 JS-render fallback unavailable)")
            print("      → pip install scout-it[js-render] && playwright install chromium")

        # Proxy pool
        pool = proxy_pool.get_default_pool()
        if pool.configured:
            print(f"  ✅ Proxy pool: {len(pool._proxies)} proxy/proxies configured")
        else:
            print("  ⚪ Proxy pool: not configured (PROXY_LIST unset) -- fetches go direct, which is fine for most use")

        # Response cache
        cache_stats = response_cache.stats()
        print(f"  ℹ️  Response cache: {cache_stats['entry_count']} entries, {cache_stats['total_size_bytes'] / 1024:.1f} KB at {cache_stats['cache_dir']}")

        # Strategy cache
        known_domains = strategy_cache.all_known_domains()
        print(f"  ℹ️  Strategy cache: {len(known_domains)} domain(s) with recorded history")

        # Credentials
        configured_creds = [c for c in ds_config.credential_status() if c["configured"]]
        print(f"  ℹ️  Credentials: {len(configured_creds)}/{len(ds_config.KNOWN_CREDENTIALS)} configured (run `scout-it config --show` for details)")

        # Basic connectivity
        try:
            probe_result = canary_probe.probe("https://www.google.com", timeout=5)
            if probe_result["reachable"]:
                print(f"  ✅ Internet connectivity: reachable (status {probe_result['status_code']}, {probe_result['latency_ms']}ms)")
            else:
                print(f"  ❌ Internet connectivity: unreachable ({probe_result.get('error', 'unknown error')})")
        except Exception as e:
            print(f"  ❌ Internet connectivity check failed: {type(e).__name__}: {e}")

        print()

    # ==========================================================================
    # GitHub extraction commands
    # ==========================================================================
    elif args.command == 'github-repo':
        _cmd_timer = _PhaseTimer(f"github-repo {args.repo}", mode="full" if args.full else "quick")
        with _cmd_timer:
            result = gh.github_repo(
                args.repo, full=args.full, include_file_tree=args.file_tree,
                max_chars=args.max_chars, max_size=args.max_size,
            )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            _cmd_timer.failed(reason=result['error'])
            print(f"❌ Error: {result['error_message']}\n")
        else:
            _cmd_timer.done(stars=result['stars'], forks=result['forks'])
            if args.full:
                print(f"   {result.get('branch_count', '?')} branches, ~{result.get('commit_count_approx', '?')} commits, "
                      f"{result.get('open_issues_only', '?')} open issues, {result.get('open_pull_requests', '?')} open PRs")
            if args.file_tree and isinstance(result.get('file_tree'), list):
                trunc_note = " (truncated by --max-chars/--max-size)" if result.get('file_tree_truncated') else ""
                print(f"   🌳 File tree: {result.get('file_tree_entries_returned', 0)}/{result.get('file_tree_total_entries', 0)} entries{trunc_note}")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-commits':
        result = gh.github_commits(
            args.repo, branch=args.branch, path=args.path, author=args.author,
            since=args.since, until=args.until, max_results=args.max,
        )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['commit_count']} commits found\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-commit':
        _cmd_timer = _PhaseTimer(f"github-commit {args.repo}@{args.sha[:12]}")
        with _cmd_timer:
            result = gh.github_commit(args.repo, args.sha, include_patch=args.include_patch)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            _cmd_timer.failed(reason=result['error'])
            print(f"❌ Error: {result['error_message']}\n")
        else:
            stats = result.get('stats', {})
            _cmd_timer.done(files_changed=result['files_changed'], additions=stats.get('additions', 0), deletions=stats.get('deletions', 0))
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-pr':
        _cmd_timer = _PhaseTimer(f"github-pr {args.repo}#{args.number}")
        with _cmd_timer:
            result = gh.github_pull_request(args.repo, args.number, include_diff=args.include_diff)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            _cmd_timer.failed(reason=result['error'])
            print(f"❌ Error: {result['error_message']}\n")
        else:
            _cmd_timer.done(state=result['state'], merged=result.get('is_merged', False))
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-prs':
        result = gh.github_prs(args.repo, state=args.state, sort=args.sort, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['pr_count']} pull requests found\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-folder':
        _cmd_timer = _PhaseTimer(f"github-folder {args.repo}:{args.path or '/'}", recursive=args.recursive)
        with _cmd_timer:
            # Route bare save-path-dir under .scout-it/
            sp_dir = args.save_path_dir
            if sp_dir is not None:
                sp_path = Path(sp_dir)
                if not sp_path.is_absolute() and sp_path.parent == Path("."):
                    sp_dir = str(Path(output_mod.DEFAULT_OUTPUT_DIR) / sp_path)
            result = gh.github_folder(
                args.repo, path=args.path, ref=args.ref, recursive=args.recursive,
                include_content=args.include_content, max_files=args.max_files,
                max_chars=args.max_chars, max_size=args.max_size, save_path_dir=sp_dir,
            )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            _cmd_timer.failed(reason=result['error'])
            print(f"❌ Error: {result['error_message']}\n")
        else:
            _cmd_timer.done(entries=result['entry_count'], files_fetched=result.get('files_fetched', 0) if args.include_content else 'n/a')
            if sp_dir and "files_saved_to_disk" in result:
                print(f"   💾 {result['files_saved_to_disk']} files written to: {Path(sp_dir).resolve()}")
                if result.get("save_errors"):
                    print(f"   ⚠️  {len(result['save_errors'])} files failed to save (see 'save_errors' in output)")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-issues':
        result = gh.github_issues(
            args.repo, state=args.state, labels=args.labels, max_results=args.max,
            include_pull_requests=args.include_pull_requests,
        )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['issue_count']} issues found\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-issue':
        result = gh.github_issue(args.repo, args.number, include_comments=args.include_comments)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ Issue #{result['number']}: {result['title']} [{result['state']}], "
                  f"{len(result.get('comments', []))} comments loaded")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-file':
        result = gh.github_file_content(args.repo, args.path, ref=args.ref)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['path']} ({result['size_bytes']} bytes)\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-search-code':
        result = gh.github_search_code(args.query, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['total_count']} total matches ({len(result['results'])} returned)\n"
                  f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-search-repos':
        result = gh.github_search_repos(args.query, sort=args.sort, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['total_count']} total matches ({len(result['results'])} returned)\n"
                  f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-discussions':
        result = gh.github_discussions(args.repo, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['total_count']} discussions found\n   📂 Results saved to: {out_path.resolve()}\n")

    # ==========================================================================
    # Social/platform command — unified social-search
    # ==========================================================================
    elif args.command == 'social-search':
        if not args.query and not args.channel and not args.channel_id \
                and not args.subreddit and not args.profile and not args.user:
            print(
                "❌ Error: provide at least one of --query, --channel, --channel-id, "
                "--subreddit, --user, or --profile. Run `scout-it social-search --help` for the "
                "capability/fallback rules.\n"
            )
        else:
            label = f"social-search '{args.query or args.channel or args.channel_id or args.subreddit or args.user or args.profile}'"
            _cmd_timer = _PhaseTimer(label, platform=args.platform or "all")
            with _cmd_timer:
                result = social.social_search(
                    query=args.query,
                    platform=args.platform,
                    channel=args.channel,
                    channel_id=args.channel_id,
                    subreddit=args.subreddit,
                    profile=args.profile,
                    user=args.user,
                    max_results=args.max,
                    sort=args.sort,
                    posts_per_channel=args.posts_per_channel,
                    max_fetch_retries=args.max_fetch_retries,
                    before=args.before,
                    extract_full=args.extract_full,
                )
            out_path = Path(args.out)
            _write_output(out_path, result)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                total = result.get("total_results", 0)
                failures = result.get("failures", [])
                platforms = result.get("platforms", [])
                if total == 0 and not failures:
                    _cmd_timer.done(results=0, platforms=",".join(platforms))
                    print("ℹ️  No results returned by any provider.\n")
                elif total == 0 and failures:
                    reasons = "; ".join(f"{f['platform']}: {f['error']}" for f in failures)
                    _cmd_timer.failed(reason="all providers failed")
                    print(f"❌ No results. Provider failures: {reasons}\n")
                else:
                    _cmd_timer.done(results=total, platforms=",".join(platforms),
                                    failures=len(failures))
                    if failures:
                        for f in failures:
                            print(f"   ⚠️  {f['platform']}: {f['error_message']}")
                    print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'index':
        _cmd_timer = _PhaseTimer(f"index '{args.query}'")
        with _cmd_timer:
            from .semantic import SemanticIndex, is_available as _sem_ok
            if not _sem_ok():
                print('❌ Semantic indexing requires: pip install sentence-transformers torch lancedb')
                return
            if args.source == 'news':
                structured_results, stats = news_search(args.query, max_results=args.max, snippets_only=True)
            else:
                structured_results, stats = web_search(args.query, max_results=args.max)
            idx = SemanticIndex()
            chunks = idx.add_documents(structured_results, source=args.source)
        print(f"   ✅ Indexed {chunks} chunks from {len(structured_results)} documents into ~/.scout-it/semantic/lancedb/")
        print(f"   🔍 Search them with: scout-it semantic-search -q '<your query>'\n")

    elif args.command == 'semantic-search':
        _cmd_timer = _PhaseTimer(f"semantic-search '{args.query}'")
        with _cmd_timer:
            from .semantic import SemanticIndex, is_available as _sem_ok
            if not _sem_ok():
                print('❌ Semantic search requires: pip install sentence-transformers torch lancedb')
                return
            idx = SemanticIndex()
            count = idx.count()
            if count == 0:
                print('📭 No indexed documents found. Build a corpus first with: scout-it index -q "<query>"')
                return
            results = idx.search(args.query, top_k=args.max)
        output = {
            'query': args.query,
            'search_type': 'semantic',
            'indexed_chunks': count,
            'structured_results': results,
        }
        out_path = Path(args.out)
        _write_output(out_path, output)
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            _cmd_timer.done(results=len(results))
            print(f"   🧠 Searched {count} indexed chunks → {len(results)} results")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    # ==========================================================================
    # sources — list available source plugins
    # ==========================================================================
    elif args.command == 'sources':
        from .sources.source_config import source_status

        statuses = source_status()
        if getattr(args, 'json', False):
            print(json.dumps(statuses, indent=2, ensure_ascii=False))
        else:
            print(f"\n📡 Source Plugins ({len(statuses)} sources)\n")
            print(f"  Use the --sources flag on web-search, news-search, image-search,")
            print(f"  video-search, or multi-search to search these in parallel.\n")
            print(f"  {'Source':<20} {'Type':<12} {'Status':<12} {'Key':<10} Description")
            print(f"  {'─'*20} {'─'*12} {'─'*12} {'─'*10} {'─'*45}")
            for s in statuses:
                if s['configured']:
                    key_status = "✅" if s['requires_key'] else "—"
                else:
                    key_status = "❌" if s['requires_key'] else "—"
                status = "✅" if (s['enabled'] and s['configured']) else "⚪"
                desc = s['description'][:50]
                print(f"  {s['name']:<20} {s['content_type']:<12} {status:<12} {key_status:<10} {desc}")
            print(f"\n  Run `scout-it config` to set API keys for sources that need them.\n")


if __name__ == '__main__':
    main()
