"""Base classes for the source plugin system.

Defines:
  - ``SearchResult`` — the unified result schema every plugin emits.
  - ``SourcePlugin`` — abstract base class every source plugin implements.
  - ``SourceConfig`` — per-source configuration (API key, base URL, enabled).

The unified ``SearchResult`` schema is the contract between sources and the
semantic pipeline. Every source normalizes its API response into this shape::

    {
        "id":           str,   # unique ID from the source
        "source":       str,   # source name (e.g. "openalex")
        "url":          str,   # canonical URL to the work/dataset/book
        "title":        str,
        "snippet":      str,   # abstract / short description
        "content":      str,   # full text (if freely available, else "")
        "content_type": str,   # "academic" | "dataset" | "book" | "code"
                               # | "event" | "media" | "geo" | "podcast"
        "timestamp":    str,   # ISO 8601 publication/creation date
        "authority_score": float,  # 0.0–1.0 (citations, downloads, etc.)
        "relevance_score": float,  # 0.0–1.0 (filled by semantic ranker)
        "lang":         str,   # language code (e.g. "en")
        "metadata":     dict,  # source-specific extras (DOI, authors, etc.)
    }
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypeAlias

logger = logging.getLogger(__name__)

# ─── Content type vocabulary ────────────────────────────────────────────────

CONTENT_TYPES = frozenset({
    "academic",    # papers, preprints, articles
    "dataset",     # research datasets
    "book",        # books, long-form text
    "code",        # repositories, code snippets
    "event",       # real-time events, news events
    "media",       # images, video, audio, archive
    "geo",         # geographic / POI data
    "podcast",     # podcast episodes
    "knowledge",   # knowledge graph entities / structured facts
})

# SearchResult is a dict with a known shape (see make_result).
SearchResult: TypeAlias = Dict[str, Any]


# ─── SearchResult ───────────────────────────────────────────────────────────

def make_result(
    *,
    id: str,
    source: str,
    url: str,
    title: str,
    snippet: str = "",
    content: str = "",
    content_type: str = "academic",
    timestamp: str = "",
    authority_score: float = 0.0,
    relevance_score: float = 0.0,
    lang: str = "en",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a normalized SearchResult dict.

    This is the factory function every source plugin uses to convert its
    API-specific response into the unified schema.
    """
    return {
        "id": str(id),
        "source": source,
        "url": url,
        "title": title.strip() if title else "",
        "snippet": (snippet or "").strip(),
        "content": content or "",
        "content_type": content_type if content_type in CONTENT_TYPES else "academic",
        "timestamp": timestamp or "",
        "authority_score": float(authority_score) if authority_score else 0.0,
        "relevance_score": float(relevance_score) if relevance_score else 0.0,
        "lang": lang or "en",
        "metadata": metadata or {},
    }


# ─── SourceConfig ───────────────────────────────────────────────────────────

@dataclass
class SourceConfig:
    """Per-source configuration."""
    name: str
    requires_api_key: bool = False
    api_key_env: str = ""           # env var name for the API key
    base_url: str = ""             # override base URL
    enabled: bool = True           # whether this source is active
    rate_limit_per_sec: float = 1.0 # polite rate limit
    description: str = ""
    free_tier: bool = True         # has a free tier (no payment required)
    get_it_url: str = ""           # where to get an API key


# ─── SourcePlugin ABC ──────────────────────────────────────────────────────

class SourcePlugin(ABC):
    """Abstract base class for all source plugins.

    Subclasses implement :meth:`search` (and optionally :meth:`fetch_content`)
    and declare their config via :attr:`config`.

    The plugin system handles:
      - Async-first fetching (httpx + asyncio)
      - Rate limiting (polite to free APIs)
      - Error isolation (one failing source doesn't kill the whole search)
      - Result normalization (every source emits SearchResult dicts)
    """

    #: Plugin name (must be unique, used as the key in the registry).
    name: str = ""

    #: Human-readable display name.
    display_name: str = ""

    #: Content type this source primarily produces.
    content_type: str = "academic"

    #: SourceConfig instance with default settings.
    config: SourceConfig = field(default_factory=lambda: SourceConfig(name=""))

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Search this source and return normalized SearchResult dicts.

        Args:
            query: search query string.
            max_results: maximum results to return.

        Returns:
            List of SearchResult dicts (see :func:`make_result`).
        """
        ...

    def fetch_content(self, result: Dict[str, Any]) -> str:
        """Fetch full content for a result (optional override).

        Default implementation returns the existing content or snippet.
        Sources with open-access full text (arXiv, Unpaywall, Gutenberg)
        override this to download and extract the full text.
        """
        return result.get("content", "") or result.get("snippet", "")

    def is_available(self) -> bool:
        """Check if this source is available (has required API key, etc.).

        Default: always available (no key needed). Sources requiring a key
        override this to check if the key is configured.
        """
        return True

    def get_api_key(self) -> Optional[str]:
        """Get the API key for this source, if any.

        Reads from the environment or the scout-it config file.
        """
        import os
        from .source_config import get_source_config as _get_cfg

        # Try environment variable first.
        if self.config.api_key_env:
            key = os.environ.get(self.config.api_key_env)
            if key:
                return key

        # Fall back to stored source config.
        cfg = _get_cfg(self.name)
        return cfg.get("api_key")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} enabled={self.config.enabled}>"
