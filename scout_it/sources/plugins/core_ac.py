"""CORE — 200M+ open-access papers with full text. Free API key required.

API docs: https://core.ac.uk/services/api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://core.ac.uk:443/api-v2/search"


class CorePlugin(SourcePlugin):
    name = "core"
    display_name = "CORE"
    content_type = "academic"
    config = SourceConfig(
        name="core",
        requires_api_key=True,
        api_key_env="CORE_API_KEY",
        rate_limit_per_sec=1.0,
        description="200M+ open-access papers with full text.",
    )

    def is_available(self) -> bool:
        return bool(self.get_api_key())

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        api_key = self.get_api_key()
        if not api_key:
            logger.warning("CORE requires an API key. Get one at https://core.ac.uk/services/api")
            return []

        cfg = get_source_config("core")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "page": 1,
            "pageSize": min(max_results, 100),
            "apiKey": api_key,
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "data" not in data:
            return []

        results = []
        for item in data["data"][:max_results]:
            doi = item.get("doi", "")
            title = item.get("title", "")
            abstract = item.get("description", "") or item.get("abstract", "")

            download_url = item.get("downloadUrl", "")
            url_val = download_url or (f"https://doi.org/{doi}" if doi else item.get("id", ""))

            cited = item.get("citationCount", 0) or 0
            authority = min(cited / 200.0, 1.0)

            results.append(make_result(
                id=str(item.get("id", "")),
                source="core",
                url=url_val,
                title=title,
                snippet=abstract[:500] if abstract else "",
                content="",
                content_type="academic",
                timestamp=item.get("yearPublished", "") or item.get("publishedDate", ""),
                authority_score=authority,
                lang=item.get("language", "en"),
                metadata={
                    "doi": doi,
                    "download_url": download_url,
                    "citation_count": cited,
                    "publisher": item.get("publisher", ""),
                    "source": item.get("source", ""),
                    "year": item.get("yearPublished"),
                },
            ))
        return results


from ..registry import register
PLUGIN = CorePlugin()
register(PLUGIN)
