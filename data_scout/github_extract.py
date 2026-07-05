#!/usr/bin/env python3
"""
🐙 GITHUB EXTRACTION — repos, commits, diffs, issues, PRs, files, discussions
================================================================================

Uses GitHub's official REST API v3 + GraphQL v4. This is the *real*,
supported way to pull GitHub data — no scraping, no ToS risk.

Auth: works unauthenticated (60 requests/hour, shared across your IP), or
set GITHUB_TOKEN (a fine-grained or classic personal access token with no
special scopes needed for public repos) for 5,000 requests/hour. GraphQL
(used for Discussions) requires a token even for public repos — that's a
GitHub platform requirement, not a limitation of this module.

Every function returns plain dicts/lists (JSON-serializable) and raises
nothing on ordinary "not found" / rate-limit conditions — it returns a
``{"error": ..., "error_message": ...}`` dict instead, so callers (and the
CLI) can handle it uniformly.
"""

import base64
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

REST_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

_REPO_URL_RE = re.compile(r'github\.com[:/]+(?P<owner>[\w.\-]+)/(?P<repo>[\w.\-]+?)(?:\.git)?/?$')


def _headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "data-scout/1.1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_repo_ref(owner_repo_or_url: str) -> Optional[Dict[str, str]]:
    """Accepts 'owner/repo', a full GitHub URL, or 'owner repo' and returns
    {'owner': ..., 'repo': ...}, or None if it can't be parsed."""
    s = str(owner_repo_or_url or "").strip()
    if not s:
        return None
    if "github.com" in s:
        parsed = urlparse(s if "://" in s else f"https://{s}")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            return {"owner": parts[0], "repo": parts[1][:-4] if parts[1].endswith('.git') else parts[1]}
        return None
    if "/" in s:
        owner, _, repo = s.partition("/")
        if owner and repo:
            return {"owner": owner, "repo": repo[:-4] if repo.endswith('.git') else repo}
    return None


def _request(method: str, path_or_url: str, params: Optional[Dict[str, Any]] = None,
             accept: Optional[str] = None, max_retries: int = 3, timeout: int = 20) -> Dict[str, Any]:
    """Low-level REST request with retry-on-transient-error and clear rate-limit
    reporting. Returns {'ok': True, 'data': ..., 'headers': ...} or
    {'ok': False, 'error': ..., 'error_message': ...}."""
    url = path_or_url if path_or_url.startswith("http") else f"{REST_BASE}{path_or_url}"
    headers = _headers()
    if accept:
        headers["Accept"] = accept

    last_error = None
    for attempt in range(max(1, max_retries)):
        try:
            resp = requests.request(method, url, headers=headers, params=params, timeout=timeout)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(1.0 * (attempt + 1))
            continue

        remaining = resp.headers.get("X-RateLimit-Remaining")
        if resp.status_code == 403 and remaining == "0":
            reset = resp.headers.get("X-RateLimit-Reset")
            reset_note = f" (resets at unix time {reset})" if reset else ""
            return {
                "ok": False,
                "error": "rate_limited",
                "error_message": (
                    "GitHub API rate limit exhausted" + reset_note + ". "
                    "Unauthenticated requests are capped at 60/hour; set the GITHUB_TOKEN "
                    "environment variable (a personal access token, no special scopes needed "
                    "for public repos) to raise this to 5,000/hour."
                ),
            }
        if resp.status_code == 404:
            return {"ok": False, "error": "not_found", "error_message": f"GitHub API 404: {url}"}
        if resp.status_code == 401:
            return {"ok": False, "error": "unauthorized", "error_message": "GITHUB_TOKEN is invalid or expired."}
        if resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code} (server error)"
            time.sleep(1.0 * (attempt + 1))
            continue
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            return {"ok": False, "error": "api_error", "error_message": f"HTTP {resp.status_code}: {detail}"}

        try:
            data = resp.json() if resp.text else None
        except ValueError:
            data = resp.text  # e.g. diff/patch media types return plain text
        return {"ok": True, "data": data, "headers": dict(resp.headers)}

    return {"ok": False, "error": "network_error", "error_message": last_error or "request failed after retries"}


