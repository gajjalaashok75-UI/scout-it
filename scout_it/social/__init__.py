"""
📡 SOCIAL / PLATFORM EXTRACTION — Telegram, Discord, Reddit, Instagram

Unified entry point: ``social_search(...)`` runs one or more platform
providers in parallel, with capability-based fallback so a platform that
doesn't support a requested source argument (e.g. ``--channel``) falls back
to public query-based discovery instead of being skipped.

Architecture (adding a future platform needs no CLI redesign):

    social/
    ├── base.py        # SocialProvider base + unified result schema
    ├── registry.py    # provider registry
    ├── telegram.py    # TelegramProvider  (query, channel)
    ├── reddit.py      # RedditProvider    (query, subreddit, user)
    ├── discord.py     # DiscordProvider   (channel-id, query)
    └── instagram.py   # InstagramProvider (query, profile)

Backwards compatibility: the original flat function names
(``telegram_channel``, ``telegram_search``, ``discord_channel_messages``,
``reddit_search``) and the HTML parsers (``_parse_telegram_primary``,
``_parse_telegram_enhanced``) are re-exported here so existing imports
``from scout_it import social`` and ``from scout_it.social import ...``
keep working unchanged.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests  # re-exported so legacy mock.patch("scout_it.social.requests.*") works

from .base import (
    CAP_CHANNEL,
    CAP_CHANNEL_ID,
    CAP_QUERY,
    CAP_SUBREDDIT,
    CAP_PROFILE,
    CAP_USER,
    SocialProvider,
    normalize_item,
    provider_result,
)
from .registry import (
    all_providers,
    available_platforms,
    get,
    register,
    resolve_platforms,
)
from .telegram import (
    TelegramProvider,
    _parse_telegram_enhanced,
    _parse_telegram_primary,
    telegram_channel,
    telegram_search,
)
from .reddit import RedditProvider, reddit_search
from .discord import DiscordProvider, discord_channel_messages
from .instagram import InstagramProvider, instagram_profile_search


# Re-export the public API names this module has always exposed (backwards
# compatibility for ``from scout_it import social`` consumers + tests).
__all__ = [
    # orchestrator
    "social_search",
    # registry
    "register", "get", "all_providers", "available_platforms", "resolve_platforms",
    "TelegramProvider", "RedditProvider", "DiscordProvider", "InstagramProvider",
    "SocialProvider",
    # legacy flat functions (still the real implementations)
    "telegram_channel", "telegram_search",
    "discord_channel_messages", "reddit_search", "instagram_profile_search",
    # parsers
    "_parse_telegram_primary", "_parse_telegram_enhanced",
]


def _ensure_registered() -> None:
    """Lazily register the built-in providers exactly once."""
    from .registry import _register_builtins
    _register_builtins()


def social_search(
    *,
    query: Optional[str] = None,
    platform: Optional[str] = None,
    channel: Optional[str] = None,
    channel_id: Optional[str] = None,
    subreddit: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
    max_results: int = 20,
    sort: str = "relevance",
    posts_per_channel: int = 3,
    max_fetch_retries: int = 3,
    before: Optional[str] = None,
    extract_full: bool = False,
    parallel: bool = True,
) -> Dict[str, Any]:
    """Run one or more social providers with capability-based fallback.

    Parameters mirror the ``social-search`` CLI. ``platform`` is a
    comma-separated list (``"telegram,reddit,discord"``) or ``None`` for
    "all enabled providers". Each provider decides which capability to
    execute and falls back to query search when a source argument it does
    not support was requested. A provider that can neither serve the
    requested capability nor fall back to query reports a failure — but
    never stops the other providers from running.

    Returns an aggregated envelope:

        {
          "query": ..., "platforms": [...], "provider_count": N,
          "total_results": N, "results": [...normalized items...],
          "results_by_platform": { "telegram": {...}, ... },
          "failures": [ {platform, error, error_message}, ... ],
        }
    """
    _ensure_registered()
    requested = resolve_platforms(platform)
    registry_names = set(available_platforms())

    targets: List[SocialProvider] = []
    unknown: List[str] = []
    for name in requested:
        prov = get(name)
        if prov is None:
            unknown.append(name)
        else:
            targets.append(prov)

    def _run(prov: SocialProvider) -> Dict[str, Any]:
        return prov.search(
            query=query, channel=channel, channel_id=channel_id,
            subreddit=subreddit, profile=profile, user=user, max_results=max_results,
            sort=sort, posts_per_channel=posts_per_channel,
            max_fetch_retries=max_fetch_retries, before=before,
            extract_full=extract_full,
        )

    by_platform: Dict[str, Dict[str, Any]] = {}
    failures: List[Dict[str, Any]] = []

    if parallel and len(targets) > 1:
        with ThreadPoolExecutor(max_workers=min(len(targets), 8)) as ex:
            futures = {ex.submit(_run, prov): prov for prov in targets}
            for fut in as_completed(futures):
                prov = futures[fut]
                try:
                    res = fut.result()
                except Exception as e:  # defensive — _run already wraps errors
                    res = provider_result(prov.platform, query=query,
                                          error="provider_error",
                                          error_message=f"{type(e).__name__}: {e}")
                by_platform[prov.platform] = res
    else:
        for prov in targets:
            by_platform[prov.platform] = _run(prov)

    all_results: List[Dict[str, Any]] = []
    for name, res in by_platform.items():
        if res.get("error"):
            failures.append({
                "platform": name,
                "error": res["error"],
                "error_message": res.get("error_message"),
                "capabilities_used": res.get("capabilities_used", []),
            })
        else:
            all_results.extend(res.get("results", []))

    for name in unknown:
        failures.append({
            "platform": name,
            "error": "unknown_platform",
            "error_message": (
                f"No provider registered for platform '{name}'. "
                f"Available: {available_platforms()}."
            ),
            "capabilities_used": [],
        })

    return {
        "query": query,
        "platforms": [p.platform for p in targets] + unknown,
        "provider_count": len(targets) + len(unknown),
        "total_results": len(all_results),
        "results": all_results,
        "results_by_platform": by_platform,
        "failures": failures,
    }


# Register built-ins at import time so ``social_search`` and the registry
# are immediately usable without an explicit call.
_ensure_registered()
