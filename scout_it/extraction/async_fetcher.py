"""Async bulk-fetch core (D3) — opt-in high-throughput fetching.

Implements the same tier-ladder *decisions* as ``fetch_resilient`` (via the
shared pure function ``looks_blocked``) on top of httpx's async client, plus
a politeness governor that preserves the sync path's per-domain guarantees:
max 1 concurrent request per domain with a minimum delay, while different
domains proceed in parallel.

Browser tiers (Playwright) are not available on the async path — callers
needing JS rendering should use the sync ladder. The async ladder runs:
httpx (with retries) -> basic-fallback -> (opt-in) alternate source is left
to the sync path as well.

Bandit/strategy-cache outcome recording happens inline on the event-loop
task (D3.3): all writes for a given run are confined to the single loop
thread, so no locking is required beyond what ``strategy_cache`` provides.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .fetcher import looks_blocked

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT_PER_DOMAIN = 1
DEFAULT_MIN_DELAY_SECONDS = 0.5


def _result(
    url: str,
    html: str,
    status: str,
    tier: str,
    attempts: int,
    errors: List[str],
    final_url: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "html": html,
        "final_url": final_url or url,
        "status": status,
        "tier": tier,
        "attempts": attempts,
        "errors": errors,
    }


class AsyncDomainGovernor:
    """Per-domain serialization + min delay inside one event loop (D3.5)."""

    def __init__(
        self,
        max_concurrent_per_domain: int = DEFAULT_MAX_CONCURRENT_PER_DOMAIN,
        min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS,
    ) -> None:
        self.max_concurrent_per_domain = max_concurrent_per_domain
        self.min_delay_seconds = min_delay_seconds
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._last_request_time: Dict[str, float] = {}

    @staticmethod
    def domain_of(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return url

    async def acquire(self, url: str) -> None:
        domain = self.domain_of(url)
        sem = self._semaphores.get(domain)
        if sem is None:
            sem = asyncio.Semaphore(self.max_concurrent_per_domain)
            self._semaphores[domain] = sem
        await sem.acquire()
        last = self._last_request_time.get(domain)
        if last is not None and self.min_delay_seconds > 0:
            wait = self.min_delay_seconds - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)

    def release(self, url: str) -> None:
        domain = self.domain_of(url)
        self._last_request_time[domain] = time.monotonic()
        sem = self._semaphores.get(domain)
        if sem is not None:
            sem.release()


async def fetch_resilient_async(
    url: str,
    *,
    client: Any = None,
    timeout: int = 25,
    max_retries: int = 3,
    enable_strategy_cache: bool = True,
    governor: Optional[AsyncDomainGovernor] = None,
) -> Dict[str, Any]:
    """Async tier ladder with the same return contract as ``fetch_resilient``.

    Tiers: ``requests`` (httpx async, retried) -> ``basic-fallback`` (bare
    headers). A response that ``looks_blocked`` triggers one retry of the
    next attempt rather than browser escalation (no Playwright here).
    """
    import httpx

    errs: List[str] = []
    total_attempts = 0

    def _record(tier: str, success: bool) -> None:
        if not enable_strategy_cache:
            return
        try:
            from .. import strategy_cache as _sc

            _sc.record_outcome(url, tier, success)
        except Exception:
            logger.debug("strategy-cache record failed", exc_info=True)

    # Disk response cache short-circuit, same as the sync ladder.
    if enable_strategy_cache:
        try:
            from .. import response_cache as _resp_cache

            cached = _resp_cache.get(url)
            if cached and cached.get("content"):
                _record("requests", True)
                out = _result(url, cached["content"], "success", "cache", 0, [])
                out["cached"] = True
                out["age_seconds"] = cached.get("age_seconds")
                return out
        except Exception:
            logger.debug("response-cache read failed", exc_info=True)

    def _cache_set(html: str) -> None:
        if not enable_strategy_cache:
            return
        try:
            from .. import response_cache as _resp_cache

            _resp_cache.set(url, html)
        except Exception:
            logger.debug("response-cache write failed", exc_info=True)

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(follow_redirects=True, timeout=timeout)

    if governor is not None:
        await governor.acquire(url)

    try:
        # ---- Tier 1: httpx (async equivalent of the requests tier) ----
        for _attempt in range(max(1, max_retries)):
            total_attempts += 1
            try:
                resp = await client.get(url)
                text = resp.text or ""
                if resp.status_code < 400 and not looks_blocked(text, resp.status_code):
                    _record("requests", True)
                    _cache_set(text)
                    return _result(
                        url, text, "success", "requests", total_attempts, errs,
                        final_url=str(resp.url),
                    )
                errs.append(f"httpx: HTTP {resp.status_code}")
            except Exception as exc:
                errs.append(f"httpx: {exc}")

        # ---- Tier 2: basic-fallback (bare headers) ----
        total_attempts += 1
        try:
            resp = await client.get(url, headers={"User-Agent": "scout-it/2.0"})
            text = resp.text or ""
            if resp.status_code < 400 and not looks_blocked(text, resp.status_code):
                _record("basic-fallback", True)
                _cache_set(text)
                return _result(
                    url, text, "success", "basic-fallback", total_attempts, errs,
                    final_url=str(resp.url),
                )
            errs.append(f"basic-fallback: HTTP {resp.status_code}")
        except Exception as exc:
            errs.append(f"basic-fallback: {exc}")

        _record("none", False)
        return _result(url, "", "failed", "none", total_attempts, errs)
    finally:
        if governor is not None:
            governor.release(url)
        if owns_client:
            await client.aclose()


async def fetch_many_async(
    urls: List[str],
    *,
    concurrency: int = 20,
    timeout: int = 25,
    max_retries: int = 3,
    min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS,
    enable_strategy_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch many URLs concurrently, preserving input order (D3.4).

    Global parallelism is capped by ``concurrency``; the per-domain governor
    additionally serializes same-domain requests with ``min_delay_seconds``
    between them so async bulk fetching cannot break politeness guarantees.
    """
    import httpx

    governor = AsyncDomainGovernor(min_delay_seconds=min_delay_seconds)
    gate = asyncio.Semaphore(max(1, concurrency))
    results: List[Optional[Dict[str, Any]]] = [None] * len(urls)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:

        async def worker(i: int, url: str) -> None:
            async with gate:
                results[i] = await fetch_resilient_async(
                    url,
                    client=client,
                    timeout=timeout,
                    max_retries=max_retries,
                    enable_strategy_cache=enable_strategy_cache,
                    governor=governor,
                )

        await asyncio.gather(*(worker(i, u) for i, u in enumerate(urls)))

    return [r if r is not None else _result(u, "", "failed", "none", 0, ["no result"]) for r, u in zip(results, urls)]


def fetch_many(
    urls: List[str],
    *,
    concurrency: int = 20,
    timeout: int = 25,
    max_retries: int = 3,
    enable_strategy_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Sync wrapper around :func:`fetch_many_async` (SDK/CLI surface)."""
    return asyncio.run(
        fetch_many_async(
            urls,
            concurrency=concurrency,
            timeout=timeout,
            max_retries=max_retries,
            enable_strategy_cache=enable_strategy_cache,
        )
    )
