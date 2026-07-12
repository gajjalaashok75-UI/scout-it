#!/usr/bin/env python3
"""
🗂️ BROWSER PROFILE — optional persistent Playwright session
=====================================================================

**Needs live verification** — built against Playwright's documented
``launch_persistent_context`` API; no live network/browser-farm here to
confirm long-term behavior (e.g. profile directory growth, cookie
expiry interaction with real sites). Please test and report back.

By default, `fetch_resilient`'s Tier 2 launches a fresh, throwaway Chromium
context for every single attempt — no cookies, no localStorage, nothing
persists. That's the safest default (no cross-request tracking-surface,
no stale-state bugs), but it also means every Tier 2 attempt looks like a
brand-new, never-seen-before visitor, which is itself sometimes a signal
some anti-bot systems weigh (a "session" with zero history is more
suspicious than one with a plausible browsing history).

This module is opt-in (`--persistent-profile` / `enable_persistent_profile=True`):
when enabled, Tier 2 uses a persistent profile directory under
``~/.scout-it/browser-profiles/<profile-name>/`` instead of a throwaway
context, so cookies and session state accumulate naturally across runs —
closer to how a real returning visitor looks.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .config import CONFIG_DIR

PROFILES_DIR = CONFIG_DIR / "browser-profiles"
DEFAULT_PROFILE_NAME = "default"


def profile_path(profile_name: str = DEFAULT_PROFILE_NAME) -> Path:
    safe_name = "".join(c for c in profile_name if c.isalnum() or c in ("-", "_")) or DEFAULT_PROFILE_NAME
    return PROFILES_DIR / safe_name


def launch_persistent(pw: Any, profile_name: str = DEFAULT_PROFILE_NAME, headless: bool = True) -> Any:
    """Launch a persistent Playwright browser context (returns a
    BrowserContext, not a Browser -- Playwright's persistent-context API
    combines the two). Caller is responsible for closing it
    (``context.close()``) when done, same as a regular browser.

    Raises whatever Playwright itself raises on failure (e.g. Chromium not
    installed) -- callers should already have that in a try/except per the
    existing Tier 2 pattern in ``fetch_resilient``.
    """
    path = profile_path(profile_name)
    path.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(path),
        headless=headless,
    )


def list_profiles() -> list:
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.name for p in PROFILES_DIR.iterdir() if p.is_dir())


def profile_size_bytes(profile_name: str = DEFAULT_PROFILE_NAME) -> int:
    path = profile_path(profile_name)
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def clear_profile(profile_name: str = DEFAULT_PROFILE_NAME) -> bool:
    import shutil
    path = profile_path(profile_name)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        return True
    return False
