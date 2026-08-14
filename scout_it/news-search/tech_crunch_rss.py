"""TechCrunch RSS provider and search module.

This module provides a reusable, production-oriented TechCrunch RSS aggregation
and search layer with a centralized feed registry, resilient fetching,
consistent entry normalization, relevance ranking, deduplication, export
helpers, runtime validation utilities, caching, and article-content enrichment.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html import unescape
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse, parse_qs, urlunparse

import requests
from requests.adapters import HTTPAdapter
from xml.etree import ElementTree as ET

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

try:
    import feedparser as _feedparser  # type: ignore
except Exception:  # pragma: no cover
    _feedparser = None

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None

try:
    from rapidfuzz import fuzz  # type: ignore
except Exception:  # pragma: no cover
    fuzz = None

__all__ = [
    "RSSProvider",
    "TechCrunchRSSProvider",
    "TECHCRUNCH_FEEDS",
    "RSSConfig",
    "RSSProviderError",
    "FeedValidationError",
    "FeedFetchError",
    "FeedParseError",
    "SearchError",
    "ExportError",
    "get_available_domains",
    "get_feed_urls",
    "validate_domain",
    "validate_feed",
    "validate_all_feeds",
    "fetch_feed",
    "fetch_multiple_feeds",
    "fetch_article_content",
    "parse_feed",
    "parse_feed_entries",
    "get_latest_entries",
    "search_entries",
    "rank_entries",
    "filter_entries",
    "search_feeds",
    "deduplicate_entries",
    "sort_entries",
    "get_feed_statistics",
    "get_feed_metadata",
    "get_feed_health",
    "get_entry_count",
    "refresh_feed_registry",
    "to_json",
    "to_yaml",
    "export_json",
    "export_yaml",
    "filter_by_date",
    "filter_by_author",
    "filter_by_domain",
    "filter_by_keyword",
    "filter_by_feed",
    "get_top_authors",
    "get_top_keywords",
    "get_feed_activity",
    "get_feed_distribution",
    "export_csv",
    "export_jsonl",
    "clear_cache",
    "invalidate_cache",
    "get_runtime_statistics",
]

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exception Hierarchy
# ============================================================================

class RSSProviderError(Exception):
    """Base exception for RSS provider errors."""
    pass


class FeedValidationError(RSSProviderError):
    """Raised when feed validation fails."""
    pass


class FeedFetchError(RSSProviderError):
    """Raised when fetching a feed fails."""
    pass


class FeedParseError(RSSProviderError):
    """Raised when parsing a feed fails."""
    pass


class SearchError(RSSProviderError):
    """Raised when search operation fails."""
    pass


class ExportError(RSSProviderError):
    """Raised when export operation fails."""
    pass


# ============================================================================
# Configuration Classes
# ============================================================================

@dataclass
class RankingWeights:
    """Configuration for ranking weights."""
    title: float = 10.0
    summary: float = 5.0
    author: float = 2.0
    url: float = 1.0
    domain: float = 2.0
    content: float = 8.0
    phrase_match_bonus: float = 50.0
    exact_phrase_in_title: float = 40.0
    all_terms_match: float = 15.0
    recency_base: float = 60.0
    recency_decay_rate: float = 1.2
    
    def validate(self) -> None:
        """Validate that all weights are non-negative."""
        for field_name, value in self.__dict__.items():
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"Weight '{field_name}' must be non-negative number, got {value}")


@dataclass
class RSSConfig:
    """Configuration for RSS provider operations.
    
    All configuration values can be overridden via environment variables:
    - TECHCRUNCH_RSS_TIMEOUT
    - TECHCRUNCH_RSS_RETRIES
    - TECHCRUNCH_RSS_BACKOFF_FACTOR
    - TECHCRUNCH_RSS_CACHE_TTL
    - TECHCRUNCH_RSS_ARTICLE_CACHE_TTL
    - TECHCRUNCH_RSS_MAX_WORKERS
    - TECHCRUNCH_RSS_USER_AGENT
    - TECHCRUNCH_RSS_DEBUG
    """
    timeout: float = 15.0
    retries: int = 3
    backoff_factor: float = 0.75
    cache_ttl_seconds: int = 600
    article_cache_ttl_seconds: int = 1800
    max_workers: int = 8
    user_agent: str = "TechCrunchRSSProvider/2.0 (+https://techcrunch.com/)"
    debug: bool = False
    max_entries_per_feed: int = 1000
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300
    ranking_weights: RankingWeights = field(default_factory=RankingWeights)
    
    @classmethod
    def from_environment(cls) -> "RSSConfig":
        """Create configuration from environment variables."""
        return cls(
            timeout=float(os.getenv("TECHCRUNCH_RSS_TIMEOUT", "15.0")),
            retries=int(os.getenv("TECHCRUNCH_RSS_RETRIES", "3")),
            backoff_factor=float(os.getenv("TECHCRUNCH_RSS_BACKOFF_FACTOR", "0.75")),
            cache_ttl_seconds=int(os.getenv("TECHCRUNCH_RSS_CACHE_TTL", "600")),
            article_cache_ttl_seconds=int(os.getenv("TECHCRUNCH_RSS_ARTICLE_CACHE_TTL", "1800")),
            max_workers=int(os.getenv("TECHCRUNCH_RSS_MAX_WORKERS", "8")),
            user_agent=os.getenv("TECHCRUNCH_RSS_USER_AGENT", "TechCrunchRSSProvider/2.0 (+https://techcrunch.com/)"),
            debug=os.getenv("TECHCRUNCH_RSS_DEBUG", "").lower() in ("1", "true", "yes"),
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
        if self.retries < 0:
            raise ValueError(f"retries must be non-negative, got {self.retries}")
        if self.backoff_factor < 0:
            raise ValueError(f"backoff_factor must be non-negative, got {self.backoff_factor}")
        if self.cache_ttl_seconds < 0:
            raise ValueError(f"cache_ttl_seconds must be non-negative, got {self.cache_ttl_seconds}")
        if self.article_cache_ttl_seconds < 0:
            raise ValueError(f"article_cache_ttl_seconds must be non-negative, got {self.article_cache_ttl_seconds}")
        if self.max_workers <= 0:
            raise ValueError(f"max_workers must be positive, got {self.max_workers}")
        if self.max_entries_per_feed <= 0:
            raise ValueError(f"max_entries_per_feed must be positive, got {self.max_entries_per_feed}")
        if self.circuit_breaker_threshold <= 0:
            raise ValueError(f"circuit_breaker_threshold must be positive, got {self.circuit_breaker_threshold}")
        if self.circuit_breaker_timeout < 0:
            raise ValueError(f"circuit_breaker_timeout must be non-negative, got {self.circuit_breaker_timeout}")
        
        # Validate ranking weights
        self.ranking_weights.validate()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        config_dict = {
            "timeout": self.timeout,
            "retries": self.retries,
            "backoff_factor": self.backoff_factor,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "article_cache_ttl_seconds": self.article_cache_ttl_seconds,
            "max_workers": self.max_workers,
            "user_agent": self.user_agent,
            "debug": self.debug,
            "max_entries_per_feed": self.max_entries_per_feed,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "circuit_breaker_timeout": self.circuit_breaker_timeout,
            "ranking_weights": self.ranking_weights.__dict__,
        }
        return config_dict


# Default configuration instance
DEFAULT_CONFIG = RSSConfig.from_environment()
DEFAULT_CONFIG.validate()

# Legacy constants for backward compatibility (deprecated - use RSSConfig instead)
DEFAULT_TIMEOUT: float = DEFAULT_CONFIG.timeout
DEFAULT_LIMIT: int = 20
DEFAULT_USER_AGENT: str = DEFAULT_CONFIG.user_agent
DEFAULT_RETRIES: int = DEFAULT_CONFIG.retries
DEFAULT_BACKOFF_FACTOR: float = DEFAULT_CONFIG.backoff_factor
DEFAULT_MAX_WORKERS: int = DEFAULT_CONFIG.max_workers
SOURCE_NAME: str = "techcrunch"
CACHE_TTL_SECONDS: int = DEFAULT_CONFIG.cache_ttl_seconds
ARTICLE_CACHE_TTL_SECONDS: int = DEFAULT_CONFIG.article_cache_ttl_seconds

# Weighted field scoring constants (deprecated - use RSSConfig.ranking_weights)
TITLE_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.title
SUMMARY_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.summary
AUTHOR_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.author
URL_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.url
DOMAIN_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.domain
CONTENT_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.content
PHRASE_MATCH_BONUS: float = DEFAULT_CONFIG.ranking_weights.phrase_match_bonus
EXACT_PHRASE_IN_TITLE_BONUS: float = DEFAULT_CONFIG.ranking_weights.exact_phrase_in_title
ALL_TERMS_MATCH_BONUS: float = DEFAULT_CONFIG.ranking_weights.all_terms_match
RECENCY_WEIGHT: float = DEFAULT_CONFIG.ranking_weights.recency_base
RECENCY_DECAY_RATE: float = DEFAULT_CONFIG.ranking_weights.recency_decay_rate

# Import TECHCRUNCH_FEEDS from news_search_feed.py
from .news_search_feed import TECHCRUNCH_FEEDS

_DOMAIN_ALIASES: Dict[str, str] = {
    "artificial-intelligence": "ai",
    "ai": "ai",
    "ml": "ai",
    "machine-learning": "ai",
    "media-entertainment": "media",
    "social-media": "social",
    "vc": "venture",
    "venture-capital": "venture",
    "crypto": "cryptocurrency",
    "cryptocurrencies": "cryptocurrency",
    "fintech": "fintech",
    "ecommerce": "commerce",
    "e-commerce": "commerce",
    "hardware": "hardware",
    "mobile": "mobile",
    "cloud": "cloud",
}

_SESSION: Optional[requests.Session] = None
_FEED_CACHE: Dict[str, Tuple[float, Any]] = {}
_ARTICLE_CACHE: Dict[str, Tuple[float, Any]] = {}
_FEED_HEALTH: Dict[str, Dict[str, Any]] = {}
_CIRCUIT_BREAKERS: Dict[str, Dict[str, Any]] = {}
_RUNTIME_STATS: Dict[str, Any] = {
    "fetch_count": 0,
    "fetch_success": 0,
    "fetch_failure": 0,
    "fetch_total_ms": 0.0,
    "parse_count": 0,
    "parse_success": 0,
    "parse_failure": 0,
    "parse_total_ms": 0.0,
    "search_count": 0,
    "search_total_ms": 0.0,
    "ranking_count": 0,
    "ranking_total_ms": 0.0,
    "cache_hits": 0,
    "cache_misses": 0,
    "export_count": 0,
    "export_total_ms": 0.0,
}


# ============================================================================
# Structured Logging Helpers
# ============================================================================

def _log_event(event_name: str, **kwargs: Any) -> None:
    """Log structured event with context."""
    if DEFAULT_CONFIG.debug:
        logger.debug(f"[{event_name}] {json.dumps(kwargs, default=str)}")
    else:
        # Log only significant events in non-debug mode
        if event_name in {"feed_fetch_failed", "feed_parse_failed", "search_error", "export_error"}:
            logger.warning(f"[{event_name}] {kwargs}")


def _log_metric(metric_name: str, value: float, unit: str = "ms", **tags: Any) -> None:
    """Log performance metric."""
    if DEFAULT_CONFIG.debug:
        tag_str = " ".join(f"{k}={v}" for k, v in tags.items())
        logger.debug(f"[metric] {metric_name}={value}{unit} {tag_str}")


def _track_duration(operation: str) -> Any:
    """Context manager to track operation duration."""
    import contextlib
    
    @contextlib.contextmanager
    def timer():
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            _log_metric(f"{operation}_duration", duration_ms, unit="ms")
    
    return timer()


class RSSProvider:
    """Base interface for RSS-based providers."""

    name = "rss-provider"

    def __init__(self, cache_ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds

    @property
    def feed_registry(self) -> Dict[str, List[Dict[str, Any]]]:
        return {}

    def get_feed_urls(self, domain: Optional[str] = None) -> List[str]:
        raise NotImplementedError

    def validate_feed(self, url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_all_feeds(self, timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_feed(self, url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
        raise NotImplementedError

    def fetch_multiple_feeds(self, urls: Sequence[str], timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Tuple[str, Optional[str]]]:
        raise NotImplementedError

    def parse_feed(self, feed: Any, domain: str = "all") -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_latest_entries(self, domain: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search_feeds(self, query: str, domains: Optional[Sequence[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
        raise NotImplementedError


class TechCrunchRSSProvider(RSSProvider):
    """Concrete provider for the TechCrunch RSS feed registry."""

    name = SOURCE_NAME

    @property
    def feed_registry(self) -> Dict[str, List[Dict[str, Any]]]:
        return TECHCRUNCH_FEEDS

    def get_feed_urls(self, domain: Optional[str] = None) -> List[str]:
        if domain is None:
            seen: set[str] = set()
            urls: List[str] = []
            for dom in get_available_domains():
                for item in TECHCRUNCH_FEEDS.get(dom, []):
                    url = item["url"]
                    if url not in seen:
                        seen.add(url)
                        urls.append(url)
            return urls
        dom = validate_domain(domain)
        return [item["url"] for item in TECHCRUNCH_FEEDS.get(dom, [])]

    def validate_feed(self, url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "url": url,
            "status": "invalid",
            "http_status": None,
            "feed_type": "unknown",
            "redirected": False,
            "details": "",
            "success_rate": 0.0,
            "last_success": None,
            "average_response_time": 0.0,
        }
        try:
            start = time.perf_counter()
            response = _request_with_retry(url, timeout=timeout)
            elapsed = time.perf_counter() - start
            result["http_status"] = response.status_code
            result["redirected"] = bool(getattr(response, "history", []))
            text = response.text[:20000]
            root = _safe_xml_root(text)
            feed_type = _detect_feed_type(root)
            result["feed_type"] = feed_type
            if feed_type in {"rss", "atom"}:
                result["status"] = "valid"
                result["details"] = "Feed parsed successfully"
            else:
                result["details"] = "Content fetched but not recognized as RSS/Atom"
            _update_feed_health(url, success=True, response_time=elapsed, status_code=response.status_code)
        except Exception as exc:
            result["details"] = str(exc)
            _update_feed_health(url, success=False, response_time=0.0, status_code=None, error=str(exc))
        health = _FEED_HEALTH.get(url, {})
        result["success_rate"] = round(float(health.get("success_rate", 0.0)), 3)
        result["last_success"] = health.get("last_success")
        result["average_response_time"] = round(float(health.get("average_response_time", 0.0)), 3)
        return result

    def validate_all_feeds(self, timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Dict[str, Any]]:
        urls = self.get_feed_urls()
        results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self.validate_feed, url, timeout): url for url in urls}
            for future in as_completed(future_map):
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append({"url": future_map[future], "status": "invalid", "http_status": None, "feed_type": "unknown", "details": str(exc)})
        results.sort(key=lambda r: str(r.get("url", "")))
        return results

    def fetch_feed(self, url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
        """Fetch feed with circuit breaker, caching, and metrics tracking."""
        start_time = time.perf_counter()
        
        try:
            # Check circuit breaker
            if _is_circuit_open(url):
                _log_event("circuit_breaker_open", url=url)
                logger.warning(f"Circuit breaker is open for {url}, skipping fetch")
                return None
            
            # Check cache
            cached = _get_cache(_FEED_CACHE, url, ttl_seconds=self.cache_ttl_seconds)
            if cached is not None:
                return cached
            
            # Log fetch start
            _log_event("feed_fetch_started", url=url)
            _RUNTIME_STATS["fetch_count"] += 1
            
            # Fetch content
            content = _request_with_retry(url, timeout=timeout).text
            
            # Safeguard against extremely large feeds
            if len(content) > 10 * 1024 * 1024:  # 10MB limit
                logger.warning(f"Feed {url} is very large: {len(content)} bytes, truncating")
                content = content[:10 * 1024 * 1024]
            
            # Cache result
            _set_cache(_FEED_CACHE, url, content, ttl_seconds=self.cache_ttl_seconds)
            
            # Track success
            duration_ms = (time.perf_counter() - start_time) * 1000
            _RUNTIME_STATS["fetch_success"] += 1
            _RUNTIME_STATS["fetch_total_ms"] += duration_ms
            _log_event("feed_fetch_completed", url=url, duration_ms=round(duration_ms, 2), size_bytes=len(content))
            _log_metric("fetch_duration", duration_ms, url=url[:50])
            
            return content
            
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _RUNTIME_STATS["fetch_failure"] += 1
            _RUNTIME_STATS["fetch_total_ms"] += duration_ms
            _log_event("feed_fetch_failed", url=url, error=str(exc), duration_ms=round(duration_ms, 2))
            logger.warning("Failed to fetch feed %s: %s", url, exc)
            return None

    def fetch_multiple_feeds(self, urls: Sequence[str], timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Tuple[str, Optional[str]]]:
        out: List[Tuple[str, Optional[str]]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self.fetch_feed, url, timeout): url for url in urls}
            for future in as_completed(future_map):
                url = future_map[future]
                try:
                    out.append((url, future.result()))
                except Exception as exc:
                    logger.warning("Failed to fetch feed %s: %s", url, exc)
                    out.append((url, None))
        return out

    def parse_feed(self, feed: Any, domain: str = "all") -> List[Dict[str, Any]]:
        """Parse feed with metrics tracking and safeguards."""
        start_time = time.perf_counter()
        _RUNTIME_STATS["parse_count"] += 1
        
        try:
            if feed is None:
                return []
            
            if hasattr(feed, "text"):
                xml_text = getattr(feed, "text", "")
            elif isinstance(feed, bytes):
                xml_text = feed.decode("utf-8", errors="ignore")
            else:
                xml_text = str(feed)
            
            if not xml_text:
                return []
            
            _log_event("feed_parse_started", domain=domain, size_bytes=len(xml_text))
            
            # Try feedparser first
            if _feedparser is not None:
                parsed = _parse_with_feedparser(xml_text)
                if parsed:
                    # Apply max entries limit
                    if len(parsed) > DEFAULT_CONFIG.max_entries_per_feed:
                        logger.warning(f"Feed has {len(parsed)} entries, limiting to {DEFAULT_CONFIG.max_entries_per_feed}")
                        parsed = parsed[:DEFAULT_CONFIG.max_entries_per_feed]
                    
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    _RUNTIME_STATS["parse_success"] += 1
                    _RUNTIME_STATS["parse_total_ms"] += duration_ms
                    _log_event("feed_parsed", parser="feedparser", entry_count=len(parsed), duration_ms=round(duration_ms, 2))
                    return parsed
            
            # Fallback to manual parsing
            result = _parse_with_manual_fallback(xml_text, domain=domain)
            
            # Apply max entries limit
            if len(result) > DEFAULT_CONFIG.max_entries_per_feed:
                logger.warning(f"Feed has {len(result)} entries, limiting to {DEFAULT_CONFIG.max_entries_per_feed}")
                result = result[:DEFAULT_CONFIG.max_entries_per_feed]
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            _RUNTIME_STATS["parse_success"] += 1
            _RUNTIME_STATS["parse_total_ms"] += duration_ms
            _log_event("feed_parsed", parser="manual", entry_count=len(result), duration_ms=round(duration_ms, 2))
            
            return result
            
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            _RUNTIME_STATS["parse_failure"] += 1
            _RUNTIME_STATS["parse_total_ms"] += duration_ms
            _log_event("feed_parse_failed", domain=domain, error=str(exc), duration_ms=round(duration_ms, 2))
            logger.error(f"Failed to parse feed for domain {domain}: {exc}")
            return []

    def get_latest_entries(self, domain: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
        urls = self.get_feed_urls(domain)
        fetched = self.fetch_multiple_feeds(urls)
        entries: List[Dict[str, Any]] = []
        for url, content in fetched:
            if not content:
                continue
            dom = _domain_from_url(url, domain)
            parsed = self.parse_feed(content, domain=dom)
            entries.extend(_enrich_entries(parsed, feed_url=url, feed_name=_feed_name_from_url(url), category=dom))
        entries = deduplicate_entries(entries)
        entries = _sort_newest_first(entries)
        return entries[: max(int(limit), 0)]

    def search_feeds(self, query: str, domains: Optional[Sequence[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Search feeds and filter by query (OLD behavior - filters before ranking)."""
        normalized_domains = _normalize_domains(domains)
        urls: List[str] = []
        if normalized_domains:
            for domain in normalized_domains:
                urls.extend(self.get_feed_urls(domain))
        else:
            urls = self.get_feed_urls()
        if not urls:
            return []
        fetched = self.fetch_multiple_feeds(urls)
        entries: List[Dict[str, Any]] = []
        for url, content in fetched:
            if not content:
                continue
            dom = _domain_from_url(url, None)
            parsed = self.parse_feed(content, domain=dom)
            enriched = _enrich_entries(parsed, feed_url=url, feed_name=_feed_name_from_url(url), category=dom)
            for entry in enriched:
                entry_url = str(entry.get("url") or "").strip()
                if entry_url:
                    article_text = fetch_article_content(entry_url)
                    if article_text:
                        entry["content"] = article_text
                        entry["article_content"] = article_text
            entries.extend(enriched)
        entries = deduplicate_entries(entries)
        ranked = search_entries(entries, query)
        return ranked[: max(int(limit), 0)]
    
    def get_all_feed_entries(self, domains: Optional[Sequence[str]] = None, limit: int = 500) -> List[Dict[str, Any]]:
        """Get ALL feed entries without query filtering (NEW - for discovery-first flow).
        
        Returns all RSS entries from specified domains for later ranking.
        NO query filtering - just raw RSS entries with metadata.
        
        Args:
            domains: Feed domains to fetch from
            limit: Max total entries to return (default: 500)
        
        Returns:
            List of ALL RSS entries with full metadata (title, summary, url, date, categories, etc.)
        """
        normalized_domains = _normalize_domains(domains)
        urls: List[str] = []
        if normalized_domains:
            for domain in normalized_domains:
                urls.extend(self.get_feed_urls(domain))
        else:
            urls = self.get_feed_urls()
        
        if not urls:
            _log_event("get_all_entries_no_urls", domains=normalized_domains)
            return []
        
        _log_event("get_all_entries_start", feed_count=len(urls), domains=normalized_domains)
        
        fetched = self.fetch_multiple_feeds(urls)
        entries: List[Dict[str, Any]] = []
        
        for url, content in fetched:
            if not content:
                continue
            dom = _domain_from_url(url, None)
            parsed = self.parse_feed(content, domain=dom)
            enriched = _enrich_entries(parsed, feed_url=url, feed_name=_feed_name_from_url(url), category=dom)
            # DO NOT fetch article content here - that's for later after ranking
            entries.extend(enriched)
        
        # Deduplicate but do NOT filter by query
        entries = deduplicate_entries(entries)
        
        _log_event("get_all_entries_complete", 
                   total_entries=len(entries),
                   feeds_fetched=len(urls),
                   domains=normalized_domains)
        
        # Return up to limit entries (sorted by date, newest first)
        sorted_entries = sort_entries(entries)
        return sorted_entries[: max(int(limit), 0)]


