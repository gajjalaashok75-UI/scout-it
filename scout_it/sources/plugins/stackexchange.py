"""Stack Exchange — Q&A sites for programming, science, math. Free, no key.

API docs: https://api.stackexchange.com/docs
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.stackexchange.com/2.3/search/advanced"


class StackExchangePlugin(SourcePlugin):
    name = "stackexchange"
    display_name = "Stack Exchange"
    content_type = "knowledge"
    config = SourceConfig(
        name="stackexchange",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="Q&A sites — Stack Overflow, Math, Science, Ask Ubuntu, etc.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("stackexchange")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "order": "desc",
            "sort": "relevance",
            "q": query,
            "pagesize": min(max_results, 50),
            "site": "stackoverflow",
            "filter": "withbody",
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "items" not in data:
            return []

        results = []
        for item in data["items"][:max_results]:
            question_id = str(item.get("question_id", ""))
            title = item.get("title", "")
            link = item.get("link", "")

            score = item.get("score", 0) or 0
            answer_count = item.get("answer_count", 0) or 0
            view_count = item.get("view_count", 0) or 0
            is_answered = item.get("is_answered", False)
            creation_date = item.get("creation_date", 0)
            tags = item.get("tags", [])

            # Body (HTML) → plain text snippet.
            body = item.get("body", "")
            import re
            snippet = re.sub(r"<[^>]+>", "", body).strip()[:500] if body else ""
            if not snippet:
                snippet = f"Score: {score} | Answers: {answer_count} | Views: {view_count}"

            authority = min(score / 100.0, 1.0)

            results.append(make_result(
                id=question_id,
                source="stackexchange",
                url=link,
                title=title,
                snippet=snippet,
                content="",
                content_type="knowledge",
                timestamp=str(creation_date),
                authority_score=authority,
                lang="en",
                metadata={
                    "score": score,
                    "answer_count": answer_count,
                    "view_count": view_count,
                    "is_answered": is_answered,
                    "tags": tags[:10],
                    "site": "stackoverflow",
                    "owner": item.get("owner", {}).get("display_name", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = StackExchangePlugin()
register(PLUGIN)
