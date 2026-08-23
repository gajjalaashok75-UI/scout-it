"""Serper — Google Search API (web/news/image/video/multi).

Requires ``SERPER_API_KEY`` (set via ``scout-it config``). Uses the REST
endpoints under ``https://google.serper.dev`` via ``requests`` — no SDK
needed. Supports all five search types used by scout-it:

  * ``web``   → ``POST /search``    payload ``{"q", "num"}`` → ``organic``
  * ``news``  → ``POST /news``      payload ``{"q", "num"}`` → ``news``
  * ``image`` → ``POST /images``     payload ``{"q", "num"}`` → ``images``
  * ``video`` → ``POST /videos``     payload ``{"q", "num"}`` → ``videos``
  * ``multi`` → ``POST /search`` with a *batch* JSON-array payload
                ``[{"q", "num"}]`` (single query, array form) →
                first element's ``organic`` list

API reference: https://serper.dev

The Serper ``num`` parameter controls the number of results returned. The
``X-API-KEY`` header carries the key. Responses are plain JSON with the
canonical Google SERP shape (``organic``/``news``/``images``/``videos``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from ..api_search_base import ApiSearchSource, _ApiKeyError, _NetworkError, _RateLimitError
from ..base import SourceConfig, make_result

logger = logging.getLogger(__name__)

BASE_URL = "https://google.serper.dev"

SUPPORTED = ("web", "news", "image", "video", "multi")

# search_type → endpoint path + the response key holding the result list.
_ENDPOINTS: Dict[str, str] = {
    "web": "/search",
    "news": "/news",
    "image": "/images",
    "video": "/videos",
    "multi": "/search",  # batch array payload
}

_RESPONSE_KEYS: Dict[str, str] = {
    "web": "organic",
    "news": "news",
    "image": "images",
    "video": "videos",
    "multi": "organic",
}


class SerperPlugin(ApiSearchSource):
    name = "serper"
    display_name = "Serper"
    content_type = "web"
    SUPPORTED_SEARCH_TYPES = SUPPORTED
    config = SourceConfig(
        name="serper",
        requires_api_key=True,
        api_key_env="SERPER_API_KEY",
        rate_limit_per_sec=2.0,
        description="Google SERP API (web/news/image/video). Use --source serper (not --sources).",
    )

    def _raw_search(
        self,
        *,
        query: str,
        max_results: int,
        search_type: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        path = _ENDPOINTS.get(search_type, "/search")
        url = f"{BASE_URL}{path}"
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }

        # multi uses the batch JSON-array payload form (one query per element).
        if search_type == "multi":
            payload: Any = [{"q": query, "num": max_results}]
            resp_key = "organic"
        else:
            payload = {"q": query, "num": max_results}
            resp_key = _RESPONSE_KEYS.get(search_type, "organic")

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
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
            if any(k in body for k in ("credit", "quota", "limit", "billing", "payment")):
                raise _RateLimitError(f"HTTP {status}: {resp.text[:200]}")
            raise _ApiKeyError(f"HTTP {status}: {resp.text[:200]}")

        try:
            data = resp.json()
        except Exception as exc:
            raise _NetworkError(f"invalid JSON response: {exc}") from exc

        # Batch (multi) response is a list of SERP objects; take the first.
        if isinstance(data, list):
            if not data or not isinstance(data[0], dict):
                return []
            data = data[0]
        if not isinstance(data, dict):
            return []

        results = data.get(resp_key, []) or []
        out: List[Dict[str, Any]] = []
        for item in results:
            if isinstance(item, dict):
                item["_serper_search_type"] = search_type
                out.append(item)
        return out

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        st = raw.get("_serper_search_type", search_type)

        if st == "image":
            img_url = raw.get("imageUrl", "") or raw.get("image", "") or raw.get("link", "")
            title = raw.get("title", "") or raw.get("name", "")
            if not img_url and not title:
                return None
            source_page = raw.get("imagePageUrl", "") or raw.get("link", "") or img_url
            return make_result(
                id=img_url or title,
                source="serper",
                url=source_page or img_url,
                title=title,
                snippet=title,
                content=title,
                content_type="media",
                metadata={
                    "image_url": img_url,
                    "image_description": title,
                    "is_image": True,
                    "search_type": st,
                },
            )

        if st == "video":
            url = raw.get("link", "") or raw.get("url", "") or raw.get("youtubeUrl", "")
            title = raw.get("title", "")
            if not url and not title:
                return None
            snippet = raw.get("snippet", "")
            thumb = raw.get("thumbnail", "") or raw.get("image", "")
            date = raw.get("date", "") or raw.get("publishDate", "") or ""
            channel = raw.get("channel", "") or raw.get("source", "")
            return make_result(
                id=url or title,
                source="serper",
                url=url,
                title=title,
                snippet=snippet,
                content=snippet or title,
                content_type="media",
                timestamp=date,
                metadata={
                    "thumbnail": thumb,
                    "image_url": thumb,
                    "channel": channel,
                    "is_video": True,
                    "search_type": st,
                },
            )

        # web / news / multi → organic / news items
        url = raw.get("link", "") or raw.get("url", "")
        title = raw.get("title", "")
        if not url and not title:
            return None
        snippet = raw.get("snippet", "")
        date = raw.get("date", "") or raw.get("publishDate", "") or ""
        source_name = raw.get("source", "") or raw.get("channel", "") or ""
        position = raw.get("position")
        return make_result(
            id=url or title,
            source="serper",
            url=url,
            title=title,
            snippet=snippet,
            content=snippet or title,
            content_type="web",
            timestamp=date,
            authority_score=0.0,
            metadata={
                "source_name": source_name,
                "position": position,
                "search_type": st,
            },
        )


from ..registry import register

PLUGIN = SerperPlugin()
register(PLUGIN)
