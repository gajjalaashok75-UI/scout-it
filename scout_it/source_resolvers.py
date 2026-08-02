#!/usr/bin/env python3
"""
Source URL Resolvers for Syndication/Wrapper Sites

Handles sites like MSN, Yahoo News, AOL that wrap original publisher content.
Extracts the original publisher URL before extraction.
"""

import logging
import re
import json
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs, unquote

logger = logging.getLogger(__name__)

# Domains that act as wrappers/syndication sites
WRAPPER_DOMAINS = {
    "msn.com",
    "www.msn.com",
    "news.yahoo.com",
    "yahoo.com",
    "www.yahoo.com",
    "aol.com",
    "www.aol.com",
    "news.google.com",
    "www.google.com",
}


def is_wrapper_domain(url: str) -> bool:
    """Check if URL is from a known wrapper domain."""
    try:
        domain = urlparse(url).netloc.lower()
        return domain in WRAPPER_DOMAINS
    except Exception:
        return False


def resolve_msn(url: str, html: Optional[str] = None) -> Optional[str]:
    """Resolve MSN wrapper URL to original publisher URL.
    
    MSN resolution methods (in order of reliability):
    1. Canonical link in HTML: <link rel="canonical" href="...">
    2. OpenGraph URL: <meta property="og:url" content="...">
    3. Source URL metadata: <meta name="sourceUrl" content="...">
    4. JSON-LD structured data: {"@type":"NewsArticle","url":"..."}
    5. "Continue Reading" button href
    6. URL parameters: ?url=..., ?originalUrl=...
    7. Data attributes: data-original-url, data-source-url
    
    Args:
        url: MSN URL
        html: Page HTML (optional, for deeper resolution)
    
    Returns:
        Original publisher URL or None
    """
    try:
        # Method 6: Check URL parameters FIRST (fastest, no HTML needed)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        # Common MSN parameter names
        for param in ['url', 'originalUrl', 'sourceUrl', 'ocid', 'source']:
            if param in params and params[param]:
                candidate = params[param][0]
                if candidate.startswith('http'):
                    logger.info(f"MSN resolver: Found original URL in parameter '{param}': {candidate[:80]}")
                    return candidate
        
        # Methods 1-5 require HTML
        if not html:
            return None
        
        # Method 1: Canonical URL (MOST RELIABLE for MSN)
        canonical_match = re.search(
            r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\'](https?://[^"\']+)["\']',
            html,
            re.IGNORECASE | re.DOTALL
        )
        if not canonical_match:
            # Try reversed order: href before rel
            canonical_match = re.search(
                r'<link\s+[^>]*href=["\'](https?://[^"\']+)["\'][^>]*rel=["\']canonical["\']',
                html,
                re.IGNORECASE | re.DOTALL
            )
        
        if canonical_match:
            candidate = canonical_match.group(1)
            # Make sure it's not just back to MSN
            if 'msn.com' not in candidate.lower():
                logger.info(f"MSN resolver: Found canonical URL: {candidate[:80]}")
                return candidate
        
        # Method 2: OpenGraph URL
        og_url_match = re.search(
            r'<meta\s+property=["\']og:url["\']\s+content=["\'](https?://[^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        if og_url_match:
            candidate = og_url_match.group(1)
            if 'msn.com' not in candidate.lower():
                logger.info(f"MSN resolver: Found og:url: {candidate[:80]}")
                return candidate
        
        # Method 3: Source URL metadata
        source_url_match = re.search(
            r'<meta\s+name=["\']sourceUrl["\']\s+content=["\'](https?://[^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        if source_url_match:
            candidate = source_url_match.group(1)
            logger.info(f"MSN resolver: Found sourceUrl meta: {candidate[:80]}")
            return candidate
        
        # Method 4: JSON-LD structured data
        json_ld_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.IGNORECASE | re.DOTALL
        )
        for json_str in json_ld_matches:
            try:
                data = json.loads(json_str)
                # Handle both single object and array
                items = [data] if isinstance(data, dict) else data if isinstance(data, list) else []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    # Check for NewsArticle type
                    if item.get('@type') in ['NewsArticle', 'Article']:
                        # Try url field
                        article_url = item.get('url') or item.get('mainEntityOfPage', {}).get('url')
                        if article_url and isinstance(article_url, str) and 'msn.com' not in article_url.lower():
                            logger.info(f"MSN resolver: Found URL in JSON-LD: {article_url[:80]}")
                            return article_url
            except (json.JSONDecodeError, AttributeError, KeyError):
                continue
        
        # Method 5: "Continue Reading" button
        continue_reading_patterns = [
            r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>.*?[Cc]ontinue\s+[Rr]eading',
            r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>.*?[Rr]ead\s+[Mm]ore',
            r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>.*?[Rr]ead\s+[Ff]ull',
        ]
        for pattern in continue_reading_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                candidate = match.group(1)
                if 'msn.com' not in candidate.lower():
                    logger.info(f"MSN resolver: Found 'Continue reading' link: {candidate[:80]}")
                    return candidate
        
        # Method 7: Data attributes
        data_url_match = re.search(
            r'data-(?:original|source)-url=["\'](https?://[^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        if data_url_match:
            candidate = data_url_match.group(1)
            logger.info(f"MSN resolver: Found data-*-url attribute: {candidate[:80]}")
            return candidate
        
        # Method 8: Search JavaScript state objects (advanced)
        js_state_patterns = [
            r'sourceUrl["\']\s*:\s*["\']([^"\']+)["\']',
            r'originalUrl["\']\s*:\s*["\']([^"\']+)["\']',
            r'providerUrl["\']\s*:\s*["\']([^"\']+)["\']',
            r'canonicalUrl["\']\s*:\s*["\']([^"\']+)["\']',
        ]
        for pattern in js_state_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                candidate = match.group(1)
                if candidate.startswith('http') and 'msn.com' not in candidate.lower():
                    logger.info(f"MSN resolver: Found URL in JavaScript state: {candidate[:80]}")
                    return candidate
        
        logger.debug(f"MSN resolver: Could not resolve {url[:80]}")
        return None
        
    except Exception as e:
        logger.warning(f"MSN resolver error: {e}")
        return None


def resolve_yahoo(url: str, html: Optional[str] = None) -> Optional[str]:
    """Resolve Yahoo News wrapper URL to original publisher URL."""
    try:
        # Yahoo often embeds source URLs in the path or parameters
        parsed = urlparse(url)
        
        # Check for redirect URLs in parameters
        params = parse_qs(parsed.query)
        for param in ['url', 'u', 'src']:
            if param in params and params[param]:
                candidate = unquote(params[param][0])
                if candidate.startswith('http'):
                    logger.info(f"Yahoo resolver: Found URL in parameter: {candidate[:80]}")
                    return candidate
        
        # Parse from HTML if provided
        if html:
            # Look for canonical URL
            canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
            if canonical_match:
                candidate = canonical_match.group(1)
                if 'yahoo.com' not in candidate.lower():
                    logger.info(f"Yahoo resolver: Found canonical URL: {candidate[:80]}")
                    return candidate
            
            # Look for source attribution
            source_match = re.search(r'<a[^>]+class=["\'][^"\']*source[^"\']*["\'][^>]+href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
            if source_match:
                candidate = source_match.group(1)
                logger.info(f"Yahoo resolver: Found source link: {candidate[:80]}")
                return candidate
        
        return None
        
    except Exception as e:
        logger.warning(f"Yahoo resolver error: {e}")
        return None


def resolve_aol(url: str, html: Optional[str] = None) -> Optional[str]:
    """Resolve AOL wrapper URL to original publisher URL."""
    try:
        # AOL resolution is similar to Yahoo (owned by same company)
        return resolve_yahoo(url, html)
    except Exception as e:
        logger.warning(f"AOL resolver error: {e}")
        return None


def resolve_google_news(url: str, html: Optional[str] = None) -> Optional[str]:
    """Resolve Google News redirect URL to original article URL.
    
    Google News uses /articles/ URLs that redirect to the publisher.
    """
    try:
        # Google News articles typically redirect, so the final_url from fetch is usually correct
        # But we can try to extract from HTML if needed
        if html:
            # Look for the actual article link
            article_match = re.search(r'<a[^>]+jsname=["\']tljFtd["\'][^>]+href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
            if article_match:
                candidate = article_match.group(1)
                if 'google.com' not in candidate.lower():
                    logger.info(f"Google News resolver: Found article link: {candidate[:80]}")
                    return candidate
        
        return None
        
    except Exception as e:
        logger.warning(f"Google News resolver error: {e}")
        return None


# Resolver registry
SOURCE_RESOLVERS: Dict[str, Any] = {
    "msn.com": resolve_msn,
    "www.msn.com": resolve_msn,
    "news.yahoo.com": resolve_yahoo,
    "yahoo.com": resolve_yahoo,
    "www.yahoo.com": resolve_yahoo,
    "aol.com": resolve_aol,
    "www.aol.com": resolve_aol,
    "news.google.com": resolve_google_news,
}


def resolve_source_url(url: str, html: Optional[str] = None) -> Optional[str]:
    """Resolve wrapper URL to original publisher URL if possible.
    
    Args:
        url: Original URL (might be wrapper)
        html: Page HTML (optional, helps with resolution)
    
    Returns:
        Resolved original URL or None if not resolvable
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        if domain in SOURCE_RESOLVERS:
            resolver = SOURCE_RESOLVERS[domain]
            resolved_url = resolver(url, html)
            
            if resolved_url and resolved_url != url:
                logger.info(f"Source resolver: {domain} → {urlparse(resolved_url).netloc}")
                return resolved_url
        
        return None
        
    except Exception as e:
        logger.warning(f"Source resolution error: {e}")
        return None


# Low-value domains that should be penalized in ranking
LOW_VALUE_DOMAINS = {
    "msn.com",
    "www.msn.com",
    "news.yahoo.com",  # Unless original URL is resolved
    "aol.com",
}


def get_domain_ranking_multiplier(url: str, was_resolved: bool = False) -> float:
    """Get ranking multiplier for a domain.
    
    Args:
        url: Article URL
        was_resolved: Whether original publisher URL was successfully resolved
    
    Returns:
        Ranking multiplier (0.25 = heavy penalty, 1.0 = no penalty)
    """
    try:
        domain = urlparse(url).netloc.lower()
        
        if domain in LOW_VALUE_DOMAINS:
            # If we successfully resolved to original publisher, no penalty
            if was_resolved:
                return 1.0
            # Otherwise, heavy penalty (wrapper pages have little value)
            return 0.25
        
        return 1.0
        
    except Exception:
        return 1.0
