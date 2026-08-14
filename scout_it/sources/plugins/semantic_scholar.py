"""Semantic Scholar — 200M+ papers with citation graphs, TLDRs, influence scores.

API docs: https://api.semanticscholar.org
Free API key increases rate limit from 1/sec to 100/sec.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config, SOURCE_BY_NAME
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarPlugin(SourcePlugin):
    name = "semantic_scholar"
    display_name = "Semantic Scholar"
    content_type = "academic"
    config = SourceConfig(
        name="semantic_scholar",
        requires_api_key=True,
        api_key_env="SEMANTIC_SCHOLAR_API_KEY",
        rate_limit_per_sec=1.0,
        description="200M+ papers with citation graphs and TLDRs.",
    )

    def is_available(self) -> bool:
        """Available even without a key (just rate-limited), but key is preferred."""
        return True  # Works without key at 1 req/sec

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        fields = "title,abstract,url,year,citationCount,influentialCitationCount,authors,tldr,openAccessPdf,externalIds,publicationDate"
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": fields,
        }

        cfg = get_source_config("semantic_scholar")
        headers = {}
        api_key = self.get_api_key()
        if api_key:
            headers["x-api-key"] = api_key

        url = cfg.get("base_url") or BASE_URL
        data = sync_fetch_json(url, params=params, headers=headers, timeout=20)
        if not data or "data" not in data:
            return []

        results = []
        for paper in data["data"][:max_results]:
            tldr = paper.get("tldr") or {}
            abstract = paper.get("abstract") or tldr.get("text", "")

            cited = paper.get("citationCount", 0) or 0
            influential = paper.get("influentialCitationCount", 0) or 0
            authority = min((cited + influential * 2) / 300.0, 1.0)

            authors = [a.get("name", "") for a in (paper.get("authors") or [])[:5]]

            oa_pdf = paper.get("openAccessPdf") or {}
            doi = (paper.get("externalIds") or {}).get("DOI", "")

            url_val = paper.get("url") or ""
            if not url_val and doi:
                url_val = f"https://doi.org/{doi}"

            results.append(make_result(
                id=paper.get("paperId", ""),
                source="semantic_scholar",
                url=url_val,
                title=paper.get("title", "") or "",
                snippet=abstract,
                content="",
                content_type="academic",
                timestamp=paper.get("publicationDate") or str(paper.get("year", "")),
                authority_score=authority,
                lang="en",
                metadata={
                    "doi": doi,
                    "authors": authors,
                    "year": paper.get("year"),
                    "citation_count": cited,
                    "influential_citations": influential,
                    "tldr": tldr.get("text", ""),
                    "oa_pdf_url": oa_pdf.get("url", ""),
                    "paper_id": paper.get("paperId", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = SemanticScholarPlugin()
register(PLUGIN)
