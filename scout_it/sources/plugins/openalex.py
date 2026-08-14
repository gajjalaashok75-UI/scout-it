"""OpenAlex — 250M+ scholarly works, free, no API key needed.

API docs: https://docs.openalex.org
Polite pool: include `mailto` parameter for faster rate limits.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import SOURCE_BY_NAME
from ..async_fetch import sync_fetch_json, RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org/works"


class OpenAlexPlugin(SourcePlugin):
    name = "openalex"
    display_name = "OpenAlex"
    content_type = "academic"
    config = SourceConfig(
        name="openalex",
        requires_api_key=False,
        rate_limit_per_sec=10.0,
        description="~250M scholarly works — the free academic Google replacement.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        params = {
            "search": query,
            "per-page": min(max_results, 200),
            "mailto": "scout-it@example.com",  # polite pool
        }
        base = SOURCE_BY_NAME.get("openalex", {})
        # Allow base_url override from config.
        from ..source_config import get_source_config
        cfg = get_source_config("openalex")
        url = cfg.get("base_url") or BASE_URL

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "results" not in data:
            return []

        results = []
        for work in data["results"][:max_results]:
            # Extract abstract from inverted index.
            abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))

            # Best URL: prefer DOI, then landing page.
            doi = work.get("doi") or ""
            url_val = doi or work.get("id", "").replace("https://openalex.org/", "https://doi.org/")
            if not url_val.startswith("http"):
                url_val = f"https://doi.org/{url_val}" if doi else work.get("id", "")

            # Authority: citation count normalized.
            cited_by = work.get("cited_by_count", 0)
            authority = min(cited_by / 500.0, 1.0)  # 500+ citations = max authority

            # Authors.
            authorships = work.get("authorships", [])
            authors = [a.get("author", {}).get("display_name", "") for a in authorships[:5]]

            results.append(make_result(
                id=work.get("id", "").split("/")[-1] or str(work.get("doi", "")),
                source="openalex",
                url=url_val,
                title=work.get("title", "") or work.get("display_name", ""),
                snippet=abstract or work.get("title", ""),
                content="",  # OpenAlex doesn't provide full text
                content_type="academic",
                timestamp=work.get("publication_date", ""),
                authority_score=authority,
                lang=work.get("language", "en"),
                metadata={
                    "doi": doi.replace("https://doi.org/", "") if doi else "",
                    "authors": authors,
                    "cited_by_count": cited_by,
                    "openalex_id": work.get("id", ""),
                    "type": work.get("type", ""),
                    "concepts": [c.get("display_name", "") for c in (work.get("concepts") or [])[:5]],
                    "is_oa": work.get("open_access", {}).get("is_oa", False),
                    "oa_url": work.get("open_access", {}).get("oa_url", ""),
                },
            ))
        return results

    @staticmethod
    def _reconstruct_abstract(inverted_index: Dict[str, List[int]]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""
        positions = []
        for word, indices in inverted_index.items():
            for idx in indices:
                positions.append((idx, word))
        positions.sort()
        return " ".join(w for _, w in positions)


# Register the plugin.
from ..registry import register
PLUGIN = OpenAlexPlugin()
register(PLUGIN)