def github_rate_limit() -> Dict[str, Any]:
    """Check current GitHub API rate-limit status for the configured token (or IP)."""
    result = _request("GET", "/rate_limit")
    if not result["ok"]:
        return result
    return result["data"]


def _map_repo_fields(d: Dict[str, Any]) -> Dict[str, Any]:
    """Shared mapping from a GitHub API repo object to our output shape.
    Used by both github_repo() and github_search_repos() so search results
    carry the same rich metadata as a direct repo lookup, not a stripped-down
    subset."""
    return {
        "full_name": d.get("full_name"),
        "description": d.get("description"),
        "url": d.get("html_url"),
        "homepage": d.get("homepage"),
        "stars": d.get("stargazers_count"),
        "forks": d.get("forks_count"),
        "watchers": d.get("subscribers_count"),
        # NOTE: GitHub's own `open_issues_count` on the repo object INCLUDES
        # open pull requests (a long-standing REST API quirk) — see
        # `open_issues_only`/`open_pull_requests` below for the split-out,
        # accurate counts fetched via the Search API in github_repo(--full).
        "open_issues_and_prs": d.get("open_issues_count"),
        "default_branch": d.get("default_branch"),
        "language": d.get("language"),
        "topics": d.get("topics", []),
        "license": (d.get("license") or {}).get("spdx_id"),
        "is_fork": d.get("fork"),
        "is_archived": d.get("archived"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
        "pushed_at": d.get("pushed_at"),
        "size_kb": d.get("size"),
        "owner": (d.get("owner") or {}).get("login"),
        "owner_type": (d.get("owner") or {}).get("type"),
    }


def _approx_count_via_link_header(headers: Dict[str, str]) -> Optional[int]:
    """GitHub's pagination Link header exposes a 'last' page number, which
    (at per_page=1) is exactly the total item count — one cheap request
    instead of paginating through everything."""
    link = headers.get("Link") or headers.get("link")
    if not link:
        return None
    match = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    return int(match.group(1)) if match else None


def github_repo(owner_repo_or_url: str, full: bool = True, tree_limit: int = 200) -> Dict[str, Any]:
    """Repository metadata. By default (``full=True``) this aggregates a
    comprehensive overview in one call: base metadata, branches, an
    approximate commit count, accurately split open-issue/open-PR counts,
    top contributors, latest release + release count, a per-language byte
    breakdown, and a preview of the repo's file tree — everything the CLI
    otherwise needs several separate ``github-*`` commands for. Pass
    ``full=False`` (``--quick`` on the CLI) for just the fast, single-call
    base metadata when you don't need all that and want to conserve rate
    limit (the full version costs ~7 API calls instead of 1).

    Every sub-call here is independently error-tolerant: if e.g. releases
    fails or contributors is disabled for this repo, that section is
    reported with its own error instead of failing the whole command.
    """
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    owner, repo = ref["owner"], ref["repo"]

    result = _request("GET", f"/repos/{owner}/{repo}")
    if not result["ok"]:
        return result
    out = _map_repo_fields(result["data"])
    default_branch = result["data"].get("default_branch") or "main"

    if not full:
        return out

    # --- languages: bytes of code per language ---
    lang_result = _request("GET", f"/repos/{owner}/{repo}/languages")
    out["languages"] = lang_result["data"] if lang_result["ok"] else {"error": lang_result.get("error_message")}

    # --- branches (names only, capped) ---
    branches_result = _request("GET", f"/repos/{owner}/{repo}/branches", params={"per_page": 100})
    if branches_result["ok"]:
        out["branches"] = [b.get("name") for b in branches_result["data"] or []]
        out["branch_count"] = len(out["branches"])
    else:
        out["branches"] = {"error": branches_result.get("error_message")}

    # --- approximate total commit count on the default branch ---
    commits_probe = _request("GET", f"/repos/{owner}/{repo}/commits", params={"sha": default_branch, "per_page": 1})
    if commits_probe["ok"]:
        approx = _approx_count_via_link_header(commits_probe.get("headers", {}))
        out["commit_count_approx"] = approx if approx is not None else (1 if commits_probe["data"] else 0)
    else:
        out["commit_count_approx"] = {"error": commits_probe.get("error_message")}

    # --- accurate open issue / open PR split, via the Search API ---
    issues_count = _request("GET", "/search/issues", params={"q": f"repo:{owner}/{repo} is:issue is:open", "per_page": 1})
    out["open_issues_only"] = issues_count["data"].get("total_count") if issues_count["ok"] else {"error": issues_count.get("error_message")}
    prs_count = _request("GET", "/search/issues", params={"q": f"repo:{owner}/{repo} is:pr is:open", "per_page": 1})
    out["open_pull_requests"] = prs_count["data"].get("total_count") if prs_count["ok"] else {"error": prs_count.get("error_message")}

    # --- top contributors ---
    contrib_result = _request("GET", f"/repos/{owner}/{repo}/contributors", params={"per_page": 15})
    if contrib_result["ok"]:
        out["top_contributors"] = [{
            "login": c.get("login"), "contributions": c.get("contributions"), "url": c.get("html_url"),
        } for c in contrib_result["data"] or []]
    else:
        # Common non-error case: contributor stats disabled for very large/empty repos (202) or private repos.
        out["top_contributors"] = {"error": contrib_result.get("error_message")}

    # --- releases: latest + total count ---
    releases_result = _request("GET", f"/repos/{owner}/{repo}/releases", params={"per_page": 1})
    if releases_result["ok"]:
        latest = (releases_result["data"] or [None])[0]
        out["latest_release"] = {
            "tag_name": latest.get("tag_name"), "name": latest.get("name"),
            "published_at": latest.get("published_at"), "url": latest.get("html_url"),
        } if latest else None
        release_count = _approx_count_via_link_header(releases_result.get("headers", {}))
        out["release_count_approx"] = release_count if release_count is not None else len(releases_result["data"] or [])
    else:
        out["latest_release"] = {"error": releases_result.get("error_message")}

    # --- file tree preview (recursive), capped so huge monorepos don't blow up the output ---
    tree_result = _request("GET", f"/repos/{owner}/{repo}/git/trees/{default_branch}", params={"recursive": "1"})
    if tree_result["ok"]:
        tree_data = tree_result["data"] or {}
        entries = tree_data.get("tree", [])
        out["file_tree_preview"] = [{
            "path": e.get("path"), "type": e.get("type"), "size": e.get("size"),
        } for e in entries[:tree_limit]]
        out["file_tree_total_entries"] = len(entries)
        out["file_tree_truncated"] = len(entries) > tree_limit
        if tree_data.get("truncated"):
            out["file_tree_note"] = "GitHub's own tree API truncated this response (repo is very large); use github-folder to walk specific subdirectories instead."
    else:
        out["file_tree_preview"] = {"error": tree_result.get("error_message")}

    return out


def github_commits(
    owner_repo_or_url: str,
    branch: Optional[str] = None,
    path: Optional[str] = None,
    author: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_results: int = 30,
) -> Dict[str, Any]:
    """List commits (metadata only — use github_commit() for full diffs)."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    params = {"per_page": min(max_results, 100)}
    if branch:
        params["sha"] = branch
    if path:
        params["path"] = path
    if author:
        params["author"] = author
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/commits", params=params)
    if not result["ok"]:
        return result

    commits = []
    for c in (result["data"] or [])[:max_results]:
        commit = c.get("commit", {})
        commits.append({
            "sha": c.get("sha"),
            "short_sha": (c.get("sha") or "")[:7],
            "message": commit.get("message"),
            "author_name": (commit.get("author") or {}).get("name"),
            "author_login": (c.get("author") or {}).get("login"),
            "date": (commit.get("author") or {}).get("date"),
            "url": c.get("html_url"),
            "comment_count": commit.get("comment_count", 0),
        })
    return {"repo": f"{ref['owner']}/{ref['repo']}", "commit_count": len(commits), "commits": commits}


def _parse_patch_lines(patch: Optional[str]) -> List[Dict[str, str]]:
    """Break a unified diff patch into individual tagged lines, so consumers
    don't have to eyeball a single run-on string to tell additions from
    deletions. Each entry is ``{"type": ..., "text": ...}`` where type is
    one of: hunk_header, added, removed, context."""
    if not patch:
        return []
    lines = []
    for raw_line in patch.split("\n"):
        if raw_line.startswith("@@"):
            lines.append({"type": "hunk_header", "text": raw_line})
        elif raw_line.startswith("+") and not raw_line.startswith("+++"):
            lines.append({"type": "added", "text": raw_line[1:]})
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            lines.append({"type": "removed", "text": raw_line[1:]})
        else:
            lines.append({"type": "context", "text": raw_line[1:] if raw_line.startswith(" ") else raw_line})
    return lines


def github_commit(owner_repo_or_url: str, sha: str, include_patch: bool = True) -> Dict[str, Any]:
    """Full details for ONE commit: stats, and every changed file with its
    status (added/modified/removed/renamed), +/- line counts, and unified
    diff patch text (the actual code changes)."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    if not sha:
        return {"error": "invalid_sha", "error_message": "A commit SHA (or branch/tag) is required."}

    result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/commits/{sha}")
    if not result["ok"]:
        return result
    d = result["data"]
    commit = d.get("commit", {})

    files = []
    for f in d.get("files", []) or []:
        entry = {
            "filename": f.get("filename"),
            "previous_filename": f.get("previous_filename"),
            "status": f.get("status"),  # added | removed | modified | renamed
            "additions": f.get("additions"),
            "deletions": f.get("deletions"),
            "changes": f.get("changes"),
            "blob_url": f.get("blob_url"),
            "raw_url": f.get("raw_url"),
        }
        if include_patch:
            entry["patch"] = f.get("patch")  # unified diff text; absent for binary/huge files
            entry["patch_lines"] = _parse_patch_lines(f.get("patch"))  # same diff, tagged line-by-line
        files.append(entry)

    parents = [{"sha": p.get("sha"), "url": p.get("html_url")} for p in d.get("parents", []) or []]

    return {
        "repo": f"{ref['owner']}/{ref['repo']}",
        "sha": d.get("sha"),
        "short_sha": (d.get("sha") or "")[:7],
        "message": commit.get("message"),
        "author_name": (commit.get("author") or {}).get("name"),
        "author_email": (commit.get("author") or {}).get("email"),
        "author_login": (d.get("author") or {}).get("login"),
        "committer_login": (d.get("committer") or {}).get("login"),
        "date": (commit.get("author") or {}).get("date"),
        "url": d.get("html_url"),
        "parents": parents,
        "is_merge": len(parents) > 1,
        "stats": d.get("stats", {}),  # {'additions':N,'deletions':N,'total':N}
        "files_changed": len(files),
        "files": files,
    }


def github_prs(
    owner_repo_or_url: str,
    state: str = "open",
    sort: str = "created",
    max_results: int = 30,
) -> Dict[str, Any]:
    """List pull requests for a repo — the PR-specific counterpart to
    github_issues(). Unlike the generic /issues endpoint (which mixes in
    PRs but only exposes issue-shaped fields), this uses /pulls directly so
    each entry carries PR-specific fields: draft status, base/head branches,
    and mergeable state."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    params = {"state": state, "sort": sort, "direction": "desc", "per_page": min(max_results, 100)}

    result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/pulls", params=params)
    if not result["ok"]:
        return result

    prs = []
    for p in (result["data"] or [])[:max_results]:
        prs.append({
            "number": p.get("number"),
            "title": p.get("title"),
            "state": p.get("state"),
            "is_draft": p.get("draft"),
            "author": (p.get("user") or {}).get("login"),
            "base_branch": (p.get("base") or {}).get("ref"),
            "head_branch": (p.get("head") or {}).get("ref"),
            "labels": [l.get("name") for l in p.get("labels", []) or []],
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "closed_at": p.get("closed_at"),
            "merged_at": p.get("merged_at"),
            "url": p.get("html_url"),
        })

    return {"repo": f"{ref['owner']}/{ref['repo']}", "pr_count": len(prs), "pull_requests": prs}


def github_pull_request(owner_repo_or_url: str, number: int, include_diff: bool = True) -> Dict[str, Any]:
    """PR metadata plus (optionally) the full unified diff and changed-files list."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}

    result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/pulls/{number}")
    if not result["ok"]:
        return result
    d = result["data"]

    out = {
        "repo": f"{ref['owner']}/{ref['repo']}",
        "number": d.get("number"),
        "title": d.get("title"),
        "state": d.get("state"),
        "is_merged": d.get("merged"),
        "author": (d.get("user") or {}).get("login"),
        "body": d.get("body"),
        "base_branch": (d.get("base") or {}).get("ref"),
        "head_branch": (d.get("head") or {}).get("ref"),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
        "merged_at": d.get("merged_at"),
        "commits": d.get("commits"),
        "additions": d.get("additions"),
        "deletions": d.get("deletions"),
        "changed_files": d.get("changed_files"),
        "url": d.get("html_url"),
        "labels": [l.get("name") for l in d.get("labels", []) or []],
    }

    if include_diff:
        files_result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/pulls/{number}/files",
                                 params={"per_page": 100})
        if files_result["ok"]:
            out["files"] = [{
                "filename": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "patch": f.get("patch"),
                "patch_lines": _parse_patch_lines(f.get("patch")),
            } for f in files_result["data"] or []]

    return out


