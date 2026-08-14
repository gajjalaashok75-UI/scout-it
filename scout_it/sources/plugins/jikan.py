"""Jikan — unofficial MyAnimeList API. Free, no key.

API docs: https://jikan.moe
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.jikan.moe/v4/anime"


class JikanPlugin(SourcePlugin):
    name = "jikan"
    display_name = "Jikan (MyAnimeList)"
    content_type = "media"
    config = SourceConfig(
        name="jikan",
        requires_api_key=False,
        rate_limit_per_sec=3.0,
        description="Anime/manga database — titles, scores, synopses, genres.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("jikan")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "limit": min(max_results, 25),
            "order_by": "score",
            "sort": "desc",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "data" not in data:
            return []

        results = []
        for anime in data["data"][:max_results]:
            mal_id = str(anime.get("mal_id", ""))
            title = anime.get("title", "") or anime.get("title_english", "")
            title_jp = anime.get("title_japanese", "")
            synopsis = anime.get("synopsis", "") or ""

            score = anime.get("score", 0) or 0
            episodes = anime.get("episodes", 0) or 0
            status = anime.get("status", "")
            year = anime.get("year", "")
            season = anime.get("season", "")
            type_val = anime.get("type", "")

            genres = [g.get("name", "") for g in anime.get("genres", [])]
            studios = [s.get("name", "") for s in anime.get("studios", [])]

            image_url = anime.get("images", {}).get("jpg", {}).get("image_url", "")
            url_val = anime.get("url", "")

            snippet_parts = []
            if type_val:
                snippet_parts.append(type_val)
            if episodes:
                snippet_parts.append(f"{episodes} eps")
            if score:
                snippet_parts.append(f"Score: {score}")
            if status:
                snippet_parts.append(status)
            snippet = " | ".join(snippet_parts)

            authority = min(score / 10.0, 1.0) if score else 0.0

            results.append(make_result(
                id=mal_id,
                source="jikan",
                url=url_val,
                title=title,
                snippet=snippet,
                content=synopsis[:500],
                content_type="media",
                timestamp=str(year),
                authority_score=authority,
                lang="en",
                metadata={
                    "title_japanese": title_jp,
                    "score": score,
                    "episodes": episodes,
                    "status": status,
                    "year": year,
                    "season": season,
                    "type": type_val,
                    "genres": genres,
                    "studios": studios,
                    "image_url": image_url,
                    "mal_id": mal_id,
                },
            ))
        return results


from ..registry import register
PLUGIN = JikanPlugin()
register(PLUGIN)
