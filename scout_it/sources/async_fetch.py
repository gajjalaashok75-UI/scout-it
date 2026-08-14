"""Async-first HTTP fetch layer for source plugins.

Uses httpx (already installed) for async HTTP with:
  - Connection pooling (one client reused across all sources)
  - Rate limiting (polite to free APIs — 1 req/sec default)
  - Automatic retries with exponential backoff
  - Timeout handling (10s default, configurable per source)
  - Sync fallback via requests (for plugins that aren't async-aware)

Multi-source search is inherently parallel — querying 10 sources at once
with the old sync model would take 10× the longest source. With asyncio,
it takes max(source_times).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 15.0       # seconds
DEFAULT_RETRIES = 2
DEFAULT_RATE_LIMIT = 1.0     # requests per second (polite to free APIs)
USER_AGENT = "scout-it/1.6.0 (https://github.com/gajjalaashok75-UI/scout-it)"

# ─── Rate limiter ──────────────────────────────────────────────────────────


class RateLimiter:
    """Simple token-bucket rate limiter for async fetches."""

    def __init__(self, rate_per_sec: float = DEFAULT_RATE_LIMIT):
        self._min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()


# ─── Async fetch ────────────────────────────────────────────────────────────

_client: Optional[Any] = None  # lazy httpx.AsyncClient


async def _get_client() -> Any:
    """Get or create the shared httpx async client."""
    global _client
    if _client is None or _client.is_closed:
        import httpx
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _client


async def async_fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    rate_limiter: Optional[RateLimiter] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch JSON from a URL asynchronously with retries and rate limiting.

    Returns the parsed JSON dict, or None on failure (error is logged, not
    raised — one failing source shouldn't kill a multi-source search).
    """
    client = await _get_client()
    merged_headers = dict(headers or {})

    for attempt in range(retries + 1):
        if rate_limiter:
            await rate_limiter.acquire()
        try:
            resp = await client.get(url, params=params, headers=merged_headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt < retries:
                wait = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s...
                logger.debug("Fetch attempt %d failed for %s: %s (retrying in %.1fs)", attempt + 1, url, exc, wait)
                await asyncio.sleep(wait)
            else:
                logger.warning("Fetch failed for %s after %d attempts: %s", url, retries + 1, exc)
                return None
    return None


async def async_fetch_text(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    rate_limiter: Optional[RateLimiter] = None,
) -> Optional[str]:
    """Fetch raw text (e.g. Atom XML, HTML) from a URL asynchronously."""
    client = await _get_client()
    merged_headers = dict(headers or {})

    for attempt in range(retries + 1):
        if rate_limiter:
            await rate_limiter.acquire()
        try:
            resp = await client.get(url, params=params, headers=merged_headers, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            if attempt < retries:
                wait = 0.5 * (2 ** attempt)
                logger.debug("Fetch attempt %d failed for %s: %s (retrying in %.1fs)", attempt + 1, url, exc, wait)
                await asyncio.sleep(wait)
            else:
                logger.warning("Fetch failed for %s: %s", url, exc)
                return None
    return None


async def async_fetch_all(
    fetch_coros: List,
) -> List:
    """Run multiple fetch coroutines concurrently and gather results.

    Failed fetches return None (not raised), so one source failing doesn't
    affect others.
    """
    results = await asyncio.gather(*fetch_coros, return_exceptions=True)
    return [
        r if not isinstance(r, Exception) else None
        for r in results
    ]


async def close_client() -> None:
    """Close the shared httpx client (call at shutdown)."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
    _client = None


# ─── Sync wrapper ────────────────────────────────────────────────────────────

def sync_fetch_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[Dict[str, Any]]:
    """Synchronous JSON fetch using requests (fallback for non-async contexts).

    This is used by plugins when running outside an event loop (e.g., in
    the CLI's sync dispatch). It uses the requests library directly.
    """
    import requests
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)
    try:
        resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("Sync fetch failed for %s: %s", url, exc)
        return None


def sync_fetch_text(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """Synchronous text fetch using requests."""
    import requests
    merged_headers = {"User-Agent": USER_AGENT}
    if headers:
        merged_headers.update(headers)
    try:
        resp = requests.get(url, params=params, headers=merged_headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logger.warning("Sync fetch failed for %s: %s", url, exc)
        return None


def run_async(coro):
    """Run an async coroutine from sync code, handling event loop lifecycle.

    If there's already a running event loop (e.g. inside Jupyter), uses
    nest_asyncio-style fallback; otherwise creates a new loop.
    """
    try:
        loop = asyncio.get_running_loop()
        # Already in an event loop — create a task and wait.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No running loop — safe to create one.
        return asyncio.run(coro)
