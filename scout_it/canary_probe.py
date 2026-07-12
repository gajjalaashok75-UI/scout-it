#!/usr/bin/env python3
"""
🐤 CANARY PROBE — cheap pre-check before committing to a full fetch attempt
================================================================================

Committing to a full Tier 1/2/3 fetch attempt is relatively expensive
(Tier 2's browser launch especially). Before trusting a cached strategy for
a domain, send one lightweight request first and check only for a status
code and a couple of known "block page" signatures — never used to extract
real content, just to sense whether the site's defenses have changed since
the last successful visit.

If the canary looks fine, proceed with the cached strategy as normal. If it
looks like the site is now blocking/challenging in a way it wasn't before,
skip straight to re-exploring strategies via the bandit instead of wasting
a full attempt on a now-stale cached one.
"""

import time
from typing import Any, Dict, Optional

import requests

# Small set of well-known challenge/block-page signatures. Deliberately
# conservative (checks for markers that are extremely unlikely to appear on
# a genuinely successful page) to avoid false positives that would trigger
# unnecessary re-exploration.
_BLOCK_SIGNATURES = [
    "checking your browser before accessing",
    "cf-browser-verification",
    "cf-challenge",
    "just a moment...",
    "attention required! | cloudflare",
    "access denied",
    "are you a robot",
    "please verify you are a human",
    "captcha-delivery.com",
    "perimeterx",
    "request unsuccessful. incapsula",
]


def probe(url: str, timeout: int = 6, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Send one cheap probe request and report whether the domain looks
    reachable and unblocked. Never raises -- any failure is reported in the
    result rather than propagated, since a probe failing is itself useful
    signal, not an error condition for the caller.

    Returns:
        {
            "reachable": bool,       # got any HTTP response at all
            "status_code": int|None,
            "looks_blocked": bool,   # status suggests blocking, or a known
                                      # challenge-page signature was found
            "latency_ms": int|None,
            "method": "HEAD"|"GET",
        }
    """
    start = time.time()
    default_headers = headers or {"User-Agent": "Mozilla/5.0 (compatible; scout-it-canary/1.0)"}

    # Try HEAD first (cheapest); some servers reject/mishandle HEAD, so fall
    # back to a minimal ranged GET if HEAD fails outright.
    try:
        resp = requests.head(url, headers=default_headers, timeout=timeout, allow_redirects=True)
        method = "HEAD"
    except Exception:
        try:
            resp = requests.get(
                url, headers={**default_headers, "Range": "bytes=0-2047"},
                timeout=timeout, allow_redirects=True, stream=True,
            )
            method = "GET"
        except Exception as exc:
            return {
                "reachable": False, "status_code": None, "looks_blocked": False,
                "latency_ms": int((time.time() - start) * 1000), "method": None,
                "error": f"{type(exc).__name__}: {exc}",
            }

    latency_ms = int((time.time() - start) * 1000)
    status = resp.status_code

    looks_blocked = status in (403, 429, 503)
    if not looks_blocked and method == "GET":
        try:
            snippet = resp.text[:4096].lower()
            looks_blocked = any(sig in snippet for sig in _BLOCK_SIGNATURES)
        except Exception:
            pass

    return {
        "reachable": True, "status_code": status, "looks_blocked": looks_blocked,
        "latency_ms": latency_ms, "method": method,
    }


def should_trust_cached_strategy(url: str, timeout: int = 6) -> bool:
    """Convenience wrapper: True if the canary suggests the cached strategy
    is still likely to work (site reachable and not obviously blocking),
    False if the bandit should re-explore instead."""
    result = probe(url, timeout=timeout)
    if not result["reachable"]:
        # Can't tell either way from an unreachable probe -- don't
        # invalidate a good cached strategy over what might just be the
        # canary itself hitting a transient network blip.
        return True
    return not result["looks_blocked"]