def github_issues(
    owner_repo_or_url: str,
    state: str = "open",
    labels: Optional[str] = None,
    max_results: int = 30,
    include_pull_requests: bool = False,
) -> Dict[str, Any]:
    """List issues (GitHub's REST API returns PRs here too unless filtered out)."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    params = {"state": state, "per_page": min(max_results, 100)}
    if labels:
        params["labels"] = labels

    result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/issues", params=params)
    if not result["ok"]:
        return result

    issues = []
    for i in result["data"] or []:
        is_pr = "pull_request" in i
        if is_pr and not include_pull_requests:
            continue
        issues.append({
            "number": i.get("number"),
            "title": i.get("title"),
            "state": i.get("state"),
            "author": (i.get("user") or {}).get("login"),
            "labels": [l.get("name") for l in i.get("labels", []) or []],
            "comments": i.get("comments"),
            "created_at": i.get("created_at"),
            "updated_at": i.get("updated_at"),
            "closed_at": i.get("closed_at"),
            "url": i.get("html_url"),
            "is_pull_request": is_pr,
        })
        if len(issues) >= max_results:
            break

    return {"repo": f"{ref['owner']}/{ref['repo']}", "issue_count": len(issues), "issues": issues}


def github_issue(owner_repo_or_url: str, number: int, include_comments: bool = True) -> Dict[str, Any]:
    """Single issue with full body and (optionally) every comment."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}

    result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/issues/{number}")
    if not result["ok"]:
        return result
    d = result["data"]

    out = {
        "repo": f"{ref['owner']}/{ref['repo']}",
        "number": d.get("number"),
        "title": d.get("title"),
        "state": d.get("state"),
        "author": (d.get("user") or {}).get("login"),
        "body": d.get("body"),
        "labels": [l.get("name") for l in d.get("labels", []) or []],
        "assignees": [a.get("login") for a in d.get("assignees", []) or []],
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
        "closed_at": d.get("closed_at"),
        "url": d.get("html_url"),
        "comment_count": d.get("comments"),
    }

    if include_comments and d.get("comments", 0) > 0:
        comments_result = _request("GET", f"/repos/{ref['owner']}/{ref['repo']}/issues/{number}/comments",
                                    params={"per_page": 100})
        if comments_result["ok"]:
            out["comments"] = [{
                "author": (c.get("user") or {}).get("login"),
                "body": c.get("body"),
                "created_at": c.get("created_at"),
                "url": c.get("html_url"),
            } for c in comments_result["data"] or []]

    return out


