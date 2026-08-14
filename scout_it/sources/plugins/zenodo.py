"""Zenodo — research data repository. Free, no key needed.

API docs: https://developers.zenodo.org
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://zenodo.org/api/records"


class ZenodoPlugin(SourcePlugin):
    name = "zenodo"
    display_name = "Zenodo"
    content_type = "dataset"
    config = SourceConfig(
        name="zenodo",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="Research data repository — datasets, software, publications.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("zenodo")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "size": min(max_results, 50),
            "sort": "bestmatch",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "hits" not in data:
            return []

        results = []
        for item in data["hits"].get("hits", [])[:max_results]:
            metadata = item.get("metadata", {})
            rec_id = str(item.get("id", ""))
            url_val = f"https://zenodo.org/records/{rec_id}"

            title = metadata.get("title", "")
            description = metadata.get("description", "") or ""
            # Strip HTML from description.
            import re
            description = re.sub(r"<[^>]+>", "", description).strip()[:500]

            # Publication date.
            pub_date = metadata.get("publication_date", "")

            # DOI.
            doi = metadata.get("doi", "")

            # Downloads (authority signal).
            files = item.get("files") or []
            total_downloads = sum(f.get("downloads", 0) for f in files)
            authority = min(total_downloads / 1000.0, 1.0)

            # Resource type.
            resource_type = (metadata.get("resource_type") or {}).get("title", "")

            # Download URL (first file).
            download_url = ""
            if files:
                download_url = f"https://zenodo.org/records/{rec_id}/files/{files[0].get('key', '')}"

            results.append(make_result(
                id=rec_id,
                source="zenodo",
                url=url_val,
                title=title,
                snippet=description,
                content="",
                content_type="dataset",
                timestamp=pub_date,
                authority_score=authority,
                lang="en",
                metadata={
                    "doi": doi,
                    "resource_type": resource_type,
                    "creators": [c.get("name", "") for c in metadata.get("creators", [])[:5]],
                    "keywords": metadata.get("keywords", [])[:10],
                    "download_url": download_url,
                    "file_count": len(files),
                    "total_downloads": total_downloads,
                    "license": metadata.get("license", {}).get("id", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = ZenodoPlugin()
register(PLUGIN)
