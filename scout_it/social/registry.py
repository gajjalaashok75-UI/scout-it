"""
📡 SOCIAL PROVIDER REGISTRY

A minimal registry so new providers can be added without CLI redesign.
Adding a future platform requires only:

    1. Provider implementation (subclass of SocialProvider).
    2. Capability declaration (SUPPORTED_CAPABILITIES).
    3. Registration here via ``register(MyProvider())``.

No new command structure is required — ``social-search`` iterates every
registered provider whose name appears in the requested ``--platform`` list.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .base import SocialProvider


_REGISTRY: Dict[str, SocialProvider] = {}


def register(provider: SocialProvider) -> SocialProvider:
    """Register a provider instance under its ``platform`` name."""
    name = (getattr(provider, "platform", None) or "").strip().lower()
    if not name:
        raise ValueError("Provider must define a non-empty 'platform' name.")
    _REGISTRY[name] = provider
    return provider


def get(name: str) -> Optional[SocialProvider]:
    """Look up a registered provider by platform name (case-insensitive)."""
    return _REGISTRY.get((name or "").strip().lower())


def all_providers() -> List[SocialProvider]:
    """Return every registered provider, in registration order."""
    return list(_REGISTRY.values())


def available_platforms() -> List[str]:
    """Return the sorted list of registered platform names."""
    return sorted(_REGISTRY.keys())


def resolve_platforms(requested: Optional[str]) -> List[str]:
    """Resolve a comma-separated ``--platform`` value to platform names.

    ``None``/empty means "all enabled providers".
    Unknown names are returned as-is so the caller can report them (rather
    than silently dropping them) — the per-provider lookup will then produce
    a clear "unknown platform" failure for that name.
    """
    if not requested:
        return available_platforms()
    parts = [p.strip().lower() for p in requested.split(",") if p.strip()]
    return parts or available_platforms()


def _register_builtins():
    """Register the built-in Telegram/Reddit/Discord/Instagram providers.

    Called lazily from ``social/__init__.py`` so importing the package is
    cheap and side-effect-free for users who only want one provider.
    """
    if _REGISTRY:
        return  # already populated
    from .telegram import TelegramProvider
    from .reddit import RedditProvider
    from .discord import DiscordProvider
    from .instagram import InstagramProvider
    for cls in (TelegramProvider, RedditProvider, DiscordProvider, InstagramProvider):
        register(cls())
