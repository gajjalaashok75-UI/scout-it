"""GitLab — open-source and private code repositories. Free, no key for public search.

API docs: https://docs.gitlab.com/ee/api/projects.html#search-for-projects-by-name

Public project search works without authentication (rate-limited).  Users
with a personal access token can raise the rate limit and search private
projects by setting ``GITLAB_TOKEN``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json, USER_AGENT

logger = logging.getLogger(__name__)

BASE_URL = "https://gitlab.com/api/v4/projects"


class GitLabPlugin(SourcePlugin):
    name = "gitlab"
    display_name = "GitLab"
    content_type = "code"
    config = SourceConfig(
        name="gitlab",
        requires_api_key=False,
        api_key_env="GITLAB_TOKEN",
        rate_limit_per_sec=2.0,
        description="Git repositories, CI/CD pipelines, and open-source projects.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("gitlab")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "search": query,
            "per_page": min(max_results, 20),
            "order_by": "updated_at",
            "sort": "desc",
        }

        headers: Dict[str, str] = {}
        token = self.get_api_key()
        if token:
            headers["PRIVATE-TOKEN"] = token

        data = sync_fetch_json(url, params=params, headers=headers or None, timeout=25)
        if not data or not isinstance(data, list):
            return []

        results: List[Dict[str, Any]] = []
        for proj in data[:max_results]:
            project_id = proj.get("id", "")
            name = proj.get("name", "") or proj.get("path_with_namespace", "")
            full_path = proj.get("path_with_namespace", name)
            web_url = proj.get("web_url", f"https://gitlab.com/{full_path}")
            description = (proj.get("description") or "").strip()[:500]

            stars = proj.get("star_count", 0) or 0
            forks = proj.get("forks_count", 0) or 0
            authority = min(stars / 500.0, 1.0)

            last_activity = proj.get("last_activity_at", "") or proj.get("created_at", "")

            results.append(make_result(
                id=str(project_id),
                source="gitlab",
                url=web_url,
                title=name,
                snippet=description or f"GitLab project {full_path} — {stars} stars, {forks} forks",
                content="",
                content_type="code",
                timestamp=last_activity,
                authority_score=authority,
                lang="en",
                metadata={
                    "full_path": full_path,
                    "stars": stars,
                    "forks": forks,
                    "open_issues": proj.get("open_issues_count", 0),
                    "default_branch": proj.get("default_branch", ""),
                    "visibility": proj.get("visibility", "public"),
                    "namespace": proj.get("namespace", {}).get("full_path", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = GitLabPlugin()
register(PLUGIN)