def github_folder(
    owner_repo_or_url: str,
    path: str = "",
    ref: Optional[str] = None,
    recursive: bool = True,
    include_content: bool = False,
    max_files: int = 20,
) -> Dict[str, Any]:
    """List every file under a folder path (e.g. 'src/'), optionally fetching
    each file's content too.

    ``recursive=True`` (default) walks the *entire* subtree under *path*
    using the Git Trees API in a single call. ``recursive=False`` lists only
    the immediate children (one Contents-API call, cheaper for huge repos
    when you just want a shallow listing).

    ``include_content=True`` fetches the actual text of up to *max_files*
    files (one API call each — capped by default to avoid silently burning
    through your whole rate limit on a big folder; raise --max-files
    explicitly if you really want more).
    """
    repo_ref = parse_repo_ref(owner_repo_or_url)
    if not repo_ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    owner, repo = repo_ref["owner"], repo_ref["repo"]
    clean_path = path.strip("/")

    if not recursive:
        result = _request("GET", f"/repos/{owner}/{repo}/contents/{clean_path}", params={"ref": ref} if ref else None)
        if not result["ok"]:
            return result
        d = result["data"]
        if not isinstance(d, list):
            return {"error": "not_a_directory", "error_message": f"'{path}' is a file, not a directory. Use github-file instead."}
        entries = [{"path": e.get("path"), "type": "blob" if e.get("type") == "file" else "tree", "size": e.get("size")} for e in d]
    else:
        branch = ref
        if not branch:
            repo_info = _request("GET", f"/repos/{owner}/{repo}")
            if not repo_info["ok"]:
                return repo_info
            branch = repo_info["data"].get("default_branch", "main")

        tree_result = _request("GET", f"/repos/{owner}/{repo}/git/trees/{branch}", params={"recursive": "1"})
        if not tree_result["ok"]:
            return tree_result
        all_entries = (tree_result["data"] or {}).get("tree", [])
        prefix = f"{clean_path}/" if clean_path else ""
        entries = [
            {"path": e.get("path"), "type": e.get("type"), "size": e.get("size")}
            for e in all_entries
            if not clean_path or e.get("path", "").startswith(prefix) or e.get("path") == clean_path
        ]
        if clean_path and not entries:
            return {"error": "not_found", "error_message": f"No entries found under '{path}' — check the path exists on branch '{branch}'."}

    out = {
        "repo": f"{owner}/{repo}",
        "path": clean_path or "/",
        "entry_count": len(entries),
        "entries": entries,
    }

    if include_content:
        file_entries = [e for e in entries if e.get("type") in ("blob", "file")][:max_files]
        fetched = []
        for e in file_entries:
            file_result = github_file_content(f"{owner}/{repo}", e["path"], ref=ref)
            fetched.append(file_result)
        out["files_fetched"] = len(fetched)
        out["files_truncated"] = len([e for e in entries if e.get("type") in ("blob", "file")]) > max_files
        out["files"] = fetched

    return out


