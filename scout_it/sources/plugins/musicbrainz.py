"""MusicBrainz — open music metadata database. Free, no key (rate limit 1/sec).

API docs: https://musicbrainz.org/doc/MusicBrainz_API
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://musicbrainz.org/ws/2/recording"


class MusicBrainzPlugin(SourcePlugin):
    name = "musicbrainz"
    display_name = "MusicBrainz"
    content_type = "media"
    config = SourceConfig(
        name="musicbrainz",
        requires_api_key=False,
        rate_limit_per_sec=1.0,
        description="Open music metadata — recordings, artists, releases, works.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("musicbrainz")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "query": query,
            "limit": min(max_results, 50),
            "fmt": "json",
        }

        headers = {"User-Agent": "scout-it/1.0 ( https://github.com/gajjalaashok75-UI/scout-it )"}
        data = sync_fetch_json(url, params=params, headers=headers, timeout=20)
        if not data or "recordings" not in data:
            return []

        results = []
        for rec in data["recordings"][:max_results]:
            mbid = rec.get("id", "")
            title = rec.get("title", "")
            length_ms = rec.get("length", 0) or 0

            # Artists.
            artists = [a.get("name", "") for a in rec.get("artist-credit", []) if isinstance(a, dict)]
            # Releases (albums).
            releases = rec.get("releases", [])[:3]
            release_titles = [r.get("title", "") for r in releases if isinstance(r, dict)]

            first_release = rec.get("first-release-date", "")

            snippet = f"Artists: {', '.join(artists)}" if artists else ""
            if release_titles:
                snippet += f" | Releases: {', '.join(release_titles[:2])}"
            if length_ms:
                snippet += f" | Length: {length_ms // 1000}s"

            url_val = f"https://musicbrainz.org/recording/{mbid}"

            results.append(make_result(
                id=mbid,
                source="musicbrainz",
                url=url_val,
                title=title,
                snippet=snippet,
                content="",
                content_type="media",
                timestamp=first_release,
                authority_score=0.3,
                lang="en",
                metadata={
                    "artists": artists,
                    "releases": release_titles,
                    "first_release_date": first_release,
                    "length_ms": length_ms,
                    "mbid": mbid,
                },
            ))
        return results


from ..registry import register
PLUGIN = MusicBrainzPlugin()
register(PLUGIN)