_PROVIDER = TechCrunchRSSProvider()


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        sess = requests.Session()
        adapter_kwargs: Dict[str, Any] = {"pool_connections": 20, "pool_maxsize": 20, "max_retries": 0}
        adapter = HTTPAdapter(**adapter_kwargs)
        sess.mount("http://", adapter)
        sess.mount("https://", adapter)
        sess.headers.update({"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*"})
        _SESSION = sess
    return _SESSION


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(tz=_dt.timezone.utc)


def _normalize_domain(domain: Optional[str]) -> Optional[str]:
    if domain is None:
        return None
    d = str(domain).strip().lower()
    d = d.replace(" ", "-")
    return _DOMAIN_ALIASES.get(d, d)


def _normalize_domains(domains: Optional[Sequence[str]]) -> List[str]:
    if not domains:
        return []
    return [validate_domain(domain) for domain in domains if domain]


def _get_cache(cache: Dict[str, Tuple[float, Any]], key: str, ttl_seconds: int) -> Optional[Any]:
    entry = cache.get(key)
    if not entry:
        _RUNTIME_STATS["cache_misses"] += 1
        _log_event("cache_miss", key=key[:60] if len(key) > 60 else key)
        return None
    timestamp, value = entry
    if time.time() - timestamp > ttl_seconds:
        cache.pop(key, None)
        _RUNTIME_STATS["cache_misses"] += 1
        _log_event("cache_expired", key=key[:60] if len(key) > 60 else key, age_seconds=int(time.time() - timestamp))
        return None
    _RUNTIME_STATS["cache_hits"] += 1
    _log_event("cache_hit", key=key[:60] if len(key) > 60 else key)
    return value


