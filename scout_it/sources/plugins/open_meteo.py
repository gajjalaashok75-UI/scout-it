"""Open-Meteo — global weather forecast API. Free, no key for non-commercial use.

API docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class OpenMeteoPlugin(SourcePlugin):
    name = "open_meteo"
    display_name = "Open-Meteo"
    content_type = "geo"
    config = SourceConfig(
        name="open_meteo",
        requires_api_key=False,
        rate_limit_per_sec=5.0,
        description="Global weather forecasts — current conditions + 16-day forecast.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("open_meteo")

        # Step 1: Geocode the query to lat/lon.
        geocode_params = {
            "name": query,
            "count": min(max_results, 10),
            "language": "en",
            "format": "json",
        }
        geo_data = sync_fetch_json(GEOCODE_URL, params=geocode_params, timeout=15)
        if not geo_data or "results" not in geo_data:
            return []

        results = []
        for place in geo_data["results"][:max_results]:
            name = place.get("name", "")
            country = place.get("country", "")
            admin1 = place.get("admin1", "")
            lat = place.get("latitude", 0)
            lon = place.get("longitude", 0)
            place_id = str(place.get("id", ""))

            full_name = f"{name}"
            if admin1:
                full_name += f", {admin1}"
            if country:
                full_name += f", {country}"

            # Step 2: Fetch weather for this location.
            forecast_params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "auto",
                "forecast_days": 3,
            }
            fc_data = sync_fetch_json(FORECAST_URL, params=forecast_params, timeout=15)

            if not fc_data or "current" not in fc_data:
                continue

            current = fc_data["current"]
            temp = current.get("temperature_2m", 0)
            humidity = current.get("relative_humidity_2m", 0)
            apparent = current.get("apparent_temperature", 0)
            wind = current.get("wind_speed_10m", 0)
            weather_code = current.get("weather_code", 0)

            daily = fc_data.get("daily", {})
            daily_max = daily.get("temperature_2m_max", [])
            daily_min = daily.get("temperature_2m_min", [])

            snippet = (
                f"Current: {temp}°C (feels like {apparent}°C) | "
                f"Humidity: {humidity}% | Wind: {wind} km/h"
            )

            results.append(make_result(
                id=place_id,
                source="open_meteo",
                url=f"https://open-meteo.com/en/docs?latitude={lat}&longitude={lon}",
                title=f"Weather: {full_name}",
                snippet=snippet,
                content="",
                content_type="geo",
                timestamp=current.get("time", ""),
                authority_score=0.5,
                lang="en",
                metadata={
                    "location": full_name,
                    "lat": lat,
                    "lon": lon,
                    "current_temp": temp,
                    "apparent_temp": apparent,
                    "humidity": humidity,
                    "wind_speed": wind,
                    "weather_code": weather_code,
                    "daily_max": daily_max[:3],
                    "daily_min": daily_min[:3],
                    "country": country,
                },
            ))
        return results


from ..registry import register
PLUGIN = OpenMeteoPlugin()
register(PLUGIN)