def github_file_content(owner_repo_or_url: str, path: str, ref: Optional[str] = None) -> Dict[str, Any]:
    """Fetch and decode a single file's contents from a repo (any text or binary
    file up to GitHub's 1MB Contents-API limit; larger files fall back to the
    raw.githubusercontent.com URL, returned but not inlined)."""
    repo_ref = parse_repo_ref(owner_repo_or_url)
    if not repo_ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    params = {"ref": ref} if ref else None

    result = _request("GET", f"/repos/{repo_ref['owner']}/{repo_ref['repo']}/contents/{path}", params=params)
    if not result["ok"]:
        return result
    d = result["data"]

    if isinstance(d, list):
        return {"error": "is_directory", "error_message": f"'{path}' is a directory, not a file.",
                "entries": [{"name": e.get("name"), "type": e.get("type")} for e in d]}

    content = None
    if d.get("encoding") == "base64" and d.get("content"):
        try:
            content = base64.b64decode(d["content"]).decode("utf-8", errors="replace")
        except Exception:
            content = None  # likely a genuinely binary file

    return {
        "repo": f"{repo_ref['owner']}/{repo_ref['repo']}",
        "path": d.get("path"),
        "sha": d.get("sha"),
        "size_bytes": d.get("size"),
        "content": content,
        "is_binary_or_too_large": content is None,
        "raw_url": d.get("download_url"),
        "html_url": d.get("html_url"),
    }