def _set_cache(cache: Dict[str, Tuple[float, Any]], key: str, value: Any, ttl_seconds: int) -> None:
    cache[key] = (time.time(), value)


def _update_feed_health(url: str, success: bool, response_time: float, status_code: Optional[int], error: Optional[str] = None) -> None:
    health = _FEED_HEALTH.setdefault(url, {
        "url": url,
        "successes": 0,
        "failures": 0,
        "total_response_time": 0.0,
        "average_response_time": 0.0,
        "success_rate": 0.0,
        "last_success": None,
        "last_attempt": None,
        "last_error": None,
        "last_status_code": None,
        "uptime_percentage": 0.0,
    })
    health["last_attempt"] = _now_utc().isoformat()
    if success:
        health["successes"] += 1
        health["last_success"] = _now_utc().isoformat()
        health["last_status_code"] = status_code
    else:
        health["failures"] += 1
        health["last_error"] = error
    if response_time >= 0:
        health["total_response_time"] += response_time
    total = max(1, health["successes"] + health["failures"])
    health["average_response_time"] = round(health["total_response_time"] / total, 3)
    health["success_rate"] = round(health["successes"] / total, 3)
    health["uptime_percentage"] = round(health["success_rate"] * 100, 2)
    
    # Update circuit breaker
    _update_circuit_breaker(url, success)


