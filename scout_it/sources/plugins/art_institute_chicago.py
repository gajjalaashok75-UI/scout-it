"""Art Institute of Chicago — art collection API. Free, no key.

API docs: https://api.artic.edu/docs/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.artic.edu/api/v1/artworks/search"


class ArtInstitutePlugin(SourcePlugin):
    name = "art_institute_chicago"
    display_name = "Art Institute of Chicago"
    content_type = "media"
    config = SourceConfig(
        name="art_institute_chicago",
        requires_api_key=False,
        rate_limit_per_sec=5.0,
        description="Art collection — paintings, sculptures, artifacts with images.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("art_institute_chicago")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "limit": min(max_results, 50),
            "fields": "id,title,artist_display,date_display,medium_display,department,artwork_type_title,image_id,thumbnail",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "data" not in data:
            return []

        results = []
        config_base = data.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")
        for artwork in data["data"][:max_results]:
            art_id = str(artwork.get("id", ""))
            title = artwork.get("title", "")
            artist = artwork.get("artist_display", "")
            date_display = artwork.get("date_display", "")
            medium = artwork.get("medium_display", "")
            department = artwork.get("department", "")
            art_type = artwork.get("artwork_type_title", "")
            image_id = artwork.get("image_id", "")

            url_val = f"https://www.artic.edu/artworks/{art_id}"
            image_url = f"{config_base}/{image_id}/full/400,/0/default.jpg" if image_id else ""

            snippet_parts = []
            if artist:
                snippet_parts.append(artist.split("\n")[0])
            if date_display:
                snippet_parts.append(date_display)
            if medium:
                snippet_parts.append(medium)
            snippet = " | ".join(snippet_parts)

            results.append(make_result(
                id=art_id,
                source="art_institute_chicago",
                url=url_val,
                title=title,
                snippet=snippet,
                content="",
                content_type="media",
                timestamp=date_display,
                authority_score=0.4,
                lang="en",
                metadata={
                    "artist": artist,
                    "date_display": date_display,
                    "medium": medium,
                    "department": department,
                    "artwork_type": art_type,
                    "image_url": image_url,
                    "image_id": image_id,
                },
            ))
        return results


from ..registry import register
PLUGIN = ArtInstitutePlugin()
register(PLUGIN)