def github_search_code(query: str, max_results: int = 20) -> Dict[str, Any]:
    """Search code across GitHub. Note: GitHub requires auth for code search
    (GITHUB_TOKEN) and applies stricter rate limits (10/min) than other
    REST endpoints, even with a token."""
    result = _request("GET", "/search/code", params={"q": query, "per_page": min(max_results, 100)})
    if not result["ok"]:
        return result
    d = result["data"] or {}
    items = []
    for item in d.get("items", [])[:max_results]:
        items.append({
            "repo": (item.get("repository") or {}).get("full_name"),
            "path": item.get("path"),
            "url": item.get("html_url"),
            "score": item.get("score"),
        })
    return {"query": query, "total_count": d.get("total_count", 0), "results": items}


def github_search_repos(query: str, sort: str = "stars", max_results: int = 20) -> Dict[str, Any]:
    """Search repositories (e.g. 'language:python stars:>1000 topic:llm').

    Each result carries the same rich metadata fields as ``github_repo()``
    (stars, forks, topics, license, timestamps, etc.) — GitHub's search API
    already returns full repo objects per hit, so there's no need to settle
    for a stripped-down subset."""
    result = _request("GET", "/search/repositories",
                       params={"q": query, "sort": sort, "order": "desc", "per_page": min(max_results, 100)})
    if not result["ok"]:
        return result
    d = result["data"] or {}
    items = [_map_repo_fields(r) for r in d.get("items", [])[:max_results]]
    return {"query": query, "total_count": d.get("total_count", 0), "results": items}


