"""data.gov — US government open data, 300k+ datasets via CKAN API. Free, no key.

API docs: https://resources.data.gov/resources/ckan/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://catalog.data.gov/api/3/action/package_search"


class DataGovPlugin(SourcePlugin):
    name = "data_gov"
    display_name = "data.gov (CKAN)"
    content_type = "dataset"
    config = SourceConfig(
        name="data_gov",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="US government open data — 300k+ datasets.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("data_gov")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "rows": min(max_results, 50),
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "result" not in data:
            return []

        results = []
        for item in data["result"].get("results", [])[:max_results]:
            ds_id = item.get("id", "")
            name = item.get("name", "")
            title = item.get("title", "") or name
            url_val = f"https://catalog.data.gov/dataset/{name}"

            notes = item.get("notes", "") or ""
            import re
            notes = re.sub(r"<[^>]+>", "", notes).strip()[:500]

            # Organization.
            org = item.get("organization", {}) or {}
            org_name = org.get("title", "") or org.get("name", "")

            # Resources (downloadable files/APIs).
            resources = item.get("resources") or []
            download_url = ""
            for res in resources:
                if res.get("format", "").lower() in ("csv", "json", "xml", "api"):
                    download_url = res.get("url", "")
                    break

            results.append(make_result(
                id=ds_id,
                source="data_gov",
                url=url_val,
                title=title,
                snippet=notes,
                content="",
                content_type="dataset",
                timestamp=item.get("metadata_created", ""),
                authority_score=0.4,  # gov datasets: moderate authority
                lang="en",
                metadata={
                    "organization": org_name,
                    "resources": len(resources),
                    "download_url": download_url,
                    "formats": list(set(r.get("format", "") for r in resources))[:5],
                    "tags": [t.get("display_name", "") for t in item.get("tags", [])[:10]],
                    "license": item.get("license_title", ""),
                    "modified": item.get("metadata_modified", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = DataGovPlugin()
register(PLUGIN)
