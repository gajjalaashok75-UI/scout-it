"""Category-aware RSS provider registry for web-search.

This module maintains a registry of RSS providers organized by technical categories.
Similar to category_providers.py but for web search (engineering blogs, research, etc.)
"""

from typing import Any, Dict, List, Optional, Sequence
import logging

logger = logging.getLogger(__name__)


def web_ai_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """Web AI provider - OpenAI, Hugging Face, DeepMind, etc."""
    try:
        from .web_search_rss import get_all_web_feed_entries
        
        logger.info(f"Fetching ALL web AI RSS entries (no query filtering)")
        results = get_all_web_feed_entries(categories=["ai"], limit=max_results)
        
        logger.info(f"Web AI: fetched {len(results)} total RSS entries")
        
        # Normalize to search format
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "snippet": entry.get("summary", ""),
                "source": f"rss:{entry.get('domain', 'ai')}",
                "publish_date": entry.get("published", ""),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                },
            })
        
        logger.info(f"Web AI provider returning {len(normalized)} entries for ranking")
        return normalized
        
    except Exception as e:
        logger.error(f"Web AI provider failed: {e}")
        return []


def web_engineering_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """Web Engineering provider - Netflix, Cloudflare, Stripe, etc."""
    try:
        from .web_search_rss import get_all_web_feed_entries
        
        logger.info(f"Fetching ALL web engineering RSS entries")
        results = get_all_web_feed_entries(categories=["engineering"], limit=max_results)
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "snippet": entry.get("summary", ""),
                "source": f"rss:{entry.get('domain', 'engineering')}",
                "publish_date": entry.get("published", ""),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                },
            })
        
        logger.info(f"Web engineering provider returning {len(normalized)} entries")
        return normalized
        
    except Exception as e:
        logger.error(f"Web engineering provider failed: {e}")
        return []


def web_cloud_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """Web Cloud provider - AWS, Azure, HashiCorp, etc."""
    try:
        from .web_search_rss import get_all_web_feed_entries
        
        results = get_all_web_feed_entries(categories=["cloud"], limit=max_results)
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "snippet": entry.get("summary", ""),
                "source": f"rss:{entry.get('domain', 'cloud')}",
                "publish_date": entry.get("published", ""),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                },
            })
        
        return normalized
        
    except Exception as e:
        logger.error(f"Web cloud provider failed: {e}")
        return []


def web_devops_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """Web DevOps provider - Kubernetes, Helm, DevOps.com, etc."""
    try:
        from .web_search_rss import get_all_web_feed_entries
        
        results = get_all_web_feed_entries(categories=["devops"], limit=max_results)
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "snippet": entry.get("summary", ""),
                "source": f"rss:{entry.get('domain', 'devops')}",
                "publish_date": entry.get("published", ""),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                },
            })
        
        return normalized
        
    except Exception as e:
        logger.error(f"Web devops provider failed: {e}")
        return []


def web_research_provider(query: str, max_results: int = 500, **kwargs) -> List[Dict[str, Any]]:
    """Web Research provider - arXiv, Nature, Papers with Code, etc."""
    try:
        from .web_search_rss import get_all_web_feed_entries
        
        results = get_all_web_feed_entries(categories=["research"], limit=max_results)
        
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "snippet": entry.get("summary", ""),
                "source": f"rss:{entry.get('domain', 'research')}",
                "publish_date": entry.get("published", ""),
                "rss_metadata": {
                    "feed_name": entry.get("feed_name", ""),
                    "category": entry.get("category", ""),
                },
            })
        
        return normalized
        
    except Exception as e:
        logger.error(f"Web research provider failed: {e}")
        return []


# Category provider registry
WEB_CATEGORY_PROVIDERS: Dict[str, List[Any]] = {
    "ai": [web_ai_provider],
    "engineering": [web_engineering_provider],
    "cloud": [web_cloud_provider],
    "devops": [web_devops_provider],
    "research": [web_research_provider],
    # Can add more as needed
}


def get_available_web_categories() -> List[str]:
    """Get list of supported web category names."""
    return sorted(WEB_CATEGORY_PROVIDERS.keys())


def get_web_category_providers(category: str) -> List[Any]:
    """Get provider functions for a specific category."""
    return WEB_CATEGORY_PROVIDERS.get(category, [])


def fetch_web_category_feeds(
    categories: Sequence[str],
    query: str,
    max_results: int = 500,
    **kwargs
) -> List[Dict[str, Any]]:
    """Fetch web search results from RSS feeds for given categories.
    
    Returns ALL matching entries from category RSS feeds (no artificial limit).
    
    Args:
        categories: List of category names
        query: Search query (for future use, not filtered here)
        max_results: Max results per provider (default: 500)
        **kwargs: Additional arguments
    
    Returns:
        List of normalized entries from all category providers
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    all_results: List[Dict[str, Any]] = []
    seen_urls: set = set()
    
    # Collect all provider functions
    providers_to_run: List[tuple] = []
    for category in categories:
        category_lower = category.lower()
        provider_funcs = get_web_category_providers(category_lower)
        
        if not provider_funcs:
            logger.warning(f"No providers for web category: {category}")
            continue
        
        for provider_func in provider_funcs:
            providers_to_run.append((category_lower, provider_func))
    
    if not providers_to_run:
        logger.warning(f"No providers found for web categories: {categories}")
        return []
    
    logger.info(f"Running {len(providers_to_run)} web category providers")
    
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
    
    logger.info(f"Total web category results after deduplication: {len(all_results)}")
    return all_results
