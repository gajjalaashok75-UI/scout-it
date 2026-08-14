"""Spaceflight News — spaceflight-related news articles. Free, no key.

API docs: https://spaceflightnewsapi.net
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.spaceflightnewsapi.net/v4/articles"


class SpaceflightNewsPlugin(SourcePlugin):
    name = "spaceflight_news"
    display_name = "Spaceflight News"
    content_type = "event"
    config = SourceConfig(
        name="spaceflight_news",
        requires_api_key=False,
        rate_limit_per_sec=5.0,
        description="Spaceflight news — articles about launches, missions, space science.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("spaceflight_news")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "search": query,
            "limit": min(max_results, 50),
            "ordering": "-published_at",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "results" not in data:
            return []

        results = []
        for article in data["results"][:max_results]:
            article_id = str(article.get("id", ""))
            title = article.get("title", "")
            url_val = article.get("url", "")
            summary = article.get("summary", "")
            published_at = article.get("published_at", "")
            news_site = article.get("news_site", "")

            image_url = article.get("image_url", "")

            results.append(make_result(
                id=article_id,
                source="spaceflight_news",
                url=url_val,
                title=title,
                snippet=summary[:500],
                content="",
                content_type="event",
                timestamp=published_at,
                authority_score=0.4,
                lang="en",
                metadata={
                    "news_site": news_site,
                    "published_at": published_at,
                    "updated_at": article.get("updated_at", ""),
                    "image_url": image_url,
                    "launches": article.get("launches", [])[:3],
                    "events": article.get("events", [])[:3],
                },
            ))
        return results


from ..registry import register
PLUGIN = SpaceflightNewsPlugin()
register(PLUGIN)
