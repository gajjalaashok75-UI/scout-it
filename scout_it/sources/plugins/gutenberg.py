"""Project Gutenberg — 70k+ free full-text ebooks. Free, no key needed.

API: https://gutendex.com (unofficial but stable JSON API for Gutenberg)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://gutendex.com/books"


class GutenbergPlugin(SourcePlugin):
    name = "gutenberg"
    display_name = "Project Gutenberg"
    content_type = "book"
    config = SourceConfig(
        name="gutenberg",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="70k+ free full-text ebooks.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("gutenberg")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "search": query,
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "results" not in data:
            return []

        results = []
        for book in data["results"][:max_results]:
            book_id = str(book.get("id", ""))
            url_val = f"https://www.gutenberg.org/ebooks/{book_id}"

            title = book.get("title", "")
            authors = [a.get("name", "") for a in book.get("authors", [])[:5]]

            # Formats — find text/html or plain text.
            formats = book.get("formats", {})
            text_url = ""
            for fmt_key, fmt_url in formats.items():
                if "text/html" in fmt_key or "text/plain" in fmt_key:
                    text_url = fmt_url
                    break

            # Subjects.
            subjects = book.get("subjects", [])[:5]

            snippet = f"Authors: {', '.join(authors)}" if authors else ""
            if subjects:
                snippet += f" | Subjects: {', '.join(subjects[:3])}"

            download_count = book.get("download_count", 0) or 0
            authority = min(download_count / 10000.0, 1.0)

            results.append(make_result(
                id=book_id,
                source="gutenberg",
                url=url_val,
                title=title,
                snippet=snippet,
                content="",
                content_type="book",
                timestamp="",
                authority_score=authority,
                lang="en",
                metadata={
                    "authors": authors,
                    "subjects": subjects,
                    "bookshelves": book.get("bookshelves", [])[:5],
                    "languages": book.get("languages", []),
                    "copyright": book.get("copyright"),
                    "download_count": download_count,
                    "media_type": book.get("media_type", ""),
                    "text_url": text_url,
                    "formats": {k: v for k, v in list(formats.items())[:5]},
                },
            ))
        return results


from ..registry import register
PLUGIN = GutenbergPlugin()
register(PLUGIN)
