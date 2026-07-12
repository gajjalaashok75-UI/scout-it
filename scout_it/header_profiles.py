#!/usr/bin/env python3
"""
🧢 HEADER PROFILES — matched, internally-consistent browser header bundles
================================================================================

A request can get flagged by *how* it looks, not just *where* it comes
from. Independently randomizing individual headers (a Chrome User-Agent
paired with Firefox's Accept-Language shape, say) is actually a stronger
tell than sending no special headers at all — real browsers send
internally-consistent bundles.

This module ships a small rotating pool of full header sets, each one
matching what a real browser of that name/version actually sends, and
always rotates a *whole* profile at once rather than mixing fields from
different ones.

No new dependency — this is just data + simple selection logic.
"""

import random
from typing import Any, Dict, List, Optional

# Each profile is a complete, internally-consistent bundle. Kept small and
# well-known rather than exhaustive -- quality over quantity, since a
# plausible-but-slightly-wrong bundle is worse than one of a few verified-real ones.
HEADER_PROFILES: List[Dict[str, str]] = [
    {
        "name": "chrome-windows",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    {
        "name": "chrome-macos",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    {
        "name": "firefox-windows",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "TE": "trailers",
    },
    {
        "name": "safari-macos",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "name": "edge-windows",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Chromium";v="124", "Microsoft Edge";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
]

_PROFILE_BY_NAME = {p["name"]: p for p in HEADER_PROFILES}


def profile_names() -> List[str]:
    return [p["name"] for p in HEADER_PROFILES]


def get_profile(name: Optional[str] = None) -> Dict[str, str]:
    """Return a header bundle by name, or a random one if name is None/unknown.
    Always returns a *copy* of the profile dict (minus the 'name' key) so
    callers can't accidentally mutate the shared pool."""
    if name and name in _PROFILE_BY_NAME:
        profile = _PROFILE_BY_NAME[name]
    else:
        profile = random.choice(HEADER_PROFILES)
    return {k: v for k, v in profile.items() if k != "name"}


def get_profile_with_name(name: Optional[str] = None) -> Dict[str, Any]:
    """Same as get_profile, but returns {"name": ..., "headers": {...}} --
    useful when the caller (e.g. the strategy bandit) needs to record which
    profile was used, not just the headers themselves."""
    if name and name in _PROFILE_BY_NAME:
        profile = _PROFILE_BY_NAME[name]
    else:
        profile = random.choice(HEADER_PROFILES)
    return {"name": profile["name"], "headers": {k: v for k, v in profile.items() if k != "name"}}
