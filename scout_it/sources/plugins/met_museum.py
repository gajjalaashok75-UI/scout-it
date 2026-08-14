"""Metropolitan Museum of Art — art collection API. Free, no key.

API docs: https://metmuseum.github.io/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

SEARCH_URL = "https://collectionapi.metmuseum.org/public/collection/v1/search"
OBJECT_URL = "https://collectionapi.metmuseum.org/public/collection/v1/objects"


class MetMuseumPlugin(SourcePlugin):
    name = "met_museum"
    display_name = "Metropolitan Museum of Art"
    content_type = "media"
    config = SourceConfig(
        name="met_museum",
        requires_api_key=False,
        rate_limit_per_sec=4.0,
        description="Met Museum collection — 490k+ artworks with images and metadata.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("met_museum")

        # Step 1: Search for object IDs.
        search_params = {
            "q": query,
            "hasImages": "true",
        }
        search_data = sync_fetch_json(SEARCH_URL, params=search_params, timeout=20)
        if not search_data or "objectIDs" not in search_data:
            return []

        object_ids = search_data["objectIDs"][:max_results]
        results = []

        # Step 2: Fetch each object (parallel via async would be better, but sequential for simplicity).
        import requests
        from ..async_fetch import USER_AGENT
        for oid in object_ids:
            try:
                resp = requests.get(
                    f"{OBJECT_URL}/{oid}",
                    headers={"User-Agent": USER_AGENT},
                    timeout=15,
                )
                resp.raise_for_status()
                obj = resp.json()
            except Exception as exc:
                logger.debug("Met Museum object %s fetch failed: %s", oid, exc)
                continue

            title = obj.get("title", "")
            artist = obj.get("artistDisplayName", "")
            department = obj.get("department", "")
            classification = obj.get("classification", "")
            culture = obj.get("culture", "")
            period = obj.get("period", "")
            date = obj.get("objectDate", "")
            medium = obj.get("medium", "")
            image_url = obj.get("primaryImage", "") or obj.get("primaryImageSmall", "")
            object_url = obj.get("objectURL", "")

            snippet_parts = []
            if artist:
                snippet_parts.append(artist)
            if date:
                snippet_parts.append(date)
            if medium:
                snippet_parts.append(medium)
            if department:
                snippet_parts.append(department)
            snippet = " | ".join(snippet_parts)

            results.append(make_result(
                id=str(oid),
                source="met_museum",
                url=object_url,
                title=title,
                snippet=snippet,
                content="",
                content_type="media",
                timestamp=date,
                authority_score=0.4,
                lang="en",
                metadata={
                    "artist": artist,
                    "department": department,
                    "classification": classification,
                    "culture": culture,
                    "period": period,
                    "object_date": date,
                    "medium": medium,
                    "image_url": image_url,
                    "object_id": oid,
                    "is_public_domain": obj.get("isPublicDomain", False),
                },
            ))
        return results


from ..registry import register
PLUGIN = MetMuseumPlugin()
register(PLUGIN)
