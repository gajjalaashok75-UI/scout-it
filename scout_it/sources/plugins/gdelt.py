"""GDELT — global events database, monitors worldwide news in real time. Free, no key.

API docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


class GdeltPlugin(SourcePlugin):
    name = "gdelt"
    display_name = "GDELT"
    content_type = "event"
    config = SourceConfig(
        name="gdelt",
        requires_api_key=False,
        rate_limit_per_sec=1.0,
        description="Global events database — monitors worldwide news in real time.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("gdelt")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(min(max_results, 250)),
            "format": "json",
            "sort": "DateDesc",
        }

        data = sync_fetch_json(url, params=params, timeout=25)
        if not data or "articles" not in data:
            return []

        results = []
        for article in data["articles"][:max_results]:
            url_val = article.get("url", "")
            title = article.get("title", "")
            domain = article.get("domain", "")
            language = article.get("language", "en")
            seen_date = article.get("seendate", "")

            # Social image and tone.
            socialimage = article.get("socialimage", "")
            tone = article.get("tone", 0) or 0
            try:
                tone_val = float(tone.split(",")[0]) if isinstance(tone, str) else float(tone)
            except (ValueError, TypeError):
                tone_val = 0.0

            results.append(make_result(
                id=url_val or f"gdelt-{seen_date}-{title[:20]}",
                source="gdelt",
                url=url_val,
                title=title,
                snippet=article.get("title", "") or f"News article from {domain}",
                content="",
                content_type="event",
                timestamp=seen_date,
                authority_score=0.3,  # News articles: moderate authority
                lang=language,
                metadata={
                    "domain": domain,
                    "language": language,
                    "social_image": socialimage,
                    "tone": tone,
                    "tone_val": tone_val,
                    "source_country": article.get("sourcecountry", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = GdeltPlugin()
register(PLUGIN)
