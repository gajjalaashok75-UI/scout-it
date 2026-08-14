"""USGS Earthquakes — real-time earthquake data. Free, no key.

API docs: https://earthquake.usgs.gov/fdsnws/event/1/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


class UsgsEarthquakesPlugin(SourcePlugin):
    name = "usgs_earthquakes"
    display_name = "USGS Earthquakes"
    content_type = "event"
    config = SourceConfig(
        name="usgs_earthquakes",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="Real-time earthquake data — magnitude, location, depth, time.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("usgs_earthquakes")
        url = cfg.get("base_url") or BASE_URL

        # USGS doesn't do text search — it queries by time/magnitude/location.
        # We use query as a location filter in the "eventid" or just return recent significant quakes.
        params = {
            "format": "geojson",
            "orderby": "time",
            "limit": min(max_results, 50),
            "minmagnitude": 4.5,  # significant earthquakes only
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "features" not in data:
            return []

        results = []
        query_lower = query.lower()
        for feature in data["features"][:max_results]:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            event_id = feature.get("id", "")

            place = props.get("place", "")
            mag = props.get("mag", 0) or 0
            title = props.get("title", "")
            time_ms = props.get("time", 0)
            url_val = props.get("url", "")
            tsunami = props.get("tsunami", 0)
            alert = props.get("alert", "")

            # Filter by query if it matches place/title.
            if query_lower not in place.lower() and query_lower not in title.lower():
                continue

            coords = geom.get("coordinates", [0, 0, 0])

            snippet = f"Magnitude: {mag} | Location: {place} | Tsunami: {'Yes' if tsunami else 'No'}"
            if alert:
                snippet += f" | Alert: {alert}"

            authority = min(mag / 10.0, 1.0)

            results.append(make_result(
                id=event_id,
                source="usgs_earthquakes",
                url=url_val,
                title=title,
                snippet=snippet,
                content="",
                content_type="event",
                timestamp=str(time_ms),
                authority_score=authority,
                lang="en",
                metadata={
                    "magnitude": mag,
                    "place": place,
                    "time": time_ms,
                    "tsunami": bool(tsunami),
                    "alert": alert,
                    "coordinates": coords,
                    "depth_km": coords[2] if len(coords) > 2 else 0,
                    "event_id": event_id,
                },
            ))
        return results


from ..registry import register
PLUGIN = UsgsEarthquakesPlugin()
register(PLUGIN)
