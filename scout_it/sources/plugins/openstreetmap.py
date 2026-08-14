"""OpenStreetMap — geographic data via Nominatim/Overpass. Free, no key.

API docs: https://nominatim.org/release-docs/develop/api/Search/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://nominatim.openstreetmap.org/search"


class OpenStreetMapPlugin(SourcePlugin):
    name = "openstreetmap"
    display_name = "OpenStreetMap"
    content_type = "geo"
    config = SourceConfig(
        name="openstreetmap",
        requires_api_key=False,
        rate_limit_per_sec=1.0,
        description="Geographic data — places, POIs, boundaries.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("openstreetmap")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "format": "jsonv2",
            "limit": min(max_results, 40),
            "addressdetails": 1,
            "extratags": 1,
        }

        headers = {"Accept": "application/json"}
        data = sync_fetch_json(url, params=params, headers=headers, timeout=20)
        if not data or not isinstance(data, list):
            return []

        results = []
        for item in data[:max_results]:
            osm_id = str(item.get("osm_id", ""))
            osm_type = item.get("osm_type", "")
            type_prefix = {"node": "N", "way": "W", "relation": "R"}.get(osm_type, "")
            place_id = str(item.get("place_id", osm_id))

            name = item.get("name", "") or item.get("display_name", "").split(",")[0]
            display_name = item.get("display_name", "")

            lat = item.get("lat", "")
            lon = item.get("lon", "")
            url_val = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}" if lat and lon else ""

            category = item.get("category", "")
            osm_category = item.get("class", "")
            osm_type_val = item.get("type", "")

            importance = item.get("importance", 0.0) or 0.0
            authority = min(float(importance), 1.0)

            address = item.get("address", {})
            extratags = item.get("extratags", {}) or {}

            results.append(make_result(
                id=f"{type_prefix}{osm_id}" if type_prefix else place_id,
                source="openstreetmap",
                url=url_val,
                title=name,
                snippet=display_name,
                content="",
                content_type="geo",
                timestamp="",
                authority_score=authority,
                lang="en",
                metadata={
                    "lat": lat,
                    "lon": lon,
                    "osm_type": osm_type,
                    "osm_id": osm_id,
                    "category": category,
                    "osm_class": osm_category,
                    "osm_type_detail": osm_type_val,
                    "address": address,
                    "extratags": extratags,
                    "boundingbox": item.get("boundingbox", []),
                    "importance": importance,
                },
            ))
        return results


from ..registry import register
PLUGIN = OpenStreetMapPlugin()
register(PLUGIN)
