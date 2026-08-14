"""Crossref — 150M+ DOI-registered works. Free, polite pool with email.

API docs: https://api.crossref.org
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crossref.org/works"


class CrossrefPlugin(SourcePlugin):
    name = "crossref"
    display_name = "Crossref"
    content_type = "academic"
    config = SourceConfig(
        name="crossref",
        requires_api_key=False,
        rate_limit_per_sec=3.0,
        description="150M+ DOI-registered works.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("crossref")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "query": query,
            "rows": min(max_results, 100),
            "select": "DOI,title,abstract,URL,published,author,is-referenced-by-count,type,container-title",
            "mailto": "scout-it@example.com",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "message" not in data:
            return []

        items = data["message"].get("items", [])
        results = []
        for item in items[:max_results]:
            titles = item.get("title") or []
            title = titles[0] if titles else ""

            abstract = item.get("abstract", "") or ""
            # Strip JATS XML tags from abstract.
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            doi = item.get("DOI", "")
            url_val = item.get("URL", "") or (f"https://doi.org/{doi}" if doi else "")

            authors = []
            for author in (item.get("author") or [])[:5]:
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if name:
                    authors.append(name)

            cited = item.get("is-referenced-by-count", 0) or 0
            authority = min(cited / 300.0, 1.0)

            published = item.get("published", {})
            date_parts = published.get("date-parts", [[]])
            timestamp = ""
            if date_parts and date_parts[0]:
                parts = date_parts[0]
                timestamp = "-".join(str(p) for p in parts)

            results.append(make_result(
                id=doi,
                source="crossref",
                url=url_val,
                title=title,
                snippet=abstract,
                content="",
                content_type="academic",
                timestamp=timestamp,
                authority_score=authority,
                lang="en",
                metadata={
                    "doi": doi,
                    "authors": authors,
                    "citation_count": cited,
                    "type": item.get("type", ""),
                    "container_title": (item.get("container-title") or [""])[0],
                },
            ))
        return results


from ..registry import register
PLUGIN = CrossrefPlugin()
register(PLUGIN)
