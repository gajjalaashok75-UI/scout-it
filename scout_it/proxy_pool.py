#!/usr/bin/env python3
"""
🔀 PROXY POOL — rotation with graceful no-proxy degradation
====================================================================

Wired into ``fetch_resilient()``: each tier's request/Playwright call pulls
its connection through this pool instead of going direct.

**Critical requirement from the spec**: this must never hard-fail if the
user hasn't configured any proxies. ``PROXY_LIST`` (comma-separated
``http://user:pass@host:port`` entries) is read the same way every other
credential is in this project — via ``scout-it config`` / the stored
credentials file / a real environment variable, checked in that order by
``config.py``'s existing ``load_stored_credentials_into_env()``. If it's
absent, every method here degrades to "direct" (`proxy_id="direct"`,
`proxies=None`) rather than raising.
"""

import os
import random
import threading
import time
from typing import Any, Dict, List, Optional

DIRECT = "direct"


def _parse_proxy_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


class ProxyPool:
    """Rotates through configured proxies with simple health tracking.
    Thread-safe (a single shared instance can be used across the parallel
    workers `fetch_resilient` already runs under)."""

    def __init__(self, proxies: Optional[List[str]] = None):
        # PROXY_LIST is read via the same credential-loading path as every
        # other key in this project (scout-it config / env var) -- see
        # config.py's load_stored_credentials_into_env(), called at CLI
        # startup, which populates os.environ before this ever runs.
        self._proxies = proxies if proxies is not None else _parse_proxy_list(os.environ.get("PROXY_LIST"))
        self._lock = threading.Lock()
        self._cooldowns: Dict[str, float] = {}  # proxy_id -> unix ts until which it's benched
        self._index = 0

    @property
    def configured(self) -> bool:
        return len(self._proxies) > 0

    def _proxy_id(self, proxy_url: str) -> str:
        # Don't leak credentials into logs/stats -- id by host:port only.
        try:
            after_scheme = proxy_url.split("://", 1)[-1]
            host_part = after_scheme.split("@")[-1]
            return host_part
        except Exception:
            return "proxy"

    def available_ids(self) -> List[str]:
        """IDs usable right now for strategy-bandit arm restriction -- always
        includes 'direct' since that's always a valid fallback."""
        now = time.time()
        ids = [DIRECT]
        for p in self._proxies:
            pid = self._proxy_id(p)
            if self._cooldowns.get(pid, 0) <= now:
                ids.append(pid)
        return ids

    def get(self, preferred_id: Optional[str] = None) -> Dict[str, Any]:
        """Return the next proxy to use, honoring a preferred id (from the
        strategy bandit) if it's still healthy, otherwise rotating.

        Returns {"proxy_id": str, "requests_proxies": dict|None} where
        requests_proxies is directly usable as ``requests.get(..., proxies=...)``,
        or None for direct (no-proxy) connections.
        """
        if not self._proxies:
            return {"proxy_id": DIRECT, "requests_proxies": None}

        now = time.time()
        with self._lock:
            if preferred_id and preferred_id != DIRECT:
                for p in self._proxies:
                    if self._proxy_id(p) == preferred_id and self._cooldowns.get(preferred_id, 0) <= now:
                        return {"proxy_id": preferred_id, "requests_proxies": {"http": p, "https": p}}

            healthy = [p for p in self._proxies if self._cooldowns.get(self._proxy_id(p), 0) <= now]
            if not healthy:
                # Everything's benched -- degrade to direct rather than
                # blocking or hard-failing.
                return {"proxy_id": DIRECT, "requests_proxies": None}

            self._index = (self._index + 1) % len(healthy)
            chosen = healthy[self._index]
            return {"proxy_id": self._proxy_id(chosen), "requests_proxies": {"http": chosen, "https": chosen}}

    def mark_failed(self, proxy_id: str, cooldown_seconds: float = 60.0) -> None:
        """Bench a proxy for a while after a failure attributable to it."""
        if proxy_id == DIRECT:
            return
        with self._lock:
            self._cooldowns[proxy_id] = time.time() + cooldown_seconds

    def mark_success(self, proxy_id: str) -> None:
        if proxy_id == DIRECT:
            return
        with self._lock:
            self._cooldowns.pop(proxy_id, None)


_default_pool: Optional[ProxyPool] = None
_default_pool_lock = threading.Lock()


def get_default_pool() -> ProxyPool:
    """Process-wide shared pool, lazily built from PROXY_LIST. Rebuilt if
    the env var changes (e.g. after `scout-it config` runs mid-session)."""
    global _default_pool
    with _default_pool_lock:
        current_raw = os.environ.get("PROXY_LIST")
        if _default_pool is None or _default_pool._proxies != _parse_proxy_list(current_raw):
            _default_pool = ProxyPool()
        return _default_pool
