"""Hugging Face Datasets — 100k+ datasets for ML/AI. Free, no key needed.

API docs: https://huggingface.co/docs/hub/datasets-api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://huggingface.co/api/datasets"


class HuggingFacePlugin(SourcePlugin):
    name = "huggingface"
    display_name = "Hugging Face Datasets"
    content_type = "dataset"
    config = SourceConfig(
        name="huggingface",
        requires_api_key=False,
        api_key_env="HF_TOKEN",
        rate_limit_per_sec=5.0,
        description="100k+ datasets for ML/AI.",
    )

    def is_available(self) -> bool:
        return True  # Works without token

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("huggingface")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "search": query,
            "limit": min(max_results, 50),
            "full": "true",
        }

        headers = {}
        token = self.get_api_key()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = sync_fetch_json(url, params=params, headers=headers, timeout=20)
        if not data or not isinstance(data, list):
            return []

        results = []
        for item in data[:max_results]:
            ds_id = item.get("id", "")
            url_val = f"https://huggingface.co/datasets/{ds_id}"

            # Description from cardData.
            card = item.get("cardData") or {}
            desc = card.get("description", "") or item.get("description", "")

            downloads = item.get("downloads", 0) or 0
            likes = item.get("likes", 0) or 0
            authority = min((downloads / 100000.0 + likes / 1000.0), 1.0)

            tags = item.get("tags") or []
            task_categories = [t.replace("task_categories:", "") for t in tags if "task_categories:" in t]

            results.append(make_result(
                id=ds_id,
                source="huggingface",
                url=url_val,
                title=ds_id,
                snippet=desc[:500] if desc else f"Dataset {ds_id}",
                content="",
                content_type="dataset",
                timestamp=item.get("lastModified", ""),
                authority_score=authority,
                lang="en",
                metadata={
                    "downloads": downloads,
                    "likes": likes,
                    "tags": [t for t in tags if ":" not in t][:10],
                    "task_categories": task_categories,
                    "size": card.get("size_categories"),
                    "papers": card.get("papers", []),
                    "download_url": f"https://huggingface.co/datasets/{ds_id}/resolve/main/",
                },
            ))
        return results


from ..registry import register
PLUGIN = HuggingFacePlugin()
register(PLUGIN)
