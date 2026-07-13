#!/usr/bin/env python3
"""
🪜 ALTERNATE SOURCE LADDER — variant URLs before giving up entirely
=========================================================================

When the primary URL is blocked or unreachable even after the full
requests -> Playwright -> basic-fallback chain, there's often an easier
path to the *same content* sitting right next to it:

  1. AMP version        (often served with fewer defenses)
  2. Mobile version      (m.example.com, or ?output=amp style params)
  3. Print/plain version (print.example.com, ?print=1)
  4. Wayback Machine      (archive.org's last snapshot -- a completely
                            different server, so it doesn't share the
                            origin's block/rate-limit state at all)

This is a genuinely different content source at each rung (not just a
retry), so it's kept as an explicit ladder tried in order rather than
folded into the tier-retry loop.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import requests


def _amp_candidates(url: str) -> List[str]:
    parsed = urlparse(url)
    candidates = []
    # Common AMP URL conventions.
    if not parsed.path.rstrip("/").endswith("amp"):
        candidates.append(urlunparse(parsed._replace(path=parsed.path.rstrip("/") + "/amp")))
    candidates.append(url + ("&" if parsed.query else "?") + "output=amp")
    return candidates


def _mobile_candidates(url: str) -> List[str]:
    parsed = urlparse(url)
    if parsed.netloc.startswith("m.") or parsed.netloc.startswith("mobile."):
        return []
    return [urlunparse(parsed._replace(netloc="m." + parsed.netloc))]


def _print_candidates(url: str) -> List[str]:
    parsed = urlparse(url)
    candidates = [url + ("&" if parsed.query else "?") + "print=1"]
    if not parsed.netloc.startswith("print."):
        candidates.append(urlunparse(parsed._replace(netloc="print." + parsed.netloc)))
    return candidates


def build_ladder(url: str) -> List[Dict[str, str]]:
    """Ordered list of {"rung": ..., "url": ...} candidates to try, cheapest
    and most-likely-to-work first. Does not include the Wayback Machine
    (that's a network lookup, handled separately by ``wayback_snapshot_url``
    since it needs its own request rather than just a URL transform)."""
    ladder = []
    for candidate in _amp_candidates(url):
        ladder.append({"rung": "amp", "url": candidate})
    for candidate in _mobile_candidates(url):
        ladder.append({"rung": "mobile", "url": candidate})
    for candidate in _print_candidates(url):
        ladder.append({"rung": "print", "url": candidate})
    return ladder


def wayback_snapshot_url(url: str, timeout: int = 10) -> Optional[str]:
    """Look up the most recent Wayback Machine snapshot of *url* via
    archive.org's public availability API. Returns the snapshot URL, or
    None if there isn't one / the lookup fails. Never raises."""
    try:
        resp = requests.get(
            "https://archive.org/wayback/available",
            params={"url": url},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        snapshot = (data.get("archived_snapshots") or {}).get("closest")
        if snapshot and snapshot.get("available"):
            return snapshot.get("url")
    except Exception:
        pass
    return None


def try_ladder(
    url: str,
    fetch_fn,
    include_wayback: bool = True,
    max_rungs: int = 5,
) -> Dict[str, Any]:
    """Try each rung of the alternate-source ladder in order using
    *fetch_fn* (expected to be ``fetch_resilient`` or a compatible
    single-argument-URL callable returning the same outcome dict shape),
    stopping at the first success.

    Returns the winning ``fetch_resilient``-shaped outcome dict with an
    added ``"alternate_source_rung"`` key (``"amp"``/``"mobile"``/``"print"``/
    ``"wayback"``), or a failure dict with
    ``{"status": "failed", "rungs_tried": [...]}`` if nothing worked.
    """
    rungs_tried = []
    ladder = build_ladder(url)[:max_rungs]

    for rung in ladder:
        outcome = fetch_fn(rung["url"])
        rungs_tried.append(rung["rung"])
        if outcome.get("status") == "success":
            outcome["alternate_source_rung"] = rung["rung"]
            outcome["alternate_source_url"] = rung["url"]
            return outcome

    if include_wayback:
        snapshot = wayback_snapshot_url(url)
        rungs_tried.append("wayback")
        if snapshot:
            outcome = fetch_fn(snapshot)
            if outcome.get("status") == "success":
                outcome["alternate_source_rung"] = "wayback"
                outcome["alternate_source_url"] = snapshot
                return outcome

    return {"status": "failed", "html": "", "rungs_tried": rungs_tried}
