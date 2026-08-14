"""Bitbucket — code repositories (Atlassian). Free, no key for public search.

API docs: https://developer.atlassian.com/cloud/bitbucket/rest/api-group-repositories/

Note: Bitbucket deprecated the global public repository listing endpoint
(CHANGE-2770).  We search within a curated list of popular open-source
workspaces using the ``/2.0/repositories/{workspace}`` endpoint with BQL
filtering.  Users can override the workspace list via source config.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json, USER_AGENT

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bitbucket.org/2.0/repositories"

# Curated workspaces with substantial open-source projects.
DEFAULT_WORKSPACES = [
    "atlassian",
    "google",
    "microsoft",
    "facebook",
]


class BitbucketPlugin(SourcePlugin):
    name = "bitbucket"
    display_name = "Bitbucket"
    content_type = "code"
    config = SourceConfig(
        name="bitbucket",
        requires_api_key=False,
        rate_limit_per_sec=2.0,
        description="Git repositories and code collaboration (Atlassian).",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("bitbucket")
        workspaces = cfg.get("workspaces") or DEFAULT_WORKSPACES

        safe_query = query.replace('"', "").strip()
        params = {
            "q": f'name~"{safe_query}"',
            "sort": "-updated_on",
            "pagelen": str(min(max_results, 20)),
            "fields": (
                "values.uuid,values.name,values.full_name,values.description,"
                "values.links.html.href,values.language,values.created_on,"
                "values.updated_on,values.owner.display_name,values.scm"
            ),
        }

        # Search each workspace and merge results.
        all_results: List[Dict[str, Any]] = []
        for ws in workspaces:
            ws_url = f"{BASE_URL}/{ws}"
            data = sync_fetch_json(ws_url, params=params, timeout=20)
            if not data or not isinstance(data, dict):
                continue
            for repo in data.get("values", []):
                all_results.append(self._parse_repo(repo))
            if len(all_results) >= max_results:
                break

        return all_results[:max_results]

    def _parse_repo(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        uuid = repo.get("uuid", "")
        name = repo.get("name", "")
        full_name = repo.get("full_name", name)

        links = repo.get("links", {})
        html_link = links.get("html", {})
        web_url = html_link.get("href", f"https://bitbucket.org/{full_name}")

        description = (repo.get("description") or "").strip()
        description = re.sub(r"<[^>]+>", "", description)[:500]

        language = repo.get("language", "") or ""
        updated = repo.get("updated_on", "") or repo.get("created_on", "")

        authority = 0.5
        if description:
            authority += 0.1
        if language:
            authority += 0.1
        authority = min(authority, 1.0)

        snippet = description or f"Bitbucket repository {full_name}"
        if language:
            snippet += f" [Language: {language}]"

        return make_result(
            id=uuid or full_name,
            source="bitbucket",
            url=web_url,
            title=name,
            snippet=snippet,
            content="",
            content_type="code",
            timestamp=updated,
            authority_score=authority,
            lang="en",
            metadata={
                "full_name": full_name,
                "language": language,
                "scm": repo.get("scm", "git"),
                "owner": repo.get("owner", {}).get("display_name", ""),
                "created_on": repo.get("created_on", ""),
            },
        )


from ..registry import register
PLUGIN = BitbucketPlugin()
register(PLUGIN)