def github_discussions(owner_repo_or_url: str, max_results: int = 20) -> Dict[str, Any]:
    """GitHub Discussions via the GraphQL API. **Requires GITHUB_TOKEN** —
    unlike REST, GraphQL has no unauthenticated access at all, even for
    public repos (this is a GitHub platform requirement, not a choice made
    by this module)."""
    ref = parse_repo_ref(owner_repo_or_url)
    if not ref:
        return {"error": "invalid_ref", "error_message": "Provide 'owner/repo' or a github.com URL."}
    if not os.environ.get("GITHUB_TOKEN"):
        return {
            "error": "auth_required",
            "error_message": (
                "GitHub Discussions requires the GraphQL API, which needs a token even for "
                "public repos. Set GITHUB_TOKEN (a classic PAT with the 'public_repo' scope, "
                "or a fine-grained token with read-only 'Discussions' repo permission)."
            ),
        }

    query = """
    query($owner: String!, $repo: String!, $first: Int!) {
      repository(owner: $owner, name: $repo) {
        discussions(first: $first, orderBy: {field: UPDATED_AT, direction: DESC}) {
          totalCount
          nodes {
            number
            title
            url
            createdAt
            updatedAt
            author { login }
            category { name }
            comments { totalCount }
            bodyText
          }
        }
      }
    }
    """
    variables = {"owner": ref["owner"], "repo": ref["repo"], "first": min(max_results, 100)}
    try:
        resp = requests.post(
            GRAPHQL_URL, headers=_headers(),
            json={"query": query, "variables": variables}, timeout=20,
        )
    except Exception as e:
        return {"error": "network_error", "error_message": f"{type(e).__name__}: {e}"}

    if resp.status_code == 401:
        return {"error": "unauthorized", "error_message": "GITHUB_TOKEN is invalid, expired, or lacks discussion read access."}
    if resp.status_code >= 400:
        return {"error": "api_error", "error_message": f"HTTP {resp.status_code}: {resp.text[:300]}"}

    payload = resp.json()
    if payload.get("errors"):
        return {"error": "graphql_error", "error_message": "; ".join(e.get("message", "") for e in payload["errors"])}

    repo_data = (payload.get("data") or {}).get("repository")
    if not repo_data:
        return {"error": "not_found", "error_message": f"Repository {ref['owner']}/{ref['repo']} not found or discussions disabled."}

    discussions_data = repo_data.get("discussions", {})
    nodes = discussions_data.get("nodes", [])
    discussions = [{
        "number": n.get("number"),
        "title": n.get("title"),
        "url": n.get("url"),
        "author": (n.get("author") or {}).get("login"),
        "category": (n.get("category") or {}).get("name"),
        "comment_count": (n.get("comments") or {}).get("totalCount", 0),
        "created_at": n.get("createdAt"),
        "updated_at": n.get("updatedAt"),
        "body": n.get("bodyText"),
    } for n in nodes]

    return {
        "repo": f"{ref['owner']}/{ref['repo']}",
        "total_count": discussions_data.get("totalCount", 0),
        "discussions": discussions,
    }
