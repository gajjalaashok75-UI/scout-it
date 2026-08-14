"""Unpaywall — open-access full-text PDF links for ~30M articles.

API docs: https://unpaywall.org/products/api
Free, requires an email address (used as the API key).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.unpaywall.org/v2/search"


class UnpaywallPlugin(SourcePlugin):
    name = "unpaywall"
    display_name = "Unpaywall"
    content_type = "academic"
    config = SourceConfig(
        name="unpaywall",
        requires_api_key=True,
        api_key_env="UNPAYWALL_EMAIL",
        rate_limit_per_sec=5.0,
        description="Open-access full-text PDF links for ~30M articles.",
    )

    def is_available(self) -> bool:
        email = self.get_api_key()
        return bool(email)

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        email = self.get_api_key()
        if not email:
            logger.warning("Unpaywall requires an email address. Set it via: scout-it config")
            return []

        cfg = get_source_config("unpaywall")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "query": query,
            "email": email,
            "per_page": min(max_results, 50),
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "results" not in data:
            return []

        results = []
        for entry in data["results"][:max_results]:
            item = entry.get("response", entry)
            doi = item.get("doi", "")
            title = item.get("title", "") or item.get("title_", "")

            # Best OA location.
            best_oa = item.get("best_oa_location") or {}
            oa_url = best_oa.get("url_for_pdf") or best_oa.get("url") or ""
            host_type = best_oa.get("host_type", "")

            is_oa = item.get("is_oa", False)
            oa_status = item.get("oa_status", "")

            # Journal/venue.
            venue = item.get("journal_name", "") or (item.get("z_authors") and "journal") or ""

            results.append(make_result(
                id=doi,
                source="unpaywall",
                url=oa_url or f"https://doi.org/{doi}" if doi else "",
                title=title,
                snippet=item.get("abstract", "") or f"Open access article (status: {oa_status})",
                content="",
                content_type="academic",
                timestamp=item.get("published_date", ""),
                authority_score=0.6 if is_oa else 0.3,
                lang="en",
                metadata={
                    "doi": doi,
                    "is_oa": is_oa,
                    "oa_status": oa_status,
                    "oa_pdf_url": oa_url,
                    "host_type": host_type,
                    "venue": venue,
                    "genre": item.get("genre", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = UnpaywallPlugin()
register(PLUGIN)
