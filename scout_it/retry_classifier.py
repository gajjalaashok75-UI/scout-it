#!/usr/bin/env python3
"""
🚦 RETRY CLASSIFIER — transient vs. permanent failure classification
==========================================================================

Not every failure deserves the same response: retrying a 404 forever wastes
the whole retry budget on something that will never succeed, while ignoring
a ``Retry-After`` header just gets you blocked harder.

This module wraps the existing ``--max-fetch-retries`` retry loop inside
``fetch_resilient()`` with:
  - Failure classification (transient vs. permanent) so permanent failures
    short-circuit straight to the alternate-source ladder / a clean failure
    instead of consuming retry attempts they can't win
  - Honoring ``Retry-After`` / ``X-RateLimit-Remaining`` / ``X-RateLimit-Reset``
    when a site provides them, instead of guessing with generic exponential
    backoff

It doesn't replace the existing tier-retry loop -- it changes how failures
inside that loop are read and how long to wait between attempts.
"""

import email.utils
import time
from typing import Any, Dict, Optional

# Status codes that are worth retrying -- the failure is expected to be
# temporary (rate limiting, server hiccup, gateway issue, request timeout).
TRANSIENT_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

# Status codes that will never succeed on retry -- retrying wastes the
# budget. 404/410 (gone), 400 (bad request), 401/403 (auth -- a retry won't
# fix missing credentials), 451 (unavailable for legal reasons).
PERMANENT_STATUS_CODES = {400, 401, 403, 404, 405, 406, 410, 451}

TRANSIENT_EXCEPTION_NAMES = {
    "ConnectionError", "Timeout", "ConnectTimeout", "ReadTimeout",
    "ChunkedEncodingError", "ProxyError", "SSLError",
}


def classify_status(status_code: int) -> str:
    """Return 'transient', 'permanent', or 'unknown' for an HTTP status code."""
    if status_code in TRANSIENT_STATUS_CODES:
        return "transient"
    if status_code in PERMANENT_STATUS_CODES:
        return "permanent"
    if 200 <= status_code < 300:
        return "success"
    # Any other 4xx defaults to permanent (client-side problem, retrying
    # with the same request won't change the outcome); any other 5xx
    # defaults to transient (server-side, might recover).
    if 400 <= status_code < 500:
        return "permanent"
    if 500 <= status_code < 600:
        return "transient"
    return "unknown"


def classify_exception(exc: Exception) -> str:
    """Return 'transient' or 'permanent' for a raised exception (connection
    errors, timeouts, etc. are transient; most everything else defaults to
    permanent since a retry of the identical request is unlikely to help)."""
    name = type(exc).__name__
    if name in TRANSIENT_EXCEPTION_NAMES:
        return "transient"
    return "permanent"


def parse_retry_after(headers: Dict[str, str]) -> Optional[float]:
    """Parse a Retry-After header (seconds, or an HTTP date) into a
    wait-seconds float. Returns None if absent or unparseable."""
    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed is None:
            return None
        delta = (parsed.timestamp() - time.time())
        return max(0.0, delta)
    except Exception:
        return None


def parse_rate_limit_reset(headers: Dict[str, str]) -> Optional[float]:
    """Parse X-RateLimit-Reset (a unix timestamp, as GitHub/many APIs use it)
    into a wait-seconds float. Returns None if absent or unparseable."""
    value = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
    if not value:
        return None
    try:
        reset_ts = float(value)
        return max(0.0, reset_ts - time.time())
    except (ValueError, TypeError):
        return None


def compute_wait_seconds(
    headers: Optional[Dict[str, str]],
    attempt: int,
    base_backoff: float = 1.5,
    max_wait: float = 60.0,
) -> float:
    """Decide how long to wait before the next retry attempt.

    Prefers an explicit ``Retry-After`` header, then ``X-RateLimit-Reset``,
    falling back to exponential backoff (``base_backoff * (attempt + 1)``)
    when the server hasn't told us anything. Always capped at *max_wait* so
    a server-supplied value can't stall a job indefinitely.
    """
    headers = headers or {}
    explicit = parse_retry_after(headers)
    if explicit is not None:
        return min(explicit, max_wait)
    rate_limit_wait = parse_rate_limit_reset(headers)
    if rate_limit_wait is not None:
        return min(rate_limit_wait, max_wait)
    return min(base_backoff * (attempt + 1), max_wait)


def classify_attempt(
    status_code: Optional[int] = None,
    exception: Optional[Exception] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Full classification for one failed attempt: whether it's worth
    retrying, and how long to wait if so.

    Returns ``{"classification": "transient"|"permanent"|"success"|"unknown",
    "should_retry": bool, "wait_seconds": float|None}``.
    """
    if exception is not None:
        classification = classify_exception(exception)
    elif status_code is not None:
        classification = classify_status(status_code)
    else:
        classification = "unknown"

    should_retry = classification in ("transient", "unknown")
    wait_seconds = compute_wait_seconds(headers, attempt=0) if should_retry else None

    return {
        "classification": classification,
        "should_retry": should_retry,
        "wait_seconds": wait_seconds,
    }
