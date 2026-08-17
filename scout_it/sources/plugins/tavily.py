"""Tavily — AI-optimized web/news/image search API.

Requires ``TAVILY_API_KEY`` (set via ``scout-it config``). Uses the
``tavily-python`` SDK. Supports web-search, news-search (``topic="news"``),
image-search (``include_images=True``), and multi-search
(``include_images`` + ``include_favicon`` + ``include_usage``).

API reference: https://docs.tavily.com

Search-type → Tavily parameters:

  * ``web``   — ``include_answer="advanced"``, ``search_depth="advanced"``,
                ``chunks_per_source=5``
  * ``news``  — same as web + ``topic="news"``
  * ``image`` — ``include_images=True``,
                ``include_image_descriptions=True``, ``topic="news"``
  * ``multi`` — ``include_images=True``,
                ``include_image_descriptions=True``,
                ``include_favicon=True``, ``include_usage=True``
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..api_search_base import ApiSearchSource, _ApiKeyError, _RateLimitError, _NetworkError, source_messages
from ..base import SourceConfig, make_result

logger = logging.getLogger(__name__)

SUPPORTED = ("web", "news", "image", "multi")

# Optional SDK — imported at module level so tests can patch
# ``scout_it.sources.plugins.tavily.TavilyClient``. The method checks for None
# so the plugin degrades gracefully when tavily-python isn't installed.
try:
    from tavily import TavilyClient  # type: ignore[import]
except ImportError:  # pragma: no cover - exercised only without the SDK
    TavilyClient = None  # type: ignore[assignment,misc]


class TavilyPlugin(ApiSearchSource):
    name = "tavily"
    display_name = "Tavily"
    content_type = "web"
    SUPPORTED_SEARCH_TYPES = SUPPORTED
    config = SourceConfig(
        name="tavily",
        requires_api_key=True,
        api_key_env="TAVILY_API_KEY",
        rate_limit_per_sec=2.0,
        description="AI-optimized web/news/image search with answer + content chunks.",
    )

    def _raw_search(
        self,
        *,
        query: str,
        max_results: int,
        search_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        if TavilyClient is None:
            logger.info("tavily-python not installed; skipping Tavily source")
            source_messages.error(self.name, "tavily-python not installed (pip install tavily-python)")
            return []

        client = TavilyClient(api_key)

        kwargs: Dict[str, Any] = {
            "query": query,
            "include_answer": "advanced",
            "search_depth": "advanced",
            "max_results": max_results,
            "chunks_per_source": 5,
        }
        if search_type == "news":
            kwargs["topic"] = "news"
        elif search_type == "image":
            kwargs["topic"] = "news"
            kwargs["include_images"] = True
            kwargs["include_image_descriptions"] = True
        elif search_type == "multi":
            kwargs["include_images"] = True
            kwargs["include_image_descriptions"] = True
            kwargs["include_favicon"] = True
            kwargs["include_usage"] = True

        try:
            response = client.search(**kwargs)
        except Exception as exc:
            _classify_tavily_error(exc)
            raise

        # Tavily returns a dict with 'results' (list), optional 'answer',
        # optional 'images' (list of dicts with url + description).
        if not isinstance(response, dict):
            return []

        results: List[Dict[str, Any]] = []
        for item in response.get("results", []) or []:
            item["_answer"] = response.get("answer", "")
            results.append(item)

        # For image/multi, Tavily returns a separate 'images' list.
        for img in response.get("images", []) or []:
            if isinstance(img, dict):
                results.append({"_is_image": True, **img})
            elif isinstance(img, str):
                results.append({"_is_image": True, "url": img})

        return results

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        if raw.get("_is_image"):
            url = raw.get("url", "")
            if not url:
                return None
            description = raw.get("description", "")
            return make_result(
                id=url,
                source="tavily",
                url=url,
                title=description or "Tavily image result",
                snippet=description,
                content=description,
                content_type="media",
                metadata={"image_url": url, "image_description": description, "is_image": True},
            )

        url = raw.get("url", "")
        title = raw.get("title", "")
        # Tavily 'content' is the full extracted text for the result — preserve
        # it untruncated so the ranker and output see everything.
        content = raw.get("content", "") or ""
        snippet = raw.get("raw_content", "") or content[:500]
        score = raw.get("score", 0.0)
        try:
            authority = min(float(score) / 10.0, 1.0) if score else 0.0
        except (TypeError, ValueError):
            authority = 0.0

        answer = raw.get("_answer", "")
        if answer and not content:
            content = answer

        return make_result(
            id=url or title,
            source="tavily",
            url=url,
            title=title,
            snippet=snippet,
            content=content,
            content_type="web",
            authority_score=authority,
            metadata={
                "score": score,
                "tavily_answer": answer[:2000] if answer else "",
                "search_type": search_type,
            },
        )


def _classify_tavily_error(exc: Exception) -> None:
    """Inspect a Tavily exception and re-raise as the right typed error."""
    msg = str(exc).lower()
    if any(k in msg for k in ("401", "403", "unauthorized", "forbidden", "invalid api key")):
        raise _ApiKeyError(str(exc)) from exc
    if any(k in msg for k in ("429", "rate limit", "quota", "credit", "insufficient", "usage limit")):
        raise _RateLimitError(str(exc)) from exc
    if any(k in msg for k in ("timeout", "connection", "network", "dns", "unreachable", "refused")):
        raise _NetworkError(str(exc)) from exc
    # Unknown — let the base class handle it as a generic error.
    raise exc


from ..registry import register
PLUGIN = TavilyPlugin()
register(PLUGIN)
