"""
Helper functions for news search - DEPRECATED

⚠️  DEPRECATION NOTICE:
This module is now DEAD CODE and scheduled for removal.

The _extract_news_content() function was a 300-line duplicate of
EnterpriseSearchEngine._phase_content_extraction() from extraction.py.

Both web-search and news-search now use EnterpriseSearchEngine directly,
which provides the same features PLUS 5 advanced features:
  - enable_alternate_source (AMP/mobile/Wayback fallback)
  - enable_dns_fallback (DNS-over-HTTPS retry)
  - enable_tls_impersonate (TLS/JA3 fingerprinting)
  - enable_persistent_profile (persistent browser cookies)
  - enable_bandit (multi-armed bandit tier selection)

This file will be removed in a future cleanup.
See: COMPARISON_WEB_VS_NEWS.md for details.

DEPRECATED: 2026-08-06
REMOVAL TARGET: Next major version
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Any, Dict, List

# Import from parent package
from ..extraction import ExtractionEngine, fetch_resilient

# Initialize logger
logger = logging.getLogger(__name__)

# Error/404 page detection phrases — short content matching any of these
# indicates a broken or removed page (dead link from search engine).
_ERROR_PAGE_PHRASES = [
    "whoops", "page doesn't exist", "can't be found",
    "page not found", "this page could not be found",
    "sorry, this page",
]


def _extract_meta_description(html_text: str) -> str:
    """Extract meta description / og:description / twitter:description from HTML
    head. These are always full sentences (never truncated like search snippets).
    
    ⚠️  DEPRECATED: This function is no longer used.
    EnterpriseSearchEngine now handles meta description extraction internally.
    """
    if not html_text:
        return ""
    patterns = [
        r'<meta\s+name="description"\s+content="([^"]*)"',
        r'<meta\s+property="og:description"\s+content="([^"]*)"',
        r'<meta\s+name="twitter:description"\s+content="([^"]*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match and match.group(1).strip():
            return unescape(match.group(1).strip())
    return ""


def _extract_news_content(
    results: List[Dict[str, Any]],
    max_workers: int = 5,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch and extract full article content for news results in parallel.

    ⚠️  DEPRECATED: This entire function is now DEAD CODE.
    
    This was a 300-line duplicate of EnterpriseSearchEngine._phase_content_extraction()
    Both web-search and news-search now use EnterpriseSearchEngine directly.
    
    DEPRECATED: 2026-08-06
    REMOVAL TARGET: Next major version
    
    DO NOT USE THIS FUNCTION - it is no longer called by news_search.py
    """
    raise DeprecationWarning(
        "_extract_news_content() is deprecated and has been replaced by "
        "EnterpriseSearchEngine.execute_search_from_urls(). "
        "This function is scheduled for removal in the next major version."
    )
