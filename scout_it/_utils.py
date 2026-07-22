"""Shared utilities for scout-it source modules.

Provides common helpers used across multiple source modules to avoid
duplicate implementations of rate limiting, text cleaning, and session
building.
"""

import hashlib
import json
import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import header_profiles as _hp
from . import proxy_pool as _pp
from . import response_cache as _rc

logger = logging.getLogger(__name__)


# ── Rate limiter ──────────────────────────────────────────────────────────────


class SimpleRateLimiter:
    """Thread-safe rate limiter."""

    def __init__(self, rate_per_sec: float = 2.0):
        self.min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


# ── Session builder ───────────────────────────────────────────────────────────


def build_retry_session(
    retries: int = 3,
    pool_connections: int = 20,
    pool_maxsize: int = 20,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[List[int]] = None,
) -> requests.Session:
    """Build a ``requests.Session`` with Retry adapter and connection pooling.

    Args:
        retries: Total retry count for connect/read/status errors.
        pool_connections: Connection pool size.
        pool_maxsize: Max pool size.
        backoff_factor: Exponential backoff factor.
        status_forcelist: HTTP status codes that trigger a retry.

    Returns:
        Configured ``requests.Session``.
    """
    s = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist or [429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=pool_connections, pool_maxsize=pool_maxsize)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def cached_request_text(
    url: str,
    session: requests.Session,
    rate_limiter: Optional[SimpleRateLimiter] = None,
    timeout: int = 25,
    cache_ttl: int = 1800,
) -> Optional[str]:
    """Fetch URL text with rate limiting, proxy, caching.

    Args:
        url: URL to fetch.
        session: Requests session (with retry adapter).
        rate_limiter: Optional rate limiter.
        timeout: Request timeout.
        cache_ttl: Cache TTL in seconds.

    Returns:
        Response text, or None on failure.
    """
    cache_key = hashlib.sha256(f"rss::{url}".encode("utf-8")).hexdigest()[:32]
    cached = _rc.get(cache_key, cache_dir=None)
    if cached and cached.get("content"):
        return cached["content"]

    proxy_info = _pp.get_default_pool().get()
    headers = _hp.get_profile()

    if rate_limiter:
        rate_limiter.wait()

    try:
        resp = session.get(url, headers=headers, timeout=timeout, proxies=proxy_info["requests_proxies"])
        resp.raise_for_status()
        text = resp.text
        _rc.set(cache_key, text, content_type="rss", ttl_seconds=cache_ttl, extra={"url": url})
        return text
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request failed for {url}: {e}")
        return None


# ── Prune empty ───────────────────────────────────────────────────────────────


def prune_empty(obj: Any) -> Any:
    """Recursively remove None / empty-string / empty-collection values."""
    if isinstance(obj, dict):
        cleaned = {k: prune_empty(v) for k, v in obj.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, "", [], {}, ())}
    if isinstance(obj, list):
        cleaned = [prune_empty(v) for v in obj]
        return [v for v in cleaned if v not in (None, "", [], {}, ())]
    return obj
