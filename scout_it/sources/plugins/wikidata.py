"""Wikidata — 100M+ entities with structured relations via SPARQL. Free, no key.

API docs: https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

SPARQL_URL = "https://query.wikidata.org/sparql"


class WikidataPlugin(SourcePlugin):
    name = "wikidata"
    display_name = "Wikidata (SPARQL)"
    content_type = "knowledge"
    config = SourceConfig(
        name="wikidata",
        requires_api_key=False,
        rate_limit_per_sec=1.0,
        description="100M+ entities with structured relations.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("wikidata")
        url = cfg.get("base_url") or SPARQL_URL

        # SPARQL query: search for entities matching the query in labels.
        # Uses the wbsearchentities API as a simpler alternative to full SPARQL.
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": min(max_results, 50),
            "type": "item",
        }

        headers = {"Accept": "application/json"}
        data = sync_fetch_json(search_url, params=params, headers=headers, timeout=20)
        if not data or "search" not in data:
            return []

        results = []
        for item in data["search"][:max_results]:
            qid = item.get("id", "")
            label = item.get("label", "")
            description = item.get("description", "")
            url_val = f"https://www.wikidata.org/wiki/{qid}"

            # Concepturi for the full entity.
            concept_uri = item.get("concepturi", url_val)

            results.append(make_result(
                id=qid,
                source="wikidata",
                url=url_val,
                title=label,
                snippet=description,
                content="",
                content_type="knowledge",
                timestamp="",
                authority_score=0.6,  # Wikidata: curated, moderate-high authority
                lang="en",
                metadata={
                    "qid": qid,
                    "concept_uri": concept_uri,
                    "match": item.get("match", {}),
                    "aliases": item.get("aliases", []),
                },
            ))
        return results


from ..registry import register
PLUGIN = WikidataPlugin()
register(PLUGIN)
