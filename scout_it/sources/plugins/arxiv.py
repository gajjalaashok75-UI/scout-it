"""arXiv — 2.4M+ preprint papers in physics, math, CS, biology.

API: Atom XML feed at https://export.arxiv.org/api/query
Free, no key needed. Rate limit: 1 req/3sec (polite).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
from xml.etree import ElementTree as ET

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_text

logger = logging.getLogger(__name__)

BASE_URL = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivPlugin(SourcePlugin):
    name = "arxiv"
    display_name = "arXiv"
    content_type = "academic"
    config = SourceConfig(
        name="arxiv",
        requires_api_key=False,
        rate_limit_per_sec=0.33,
        description="2.4M+ preprint papers in physics, math, CS, biology.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max_results, 50),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        cfg = get_source_config("arxiv")
        url = cfg.get("base_url") or BASE_URL

        xml_text = sync_fetch_text(url, params=params, timeout=20)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("arXiv XML parse error: %s", exc)
            return []

        results = []
        for entry in root.findall("atom:entry", NS):
            title = (entry.findtext("atom:title", "", NS) or "").strip()
            title = re.sub(r"\s+", " ", title)

            summary = (entry.findtext("atom:summary", "", NS) or "").strip()
            summary = re.sub(r"\s+", " ", summary)

            # arXiv URL (abs page).
            arxiv_url = ""
            id_text = entry.findtext("atom:id", "", NS) or ""
            for link in entry.findall("atom:link", NS):
                if link.get("type") == "text/html":
                    arxiv_url = link.get("href", "")
                    break
            if not arxiv_url:
                arxiv_url = id_text

            published = entry.findtext("atom:published", "", NS) or ""
            updated = entry.findtext("atom:updated", "", NS) or ""

            # Authors.
            authors = []
            for author in entry.findall("atom:author", NS):
                name = author.findtext("atom:name", "", NS)
                if name:
                    authors.append(name)

            # DOI if present.
            doi = ""
            for link in entry.findall("atom:link", NS):
                if link.get("title") == "doi":
                    doi = link.get("href", "").replace("https://doi.org/", "")
                    break

            # PDF link.
            pdf_url = ""
            for link in entry.findall("atom:link", NS):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break

            results.append(make_result(
                id=id_text.split("/")[-1],
                source="arxiv",
                url=arxiv_url,
                title=title,
                snippet=summary,
                content="",
                content_type="academic",
                timestamp=published,
                authority_score=0.5,  # arXiv preprints: moderate authority
                lang="en",
                metadata={
                    "authors": authors[:5],
                    "doi": doi,
                    "pdf_url": pdf_url,
                    "arxiv_id": id_text.split("/")[-1],
                    "categories": [c.get("term", "") for c in entry.findall("atom:category", NS)],
                    "updated": updated,
                },
            ))
            if len(results) >= max_results:
                break
        return results


from ..registry import register
PLUGIN = ArxivPlugin()
register(PLUGIN)