def _update_circuit_breaker(url: str, success: bool) -> None:
    """Update circuit breaker state for a feed URL.
    
    Circuit breaker states:
    - closed: Feed is working, requests go through
    - open: Feed has failed repeatedly, requests are blocked
    - half_open: Testing if feed has recovered
    """
    breaker = _CIRCUIT_BREAKERS.setdefault(url, {
        "state": "closed",
        "failure_count": 0,
        "last_failure_time": None,
        "last_success_time": None,
        "threshold": 5,  # Open circuit after 5 consecutive failures
        "timeout": 300,  # Try again after 5 minutes
    })
    
    if success:
        breaker["failure_count"] = 0
        breaker["state"] = "closed"
        breaker["last_success_time"] = time.time()
    else:
        breaker["failure_count"] += 1
        breaker["last_failure_time"] = time.time()
        
        if breaker["failure_count"] >= breaker["threshold"]:
            breaker["state"] = "open"
            logger.warning(f"Circuit breaker opened for {url} after {breaker['failure_count']} failures")


def _is_circuit_open(url: str) -> bool:
    """Check if circuit breaker is open for a URL."""
    breaker = _CIRCUIT_BREAKERS.get(url)
    if not breaker or breaker["state"] == "closed":
        return False
    
    if breaker["state"] == "open":
        # Check if timeout has passed
        last_failure = breaker.get("last_failure_time", 0)
        if time.time() - last_failure > breaker["timeout"]:
            breaker["state"] = "half_open"
            logger.info(f"Circuit breaker for {url} entering half-open state")
            return False
        return True
    
    return False


def get_available_domains() -> List[str]:
    return sorted(TECHCRUNCH_FEEDS.keys())


def validate_domain(domain: str) -> str:
    resolved = _normalize_domain(domain)
    if resolved in TECHCRUNCH_FEEDS:
        return resolved  # type: ignore[return-value]
    raise ValueError(f"Unknown TechCrunch domain: {domain!r}")


def get_feed_urls(domain: Optional[str] = None) -> List[str]:
    return _PROVIDER.get_feed_urls(domain)


