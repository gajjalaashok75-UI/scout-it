"""
📡 SOCIAL PROVIDER BASE — capability declaration + unified result schema.

Each social platform is a Provider that:
  1. Declares ``SUPPORTED_CAPABILITIES`` (the source-arg shapes it can serve).
  2. Exposes ``search(...)`` returning a normalized result payload.

Capability-based execution + fallback rules (see ``social_search``):

    Requested feature supported        -> execute requested feature
    Requested feature unsupported      -> fall back to provider query search
    Provider unavailable / no fallback -> report provider failure (never crash)

A "capability" is the name of a platform-specific source argument:
    query, channel, channel-id, subreddit, profile, ...

The CLI does NOT restrict platform-specific arguments; each provider decides
whether it supports a given argument and falls back gracefully otherwise.

Unified per-item result schema (so multi-platform results can be aggregated,
ranked, filtered, and exported uniformly):

    {
        "platform":   "telegram",
        "author":     "...",
        "content":    "...",
        "url":        "...",
        "timestamp":  "...",
        "metadata":   {...},
    }
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Canonical capability names (map 1:1 to the CLI's platform-specific args).
CAP_QUERY = "query"
CAP_CHANNEL = "channel"
CAP_CHANNEL_ID = "channel-id"
CAP_SUBREDDIT = "subreddit"
CAP_PROFILE = "profile"
CAP_USER = "user"


def normalize_item(
    platform: str,
    *,
    author: Optional[str] = None,
    content: Optional[str] = None,
    url: Optional[str] = None,
    timestamp: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build one normalized result item in the unified schema."""
    return {
        "platform": platform,
        "author": author,
        "content": content,
        "url": url,
        "timestamp": timestamp,
        "metadata": metadata or {},
    }


def provider_result(
    platform: str,
    *,
    query: Optional[str] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    capabilities_used: Optional[List[str]] = None,
    raw: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    error_message: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a normalized per-provider result envelope.

    A provider returns exactly one of:
      - a successful envelope (``results`` populated), or
      - a failure envelope (``error`` + ``error_message`` populated).
    ``capabilities_used`` records which capabilities actually executed, which
    makes the fallback path transparent to the caller.
    """
    return {
        "platform": platform,
        "query": query,
        "result_count": len(results) if results is not None else 0,
        "results": results or [],
        "capabilities_used": capabilities_used or [],
        "raw": raw,
        "error": error,
        "error_message": error_message,
        "note": note,
    }


class SocialProvider:
    """Base class for social platform providers.

    Subclasses set ``platform`` and ``SUPPORTED_CAPABILITIES`` and implement
    ``_execute(capability, params)``. The public ``search(...)`` method
    handles capability selection + fallback centrally so each provider only
    has to implement the capabilities it genuinely supports.
    """

    platform: str = "base"
    SUPPORTED_CAPABILITIES: set = set()

    # The capability this provider falls back to when a requested capability
    # is unsupported. Providers with no public discovery path (e.g. Discord)
    # set this to None, which makes fallback report a failure instead.
    FALLBACK_CAPABILITY: Optional[str] = CAP_QUERY

    # Maps a capability name to the params-key that carries its value.
    _CAPABILITY_PARAMS = {
        CAP_QUERY: "query",
        CAP_CHANNEL: "channel",
        CAP_CHANNEL_ID: "channel_id",
        CAP_SUBREDDIT: "subreddit",
        CAP_PROFILE: "profile",
        CAP_USER: "user",
    }

    def search(self, *, query=None, channel=None, channel_id=None,
               subreddit=None, profile=None, user=None,
               max_results=20, **kwargs) -> Dict[str, Any]:
        """Capability-aware entry point.

        Selection order:
          1. The first supported *source* capability with a non-empty value
             is executed (e.g. --channel for Telegram).
          2. If no source capability matches, fall back to ``query`` search
             (when supported).
          3. If query fallback is unavailable (Discord), report failure.
        """
        params = {
            "query": query,
            "channel": channel,
            "channel_id": channel_id,
            "subreddit": subreddit,
            "profile": profile,
            "user": user,
            "max_results": max_results,
            **kwargs,
        }

        # 1. Try a requested source capability this provider supports.
        chosen: Optional[str] = None
        for cap, key in self._CAPABILITY_PARAMS.items():
            if cap == CAP_QUERY:
                continue  # query is the fallback, not a primary source here
            if cap in self.SUPPORTED_CAPABILITIES and params.get(key):
                chosen = cap
                break

        # 2. Fall back to query search if nothing else matched.
        if chosen is None:
            if (self.FALLBACK_CAPABILITY
                    and self.FALLBACK_CAPABILITY in self.SUPPORTED_CAPABILITIES):
                if params.get(self._CAPABILITY_PARAMS[self.FALLBACK_CAPABILITY]):
                    chosen = self.FALLBACK_CAPABILITY
                else:
                    # No source arg AND no query -> nothing to search.
                    return provider_result(
                        self.platform,
                        error="no_input",
                        error_message=(
                            f"No supported source argument or --query provided for "
                            f"'{self.platform}'. Supported capabilities: "
                            f"{sorted(self.SUPPORTED_CAPABILITIES)}."
                        ),
                    )
            else:
                # Provider has no query/public-discovery fallback at all.
                unsupported = [k for k, v in {
                    "channel": channel, "channel_id": channel_id,
                    "subreddit": subreddit, "profile": profile,
                    "user": user,
                }.items() if v]
                return provider_result(
                    self.platform,
                    query=query,
                    error="unsupported_capability",
                    error_message=(
                        f"'{self.platform}' does not support "
                        f"{unsupported or 'the requested capability'} and has no public "
                        f"query-search fallback (no anonymous/public API exists). "
                        f"Supported: {sorted(self.SUPPORTED_CAPABILITIES)}."
                    ),
                )

        try:
            return self._execute(chosen, params)
        except Exception as e:  # never let one provider crash the aggregator
            return provider_result(
                self.platform,
                query=query,
                error="provider_error",
                error_message=f"{type(e).__name__}: {e}",
            )

    def _execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one capability. Override in subclasses."""
        raise NotImplementedError
