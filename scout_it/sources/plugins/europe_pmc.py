"""Europe PMC — 40M+ biomedical and life science articles. Free, no key.

API docs: https://europepmc.org/RestfulWebService
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePmcPlugin(SourcePlugin):
    name = "europe_pmc"
    display_name = "Europe PMC"
    content_type = "academic"
    config = SourceConfig(
        name="europe_pmc",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="40M+ biomedical and life science articles.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("europe_pmc")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "query": query,
            "format": "json",
            "pageSize": min(max_results, 100),
            "resultType": "core",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "resultList" not in data:
            return []

        results = []
        for item in data["resultList"].get("results", [])[:max_results]:
            doi = item.get("doi", "")
            pmid = item.get("pmid", "")
            pmcid = item.get("pmcid", "")

            # Best URL: PMC full text if available, else DOI.
            url_val = ""
            if pmcid:
                url_val = f"https://europepmc.org/article/PMC/{pmcid}"
            elif doi:
                url_val = f"https://doi.org/{doi}"
            elif pmid:
                url_val = f"https://europepmc.org/article/MED/{pmid}"

            title = item.get("title", "")
            abstract = item.get("abstractText", "") or ""

            cited = item.get("citedByCount", 0) or 0
            authority = min(cited / 200.0, 1.0)

            authors = []
            for author in (item.get("authorList") or {}).get("author", [])[:5]:
                name = f"{author.get('firstName', '')} {author.get('lastName', '')}".strip()
                if name:
                    authors.append(name)

            results.append(make_result(
                id=pmcid or pmid or doi,
                source="europe_pmc",
                url=url_val,
                title=title,
                snippet=abstract,
                content="",
                content_type="academic",
                timestamp=item.get("firstPublicationDate", ""),
                authority_score=authority,
                lang="en",
                metadata={
                    "doi": doi,
                    "pmid": pmid,
                    "pmcid": pmcid,
                    "authors": authors,
                    "journal": item.get("journalTitle", ""),
                    "cited_by_count": cited,
                    "is_open_access": item.get("inEPMC", "N") == "Y",
                },
            ))
        return results


from ..registry import register
PLUGIN = EuropePmcPlugin()
register(PLUGIN)
