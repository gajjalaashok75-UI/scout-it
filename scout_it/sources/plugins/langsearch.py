"""LangSearch — web search API with summaries.

Requires ``LANGSEARCH_API_KEY`` (set via ``scout-it config``). Uses the REST
endpoint ``POST https://api.langsearch.com/v1/web-search`` via ``requests`` —
no SDK needed. Supports web-search and multi-search (both hit the same
``/v1/web-search`` endpoint; multi reuses web results).

API reference: https://docs.langsearch.com/api/web-search-api

Response shape::

    {"code": 200, "log_id": "...", "msg": null,
     "data": {"_type": "SearchResponse",
              "queryContext": {"originalQuery": "..."},
              "webPages": {"webSearchUrl": "...", "totalEstimatedMatches": N,
                            "value": [{"id": "...", "name": "...", "url": "...",
                                       "displayUrl": "...", "snippet": "...",
                                       "summary": "...", ...}]}}}

The ``summary`` field (when ``summary=True``) is a richer snippet; it is
preserved on ``content`` so the semantic ranker sees the full context.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from ..api_search_base import ApiSearchSource, _ApiKeyError, _NetworkError, _RateLimitError
from ..base import SourceConfig, make_result

logger = logging.getLogger(__name__)

BASE_URL = "https://api.langsearch.com/v1/web-search"

SUPPORTED = ("web", "multi")


class LangsearchPlugin(ApiSearchSource):
    name = "langsearch"
    display_name = "LangSearch"
    content_type = "web"
    SUPPORTED_SEARCH_TYPES = SUPPORTED
    config = SourceConfig(
        name="langsearch",
        requires_api_key=True,
        api_key_env="LANGSEARCH_API_KEY",
        rate_limit_per_sec=2.0,
        description="Web search with summaries. Use --source langsearch (not --sources).",
    )

    def _raw_search(
        self,
        *,
        query: str,
        max_results: int,
        search_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "query": query,
            "freshness": "noLimit",
            "summary": True,
            "count": max_results,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(BASE_URL, json=payload, headers=headers, timeout=30)
        except Exception as exc:
            raise _NetworkError(str(exc)) from exc

        status = resp.status_code
        if status in (401, 403):
            raise _ApiKeyError(f"HTTP {status}: {resp.text[:200]}")
        if status == 429:
            raise _RateLimitError(f"HTTP 429: rate limited — {resp.text[:200]}")
        if status >= 500:
            raise _NetworkError(f"HTTP {status}: server error — {resp.text[:200]}")
        if status >= 400:
            body = resp.text[:300].lower()
            if any(
                k in body
                for k in ("credit", "quota", "limit", "billing", "payment", "insufficient")
            ):
                raise _RateLimitError(f"HTTP {status}: {resp.text[:200]}")
            raise _ApiKeyError(f"HTTP {status}: {resp.text[:200]}")

        try:
            data = resp.json()
        except Exception as exc:
            raise _NetworkError(f"invalid JSON response: {exc}") from exc

        # Navigate the nested response; tolerate missing levels.
        if not isinstance(data, dict):
            return []
        payload_data = data.get("data") if isinstance(data.get("data"), dict) else data
        web_pages = payload_data.get("webPages") if isinstance(payload_data, dict) else None
        if not isinstance(web_pages, dict):
            return []
        values = web_pages.get("value", []) or []

        out: List[Dict[str, Any]] = []
        for item in values:
            if isinstance(item, dict):
                out.append(item)
        return out

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        url = raw.get("url", "") or raw.get("displayUrl", "") or raw.get("link", "")
        name = raw.get("name", "") or raw.get("title", "")
        if not url and not name:
            return None

        snippet = raw.get("snippet", "") or ""
        summary = raw.get("summary", "") or ""
        # summary is the richer field when summary=True; prefer it as content.
        content = summary or snippet

        return make_result(
            id=raw.get("id", "") or url or name,
            source="langsearch",
            url=url,
            title=name,
            snippet=snippet or (content[:500] if content else ""),
            content=content,
            content_type="web",
            metadata={
                "display_url": raw.get("displayUrl", ""),
                "summary": summary[:2000] if summary else "",
                "search_type": search_type,
            },
        )


from ..registry import register

PLUGIN = LangsearchPlugin()
register(PLUGIN)
