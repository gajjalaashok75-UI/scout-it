"""Base class for API-backed search source plugins (Tavily, Exa, Firecrawl).

These differ from the academic/dataset source plugins in ``plugins/``: they are
general-purpose web/news/image search APIs that require an API key, return rich
content (snippets, highlights, full-page text), and must degrade gracefully when
the key is missing or the API errors out (rate limit, network, exhausted
credits). The base class centralizes that shared behaviour so adding a new API
search source is a matter of subclassing and implementing ``_raw_search``.

Design contract
----------------
* **Credential gate** — ``is_available()`` checks the API key. ``search()``
  short-circuits with a skip message when the key is absent (never raises).
* **Error isolation** — every API call is wrapped; rate-limit / network /
  credit-exhausted errors are captured as human-readable messages and the
  source returns ``[]`` so the rest of the pipeline continues.
* **No truncation** — content returned by the API is preserved in full on the
  ``content`` field so the semantic ranker and the final output see everything.
* **Search-type dispatch** — ``search(query, max_results, search_type=...)``
  routes to ``_raw_search`` with the right API parameters for web / news /
  image / multi. Subclasses declare which search types they support via
  ``SUPPORTED_SEARCH_TYPES``.
* **Structured for growth** — a new provider only implements ``_raw_search``
  and ``_normalize_result``; the base handles credentials, errors, messages,
  and result normalization into the ``SearchResult`` schema.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .base import SourcePlugin, SourceConfig, make_result

logger = logging.getLogger(__name__)

__all__ = ["ApiSearchSource", "SourceMessageCollector", "source_messages"]


class SourceMessageCollector:
    """Thread-safe collector for skip/error messages emitted by API sources.

    Plugins call :meth:`skip` when they cannot run (missing key) and
    :meth:`error` when the API call fails (rate limit, network, credits).
    The CLI reads :meth:`drain` after augmentation to print a concise summary.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._messages: List[Dict[str, str]] = []

    def skip(self, source: str, reason: str) -> None:
        with self._lock:
            self._messages.append({"source": source, "type": "skip", "reason": reason})

    def error(self, source: str, reason: str) -> None:
        with self._lock:
            self._messages.append({"source": source, "type": "error", "reason": reason})

    def drain(self) -> List[Dict[str, str]]:
        """Return and clear all collected messages."""
        with self._lock:
            msgs = list(self._messages)
            self._messages.clear()
            return msgs

    def has_messages(self) -> bool:
        with self._lock:
            return bool(self._messages)


# Singleton collector shared across all API source plugins in a process.
source_messages = SourceMessageCollector()


class ApiSearchSource(SourcePlugin):
    """Base class for API-key-gated search sources (Tavily, Exa, Firecrawl).

    Subclasses must set:
      * ``name``, ``display_name``
      * ``config`` (a :class:`SourceConfig` with ``requires_api_key=True``)
      * ``SUPPORTED_SEARCH_TYPES`` — tuple of search types this source handles
      * ``_raw_search(query, max_results, search_type)`` — returns a list of
        provider-native result dicts (will be normalized via
        :meth:`_normalize_result`).
      * ``_normalize_result(raw, search_type)`` — converts one provider result
        into a ``SearchResult`` dict.
    """

    SUPPORTED_SEARCH_TYPES: tuple = ("web", "news", "image", "multi")

    def is_available(self) -> bool:
        return bool(self.get_api_key())

    def _skip_reason_no_key(self) -> str:
        env = self.config.api_key_env or f"(key for {self.name})"
        return (
            f"API key not set — add {env} via `scout-it config` to enable {self.display_name}. "
            f"Skipped; continuing with other sources."
        )

    def search(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = "web",
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Search with credential gating + error isolation.

        Returns ``[]`` (and records a message) when the key is missing or the
        API call fails — never raises.
        """
        api_key = self.get_api_key()
        if not api_key:
            source_messages.skip(self.name, self._skip_reason_no_key())
            return []

        # Unsupported search type for this provider → skip silently (no message;
        # e.g. Exa does not support image search, so --sources exa on
        # image-search simply does nothing for Exa).
        if search_type not in self.SUPPORTED_SEARCH_TYPES:
            return []

        try:
            raw_results = self._raw_search(
                query=query,
                max_results=max_results,
                search_type=search_type,
                api_key=api_key,
            )
        except _ApiKeyError as exc:
            source_messages.error(self.name, f"authentication failed: {exc}")
            return []
        except _RateLimitError as exc:
            source_messages.error(self.name, f"rate limited / credits exhausted: {exc}")
            return []
        except _NetworkError as exc:
            source_messages.error(self.name, f"network error: {exc}")
            return []
        except Exception as exc:
            source_messages.error(self.name, f"unexpected error: {exc}")
            return []

        normalized: List[Dict[str, Any]] = []
        for raw in raw_results:
            try:
                result = self._normalize_result(raw, search_type)
                if result:
                    normalized.append(result)
            except Exception as exc:
                logger.debug("%s: failed to normalize result: %s", self.name, exc)
        return normalized

    # ── Hooks subclasses implement ────────────────────────────────────────

    def _raw_search(
        self,
        *,
        query: str,
        max_results: int,
        search_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


# ── Typed errors so the base class can classify failures ────────────────────

class _ApiKeyError(Exception):
    """API rejected the key (401/403)."""


class _RateLimitError(Exception):
    """Rate limit hit or credits exhausted (429 / quota message)."""


class _NetworkError(Exception):
    """Network/timeout/connection error."""
