#!/usr/bin/env python3
"""
🚧 POLITENESS GOVERNOR — per-domain concurrency caps + robots.txt
========================================================================

`web-search`/`multi-search`/`news-search` run several results through a
shared worker pool in parallel. Most of the time those results are spread
across many domains, so the aggregate worker count is fine -- but nothing
currently stops several results *from the same domain* from all being
fetched simultaneously, which is both impolite and a common trigger for
rate-limiting.

This module provides:
  - A per-domain semaphore (max concurrent in-flight requests to one host,
    independent of the overall worker pool size)
  - A per-domain minimum-delay-between-requests with jitter
  - robots.txt compliance checking (stdlib ``urllib.robotparser`` -- no new
    dependency), cached per domain so it's only fetched once per run
"""

import random
import threading
import time
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

DEFAULT_MAX_CONCURRENT_PER_DOMAIN = 2
DEFAULT_MIN_DELAY_SECONDS = 0.5
DEFAULT_JITTER_SECONDS = 0.5


class PolitenessGovernor:
    """Shared, thread-safe governor for a single run. Create one instance
    per top-level command invocation (e.g. one per `web-search` call) and
    pass it into the worker pool, rather than a global singleton -- keeps
    behavior predictable and testable."""

    def __init__(
        self,
        max_concurrent_per_domain: int = DEFAULT_MAX_CONCURRENT_PER_DOMAIN,
        min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS,
        jitter_seconds: float = DEFAULT_JITTER_SECONDS,
        respect_robots_txt: bool = True,
    ):
        self.max_concurrent_per_domain = max_concurrent_per_domain
        self.min_delay_seconds = min_delay_seconds
        self.jitter_seconds = jitter_seconds
        self.respect_robots_txt = respect_robots_txt

        self._lock = threading.Lock()
        self._semaphores: Dict[str, threading.Semaphore] = {}
        self._last_request_time: Dict[str, float] = {}
        self._robots_cache: Dict[str, Optional[RobotFileParser]] = {}

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return url

    def _get_semaphore(self, domain: str) -> threading.Semaphore:
        with self._lock:
            sem = self._semaphores.get(domain)
            if sem is None:
                sem = threading.Semaphore(self.max_concurrent_per_domain)
                self._semaphores[domain] = sem
            return sem

    def is_allowed_by_robots(self, url: str, user_agent: str = "*", timeout: int = 5) -> bool:
        """Check robots.txt for *url*. Fails OPEN (returns True) if
        robots.txt can't be fetched/parsed at all -- an unreachable
        robots.txt shouldn't block otherwise-legitimate fetching, and this
        matches standard crawler behavior (RFC 9309 section 2.3.1.4: unreachable
        robots.txt is treated as "no restrictions")."""
        if not self.respect_robots_txt:
            return True

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        with self._lock:
            cached = self._robots_cache.get(domain, "MISS")

        if cached == "MISS":
            rp = RobotFileParser()
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                rp = None  # treat as "no robots.txt" -> allowed
            with self._lock:
                self._robots_cache[domain] = rp
            cached = rp

        if cached is None:
            return True
        try:
            return cached.can_fetch(user_agent, url)
        except Exception:
            return True

    def wait_turn(self, url: str) -> None:
        """Block (briefly) until it's this domain's turn: enforces the
        minimum delay since the last request to the same domain, with
        jitter so parallel workers don't all wake up in lockstep."""
        domain = self._domain(url)
        with self._lock:
            last = self._last_request_time.get(domain)
        if last is not None:
            elapsed = time.time() - last
            required = self.min_delay_seconds + random.uniform(0, self.jitter_seconds)
            remaining = required - elapsed
            if remaining > 0:
                time.sleep(remaining)
        with self._lock:
            self._last_request_time[domain] = time.time()

    def acquire(self, url: str, timeout: Optional[float] = 30.0) -> bool:
        """Acquire a concurrency slot for this domain (blocks if the domain
        is already at its concurrency cap). Returns False on timeout rather
        than blocking forever."""
        domain = self._domain(url)
        sem = self._get_semaphore(domain)
        return sem.acquire(timeout=timeout)

    def release(self, url: str) -> None:
        domain = self._domain(url)
        sem = self._get_semaphore(domain)
        try:
            sem.release()
        except ValueError:
            pass  # released more times than acquired -- ignore rather than crash a worker thread

    def governed(self, url: str):
        """Context-manager form: waits for turn + acquires the concurrency
        slot, released automatically. Usage:
            with governor.governed(url):
                ... do the fetch ...
        """
        return _GovernedContext(self, url)


class _GovernedContext:
    def __init__(self, governor: PolitenessGovernor, url: str):
        self.governor = governor
        self.url = url

    def __enter__(self):
        self.governor.acquire(self.url)
        self.governor.wait_turn(self.url)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.governor.release(self.url)
        return False
