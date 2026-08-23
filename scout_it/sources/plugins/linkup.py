"""Linkup — agentic web/image search API.

Requires ``LINKUP_API_KEY`` (set via ``scout-it config``). Uses the ``linkup``
SDK shipped by the ``linkup-sdk`` distribution (``from linkup import
LinkupClient``). Supports web-search, image-search, and multi-search.

API reference: https://docs.linkup.so

Search-type → Linkup parameters:

  * ``web``   — ``depth="standard"``, ``output_type="sourcedAnswer"``,
                ``include_images=False``, ``include_inline_citations=True``
  * ``image`` — same + ``include_images=True``
  * ``multi`` — same + ``include_images=True``

A ``sourcedAnswer`` response carries a natural-language ``answer`` plus a
``sources`` list (each ``{name, url, snippet, favicon}``). The sources are
normalized into the ``SearchResult`` schema and the answer is preserved on
``metadata["linkup_answer"]`` so the ranker and final output see it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..api_search_base import (
    ApiSearchSource,
    _ApiKeyError,
    _NetworkError,
    _RateLimitError,
    source_messages,
)
from ..base import SourceConfig, make_result

logger = logging.getLogger(__name__)

SUPPORTED = ("web", "image", "multi")

# Optional SDK — imported at module level so tests can patch
# ``scout_it.sources.plugins.linkup.LinkupClient``. The method checks for None
# so the plugin degrades gracefully when linkup-sdk isn't installed.
try:
    from linkup import (
        AuthenticationError,
        BudgetLimitExceededError,
        InsufficientCreditError,
        LinkupClient,  # type: ignore[import]
        LinkupTimeoutError,
        TooManyRequestsError,
    )  # type: ignore[import]
except ImportError:  # pragma: no cover - exercised only without the SDK
    LinkupClient = None  # type: ignore[assignment,misc]
    AuthenticationError = BudgetLimitExceededError = InsufficientCreditError = (
        LinkupTimeoutError
    ) = TooManyRequestsError = ()  # type: ignore[assignment,misc]


class LinkupPlugin(ApiSearchSource):
    name = "linkup"
    display_name = "Linkup"
    content_type = "web"
    SUPPORTED_SEARCH_TYPES = SUPPORTED
    config = SourceConfig(
        name="linkup",
        requires_api_key=True,
        api_key_env="LINKUP_API_KEY",
        rate_limit_per_sec=2.0,
        description="Agentic web/image search with sourced answers. Use --source linkup (not --sources).",
    )

    def _raw_search(
        self,
        *,
        query: str,
        max_results: int,
        search_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        if LinkupClient is None:
            logger.info("linkup-sdk not installed; skipping Linkup source")
            source_messages.error(self.name, "linkup-sdk not installed (pip install linkup-sdk)")
            return []

        client = LinkupClient(api_key)

        kwargs: Dict[str, Any] = {
            "query": query,
            "depth": "standard",
            "output_type": "sourcedAnswer",
            "include_images": search_type in ("image", "multi"),
            "include_inline_citations": True,
            "max_results": max_results,
        }

        try:
            response = client.search(**kwargs)
        except Exception as exc:
            _classify_linkup_error(exc)
            raise

        # sourcedAnswer → SourcedAnswer(answer, sources[{name,url,snippet,favicon}]).
        # Be defensive: support pydantic models, plain dicts, and objects.
        answer = _get(response, "answer", "") or ""
        sources = _get(response, "sources", []) or []
        # Some SDK responses expose a separate images list when include_images
        # is set; surface it if present.
        images = _get(response, "images", []) or []

        out: List[Dict[str, Any]] = []
        for src in sources:
            out.append(
                {
                    "name": _get(src, "name", ""),
                    "url": _get(src, "url", ""),
                    "snippet": _get(src, "snippet", ""),
                    "favicon": _get(src, "favicon", ""),
                    "_answer": answer,
                    "_is_image": False,
                }
            )
        for img in images:
            url = _get(img, "url", "") or _get(img, "image_url", "")
            if url:
                out.append(
                    {
                        "url": url,
                        "name": _get(img, "name", "") or _get(img, "title", ""),
                        "_is_image": True,
                    }
                )
        return out

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        url = raw.get("url", "")
        name = raw.get("name", "") or raw.get("title", "")
        if not url and not name:
            return None

        if raw.get("_is_image"):
            return make_result(
                id=url,
                source="linkup",
                url=url,
                title=name or "Linkup image result",
                snippet=name,
                content=name,
                content_type="media",
                metadata={"image_url": url, "image_description": name, "is_image": True},
            )

        snippet = raw.get("snippet", "")
        answer = raw.get("_answer", "")
        return make_result(
            id=url or name,
            source="linkup",
            url=url,
            title=name,
            snippet=snippet,
            content=snippet or answer,
            content_type="web",
            metadata={
                "favicon": raw.get("favicon", ""),
                "linkup_answer": answer[:2000] if answer else "",
                "search_type": search_type,
            },
        )


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a key from a pydantic model, mapping, or attribute object."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    # pydantic v2 model
    model_fields = getattr(type(obj), "model_fields", None)
    if model_fields and key in model_fields:
        return getattr(obj, key, default)
    return getattr(obj, key, default)


def _classify_linkup_error(exc: Exception) -> None:
    """Inspect a Linkup exception and re-raise as the right typed error."""
    if isinstance(exc, (AuthenticationError,)):
        raise _ApiKeyError(str(exc)) from exc
    if isinstance(exc, (TooManyRequestsError, BudgetLimitExceededError, InsufficientCreditError)):
        raise _RateLimitError(str(exc)) from exc
    if isinstance(exc, (LinkupTimeoutError,)):
        raise _NetworkError(str(exc)) from exc
    # Fall back to message inspection for untyped errors / SDK versions where
    # the typed exception classes aren't importable.
    msg = str(exc).lower()
    if any(
        k in msg
        for k in (
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "invalid api key",
            "ip not whitelisted",
        )
    ):
        raise _ApiKeyError(str(exc)) from exc
    if any(
        k in msg
        for k in (
            "429",
            "rate limit",
            "quota",
            "credit",
            "insufficient",
            "budget",
            "payment required",
        )
    ):
        raise _RateLimitError(str(exc)) from exc
    if any(k in msg for k in ("timeout", "connection", "network", "dns", "unreachable", "refused")):
        raise _NetworkError(str(exc)) from exc
    raise exc


from ..registry import register

PLUGIN = LinkupPlugin()
register(PLUGIN)
