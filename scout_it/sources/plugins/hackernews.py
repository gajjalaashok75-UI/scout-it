"""Hacker News — CS/entrepreneurship social news. Free, no key.

Uses the Algolia HN Search API: https://hn.algolia.com/api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://hn.algolia.com/api/v1/search"


class HackerNewsPlugin(SourcePlugin):
    name = "hackernews"
    display_name = "Hacker News"
    content_type = "event"
    config = SourceConfig(
        name="hackernews",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="CS/entrepreneurship social news — stories, comments, discussions.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("hackernews")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": min(max_results, 50),
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "hits" not in data:
            return []

        results = []
        for hit in data["hits"][:max_results]:
            object_id = hit.get("objectID", "")
            title = hit.get("title", "") or hit.get("story_title", "")
            url_val = hit.get("url", "") or f"https://news.ycombinator.com/item?id={object_id}"

            points = hit.get("points", 0) or 0
            num_comments = hit.get("num_comments", 0) or 0
            author = hit.get("author", "")
            created_at = hit.get("created_at", "")

            authority = min(points / 500.0, 1.0)

            snippet = f"Points: {points} | Comments: {num_comments} | Author: {author}"
            story_text = hit.get("story_text", "")
            if story_text:
                import re
                snippet = re.sub(r"<[^>]+>", "", story_text).strip()[:300]

            results.append(make_result(
                id=object_id,
                source="hackernews",
                url=url_val,
                title=title,
                snippet=snippet,
                content="",
                content_type="event",
                timestamp=created_at,
                authority_score=authority,
                lang="en",
                metadata={
                    "points": points,
                    "num_comments": num_comments,
                    "author": author,
                    "created_at": created_at,
                    "tags": hit.get("_tags", []),
                    "hn_url": f"https://news.ycombinator.com/item?id={object_id}",
                },
            ))
        return results


from ..registry import register
PLUGIN = HackerNewsPlugin()
register(PLUGIN)
