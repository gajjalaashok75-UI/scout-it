"""Web Search RSS provider module.

This module provides RSS aggregation for web-search with category support.
Reuses core RSS functionality from tech_crunch_rss.py but uses web-focused feeds.
"""

from typing import Any, Dict, List, Optional, Sequence

# Import web search feed registry
from .web_search_feed import WEB_SEARCH_FEEDS

# Import core RSS functions from tech_crunch_rss
from .tech_crunch_rss import (
    TechCrunchRSSProvider,
    RSSProvider,
    deduplicate_entries,
    sort_entries,
    _domain_from_url,
    _feed_name_from_url,
    _enrich_entries,
    _log_event,
)

__all__ = [
    'WebSearchRSSProvider',
    'WEB_SEARCH_FEEDS',
    'get_all_web_feed_entries',
    'get_available_web_categories',
]


def _normalize_web_domains(domains: Optional[Sequence[str]]) -> List[str]:
    """Normalize domain names for web search (doesn't validate against TECHCRUNCH_FEEDS)."""
    if not domains:
        return []
    
    # Simple normalization - just clean and lowercase
    normalized = []
    for domain in domains:
        if domain:
            clean_domain = str(domain).strip().lower().replace('-', '_')
            # Check if it exists in WEB_SEARCH_FEEDS
            if clean_domain in WEB_SEARCH_FEEDS:
                normalized.append(clean_domain)
            else:
                # Try to find close match
                available = list(WEB_SEARCH_FEEDS.keys())
                raise ValueError(f"Unknown web search category: '{domain}'. Available categories: {', '.join(available)}")
    
    return normalized


class WebSearchRSSProvider(RSSProvider):
    """RSS provider for web search categories (engineering, research, etc.)."""
    
    name = "web-search"
    
    @property
    def feed_registry(self) -> Dict[str, List[Dict[str, Any]]]:
        return WEB_SEARCH_FEEDS
    
    def get_feed_urls(self, domain: Optional[str] = None) -> List[str]:
        """Get RSS feed URLs for a category."""
        if domain is None:
            # Get all URLs from all categories
            seen: set = set()
            urls: List[str] = []
            for cat in WEB_SEARCH_FEEDS.keys():
                for item in WEB_SEARCH_FEEDS.get(cat, []):
                    url = item["url"]
                    if url not in seen:
                        seen.add(url)
                        urls.append(url)
            return urls
        
        # Get URLs for specific category
        return [item["url"] for item in WEB_SEARCH_FEEDS.get(domain, [])]
    
    def get_all_feed_entries(
        self, 
        domains: Optional[Sequence[str]] = None, 
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Get ALL feed entries without query filtering.
        
        Returns all RSS entries from specified categories for later ranking.
        NO query filtering - just raw RSS entries with metadata.
        
        Args:
            domains: Categories to fetch from (e.g., ['ai', 'engineering'])
            limit: Max total entries to return (default: 500)
        
        Returns:
            List of ALL RSS entries ready for ranking
        """
        normalized_domains = _normalize_web_domains(domains) if domains else None
        urls: List[str] = []
        
        if normalized_domains:
            for domain in normalized_domains:
                urls.extend(self.get_feed_urls(domain))
        else:
            urls = self.get_feed_urls()
        
        if not urls:
            _log_event("get_all_web_entries_no_urls", domains=normalized_domains)
            return []
        
        _log_event("get_all_web_entries_start", 
                   feed_count=len(urls), 
                   domains=normalized_domains)
        
        # Fetch all feeds in parallel
        fetched = self.fetch_multiple_feeds(urls)
        entries: List[Dict[str, Any]] = []
        
        for url, content in fetched:
            if not content:
                continue
            
            dom = _domain_from_url(url, None)
            parsed = self.parse_feed(content, domain=dom)
            enriched = _enrich_entries(
                parsed, 
                feed_url=url, 
                feed_name=_feed_name_from_url(url), 
                category=dom
            )
            entries.extend(enriched)
        
        # Deduplicate but do NOT filter by query
        entries = deduplicate_entries(entries)
        
        _log_event("get_all_web_entries_complete", 
                   total_entries=len(entries),
                   feeds_fetched=len(urls),
                   domains=normalized_domains)
        
        # Return up to limit entries (sorted by date, newest first)
        sorted_entries = sort_entries(entries)
        return sorted_entries[: max(int(limit), 0)]
    
    # Inherit other methods from TechCrunchRSSProvider via parent class
    def validate_feed(self, url: str, timeout: float = 15.0) -> Dict[str, Any]:
        """Inherit from parent."""
        return super().validate_feed(url, timeout)
    
    def fetch_feed(self, url: str, timeout: float = 15.0) -> Optional[str]:
        """Inherit from parent - uses TechCrunchRSSProvider implementation."""
        # Create temporary TechCrunchRSSProvider to reuse fetch logic
        from .tech_crunch_rss import TechCrunchRSSProvider as TCProvider
        temp_provider = TCProvider()
        return temp_provider.fetch_feed(url, timeout)
    
    def fetch_multiple_feeds(self, urls: Sequence[str], timeout: float = 15.0, max_workers: int = 8) -> List[tuple]:
        """Inherit from parent."""
        from .tech_crunch_rss import TechCrunchRSSProvider as TCProvider
        temp_provider = TCProvider()
        return temp_provider.fetch_multiple_feeds(urls, timeout, max_workers)
    
    def parse_feed(self, feed: Any, domain: str = "all") -> List[Dict[str, Any]]:
        """Inherit from parent - but use UNLIMITED entries for web search."""
        from .tech_crunch_rss import TechCrunchRSSProvider as TCProvider, DEFAULT_CONFIG
        
        # Temporarily increase limit for web search (we want ALL entries)
        original_limit = DEFAULT_CONFIG.max_entries_per_feed
        DEFAULT_CONFIG.max_entries_per_feed = 10000  # Set very high limit (was 5000)
        
        try:
            temp_provider = TCProvider()
            result = temp_provider.parse_feed(feed, domain)
            return result
        finally:
            # Restore original limit
            DEFAULT_CONFIG.max_entries_per_feed = original_limit


# Global provider instance
_WEB_PROVIDER = WebSearchRSSProvider()


def get_all_web_feed_entries(
    categories: Optional[Sequence[str]] = None, 
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Get ALL web search RSS feed entries for specified categories.
    
    Public API function for web search RSS integration.
    
    Args:
        categories: Categories to fetch (e.g., ['ai', 'engineering', 'cloud'])
        limit: Max entries to return (default: 500)
    
    Returns:
        List of RSS entries ready for ranking
    """
    return _WEB_PROVIDER.get_all_feed_entries(domains=categories, limit=limit)


def get_available_web_categories() -> List[str]:
    """Get list of available web search RSS categories.
    
    Returns:
        Sorted list of category names
    """
    return sorted(WEB_SEARCH_FEEDS.keys())
