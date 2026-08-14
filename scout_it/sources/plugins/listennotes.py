"""ListenNotes — 2.5M+ podcasts and episodes. Free tier: 1000 req/month.

API docs: https://listennotes.com/api/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://listen-api.listennotes.com/api/v2/search"


class ListenNotesPlugin(SourcePlugin):
    name = "listennotes"
    display_name = "ListenNotes"
    content_type = "podcast"
    config = SourceConfig(
        name="listennotes",
        requires_api_key=True,
        api_key_env="LISTENNOTES_API_KEY",
        rate_limit_per_sec=1.0,
        description="2.5M+ podcasts and episodes with transcripts.",
    )

    def is_available(self) -> bool:
        return bool(self.get_api_key())

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        api_key = self.get_api_key()
        if not api_key:
            logger.warning("ListenNotes requires an API key. Get one at https://listennotes.com/api/")
            return []

        cfg = get_source_config("listennotes")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "type": "episode",
            "size": min(max_results, 10),
        }

        headers = {"X-ListenAPI-Key": api_key}
        data = sync_fetch_json(url, params=params, headers=headers, timeout=20)
        if not data or "results" not in data:
            return []

        results = []
        for item in data["results"][:max_results]:
            episode_id = item.get("id", "")
            title = item.get("title_original", "") or item.get("title", "")
            podcast_title = item.get("podcast_title_original", "") or item.get("podcast_title", "")
            audio_url = item.get("audio", "")
            url_val = item.get("link", "") or audio_url

            description = item.get("description_original", "") or item.get("description", "")
            import re
            description = re.sub(r"<[^>]+>", "", description).strip()[:500]

            results.append(make_result(
                id=episode_id,
                source="listennotes",
                url=url_val,
                title=f"{title} — {podcast_title}" if podcast_title else title,
                snippet=description,
                content="",
                content_type="podcast",
                timestamp=item.get("pub_date_ms", ""),
                authority_score=0.4,
                lang="en",
                metadata={
                    "podcast_title": podcast_title,
                    "podcast_id": item.get("podcast_id", ""),
                    "audio_url": audio_url,
                    "audio_length_sec": item.get("audio_length_sec", 0),
                    "image": item.get("image", ""),
                    "publisher": item.get("podcast_publisher_original", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = ListenNotesPlugin()
register(PLUGIN)
