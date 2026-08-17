"""Exa (formerly Metaphor) — neural web/news search API.

Requires ``EXA_API_KEY`` (set via ``scout-it config``). Uses the ``exa-py``
SDK. Supports web-search and multi-search (general search with highlights) and
news-search (``category="news"``). Does **not** support image-search.

API reference: https://docs.exa.ai

Search-type → Exa parameters:

  * ``web`` / ``multi`` — ``num_results``, ``type="auto"``,
                          ``contents={"highlights": True}``
  * ``news``            — same + ``category="news"``
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..api_search_base import ApiSearchSource, _ApiKeyError, _RateLimitError, _NetworkError, source_messages
from ..base import SourceConfig, make_result

logger = logging.getLogger(__name__)

SUPPORTED = ("web", "news", "multi")

# Optional SDK — imported at module level so tests can patch
# ``scout_it.sources.plugins.exa.Exa``. The method checks for None so the
# plugin degrades gracefully when exa-py isn't installed.
try:
    from exa_py import Exa  # type: ignore[import]
except ImportError:  # pragma: no cover - exercised only without the SDK
    Exa = None  # type: ignore[assignment,misc]


class ExaPlugin(ApiSearchSource):
    name = "exa"
    display_name = "Exa"
    content_type = "web"
    SUPPORTED_SEARCH_TYPES = SUPPORTED
    config = SourceConfig(
        name="exa",
        requires_api_key=True,
        api_key_env="EXA_API_KEY",
        rate_limit_per_sec=2.0,
        description="Neural web/news search with highlights. Web + news + multi only (no image).",
    )

    def _raw_search(
        self,
        *,
        query: str,
        max_results: int,
        search_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        if Exa is None:
            logger.info("exa-py not installed; skipping Exa source")
            source_messages.error(self.name, "exa-py not installed (pip install exa-py)")
            return []

        exa = Exa(api_key)

        kwargs: Dict[str, Any] = {
            "num_results": max_results,
            "type": "auto",
            "contents": {"highlights": True},
        }
        if search_type == "news":
            kwargs["category"] = "news"

        try:
            result = exa.search(query, **kwargs)
        except Exception as exc:
            _classify_exa_error(exc)
            raise

        # exa.search returns an object with a .results list (each has url,
        # title, text, highlights, score, etc.) — normalize to dicts.
        raw_results: List[Dict[str, Any]] = []
        results_attr = getattr(result, "results", None)
        if results_attr is None and isinstance(result, dict):
            results_attr = result.get("results", [])
        for item in results_attr or []:
            if isinstance(item, dict):
                raw_results.append(item)
            else:
                # exa-py returns dataclass-like objects; convert to dict.
                raw_results.append({
                    k: getattr(item, k, "")
                    for k in ("url", "title", "text", "highlights", "score", "author", "published_date", "id")
                })
        return raw_results

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        url = raw.get("url", "")
        title = raw.get("title", "")
        if not url and not title:
            return None

        # Exa 'text' is the full extracted content; 'highlights' is a list of
        # relevant snippets. Preserve both untruncated.
        content = raw.get("text", "") or ""
        highlights = raw.get("highlights", []) or []
        if isinstance(highlights, list):
            highlights_text = "\n".join(str(h) for h in highlights)
        else:
            highlights_text = str(highlights)
        snippet = highlights_text or (content[:500] if content else "")

        score = raw.get("score", 0.0)
        try:
            authority = min(float(score), 1.0) if score else 0.0
        except (TypeError, ValueError):
            authority = 0.0

        published = raw.get("published_date", "") or ""

        return make_result(
            id=raw.get("id", "") or url or title,
            source="exa",
            url=url,
            title=title,
            snippet=snippet,
            content=content or highlights_text,
            content_type="web",
            timestamp=published,
            authority_score=authority,
            metadata={
                "score": score,
                "highlights": highlights_text[:2000] if highlights_text else "",
                "author": raw.get("author", ""),
                "search_type": search_type,
            },
        )


def _classify_exa_error(exc: Exception) -> None:
    msg = str(exc).lower()
    if any(k in msg for k in ("401", "403", "unauthorized", "forbidden", "invalid")):
        raise _ApiKeyError(str(exc)) from exc
    if any(k in msg for k in ("429", "rate limit", "quota", "credit", "insufficient", "usage limit")):
        raise _RateLimitError(str(exc)) from exc
    if any(k in msg for k in ("timeout", "connection", "network", "dns", "unreachable", "refused")):
        raise _NetworkError(str(exc)) from exc
    raise exc


from ..registry import register
PLUGIN = ExaPlugin()
register(PLUGIN)
