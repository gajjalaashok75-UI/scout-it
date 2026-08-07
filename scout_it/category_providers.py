"""
Category-aware RSS provider registry for news-search.

This module maintains a registry of RSS providers organized by news categories.
Providers can be easily added without modifying the news-search pipeline.

Architecture:
- CATEGORY_PROVIDERS: Maps categories to provider functions
- Each provider returns normalized news entries
- Results are merged with existing news sources (DuckDuckGo, Google News, ToI)
"""

from typing import Any, Dict, List, Optional, Sequence
import logging

logger = logging.getLogger(__name__)

# Provider function signature: (query, max_results, **kwargs) -> List[Dict[str, Any]]


def techcrunch_ai_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """TechCrunch AI news provider - returns ALL matching entries (no query filtering).
    
    Discovery-first approach: Return ALL RSS entries, let ranking decide relevance.
    """
    try:
        # Import using importlib for hyphenated folder name
        import importlib
        _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
        get_all_feed_entries = _tech_crunch_rss.get_all_feed_entries
        
        logger.info(f"Fetching ALL TechCrunch AI RSS entries (no query filtering)")
        # Get ALL entries from AI feeds (NO query filtering)
        results = get_all_feed_entries(domains=["ai"], limit=max_results)
        
        logger.info(f"TechCrunch AI: fetched {len(results)} total RSS entries")
        
        # Normalize to news-search format
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "source": f"techcrunch:{entry.get('domain', 'ai')}",
                "publish_date": entry.get("published", ""),
                "score": entry.get("score", 0),
                "author": entry.get("author", ""),
                "categories": entry.get("categories", []),  # Preserve RSS categories
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                    "categories": entry.get("categories", []),
                },
            })
        
        logger.info(f"TechCrunch AI provider returning {len(normalized)} entries for ranking")
        return normalized
        
    except Exception as e:
        logger.error(f"TechCrunch AI provider failed: {e}")
        return []


def techcrunch_startups_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """TechCrunch startups news provider - returns ALL matching entries (no query filtering)."""
    try:
        import importlib
        _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
        get_all_feed_entries = _tech_crunch_rss.get_all_feed_entries
        
        logger.info(f"Fetching ALL TechCrunch startups RSS entries (no query filtering)")
        results = get_all_feed_entries(domains=["startups", "venture"], limit=max_results)
        
        logger.info(f"TechCrunch startups: fetched {len(results)} total RSS entries")
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "source": f"techcrunch:{entry.get('domain', 'startups')}",
                "publish_date": entry.get("published", ""),
                "score": entry.get("score", 0),
                "author": entry.get("author", ""),
                "categories": entry.get("categories", []),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                    "categories": entry.get("categories", []),
                },
            })
        
        logger.info(f"TechCrunch startups provider returning {len(normalized)} entries for ranking")
        return normalized
        
    except Exception as e:
        logger.error(f"TechCrunch startups provider failed: {e}")
        return []


def techcrunch_security_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """TechCrunch security news provider - returns ALL matching entries (no query filtering)."""
    try:
        import importlib
        _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
        get_all_feed_entries = _tech_crunch_rss.get_all_feed_entries
        
        logger.info(f"Fetching ALL TechCrunch security RSS entries (no query filtering)")
        results = get_all_feed_entries(domains=["security"], limit=max_results)
        
        logger.info(f"TechCrunch security: fetched {len(results)} total RSS entries")
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "source": f"techcrunch:{entry.get('domain', 'security')}",
                "publish_date": entry.get("published", ""),
                "score": entry.get("score", 0),
                "author": entry.get("author", ""),
                "categories": entry.get("categories", []),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                    "categories": entry.get("categories", []),
                },
            })
        
        logger.info(f"TechCrunch security provider returning {len(normalized)} entries for ranking")
        return normalized
        
    except Exception as e:
        logger.error(f"TechCrunch security provider failed: {e}")
        return []


def techcrunch_cloud_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """TechCrunch cloud/enterprise news provider - returns ALL matching entries (no query filtering)."""
    try:
        import importlib
        _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
        get_all_feed_entries = _tech_crunch_rss.get_all_feed_entries
        
        logger.info(f"Fetching ALL TechCrunch cloud RSS entries (no query filtering)")
        results = get_all_feed_entries(domains=["cloud", "enterprise"], limit=max_results)
        
        logger.info(f"TechCrunch cloud: fetched {len(results)} total RSS entries")
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "source": f"techcrunch:{entry.get('domain', 'cloud')}",
                "publish_date": entry.get("published", ""),
                "score": entry.get("score", 0),
                "author": entry.get("author", ""),
                "categories": entry.get("categories", []),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                    "categories": entry.get("categories", []),
                },
            })
        
        logger.info(f"TechCrunch cloud provider returning {len(normalized)} entries for ranking")
        return normalized
        
    except Exception as e:
        logger.error(f"TechCrunch cloud provider failed: {e}")
        return []


