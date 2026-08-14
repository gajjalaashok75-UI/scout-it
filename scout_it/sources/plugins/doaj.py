"""DOAJ — Directory of Open Access Journals. Free, no key.

API docs: https://doaj.org/api/v1/docs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://doaj.org/api/search/articles"


class DoajPlugin(SourcePlugin):
    name = "doaj"
    display_name = "DOAJ"
    content_type = "academic"
    config = SourceConfig(
        name="doaj",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="Directory of Open Access Journals — 8M+ OA articles.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("doaj")
        url = cfg.get("base_url") or BASE_URL

        # DOAJ uses Lucene query syntax.
        params = {
            "search": f'title:"{query}" OR abstract:"{query}"',
            "pageSize": min(max_results, 50),
        }

        data = sync_fetch_json(f"{url}/{query}", params={"pageSize": min(max_results, 50)}, timeout=20)
        if not data or "results" not in data:
            return []

        results = []
        for item in data["results"][:max_results]:
            bibjson = item.get("bibjson", {})
            article_id = item.get("id", "")

            title = bibjson.get("title", "")
            abstract = bibjson.get("abstract", "") or ""
            year = bibjson.get("year", "")
            month = bibjson.get("month", "")
            doi = bibjson.get("identifier", {}).get("doi", "")

            # Authors.
            authors = []
            for author in bibjson.get("author", []):
                name = author.get("name", "")
                if name:
                    authors.append(name)

            # Journal.
            journal = bibjson.get("journal", {})
            journal_title = journal.get("title", "")
            publisher = journal.get("publisher", "")

            # Keywords/subjects.
            keywords = bibjson.get("keywords", [])
            subjects = [s.get("term", "") for s in bibjson.get("subject", []) if isinstance(s, dict)]

            # Links.
            links = bibjson.get("link", [])
            pdf_url = ""
            for link in links:
                if link.get("type", "") == "fulltext":
                    pdf_url = link.get("url", "")
                    break

            url_val = f"https://doaj.org/article/{article_id}" if article_id else pdf_url

            snippet_parts = []
            if authors:
                snippet_parts.append(f"Authors: {', '.join(authors[:3])}")
            if journal_title:
                snippet_parts.append(f"Journal: {journal_title}")
            if year:
                snippet_parts.append(f"Year: {year}")
            snippet = " | ".join(snippet_parts)

            results.append(make_result(
                id=article_id or doi,
                source="doaj",
                url=url_val,
                title=title,
                snippet=snippet,
                content=abstract[:500],
                content_type="academic",
                timestamp=f"{year}-{month}" if month else str(year),
                authority_score=0.5,
                lang="en",
                metadata={
                    "authors": authors,
                    "journal": journal_title,
                    "publisher": publisher,
                    "doi": doi,
                    "year": year,
                    "keywords": keywords,
                    "subjects": subjects,
                    "pdf_url": pdf_url,
                },
            ))
        return results


from ..registry import register
PLUGIN = DoajPlugin()
register(PLUGIN)
