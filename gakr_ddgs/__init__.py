"""
gakr-ddgs: Enterprise-grade DuckDuckGo search toolkit with content extraction, cleaning, and structured JSON output.

Version: 1.0.0
Author: Ashok-gakr
License: MIT

Quick Start:
    from gakr_ddgs import search_web, search_images, search_news, search_videos
    
    # Web search with content extraction
    results, stats = search_web("python automation", max_results=10)
    
    # Image search
    images, stats = search_images("sunset landscapes", max_results=20)
    
    # News search
    news, stats = search_news("technology news", max_results=10)
    
    # Video search
    videos, stats = search_videos("python tutorial", max_results=10)
"""

from .cleaner import advanced_clean_text, process_results
from .extraction import (
    DDGS,
    EnterpriseResult,
    EnterpriseSearchEngine,
    ExtractionEngine,
    ImageSearchEngine,
    ImageSearchResult,
)

__version__ = "1.0.0"
__author__ = "Ashok-gakr"
__license__ = "MIT"

__all__ = [
    "EnterpriseSearchEngine",
    "EnterpriseResult",
    "ExtractionEngine",
    "ImageSearchEngine",
    "ImageSearchResult",
    "DDGS",
    "process_results",
    "advanced_clean_text",
]
