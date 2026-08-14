"""Internet Archive — digital archive of websites, books, audio, video. Free, no key.

API docs: https://archive.org/developers/index.html
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

import requests

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json, USER_AGENT

logger = logging.getLogger(__name__)

BASE_URL = "https://archive.org/advancedsearch.php"


class InternetArchivePlugin(SourcePlugin):
    name = "internet_archive"
    display_name = "Internet Archive"
    content_type = "media"
    config = SourceConfig(
        name="internet_archive",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="Digital archive of websites, books, audio, video, software.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("internet_archive")
        url = cfg.get("base_url") or BASE_URL

        # IA expects repeated fl[] params; use the requests list format.
        try:
            resp = requests.get(url, params=[
                ("q", query),
                ("rows", str(min(max_results, 50))),
                ("output", "json"),
                ("fl[]", "identifier"),
                ("fl[]", "title"),
                ("fl[]", "description"),
                ("fl[]", "mediatype"),
                ("fl[]", "date"),
                ("fl[]", "downloads"),
                ("fl[]", "creator"),
                ("fl[]", "language"),
            ], headers={"User-Agent": USER_AGENT}, timeout=25)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Internet Archive fetch failed: %s", exc)
            return []

        if not data or "response" not in data:
            return []

        docs = data["response"].get("docs", [])
        results = []
        for doc in docs[:max_results]:
            identifier = doc.get("identifier", "")
            url_val = f"https://archive.org/details/{identifier}"

            title = doc.get("title", "")
            if isinstance(title, list):
                title = title[0] if title else ""

            desc = doc.get("description", "")
            if isinstance(desc, list):
                desc = desc[0] if desc else ""
            desc = re.sub(r"<[^>]+>", "", str(desc)).strip()[:500]

            mediatype = doc.get("mediatype", "data")
            downloads = doc.get("downloads", 0) or 0
            authority = min(downloads / 5000.0, 1.0)

            results.append(make_result(
                id=identifier,
                source="internet_archive",
                url=url_val,
                title=title,
                snippet=desc,
                content="",
                content_type="media",
                timestamp=doc.get("date", ""),
                authority_score=authority,
                lang=doc.get("language", "en") if isinstance(doc.get("language"), str) else "en",
                metadata={
                    "mediatype": mediatype,
                    "downloads": downloads,
                    "creator": doc.get("creator", "") if isinstance(doc.get("creator"), str) else "",
                    "identifier": identifier,
                    "details_url": f"https://archive.org/metadata/{identifier}",
                },
            ))
        return results


from ..registry import register
PLUGIN = InternetArchivePlugin()
register(PLUGIN)
