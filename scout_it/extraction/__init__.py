"""Extraction module - content extraction and search engines."""

# Import from new modular structure
from .types import EnterpriseResult, ImageSearchResult
from .engine import ExtractionEngine
from .fetcher import fetch_resilient
from .search import (
    EnterpriseSearchEngine,
    ImageSearchEngine,
    _compact_options,
    _ddg_html_lite_fallback_search,
    _ddgs_list_search,
    _ddgs_list_search_with_retry,
    _build_list_attempt_options,
)

# Re-export DDGS for backward compatibility
try:
    from ddgs import DDGS
except Exception:
    from duckduckgo_search import DDGS

__all__ = [
    "EnterpriseResult",
    "ImageSearchResult",
    "ExtractionEngine",
    "fetch_resilient",
    "DDGS",
    "EnterpriseSearchEngine",
    "ImageSearchEngine",
    "_compact_options",
    "_ddg_html_lite_fallback_search",
    "_ddgs_list_search",
    "_ddgs_list_search_with_retry",
    "_build_list_attempt_options",
]