def techcrunch_general_provider(query: str, max_results: int = 500, categories: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
    """TechCrunch general news provider - returns ALL matching entries across categories (no query filtering)."""
    try:
        import importlib
        _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
        get_all_feed_entries = _tech_crunch_rss.get_all_feed_entries
        
        # Default categories for general tech news
        domains = categories or ["all", "ai", "startups", "apps", "business"]
        
        logger.info(f"Fetching ALL TechCrunch general RSS entries (no query filtering), domains: {domains}")
        results = get_all_feed_entries(domains=domains, limit=max_results)
        
        logger.info(f"TechCrunch general: fetched {len(results)} total RSS entries")
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "source": f"techcrunch:{entry.get('domain', 'tech')}",
                "publish_date": entry.get("published", ""),
                "score": entry.get("score", 0),
                "author": entry.get("author", ""),
                "categories": entry.get("categories", []),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                    "categories": entry.get("categories", []),
                },
            })
        
        logger.info(f"TechCrunch general provider returning {len(normalized)} entries for ranking")
        return normalized
        
    except Exception as e:
        logger.error(f"TechCrunch general provider failed: {e}")
        return []


# Category provider registry
# Maps category names to lists of provider functions
CATEGORY_PROVIDERS: Dict[str, List[Any]] = {
    "ai": [techcrunch_ai_provider],
    "startups": [techcrunch_startups_provider],
    "security": [techcrunch_security_provider],
    "cloud": [techcrunch_cloud_provider],
    # Future categories can be added here:
    # "linux": [techcrunch_linux_provider, phoronix_provider],
    # "opensource": [techcrunch_opensource_provider, github_blog_provider],
    # "programming": [hacker_news_provider, dev_to_provider],
    # "business": [techcrunch_business_provider, venturebeat_provider],
    # "gadgets": [techcrunch_hardware_provider, verge_provider],
    # "science": [arxiv_provider, nature_provider],
}


def get_available_categories() -> List[str]:
    """Get list of supported category names."""
    return sorted(CATEGORY_PROVIDERS.keys())


def get_category_providers(category: str) -> List[Any]:
    """Get provider functions for a specific category."""
    return CATEGORY_PROVIDERS.get(category, [])


def fetch_category_news(
    categories: Sequence[str],
    query: str,
    max_results: int = 500,
    **kwargs
) -> List[Dict[str, Any]]:
    """Fetch news from all providers for the given categories.
    
    Returns ALL matching entries from category RSS feeds (no artificial limit).
    
    Args:
        categories: List of category names
        query: Search query (used by TechCrunch RSS search)
        max_results: Max results per provider (default: 500 for comprehensive discovery)
        **kwargs: Additional arguments passed to providers
    
    Returns:
        List of normalized news entries from all category providers
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()
    
    # Collect all provider functions for requested categories
    providers_to_run: List[tuple] = []
    for category in categories:
        category_lower = category.lower()
        provider_funcs = get_category_providers(category_lower)
        
        if not provider_funcs:
            logger.warning(f"No providers configured for category: {category}")
            continue
        
        for provider_func in provider_funcs:
            providers_to_run.append((category_lower, provider_func))
    
    if not providers_to_run:
        logger.warning(f"No providers found for categories: {categories}")
        return []
    
    logger.info(f"Running {len(providers_to_run)} category providers")
    
    # Run all providers in parallel
    with ThreadPoolExecutor(max_workers=min(len(providers_to_run), 4)) as executor:
        futures = {
            executor.submit(provider_func, query, max_results, **kwargs): (category, provider_func.__name__)
            for category, provider_func in providers_to_run
        }
        
        for future in as_completed(futures):
            category, provider_name = futures[future]
            try:
                results = future.result()
                
                # Deduplicate by URL
                for entry in results:
                    url = entry.get("url", "") or entry.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(entry)
                
                logger.info(f"Provider {provider_name} ({category}) returned {len(results)} results")
                
            except Exception as e:
                logger.error(f"Provider {provider_name} ({category}) failed: {e}")
    
    logger.info(f"Total category results after deduplication: {len(all_results)}")
    return all_results