def _build_retry(total: int = DEFAULT_RETRIES, backoff_factor: float = DEFAULT_BACKOFF_FACTOR) -> Optional[Any]:
    if Retry is None:
        return None
    return Retry(total=total, read=total, connect=total, status=total, backoff_factor=backoff_factor, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET", "HEAD"}), raise_on_status=False)


def _request_with_retry(url: str, timeout: float = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES, backoff_factor: float = DEFAULT_BACKOFF_FACTOR) -> requests.Response:
    session = _session()
    retry = _build_retry(retries, backoff_factor)
    if retry is not None:
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                # Add jitter to avoid synchronized retries
                import random
                jitter = random.uniform(0, 0.1 * backoff_factor)
                sleep_for = backoff_factor * (2**attempt) + jitter
                time.sleep(sleep_for)
    assert last_exc is not None
    raise last_exc


def validate_feed(url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    return _PROVIDER.validate_feed(url, timeout=timeout)


def validate_all_feeds(timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Dict[str, Any]]:
    return _PROVIDER.validate_all_feeds(timeout=timeout, max_workers=max_workers)


def fetch_feed(url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
    return _PROVIDER.fetch_feed(url, timeout=timeout)


def fetch_multiple_feeds(urls: Sequence[str], timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> List[Tuple[str, Optional[str]]]:
    return _PROVIDER.fetch_multiple_feeds(urls, timeout=timeout, max_workers=max_workers)


def fetch_article_content(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    cached = _get_cache(_ARTICLE_CACHE, url, ttl_seconds=ARTICLE_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    try:
        response = _request_with_retry(url, timeout=timeout)
        body = _extract_text_from_html(response.text)
        _set_cache(_ARTICLE_CACHE, url, body, ttl_seconds=ARTICLE_CACHE_TTL_SECONDS)
        return body
    except Exception as exc:
        logger.warning("Unable to fetch article content from %s: %s", url, exc)
        return ""


def _extract_text_from_html(html_text: str) -> str:
    cleaned = re.sub(r"<script.*?</script>", " ", html_text, flags=re.S | re.I)
    cleaned = re.sub(r"<style.*?</style>", " ", cleaned, flags=re.S | re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _safe_xml_root(xml_text: str) -> Optional[ET.Element]:
    if not xml_text:
        return None
    try:
        return ET.fromstring(xml_text.encode("utf-8", errors="ignore") if isinstance(xml_text, str) else xml_text)
    except Exception:
        try:
            parser = ET.XMLParser(encoding="utf-8")
            return ET.fromstring(xml_text, parser=parser)
        except Exception:
            return None


def _detect_feed_type(root: Optional[ET.Element]) -> str:
    if root is None:
        return "unknown"
    tag = _strip_ns(root.tag).lower()
    if tag == "rss":
        return "rss"
    if tag == "feed":
        return "atom"
    return "unknown"


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_text(node: Optional[ET.Element], paths: Sequence[str]) -> str:
    if node is None:
        return ""
    for path in paths:
        child = node.find(path)
        if child is not None and child.text:
            return unescape(child.text.strip())
    return ""


def _enrich_entries(entries: Sequence[Mapping[str, Any]], feed_url: str, feed_name: str, category: str) -> List[Dict[str, Any]]:
    fetched_at = _now_utc().isoformat()
    out: List[Dict[str, Any]] = []
    for entry in entries:
        enriched = dict(entry)
        enriched["feed_url"] = feed_url
        enriched["feed_name"] = feed_name
        enriched["category"] = category
        enriched["fetched_at"] = fetched_at
        out.append(enriched)
    return out


def _feed_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.replace("www.", "") if parsed.netloc else "techcrunch"


def _normalize_url(url: str) -> str:
    """Normalize URL by removing tracking parameters and fragments."""
    if not url:
        return url
    
    try:
        parsed = urlparse(url)
        
        # Remove common tracking parameters
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'mc_cid', 'mc_eid', '_ga', 'ref', 'source'
        }
        
        if parsed.query:
            query_params = parse_qs(parsed.query, keep_blank_values=False)
            cleaned_params = {k: v for k, v in query_params.items() if k not in tracking_params}
            
            # Rebuild query string
            if cleaned_params:
                from urllib.parse import urlencode
                new_query = urlencode(cleaned_params, doseq=True)
            else:
                new_query = ''
        else:
            new_query = ''
        
        # Rebuild URL without fragment and with cleaned query
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),  # Lowercase domain
            parsed.path,
            parsed.params,
            new_query,
            ''  # No fragment
        ))
        
        # Remove trailing slash
        if normalized.endswith('/') and len(parsed.path) > 1:
            normalized = normalized.rstrip('/')
        
        return normalized
        
    except Exception:
        return url


def _parse_date(value: str) -> str:
    """Parse and normalize date to UTC ISO format with comprehensive format support."""
    if not value:
        return ""
    
    value_stripped = value.strip()
    
    # Try ISO format first (fastest path)
    try:
        dt = _dt.datetime.fromisoformat(value_stripped.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt.astimezone(_dt.timezone.utc).isoformat()
    except Exception:
        pass
    
    # Common RSS/Atom date formats
    date_formats = [
        "%a, %d %b %Y %H:%M:%S %z",      # RFC 822/2822: Mon, 01 Jan 2024 12:00:00 +0000
        "%a, %d %b %Y %H:%M:%S %Z",      # With timezone name
        "%Y-%m-%dT%H:%M:%S%z",            # ISO 8601 with timezone
        "%Y-%m-%dT%H:%M:%SZ",             # ISO 8601 UTC (Zulu)
        "%Y-%m-%dT%H:%M:%S.%f%z",        # ISO with microseconds and tz
        "%Y-%m-%dT%H:%M:%S.%fZ",         # ISO with microseconds UTC
        "%Y-%m-%d %H:%M:%S",              # Simple datetime
        "%Y-%m-%d",                       # Date only
        "%d %b %Y %H:%M:%S %z",          # 01 Jan 2024 12:00:00 +0000
        "%d %b %Y",                       # 01 Jan 2024
    ]
    
    for fmt in date_formats:
        try:
            dt = _dt.datetime.strptime(value_stripped, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
            return dt.astimezone(_dt.timezone.utc).isoformat()
        except Exception:
            continue
    
    # Handle special timezone names
    try:
        # Replace common timezone abbreviations
        value_normalized = value_stripped
        for tz_abbr, tz_offset in [
            ('GMT', '+0000'), ('UTC', '+0000'), ('EST', '-0500'), 
            ('EDT', '-0400'), ('CST', '-0600'), ('CDT', '-0500'),
            ('MST', '-0700'), ('MDT', '-0600'), ('PST', '-0800'), ('PDT', '-0700')
        ]:
            if tz_abbr in value_normalized:
                value_normalized = value_normalized.replace(tz_abbr, tz_offset)
                break
        
        if value_normalized != value_stripped:
            return _parse_date(value_normalized)
    except Exception:
        pass
    
    # If all parsing fails, return original value
    logger.debug(f"Could not parse date: {value_stripped}")
    return value_stripped


def _parse_with_feedparser(xml_text: str) -> List[Dict[str, Any]]:
    if _feedparser is None:
        return []
    try:
        parsed = _feedparser.parse(xml_text)
        entries: List[Dict[str, Any]] = []
        for item in getattr(parsed, "entries", []) or []:
            title = item.get("title") or ""
            link = item.get("link") or item.get("id") or ""
            published = item.get("published") or item.get("updated") or item.get("created") or ""
            summary = item.get("summary") or ""
            if isinstance(summary, dict):
                summary = summary.get("value", "")
            content_parts = item.get("content") or []
            if content_parts and isinstance(content_parts[0], dict):
                summary = content_parts[0].get("value", summary)
            author = item.get("author") or ""
            guid = item.get("id") or link or title
            entries.append(_normalize_entry({
                "title": title,
                "url": link,
                "published": published,
                "summary": summary,
                "author": author,
                "guid": guid,
            }, domain="all"))
        return entries
    except Exception:
        return []


def _parse_with_manual_fallback(xml_text: str, domain: str = "all") -> List[Dict[str, Any]]:
    root = _safe_xml_root(xml_text)
    if root is None:
        return []
    feed_type = _detect_feed_type(root)
    entries: List[Dict[str, Any]] = []
    if feed_type == "rss":
        channel = root.find("channel")
        if channel is None:
            channel = root
        items = channel.findall("item")
        for item in items:
            raw = {
                "title": _find_text(item, ["title"]),
                "url": _find_text(item, ["link"]),
                "published": _find_text(item, ["pubDate", "published"]),
                "summary": _find_text(item, ["description", "summary", "content"]),
                "author": _find_text(item, ["author"]),
                "guid": _find_text(item, ["guid"]),
            }
            try:
                dc_creator = ""
                for child in item.iter():
                    if _strip_ns(child.tag) in {"creator", "author"} and child.text:
                        dc_creator = child.text.strip()
                        break
                if not raw["author"]:
                    raw["author"] = dc_creator
            except Exception:
                pass
            entries.append(_normalize_entry(raw, domain))
    elif feed_type == "atom":
        for entry in root.findall(".//{*}entry"):
            link = ""
            for lnk in entry.findall("{*}link"):
                href = lnk.attrib.get("href", "")
                rel = lnk.attrib.get("rel", "alternate")
                if href and rel in {"alternate", ""}:
                    link = href
                    break
            raw = {
                "title": _find_text(entry, ["{*}title"]),
                "url": link,
                "published": _find_text(entry, ["{*}published", "{*}updated"]),
                "summary": _find_text(entry, ["{*}summary", "{*}content"]),
                "author": _find_text(entry, ["{*}author/{*}name"]),
                "guid": _find_text(entry, ["{*}id"]),
            }
            entries.append(_normalize_entry(raw, domain))
    return entries


def _entry_hash(entry: Mapping[str, Any]) -> str:
    key = "|".join(str(entry.get(k, "")).strip().lower() for k in ("guid", "url", "title"))
    return hashlib.sha256(key.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_entry(raw: Mapping[str, Any], domain: str) -> Dict[str, Any]:
    """Normalize entry with sanitization, URL normalization, and metadata."""
    try:
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("url") or raw.get("link") or "").strip()
        published = _parse_date(str(raw.get("published") or raw.get("pubDate") or raw.get("updated") or ""))
        summary = str(raw.get("summary") or raw.get("description") or raw.get("content") or "").strip()
        author = str(raw.get("author") or raw.get("creator") or raw.get("dc_creator") or "").strip()
        guid = str(raw.get("guid") or raw.get("id") or url or title).strip()
        
        # Sanitize title (remove excessive whitespace, HTML artifacts)
        if title:
            title = re.sub(r'\s+', ' ', title)
            title = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', title)  # Remove control chars
            title = unescape(title)
        
        # Normalize URL
        if url:
            url = _normalize_url(url)
        
        # Sanitize summary (remove HTML if present, excessive whitespace)
        if summary:
            # Remove HTML tags if present
            if '<' in summary and '>' in summary:
                summary = re.sub(r'<[^>]+>', ' ', summary)
            summary = re.sub(r'\s+', ' ', summary)
            summary = unescape(summary)
            # Limit summary length
            if len(summary) > 5000:
                summary = summary[:5000] + "..."
        
        # Calculate content metrics
        content = raw.get("content") or raw.get("article_content") or summary
        content_text = str(content).strip()
        word_count = len(content_text.split()) if content_text else 0
        reading_time_minutes = max(1, word_count // 200)  # Avg reading speed: 200 words/min
        
        return {
            "title": title,
            "url": url,
            "published": published,
            "summary": summary,
            "author": author,
            "domain": domain,
            "source": SOURCE_NAME,
            "guid": guid,
            "content_length": len(content_text),
            "word_count": word_count,
            "reading_time_minutes": reading_time_minutes,
        }
    except Exception as e:
        logger.error(f"Error normalizing entry: {e}")
        # Return minimal valid entry
        return {
            "title": str(raw.get("title", "Untitled")),
            "url": str(raw.get("url", "")),
            "published": "",
            "summary": "",
            "author": "",
            "domain": domain,
            "source": SOURCE_NAME,
            "guid": str(raw.get("guid", "")),
            "content_length": 0,
            "word_count": 0,
            "reading_time_minutes": 0,
        }


def parse_feed(feed: Any, domain: str = "all") -> List[Dict[str, Any]]:
    return _PROVIDER.parse_feed(feed, domain=domain)


def parse_feed_entries(feed: Any, domain: str = "all") -> List[Dict[str, Any]]:
    return parse_feed(feed, domain=domain)


def deduplicate_entries(entries: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate entries using URL, GUID, and title similarity."""
    seen: set[str] = set()
    seen_titles: Dict[str, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    
    for entry in entries:
        normalized = dict(entry)
        
        # Check exact fingerprint (URL + GUID + title)
        fingerprint = _entry_hash(normalized)
        if fingerprint in seen:
            continue
        
        # Check title similarity for near-duplicates
        title = str(normalized.get("title", "")).strip().lower()
        url = str(normalized.get("url", "")).strip()
        
        if title and url:
            # Normalize title for comparison
            title_normalized = re.sub(r'[^\w\s]', '', title)
            title_normalized = re.sub(r'\s+', ' ', title_normalized).strip()
            
            # Check for very similar titles
            is_duplicate = False
            for seen_title, seen_entry in list(seen_titles.items()):
                # Exact match after normalization
                if title_normalized == seen_title:
                    is_duplicate = True
                    break
                
                # High similarity (> 90% common words)
                if title_normalized and seen_title:
                    title_words = set(title_normalized.split())
                    seen_words = set(seen_title.split())
                    if title_words and seen_words:
                        common = len(title_words & seen_words)
                        total = len(title_words | seen_words)
                        similarity = common / total if total > 0 else 0
                        if similarity > 0.9:
                            is_duplicate = True
                            break
            
            if is_duplicate:
                continue
            
            seen_titles[title_normalized] = normalized
        
        seen.add(fingerprint)
        out.append(normalized)
    
    return out


def sort_entries(entries: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Sort entries newest-first with proper timestamp parsing and fallbacks."""
    def key(entry: Mapping[str, Any]) -> Tuple[int, float, str]:
        published = str(entry.get("published") or "")
        try:
            if published:
                dt = _dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_dt.timezone.utc)
                ts = dt.timestamp()
            else:
                ts = 0.0
        except Exception:
            ts = 0.0
        # Sort by: (has_timestamp [0=yes, 1=no], -timestamp [newest first], title)
        return (0 if ts > 0 else 1, -ts, str(entry.get("title", "")).lower())
    
    return sorted((dict(e) for e in entries), key=key)


def _sort_newest_first(entries: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return sort_entries(entries)


def get_latest_entries(domain: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    return _PROVIDER.get_latest_entries(domain=domain, limit=limit)


def _domain_from_url(url: str, fallback_domain: Optional[str] = None) -> str:
    if fallback_domain:
        try:
            return validate_domain(fallback_domain)
        except Exception:
            pass
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")
    if len(path) >= 2 and path[0] in {"category", "tag"}:
        return _normalize_domain(path[1]) or path[1]
    return "all"


def _tokenize(query: str) -> List[str]:
    query = (query or "").strip().lower()
    if not query:
        return []
    return [t for t in re.findall(r'"[^"]+"|\S+', query) if t]


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _fuzzy_match(term: str, text: str, threshold: int = 85) -> bool:
    """Check if term fuzzy matches text with given threshold."""
    if not term or not text:
        return False
    
    # Exact match
    if term in text:
        return True
    
    # Use rapidfuzz if available
    if fuzz is not None:
        try:
            score = fuzz.partial_ratio(term, text)
            return score >= threshold
        except Exception:
            pass
    
    # Fallback: simple character-based similarity
    term_lower = term.lower()
    text_lower = text.lower()
    
    # Check for term with minor variations (openai -> open ai)
    term_no_space = term_lower.replace(" ", "")
    if term_no_space in text_lower.replace(" ", ""):
        return True
    
    return False


def _parse_search_operators(query: str) -> Tuple[List[str], List[str], List[str]]:
    """Parse search query for operators: +required -excluded "exact phrase"
    
    Returns:
        Tuple of (required_terms, excluded_terms, phrases)
    """
    required: List[str] = []
    excluded: List[str] = []
    phrases: List[str] = []
    
    # Extract quoted phrases first
    phrase_pattern = r'"([^"]+)"'
    for match in re.finditer(phrase_pattern, query):
        phrases.append(match.group(1).lower().strip())
    
    # Remove phrases from query for further processing
    query_without_phrases = re.sub(phrase_pattern, "", query)
    
    # Extract operators
    tokens = query_without_phrases.split()
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        
        if token.startswith("+"):
            term = token[1:].strip()
            if term:
                required.append(term.lower())
        elif token.startswith("-"):
            term = token[1:].strip()
            if term:
                excluded.append(term.lower())
        else:
            # Regular word becomes a required term
            required.append(token.lower())
    
    return required, excluded, phrases


def _parse_query(query: str) -> Tuple[List[str], List[str]]:
    tokens = _tokenize(query)
    phrases = [t.strip('"').lower() for t in tokens if t.startswith('"') and t.endswith('"') and len(t) > 1]
    words: List[str] = []
    for t in tokens:
        if t.startswith('"') and t.endswith('"'):
            continue
        words.extend([w for w in re.split(r"\W+", t.lower()) if w])
    return phrases, words


def rank_entries(entries: Sequence[Mapping[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Rank entries by relevance with weighted scoring, phrase matching, operators, and recency boost."""
    start_time = time.perf_counter()
    _RUNTIME_STATS["ranking_count"] += 1
    
    try:
        phrases, words = _parse_query(query)
        required, excluded, operator_phrases = _parse_search_operators(query)
        
        # Combine phrases
        all_phrases = list(set(phrases + operator_phrases))
        
        # Combine words and required terms
        all_words = list(set(words + required))
        
        if not all_phrases and not all_words:
            return []
        
        scored: List[Dict[str, Any]] = []
        now = _now_utc()
        weights = DEFAULT_CONFIG.ranking_weights
        
        for entry in entries:
            e = dict(entry)
            text_title = _clean_text(e.get("title", ""))
            text_summary = _clean_text(e.get("summary", ""))
            text_author = _clean_text(e.get("author", ""))
            text_url = _clean_text(e.get("url", ""))
            text_domain = _clean_text(e.get("domain", ""))
            text_content = _clean_text(e.get("content") or e.get("article_content") or "")
            combined = " ".join([text_title, text_summary, text_author, text_url, text_domain, text_content])
            
            # Check exclusions first
            should_exclude = False
            for excluded_term in excluded:
                if excluded_term in combined:
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
            
            score = 0.0
            matched_terms: List[str] = []
            match_locations: Dict[str, List[str]] = {}
            ranking_breakdown: Dict[str, float] = {
                "phrase_matches": 0.0,
                "title_matches": 0.0,
                "summary_matches": 0.0,
                "content_matches": 0.0,
                "author_matches": 0.0,
                "domain_matches": 0.0,
                "url_matches": 0.0,
                "recency_bonus": 0.0,
                "all_terms_bonus": 0.0,
            }
            
            # Score exact phrase matches
            for phrase in all_phrases:
                phrase_score = 0.0
                locations = []
                
                if phrase in text_title:
                    phrase_score += weights.exact_phrase_in_title
                    locations.append("title")
                if phrase in text_summary:
                    phrase_score += weights.phrase_match_bonus * 0.4
                    locations.append("summary")
                if phrase in text_content:
                    phrase_score += weights.phrase_match_bonus * 0.6
                    locations.append("content")
                if phrase in combined and not locations:
                    phrase_score += weights.phrase_match_bonus * 0.2
                    locations.append("other")
                
                if phrase_score > 0:
                    score += phrase_score
                    ranking_breakdown["phrase_matches"] += phrase_score
                    matched_terms.append(f'"{phrase}"')
                    match_locations[f'"{phrase}"'] = locations
            
            # Score individual words with weighted fields
            for word in all_words:
                word_score = 0.0
                locations = []
                
                # Count occurrences in each field
                title_count = text_title.count(word)
                summary_count = text_summary.count(word)
                author_count = text_author.count(word)
                url_count = text_url.count(word)
                domain_count = text_domain.count(word)
                content_count = text_content.count(word)
                
                # Apply weighted scoring
                if title_count > 0:
                    field_score = title_count * weights.title
                    word_score += field_score
                    ranking_breakdown["title_matches"] += field_score
                    locations.append("title")
                
                if summary_count > 0:
                    field_score = summary_count * weights.summary
                    word_score += field_score
                    ranking_breakdown["summary_matches"] += field_score
                    locations.append("summary")
                
                if content_count > 0:
                    field_score = content_count * weights.content
                    word_score += field_score
                    ranking_breakdown["content_matches"] += field_score
                    locations.append("content")
                
                if author_count > 0:
                    field_score = author_count * weights.author
                    word_score += field_score
                    ranking_breakdown["author_matches"] += field_score
                    locations.append("author")
                
                if url_count > 0:
                    field_score = url_count * weights.url
                    word_score += field_score
                    ranking_breakdown["url_matches"] += field_score
                    locations.append("url")
                
                if domain_count > 0:
                    field_score = domain_count * weights.domain
                    word_score += field_score
                    ranking_breakdown["domain_matches"] += field_score
                    locations.append("domain")
                
                # Fuzzy matching bonus
                if not locations and _fuzzy_match(word, combined):
                    word_score += 3.0
                    locations.append("fuzzy")
                
                if word_score > 0:
                    score += word_score
                    matched_terms.append(word)
                    match_locations[word] = locations
            
            # Bonus for all required terms present
            if required:
                all_required_present = all(
                    req_term in combined or _fuzzy_match(req_term, combined)
                    for req_term in required
                )
                if not all_required_present:
                    continue  # Skip entries missing required terms
            
            # Bonus for all words present
            if all_words and all(w in combined for w in all_words):
                score += weights.all_terms_match
                ranking_breakdown["all_terms_bonus"] = weights.all_terms_match
            
            # Recency bonus with increased weight
            published = str(e.get("published") or "")
            try:
                if published:
                    dt = _dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=_dt.timezone.utc)
                    
                    age_days = max((now - dt.astimezone(_dt.timezone.utc)).total_seconds() / 86400.0, 0.0)
                    recency_bonus = max(0.0, weights.recency_base - age_days * weights.recency_decay_rate)
                    score += recency_bonus
                    ranking_breakdown["recency_bonus"] = round(recency_bonus, 2)
            except Exception:
                pass
            
            if score > 0:
                # Deduplicate matched terms while preserving order
                matched_terms = list(dict.fromkeys(matched_terms))
                
                # Add confidence score (0-1 scale based on match quality)
                confidence = min(1.0, score / 200.0)  # Normalize to 0-1
                
                e["score"] = round(score, 2)
                e["matched_terms"] = matched_terms
                e["match_count"] = len(matched_terms)
                e["match_locations"] = match_locations
                e["ranking_breakdown"] = {k: round(v, 2) for k, v in ranking_breakdown.items()}
                e["confidence"] = round(confidence, 3)
                scored.append(e)
        
        # Sort by score (desc), then by published date (desc), then by title
        scored.sort(key=lambda x: (
            -float(x.get("score", 0.0)),
            str(x.get("published", "")) != "",
            -_timestamp_from_iso(str(x.get("published", ""))),
            str(x.get("title", "")).lower()
        ))
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["ranking_total_ms"] += duration_ms
        _log_metric("ranking_duration", duration_ms, result_count=len(scored))
        
        return scored
        
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["ranking_total_ms"] += duration_ms
        logger.error(f"Ranking failed: {exc}")
        return []


def _timestamp_from_iso(iso_str: str) -> float:
    """Convert ISO timestamp to float for sorting."""
    if not iso_str:
        return 0.0
    try:
        dt = _dt.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def search_entries(entries: Sequence[Mapping[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Search entries with metrics tracking and error handling."""
    start_time = time.perf_counter()
    _RUNTIME_STATS["search_count"] += 1
    
    try:
        _log_event("search_started", query=query, entry_count=len(list(entries)))
        
        ranked = rank_entries(entries, query)
        results = [e for e in ranked if e.get("score", 0.0) > 0]
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["search_total_ms"] += duration_ms
        _log_event("search_completed", query=query, result_count=len(results), duration_ms=round(duration_ms, 2))
        _log_metric("search_duration", duration_ms, query_length=len(query))
        
        return results
        
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["search_total_ms"] += duration_ms
        _log_event("search_error", query=query, error=str(exc), duration_ms=round(duration_ms, 2))
        logger.error(f"Search failed for query '{query}': {exc}")
        raise SearchError(f"Search failed: {exc}") from exc


def filter_entries(entries: Sequence[Mapping[str, Any]], query: str) -> List[Dict[str, Any]]:
    return search_entries(entries, query)


def filter_by_date(
    entries: Sequence[Mapping[str, Any]], 
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filter entries by publication date.
    
    Args:
        entries: List of entries to filter
        days: Filter to last N days (e.g., 7 for last week)
        start_date: ISO format start date (inclusive)
        end_date: ISO format end date (inclusive)
    
    Returns:
        Filtered list of entries
    """
    now = _now_utc()
    filtered: List[Dict[str, Any]] = []
    
    for entry in entries:
        e = dict(entry)
        published_str = str(e.get("published") or "")
        
        if not published_str:
            continue
        
        try:
            published_dt = _dt.datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            if published_dt.tzinfo is None:
                published_dt = published_dt.replace(tzinfo=_dt.timezone.utc)
            
            # Filter by days
            if days is not None:
                age_days = (now - published_dt).total_seconds() / 86400.0
                if age_days > days:
                    continue
            
            # Filter by date range
            if start_date:
                start_dt = _dt.datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=_dt.timezone.utc)
                if published_dt < start_dt:
                    continue
            
            if end_date:
                end_dt = _dt.datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=_dt.timezone.utc)
                if published_dt > end_dt:
                    continue
            
            filtered.append(e)
        except Exception:
            continue
    
    return filtered


def filter_by_author(entries: Sequence[Mapping[str, Any]], author: str) -> List[Dict[str, Any]]:
    """Filter entries by author name (case-insensitive partial match)."""
    author_lower = author.lower().strip()
    return [
        dict(e) for e in entries 
        if author_lower in str(e.get("author", "")).lower()
    ]


def filter_by_domain(entries: Sequence[Mapping[str, Any]], domain: str) -> List[Dict[str, Any]]:
    """Filter entries by domain/category."""
    domain_normalized = _normalize_domain(domain)
    return [
        dict(e) for e in entries 
        if e.get("domain") == domain_normalized
    ]


def filter_by_keyword(entries: Sequence[Mapping[str, Any]], keyword: str) -> List[Dict[str, Any]]:
    """Filter entries containing keyword in title, summary, or content."""
    keyword_lower = keyword.lower().strip()
    filtered: List[Dict[str, Any]] = []
    
    for entry in entries:
        e = dict(entry)
        searchable = " ".join([
            str(e.get("title", "")),
            str(e.get("summary", "")),
            str(e.get("content", "")),
            str(e.get("article_content", "")),
        ]).lower()
        
        if keyword_lower in searchable:
            filtered.append(e)
    
    return filtered


def filter_by_feed(entries: Sequence[Mapping[str, Any]], feed_url: str) -> List[Dict[str, Any]]:
    """Filter entries by feed URL."""
    return [
        dict(e) for e in entries 
        if e.get("feed_url") == feed_url
    ]


def search_feeds(query: str, domains: Optional[Sequence[str]] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Search feeds and filter by query (OLD behavior)."""
    return _PROVIDER.search_feeds(query=query, domains=domains, limit=limit)


def get_all_feed_entries(domains: Optional[Sequence[str]] = None, limit: int = 500) -> List[Dict[str, Any]]:
    """Get ALL feed entries without query filtering - for discovery-first flow.
    
    Returns all RSS entries from specified domains without any query filtering.
    This allows the ranking engine to decide relevance, not the RSS parser.
    
    Args:
        domains: Feed domains to fetch from (e.g., ['ai', 'startups'])
        limit: Max total entries to return (default: 500)
    
    Returns:
        List of ALL RSS entries with metadata ready for ranking
    """
    return _PROVIDER.get_all_feed_entries(domains=domains, limit=limit)



def get_top_authors(entries: Sequence[Mapping[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Get top authors by article count.
    
    Returns:
        List of dicts with 'author', 'count', 'articles'
    """
    from collections import Counter
    
    author_articles: Dict[str, List[Dict[str, Any]]] = {}
    
    for entry in entries:
        author = str(entry.get("author", "")).strip()
        if not author or author.lower() in {"unknown", "anonymous", "n/a"}:
            continue
        
        if author not in author_articles:
            author_articles[author] = []
        author_articles[author].append(dict(entry))
    
    results = [
        {
            "author": author,
            "count": len(articles),
            "articles": articles[:5],  # Sample of recent articles
        }
        for author, articles in author_articles.items()
    ]
    
    results.sort(key=lambda x: (-x["count"], x["author"]))
    return results[:limit]


def get_top_keywords(entries: Sequence[Mapping[str, Any]], limit: int = 20, min_length: int = 4) -> List[Dict[str, Any]]:
    """Extract top keywords from entries.
    
    Returns:
        List of dicts with 'keyword' and 'count'
    """
    from collections import Counter
    
    # Common stop words to exclude
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "have", "has", 
        "will", "what", "when", "where", "who", "why", "how", "said", "says",
        "about", "after", "before", "into", "through", "during", "more", "most",
        "also", "than", "been", "were", "they", "their", "there", "these", "those",
        "which", "your", "our", "can", "could", "would", "should", "may", "might"
    }
    
    word_counts: Counter = Counter()
    
    for entry in entries:
        text = " ".join([
            str(entry.get("title", "")),
            str(entry.get("summary", "")),
        ]).lower()
        
        # Extract words
        words = re.findall(r'\b[a-z]+\b', text)
        
        for word in words:
            if len(word) >= min_length and word not in stop_words:
                word_counts[word] += 1
    
    results = [
        {"keyword": word, "count": count}
        for word, count in word_counts.most_common(limit)
    ]
    
    return results


def get_feed_activity(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Analyze feed activity patterns.
    
    Returns:
        Dict with activity metrics by feed, domain, and time
    """
    from collections import defaultdict
    
    by_feed: Dict[str, int] = defaultdict(int)
    by_domain: Dict[str, int] = defaultdict(int)
    by_date: Dict[str, int] = defaultdict(int)
    
    for entry in entries:
        feed_url = str(entry.get("feed_url", ""))
        domain = str(entry.get("domain", "all"))
        published = str(entry.get("published", ""))
        
        if feed_url:
            by_feed[feed_url] += 1
        
        if domain:
            by_domain[domain] += 1
        
        if published:
            try:
                dt = _dt.datetime.fromisoformat(published.replace("Z", "+00:00"))
                date_key = dt.strftime("%Y-%m-%d")
                by_date[date_key] += 1
            except Exception:
                pass
    
    return {
        "total_entries": len(list(entries)),
        "by_feed": dict(sorted(by_feed.items(), key=lambda x: -x[1])),
        "by_domain": dict(sorted(by_domain.items(), key=lambda x: -x[1])),
        "by_date": dict(sorted(by_date.items(), reverse=True)[:30]),  # Last 30 days
    }


def get_feed_distribution(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Get distribution statistics across feeds and domains.
    
    Returns:
        Dict with distribution metrics
    """
    from collections import Counter
    
    feeds = [str(e.get("feed_url", "")) for e in entries if e.get("feed_url")]
    domains = [str(e.get("domain", "")) for e in entries if e.get("domain")]
    authors = [str(e.get("author", "")) for e in entries if e.get("author")]
    
    feed_counts = Counter(feeds)
    domain_counts = Counter(domains)
    author_counts = Counter(authors)
    
    return {
        "total_entries": len(list(entries)),
        "unique_feeds": len(feed_counts),
        "unique_domains": len(domain_counts),
        "unique_authors": len(author_counts),
        "top_feeds": [{"feed": f, "count": c} for f, c in feed_counts.most_common(10)],
        "top_domains": [{"domain": d, "count": c} for d, c in domain_counts.most_common(10)],
        "top_authors": [{"author": a, "count": c} for a, c in author_counts.most_common(10)],
    }


def get_feed_metadata() -> Dict[str, Any]:
    domains = get_available_domains()
    urls = get_feed_urls()
    return {
        "source": SOURCE_NAME,
        "domain_count": len(domains),
        "feed_count": len(urls),
        "domains": domains,
        "feeds": {domain: [item["url"] for item in TECHCRUNCH_FEEDS.get(domain, [])] for domain in domains},
    }


def get_feed_health(url: Optional[str] = None) -> Dict[str, Any]:
    if url is None:
        return {k: dict(v) for k, v in _FEED_HEALTH.items()}
    return dict(_FEED_HEALTH.get(url, {}))


def get_entry_count(domain: Optional[str] = None) -> int:
    return len(get_latest_entries(domain=domain, limit=10_000))


def get_feed_statistics() -> Dict[str, Any]:
    metadata = get_feed_metadata()
    validation = validate_all_feeds()
    valid = sum(1 for item in validation if item.get("status") == "valid")
    invalid = sum(1 for item in validation if item.get("status") != "valid")
    return {
        "source": SOURCE_NAME,
        "domain_count": metadata["domain_count"],
        "feed_count": metadata["feed_count"],
        "valid_feeds": valid,
        "invalid_feeds": invalid,
        "validation_results": validation,
    }


def refresh_feed_registry(timeout: float = DEFAULT_TIMEOUT, max_workers: int = DEFAULT_MAX_WORKERS) -> Dict[str, Any]:
    results = validate_all_feeds(timeout=timeout, max_workers=max_workers)
    summary = {"valid": 0, "redirected": 0, "unreachable": 0, "invalid": 0, "results": results}
    for item in results:
        if item.get("status") == "valid":
            if item.get("redirected"):
                summary["redirected"] += 1
            else:
                summary["valid"] += 1
        elif item.get("http_status") in {None, 0}:
            summary["unreachable"] += 1
        else:
            summary["invalid"] += 1
    return summary


def to_json(entries: Sequence[Mapping[str, Any]]) -> str:
    return json.dumps([dict(e) for e in entries], ensure_ascii=False, indent=2, sort_keys=False)


def to_yaml(entries: Sequence[Mapping[str, Any]]) -> str:
    if yaml is None:
        raise RuntimeError("PyYAML is not installed. Install 'pyyaml' to use to_yaml().")
    return yaml.safe_dump([dict(e) for e in entries], sort_keys=False, allow_unicode=True)


def export_json(entries: Sequence[Mapping[str, Any]], path: str) -> str:
    """Export entries to JSON with error handling."""
    start_time = time.perf_counter()
    _RUNTIME_STATS["export_count"] += 1
    
    try:
        payload = to_json(entries)
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_completed", format="json", path=path, entry_count=len(list(entries)), duration_ms=round(duration_ms, 2))
        
        return path
        
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_error", format="json", path=path, error=str(exc))
        logger.error(f"Failed to export JSON to {path}: {exc}")
        raise ExportError(f"JSON export failed: {exc}") from exc


def export_yaml(entries: Sequence[Mapping[str, Any]], path: str) -> str:
    """Export entries to YAML with error handling."""
    start_time = time.perf_counter()
    _RUNTIME_STATS["export_count"] += 1
    
    try:
        payload = to_yaml(entries)
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_completed", format="yaml", path=path, entry_count=len(list(entries)), duration_ms=round(duration_ms, 2))
        
        return path
        
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_error", format="yaml", path=path, error=str(exc))
        logger.error(f"Failed to export YAML to {path}: {exc}")
        raise ExportError(f"YAML export failed: {exc}") from exc


def export_csv(entries: Sequence[Mapping[str, Any]], path: str) -> str:
    """Export entries to CSV format with error handling."""
    import csv
    
    start_time = time.perf_counter()
    _RUNTIME_STATS["export_count"] += 1
    
    try:
        if not entries:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("")
            return path
        
        # Determine all unique keys across entries
        all_keys = set()
        for entry in entries:
            all_keys.update(entry.keys())
        
        # Define field order (common fields first)
        priority_fields = [
            "title", "url", "published", "author", "summary", "domain", 
            "source", "score", "matched_terms", "match_count", "feed_name",
            "feed_url", "category", "content_length", "word_count", 
            "reading_time_minutes", "fetched_at", "confidence"
        ]
        
        ordered_fields = [f for f in priority_fields if f in all_keys]
        remaining_fields = sorted(all_keys - set(ordered_fields))
        fieldnames = ordered_fields + remaining_fields
        
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            
            for entry in entries:
                row = dict(entry)
                # Convert lists/dicts to strings for CSV
                for key, value in row.items():
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)
                writer.writerow(row)
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_completed", format="csv", path=path, entry_count=len(list(entries)), duration_ms=round(duration_ms, 2))
        
        return path
        
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_error", format="csv", path=path, error=str(exc))
        logger.error(f"Failed to export CSV to {path}: {exc}")
        raise ExportError(f"CSV export failed: {exc}") from exc


def export_jsonl(entries: Sequence[Mapping[str, Any]], path: str) -> str:
    """Export entries to JSON Lines format with error handling."""
    start_time = time.perf_counter()
    _RUNTIME_STATS["export_count"] += 1
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            for entry in entries:
                line = json.dumps(dict(entry), ensure_ascii=False, sort_keys=False)
                f.write(line + "\n")
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_completed", format="jsonl", path=path, entry_count=len(list(entries)), duration_ms=round(duration_ms, 2))
        
        return path
        
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        _RUNTIME_STATS["export_total_ms"] += duration_ms
        _log_event("export_error", format="jsonl", path=path, error=str(exc))
        logger.error(f"Failed to export JSONL to {path}: {exc}")
        raise ExportError(f"JSONL export failed: {exc}") from exc


def clear_cache(cache_type: Optional[str] = None) -> Dict[str, int]:
    """Clear caches.
    
    Args:
        cache_type: Type of cache to clear ('feed', 'article', or None for all)
    
    Returns:
        Dict with count of cleared entries per cache
    """
    cleared = {}
    
    if cache_type is None or cache_type == "feed":
        count = len(_FEED_CACHE)
        _FEED_CACHE.clear()
        cleared["feed_cache"] = count
    
    if cache_type is None or cache_type == "article":
        count = len(_ARTICLE_CACHE)
        _ARTICLE_CACHE.clear()
        cleared["article_cache"] = count
    
    return cleared


def invalidate_cache(url: str, cache_type: str = "feed") -> bool:
    """Invalidate a specific cache entry.
    
    Args:
        url: The URL to invalidate
        cache_type: 'feed' or 'article'
    
    Returns:
        True if entry was found and removed, False otherwise
    """
    try:
        if cache_type == "feed":
            return _FEED_CACHE.pop(url, None) is not None
        elif cache_type == "article":
            return _ARTICLE_CACHE.pop(url, None) is not None
        return False
    except Exception as e:
        logger.error(f"Failed to invalidate cache for {url}: {e}")
        return False


def get_runtime_statistics() -> Dict[str, Any]:
    """Get aggregate runtime statistics.
    
    Returns:
        Dict with performance metrics and counts
    """
    stats = dict(_RUNTIME_STATS)
    
    # Calculate averages
    if stats["fetch_count"] > 0:
        stats["avg_fetch_ms"] = round(stats["fetch_total_ms"] / stats["fetch_count"], 2)
    else:
        stats["avg_fetch_ms"] = 0.0
    
    if stats["parse_count"] > 0:
        stats["avg_parse_ms"] = round(stats["parse_total_ms"] / stats["parse_count"], 2)
    else:
        stats["avg_parse_ms"] = 0.0
    
    if stats["search_count"] > 0:
        stats["avg_search_ms"] = round(stats["search_total_ms"] / stats["search_count"], 2)
    else:
        stats["avg_search_ms"] = 0.0
    
    if stats["ranking_count"] > 0:
        stats["avg_ranking_ms"] = round(stats["ranking_total_ms"] / stats["ranking_count"], 2)
    else:
        stats["avg_ranking_ms"] = 0.0
    
    if stats["export_count"] > 0:
        stats["avg_export_ms"] = round(stats["export_total_ms"] / stats["export_count"], 2)
    else:
        stats["avg_export_ms"] = 0.0
    
    # Cache hit rate
    total_cache_ops = stats["cache_hits"] + stats["cache_misses"]
    if total_cache_ops > 0:
        stats["cache_hit_rate"] = round(stats["cache_hits"] / total_cache_ops, 3)
    else:
        stats["cache_hit_rate"] = 0.0
    
    return stats


def _self_test() -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    results["domains"] = get_available_domains()
    results["metadata"] = get_feed_metadata()
    results["sample_urls"] = get_feed_urls("ai")[:5]
    validation = validate_all_feeds()
    results["validation"] = validation[:3]
    sample_entries = get_latest_entries("ai", limit=5)
    results["sample_entries"] = sample_entries
    results["search"] = search_entries(sample_entries, "openai")
    results["ranked"] = rank_entries(sample_entries, "openai agents")
    
    # Test new filtering features
    results["filter_by_date"] = filter_by_date(sample_entries, days=7)
    results["top_keywords"] = get_top_keywords(sample_entries, limit=10)
    results["feed_activity"] = get_feed_activity(sample_entries)
    results["feed_distribution"] = get_feed_distribution(sample_entries)
    
    # Test search operators
    results["search_with_operators"] = search_entries(sample_entries, '+openai -funding "AI agents"')
    
    results["json"] = to_json(sample_entries[:2])
    try:
        results["yaml"] = to_yaml(sample_entries[:2])
    except Exception as exc:
        results["yaml_error"] = str(exc)
    results["count"] = get_entry_count("ai")
    results["stats"] = get_feed_statistics()
    
    # Cache stats
    results["cache_stats"] = {
        "feed_cache_size": len(_FEED_CACHE),
        "article_cache_size": len(_ARTICLE_CACHE),
        "circuit_breakers": len(_CIRCUIT_BREAKERS),
    }
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo = _self_test()
    print(json.dumps(demo, ensure_ascii=False, indent=2, default=str))
