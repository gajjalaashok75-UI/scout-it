"""Open Library — 30M+ book records. Free, no key needed.

API docs: https://openlibrary.org/developers/api
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://openlibrary.org/search.json"


class OpenLibraryPlugin(SourcePlugin):
    name = "open_library"
    display_name = "Open Library"
    content_type = "book"
    config = SourceConfig(
        name="open_library",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="30M+ book records with metadata and availability.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("open_library")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "q": query,
            "limit": min(max_results, 100),
            "fields": "key,title,author_name,first_publish_year,isbn,subject,cover_i,language,edition_count",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "docs" not in data:
            return []

        results = []
        for doc in data["docs"][:max_results]:
            ol_key = doc.get("key", "")  # e.g. /works/OL12345W
            url_val = f"https://openlibrary.org{ol_key}" if ol_key else ""

            title = doc.get("title", "")
            authors = doc.get("author_name", [])[:5]

            # Subjects as snippet.
            subjects = doc.get("subject", [])[:5]
            snippet = f"Authors: {', '.join(authors)}" if authors else ""
            if subjects:
                snippet += f" | Subjects: {', '.join(subjects)}"

            # Cover image.
            cover_id = doc.get("cover_i")
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ""

            edition_count = doc.get("edition_count", 0) or 0
            authority = min(edition_count / 50.0, 1.0)

            results.append(make_result(
                id=ol_key,
                source="open_library",
                url=url_val,
                title=title,
                snippet=snippet,
                content="",
                content_type="book",
                timestamp=str(doc.get("first_publish_year", "")),
                authority_score=authority,
                lang="en",
                metadata={
                    "authors": authors,
                    "first_publish_year": doc.get("first_publish_year"),
                    "isbn": (doc.get("isbn") or [])[:3],
                    "subjects": subjects,
                    "edition_count": edition_count,
                    "cover_url": cover_url,
                    "languages": doc.get("language", []),
                },
            ))
        return results


from ..registry import register
PLUGIN = OpenLibraryPlugin()
register(PLUGIN)
