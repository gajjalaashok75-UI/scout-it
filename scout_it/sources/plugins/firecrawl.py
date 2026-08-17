"""Firecrawl — web/news/image search API with built-in scraping.

Requires ``FIRECRAWL_API_KEY`` (set via ``scout-it config``). Uses the
Firecrawl v2 search REST endpoint (``POST /v2/search``) via ``requests`` — no
SDK needed. Supports web-search (``sources=["web"]``), news-search
(``sources=["news"]``), image-search (``sources=["images"]``), and
multi-search (``sources=["news","web","images"]``).

API reference: https://docs.firecrawl.dev

The Firecrawl response includes scraped page content (``markdown`` / ``html``
/ ``json`` depending on ``scrapeOptions.formats``), which is preserved
untruncated on the ``content`` field for ranking and output.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from ..api_search_base import ApiSearchSource, _ApiKeyError, _RateLimitError, _NetworkError
from ..base import SourceConfig, make_result

logger = logging.getLogger(__name__)

BASE_URL = "https://api.firecrawl.dev/v2/search"

SUPPORTED = ("web", "news", "image", "multi")

_SOURCE_MAP = {
    "web": ["web"],
    "news": ["news"],
    "image": ["images"],
    "multi": ["news", "web", "images"],
}


class FirecrawlPlugin(ApiSearchSource):
    name = "firecrawl"
    display_name = "Firecrawl"
    content_type = "web"
    SUPPORTED_SEARCH_TYPES = SUPPORTED
    config = SourceConfig(
        name="firecrawl",
        requires_api_key=True,
        api_key_env="FIRECRAWL_API_KEY",
        rate_limit_per_sec=2.0,
        description="Web/news/image search with built-in page scraping. Web + news + image + multi.",
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
            "sources": _SOURCE_MAP.get(search_type, ["web"]),
            "categories": [],
            "limit": max_results,
            "scrapeOptions": {
                "onlyMainContent": True,
                "maxAge": 172800000,
                "parsers": ["pdf"],
                "formats": [
                    {
                        "type": "json",
                        "schema": {
                            "type": "object",
                            "required": [],
                            "properties": {
                                "company_name": {"type": "string"},
                                "company_description": {"type": "string"},
                            },
                        },
                    }
                ],
            },
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
            raise _RateLimitError(f"HTTP 429: rate limited or credits exhausted — {resp.text[:200]}")
        if status >= 500:
            raise _NetworkError(f"HTTP {status}: server error — {resp.text[:200]}")
        if status >= 400:
            # Other 4xx — could be quota/billing. Treat as rate-limit-style.
            body = resp.text[:300].lower()
            if any(k in body for k in ("credit", "quota", "limit", "billing", "payment")):
                raise _RateLimitError(f"HTTP {status}: {resp.text[:200]}")
            raise _ApiKeyError(f"HTTP {status}: {resp.text[:200]}")

        try:
            data = resp.json()
        except Exception as exc:
            raise _NetworkError(f"invalid JSON response: {exc}") from exc

        # Firecrawl v2 returns {"data": [ {url, title, markdown, html, ...}, ... ]}
        # (or sometimes {"success": true, "data": [...]}). Normalize to a list.
        if isinstance(data, dict):
            results = data.get("data") or data.get("results") or []
        elif isinstance(data, list):
            results = data
        else:
            results = []

        out: List[Dict[str, Any]] = []
        for item in results:
            if isinstance(item, dict):
                out.append(item)
        return out

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        search_type: str,
    ) -> Optional[Dict[str, Any]]:
        url = raw.get("url", "") or raw.get("link", "")
        title = raw.get("title", "") or raw.get("name", "")
        if not url and not title:
            return None

        # Firecrawl returns 'markdown' (full extracted text), 'html', 'json',
        # 'description', and 'summary'. Preserve the richest content untruncated.
        content = raw.get("markdown", "") or raw.get("html", "") or ""
        snippet = raw.get("description", "") or raw.get("summary", "") or (content[:500] if content else "")

        # Image-specific: Firecrawl image results may have 'image' or 'thumbnail'.
        is_image = search_type == "image" or bool(raw.get("image") or raw.get("thumbnail"))
        image_url = raw.get("image", "") or raw.get("thumbnail", "")

        metadata: Dict[str, Any] = {"search_type": search_type}
        if raw.get("json"):
            metadata["structured_json"] = raw["json"]
        if raw.get("favicon"):
            metadata["favicon"] = raw["favicon"]
        if image_url:
            metadata["image_url"] = image_url
            metadata["is_image"] = True

        return make_result(
            id=url or title,
            source="firecrawl",
            url=url or image_url,
            title=title,
            snippet=snippet,
            content=content,
            content_type="media" if is_image else "web",
            authority_score=0.0,
            metadata=metadata,
        )


from ..registry import register
PLUGIN = FirecrawlPlugin()
register(PLUGIN)
