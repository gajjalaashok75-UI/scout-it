"""
Tests for the multi-source additions: scout_it.github_extract,
scout_it.engines, and scout_it.social. All HTTP calls are mocked —
no real network access needed.
"""
import base64
import json
import os
from pathlib import Path
from unittest import mock

import pytest

from scout_it import github_extract as gh
from scout_it import engines as eng
from scout_it import social


class _FakeResp:
    def __init__(self, status_code=200, json_data=None, headers=None, text=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text if text is not None else (json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json


class TestGithubParseRef:
    def test_owner_slash_repo(self):
        assert gh.parse_repo_ref("psf/requests") == {"owner": "psf", "repo": "requests"}

    def test_full_url(self):
        assert gh.parse_repo_ref("https://github.com/psf/requests") == {"owner": "psf", "repo": "requests"}

    def test_url_with_git_suffix(self):
        assert gh.parse_repo_ref("https://github.com/psf/requests.git") == {"owner": "psf", "repo": "requests"}

    def test_empty_returns_none(self):
        assert gh.parse_repo_ref("") is None

    def test_garbage_returns_none(self):
        assert gh.parse_repo_ref("not-a-valid-ref-at-all") is None


class TestGithubRepo:
    @mock.patch("scout_it.extraction.fetch_resilient")
    @mock.patch("scout_it.github_extract.requests.request")
    def test_error_dicts_never_leak_internal_ok_key(self, mock_request, mock_fetch):
        """Regression guard: every public github_* function's error contract
        is {"error": ..., "error_message": ...} -- several of them used to
        return _request()'s internal dict verbatim on failure, leaking the
        {"ok": False, ...} bookkeeping shape to callers."""
        mock_request.return_value = _FakeResp(403, {}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "999"})
        mock_fetch.return_value = {"html": "", "final_url": "u", "status": "failed", "tier": "none", "attempts": 1, "errors": ["e"]}

        for result in [
            gh.github_repo("x/y"),
            gh.github_commits("x/y"),
            gh.github_commit("x/y", "sha123"),
            gh.github_pull_request("x/y", 1),
            gh.github_issues("x/y"),
            gh.github_issue("x/y", 1),
            gh.github_file_content("x/y", "a.py"),
            gh.github_search_code("query"),
            gh.github_search_repos("query"),
            gh.github_folder("x/y", path="src/"),
            gh.github_prs("x/y"),
        ]:
            assert "ok" not in result, f"leaked internal 'ok' key: {result}"
            assert result.get("error") == "rate_limited"

    @mock.patch("scout_it.github_extract.requests.request")
    def test_happy_path_quick_mode(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "full_name": "psf/requests", "description": "HTTP for humans",
            "html_url": "https://github.com/psf/requests", "stargazers_count": 50000,
            "forks_count": 9000, "subscribers_count": 100, "open_issues_count": 5,
            "default_branch": "main", "language": "Python", "topics": ["http"],
            "license": {"spdx_id": "Apache-2.0"}, "fork": False, "archived": False,
            "created_at": "x", "updated_at": "x", "pushed_at": "x", "size": 1000,
            "owner": {"login": "psf", "type": "Organization"},
        })
        out = gh.github_repo("psf/requests", full=False)
        assert out["full_name"] == "psf/requests"
        assert out["stars"] == 50000
        assert out["language"] == "Python"
        assert "branches" not in out  # quick mode skips the rich aggregation

    @mock.patch("scout_it.github_extract.requests.request")
    def test_full_mode_aggregates_multiple_endpoints(self, mock_request):
        base = {
            "full_name": "psf/requests", "description": "d", "html_url": "u", "stargazers_count": 1,
            "forks_count": 1, "subscribers_count": 1, "open_issues_count": 1, "default_branch": "main",
            "language": "Python", "topics": [], "license": None, "fork": False, "archived": False,
            "created_at": "x", "updated_at": "x", "pushed_at": "x", "size": 1,
            "owner": {"login": "psf", "type": "Organization"},
        }

        def side_effect(method, url, headers=None, params=None, timeout=None):
            if url.endswith("/repos/psf/requests"):
                return _FakeResp(200, base)
            if url.endswith("/languages"):
                return _FakeResp(200, {"Python": 12345})
            if url.endswith("/branches"):
                return _FakeResp(200, [{"name": "main"}, {"name": "dev"}])
            if url.endswith("/commits"):
                return _FakeResp(200, [{"sha": "abc"}])
            if url.endswith("/search/issues"):
                return _FakeResp(200, {"total_count": 3})
            if url.endswith("/contributors"):
                return _FakeResp(200, [{"login": "alice", "contributions": 100, "html_url": "u"}])
            if url.endswith("/releases"):
                return _FakeResp(200, [{"tag_name": "v1.0", "name": "v1.0", "published_at": "x", "html_url": "u"}])
            if "/git/trees/" in url:
                return _FakeResp(200, {"tree": [{"path": "a.py", "type": "blob", "size": 10}], "truncated": False})
            return _FakeResp(404, {})

        mock_request.side_effect = side_effect
        out = gh.github_repo("psf/requests", full=True, include_file_tree=True)
        assert out["languages"] == {"Python": 12345}
        assert out["branches"] == ["main", "dev"]
        assert out["branch_count"] == 2
        assert out["open_issues_only"] == 3
        assert out["open_pull_requests"] == 3
        assert out["top_contributors"][0]["login"] == "alice"
        assert out["latest_release"]["tag_name"] == "v1.0"
        assert out["file_tree"][0]["path"] == "a.py"
        assert out["file_tree_truncated"] is False

    @mock.patch("scout_it.github_extract.requests.request")
    def test_file_tree_not_included_by_default(self, mock_request):
        base = {
            "full_name": "psf/requests", "description": "d", "html_url": "u", "stargazers_count": 1,
            "forks_count": 1, "subscribers_count": 1, "open_issues_count": 1, "default_branch": "main",
            "language": "Python", "topics": [], "license": None, "fork": False, "archived": False,
            "created_at": "x", "updated_at": "x", "pushed_at": "x", "size": 1,
            "owner": {"login": "psf", "type": "Organization"},
        }
        mock_request.return_value = _FakeResp(200, base)
        out = gh.github_repo("psf/requests", full=False)
        assert "file_tree" not in out

    def test_file_tree_rejects_both_max_chars_and_max_size(self):
        out = gh.github_repo("psf/requests", full=False, include_file_tree=True, max_chars=100, max_size="5mb")
        assert out["error"] == "invalid_arguments"

    @mock.patch("scout_it.extraction.fetch_resilient")
    @mock.patch("scout_it.github_extract.requests.request")
    def test_rate_limited_falls_back_to_html_scrape(self, mock_request, mock_fetch):
        """When the REST API is rate-limited, github_repo() should try the
        HTML-scrape fallback (a genuinely independent layer -- doesn't share
        the API's rate limit) before giving up."""
        mock_request.return_value = _FakeResp(403, {}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "999"})
        mock_fetch.return_value = {
            "html": '<html><head><meta property="og:description" content="A test repo"/></head>'
                    '<body><a aria-label="150 users starred this repository">Star</a>'
                    '<a aria-label="20 users forked this repository">Fork</a></body></html>',
            "final_url": "https://github.com/psf/requests", "status": "success", "tier": "requests",
            "attempts": 1, "errors": [],
        }
        out = gh.github_repo("psf/requests")
        assert out["source"] == "html_fallback"
        assert out["description"] == "A test repo"
        assert out["stars"] == 150
        assert out["forks"] == 20

    @mock.patch("scout_it.extraction.fetch_resilient")
    @mock.patch("scout_it.github_extract.requests.request")
    def test_rate_limited_reports_original_error_if_fallback_also_fails(self, mock_request, mock_fetch):
        mock_request.return_value = _FakeResp(403, {}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "999"})
        mock_fetch.return_value = {"html": "", "final_url": "u", "status": "failed", "tier": "none", "attempts": 5, "errors": ["e1"]}
        out = gh.github_repo("psf/requests")
        # Both layers failed -- the ORIGINAL rate-limit error is more useful
        # (has reset time + GITHUB_TOKEN guidance) than the fallback's generic failure.
        assert out["error"] == "rate_limited"
        assert "GITHUB_TOKEN" in out["error_message"]

    @mock.patch("scout_it.github_extract.requests.request")
    def test_not_found(self, mock_request):
        mock_request.return_value = _FakeResp(404, {})
        out = gh.github_repo("nonexistent/nonexistent")
        assert out["error"] == "not_found"

    def test_invalid_ref(self):
        out = gh.github_repo("")
        assert out["error"] == "invalid_ref"


class TestGithubCommit:
    @mock.patch("scout_it.github_extract.requests.request")
    def test_full_diff_extraction(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "sha": "abc1234567890", "html_url": "https://github.com/x/y/commit/abc",
            "commit": {"message": "fix bug", "author": {"name": "Alice", "email": "a@x.com", "date": "2026-01-01"}},
            "author": {"login": "alice"}, "committer": {"login": "alice"},
            "parents": [{"sha": "parent1", "html_url": "u"}],
            "stats": {"additions": 10, "deletions": 2, "total": 12},
            "files": [{"filename": "a.py", "status": "modified", "additions": 10, "deletions": 2,
                       "changes": 12, "blob_url": "u", "raw_url": "u", "patch": "@@ -1,2 +1,10 @@\n+new code"}],
        })
        out = gh.github_commit("x/y", "abc1234567890")
        assert out["files_changed"] == 1
        assert out["files"][0]["patch"].startswith("@@")
        assert out["stats"]["additions"] == 10
        assert out["is_merge"] is False

    def test_missing_sha(self):
        out = gh.github_commit("x/y", "")
        assert out["error"] == "invalid_sha"

    @mock.patch("scout_it.github_extract.requests.request")
    def test_no_patch_option(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "sha": "abc", "html_url": "u", "commit": {"message": "m", "author": {}},
            "author": {}, "committer": {}, "parents": [],
            "stats": {}, "files": [{"filename": "a.py", "status": "modified", "patch": "@@ diff @@"}],
        })
        out = gh.github_commit("x/y", "abc", include_patch=False)
        assert "patch" not in out["files"][0]


class TestGithubFileContent:
    @mock.patch("scout_it.github_extract.requests.request")
    def test_decodes_base64_text_file(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "encoding": "base64", "content": base64.b64encode(b"print('hi')").decode(),
            "path": "a.py", "sha": "s", "size": 11, "download_url": "u", "html_url": "u",
        })
        out = gh.github_file_content("x/y", "a.py")
        assert out["content"] == "print('hi')"
        assert out["is_binary_or_too_large"] is False

    @mock.patch("scout_it.github_extract.requests.request")
    def test_directory_returns_error(self, mock_request):
        mock_request.return_value = _FakeResp(200, [{"name": "a.py", "type": "file"}])
        out = gh.github_file_content("x/y", "src")
        assert out["error"] == "is_directory"


class TestGithubDiscussions:
    def test_requires_token(self):
        os.environ.pop("GITHUB_TOKEN", None)
        out = gh.github_discussions("x/y")
        assert out["error"] == "auth_required"


class TestMultiEngineSearch:
    def test_unconfigured_engines_are_skipped_not_errored(self):
        os.environ.pop("BRAVE_API_KEY", None)
        with mock.patch.object(eng.DuckDuckGoEngine, "search",
                                return_value=[{"title": "t", "url": "http://a.com", "snippet": "s", "source": "duckduckgo"}]):
            result = eng.multi_engine_search("q", engines=["duckduckgo", "brave", "nope"], max_results=5)
            assert len(result["merged_results"]) == 1
            assert result["stats"]["engines_run"] == ["duckduckgo"]
            skipped = {s["engine"] for s in result["stats"]["skipped"]}
            assert skipped == {"brave", "nope"}

    def test_dedupe_across_engines(self):
        os.environ["BRAVE_API_KEY"] = "fake"
        try:
            with mock.patch.object(eng.DuckDuckGoEngine, "search",
                                    return_value=[{"title": "t1", "url": "http://dup.com/", "snippet": "s", "source": "duckduckgo"}]), \
                 mock.patch.object(eng.BraveSearchEngine, "search",
                                    return_value=[{"title": "t2", "url": "http://dup.com", "snippet": "s2", "source": "brave"}]):
                result = eng.multi_engine_search("q", engines=["duckduckgo", "brave"], max_results=5)
                assert len(result["merged_results"]) == 1
        finally:
            os.environ.pop("BRAVE_API_KEY", None)

    def test_list_engines_reports_duckduckgo_as_zero_config(self):
        info = {e["name"]: e for e in eng.list_engines()}
        assert info["duckduckgo"]["tier"] == 0
        assert info["duckduckgo"]["configured"] is True
        assert info["brave"]["tier"] == 1


class TestTelegramChannel:
    def test_parses_public_preview(self):
        fake_html = """
        <div class="tgme_channel_info_header_title">Test Channel</div>
        <div class="tgme_channel_info_description">A test channel</div>
        <div class="tgme_widget_message_wrap">
          <div class="tgme_widget_message" data-post="testchan/123">
            <div class="tgme_widget_message_text">Hello world post</div>
            <time datetime="2026-01-01T00:00:00+00:00"></time>
            <span class="tgme_widget_message_views">1.2K</span>
          </div>
        </div>
        """
        with mock.patch("scout_it.extraction.fetch_resilient", return_value={
            "html": fake_html, "final_url": "u", "status": "success", "tier": "requests", "attempts": 1, "errors": [],
        }):
            out = social.telegram_channel("testchan")
            assert out["post_count_returned"] == 1
            assert out["posts"][0]["text"] == "Hello world post"
            assert out["title"] == "Test Channel"
            assert out["parser_used"] == "primary"

    def test_fetch_failure_reported(self):
        with mock.patch("scout_it.extraction.fetch_resilient", return_value={
            "html": "", "final_url": "u", "status": "failed", "tier": "none", "attempts": 7, "errors": ["e1"],
        }):
            out = social.telegram_channel("testchan")
            assert out["error"] == "fetch_failed"

    def test_empty_channel_name(self):
        out = social.telegram_channel("")
        assert out["error"] == "invalid_channel"

    def test_reports_none_found_when_channel_page_has_no_messages(self):
        # Both parsers rely on the same underlying t.me/s/ page structure to
        # even detect that a message exists -- if the page genuinely has no
        # messages, there's nothing for either parser to recover.
        fake_html = """
        <meta property="og:title" content="Empty Channel" />
        <div class="tgme_channel_info_header_title">Empty Channel</div>
        """
        with mock.patch("scout_it.extraction.fetch_resilient", return_value={
            "html": fake_html, "final_url": "u", "status": "success", "tier": "requests", "attempts": 1, "errors": [],
        }):
            out = social.telegram_channel("chan", max_fetch_retries=1)
            assert out["post_count_returned"] == 0
            assert out["parser_used"] == "none_found"

    def test_parse_telegram_enhanced_extracts_rich_fields(self):
        fake_html = """
        <meta property="og:title" content="Chan" />
        <div class="tgme_widget_message_wrap">
          <div class="tgme_widget_message" data-post="chan/5">
            <span class="tgme_widget_message_from_author">Alice</span>
            <span class="tgme_widget_message_meta">12:00, edited</span>
            <div class="tgme_widget_message_text">hello</div>
            <time datetime="2026-01-01T00:00:00+00:00"></time>
          </div>
        </div>
        """
        result = social._parse_telegram_enhanced(fake_html, max_results=10)
        assert result["posts"][0]["author"] == "Alice"
        assert result["posts"][0]["edited"] is True
        assert result["posts"][0]["text"] == "hello"
        assert result["title"] == "Chan"


class TestDiscordChannel:
    def test_requires_token(self):
        os.environ.pop("DISCORD_BOT_TOKEN", None)
        out = social.discord_channel_messages("123456789012345678")
        assert out["error"] == "auth_required"

    def test_invalid_channel_id(self):
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            out = social.discord_channel_messages("not-a-numeric-id")
            assert out["error"] == "invalid_channel_id"
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)

    def test_happy_path(self):
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            with mock.patch("scout_it.social.requests.get") as mock_get:
                mock_get.return_value = _FakeResp(200, [
                    {"id": "1", "author": {"username": "alice"}, "content": "hi", "timestamp": "t", "attachments": []}
                ])
                out = social.discord_channel_messages("123456789012345678")
                assert out["message_count"] == 1
                assert out["messages"][0]["content"] == "hi"
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)


class TestRedditSearch:
    def test_403_reports_honest_blocked_error_not_empty_results(self):
        with mock.patch("scout_it.social.requests.get") as mock_get:
            mock_get.return_value = _FakeResp(403)
            out = social.reddit_search("python")
            assert out["error"] == "blocked"
            assert "2026" in out["error_message"] or "REDDIT_COOKIE" in out["error_message"]

    def test_happy_path(self):
        with mock.patch("scout_it.social.requests.get") as mock_get:
            mock_get.return_value = _FakeResp(200, {
                "data": {"children": [{"data": {
                    "title": "Post title", "subreddit": "python", "author": "bob", "score": 42,
                    "num_comments": 3, "url": "http://x", "permalink": "/r/python/comments/abc",
                    "created_utc": 123, "selftext": "body text",
                }}]}
            })
            out = social.reddit_search("python")
            assert out["result_count"] == 1
            assert out["posts"][0]["title"] == "Post title"


class TestGithubPatchLines:
    def test_parses_added_removed_context_and_hunk(self):
        patch = "@@ -1,2 +1,3 @@\n-old line\n+new line one\n+new line two\n context line"
        lines = gh._parse_patch_lines(patch)
        types = [l["type"] for l in lines]
        assert types == ["hunk_header", "removed", "added", "added", "context"]
        assert lines[1]["text"] == "old line"
        assert lines[2]["text"] == "new line one"

    def test_tracks_old_and_new_line_numbers(self):
        # Hunk starts at old line 10, new line 10. One line removed, two added, one context.
        patch = "@@ -10,2 +10,3 @@\n-removed at old 10\n+added at new 10\n+added at new 11\n context at old11/new12"
        lines = gh._parse_patch_lines(patch)
        removed = lines[1]
        added1, added2 = lines[2], lines[3]
        context = lines[4]

        assert removed["type"] == "removed" and removed["old_line"] == 10 and removed["new_line"] is None
        assert added1["type"] == "added" and added1["new_line"] == 10 and added1["old_line"] is None
        assert added2["type"] == "added" and added2["new_line"] == 11
        # after 1 removed (old: 10->11) and context not yet counted, context should be old=11
        assert context["old_line"] == 11
        assert context["new_line"] == 12

    def test_hunk_header_has_no_line_numbers(self):
        lines = gh._parse_patch_lines("@@ -1,2 +1,3 @@\n context")
        assert lines[0]["old_line"] is None and lines[0]["new_line"] is None

    def test_empty_patch_returns_empty_list(self):
        assert gh._parse_patch_lines(None) == []
        assert gh._parse_patch_lines("") == []

    @mock.patch("scout_it.github_extract.requests.request")
    def test_commit_includes_patch_lines(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "sha": "abc", "html_url": "u", "commit": {"message": "m", "author": {}},
            "author": {}, "committer": {}, "parents": [], "stats": {},
            "files": [{"filename": "a.py", "status": "modified",
                       "patch": "@@ -1 +1 @@\n-a\n+b"}],
        })
        out = gh.github_commit("x/y", "abc")
        assert out["files"][0]["patch_lines"][1]["type"] == "removed"
        assert out["files"][0]["patch_lines"][2]["type"] == "added"
        assert out["files"][0]["patch_lines"][1]["old_line"] == 1
        assert out["files"][0]["patch_lines"][2]["new_line"] == 1


class TestGithubPrs:
    @mock.patch("scout_it.github_extract.requests.request")
    def test_lists_prs_with_pr_specific_fields(self, mock_request):
        mock_request.return_value = _FakeResp(200, [{
            "number": 5, "title": "Add feature", "state": "open", "draft": False,
            "user": {"login": "alice"}, "base": {"ref": "main"}, "head": {"ref": "feature"},
            "labels": [], "created_at": "x", "updated_at": "x", "closed_at": None,
            "merged_at": None, "html_url": "u",
        }])
        out = gh.github_prs("x/y")
        assert out["pr_count"] == 1
        assert out["pull_requests"][0]["base_branch"] == "main"
        assert out["pull_requests"][0]["head_branch"] == "feature"
        assert out["pull_requests"][0]["is_draft"] is False


class TestGithubFolder:
    @mock.patch("scout_it.github_extract.requests.request")
    def test_recursive_listing_filters_by_prefix(self, mock_request):
        def side_effect(method, url, headers=None, params=None, timeout=None):
            if url.endswith("/repos/x/y"):
                return _FakeResp(200, {"default_branch": "main"})
            if "/git/trees/" in url:
                return _FakeResp(200, {"tree": [
                    {"path": "src/a.py", "type": "blob", "size": 10},
                    {"path": "src/sub/b.py", "type": "blob", "size": 20},
                    {"path": "README.md", "type": "blob", "size": 5},
                ]})
            return _FakeResp(404, {})
        mock_request.side_effect = side_effect
        out = gh.github_folder("x/y", path="src/")
        paths = [e["path"] for e in out["entries"]]
        assert "src/a.py" in paths
        assert "src/sub/b.py" in paths
        assert "README.md" not in paths

    @mock.patch("scout_it.github_extract.requests.request")
    def test_non_recursive_single_level(self, mock_request):
        mock_request.return_value = _FakeResp(200, [
            {"path": "src/a.py", "type": "file", "size": 10},
            {"path": "src/sub", "type": "dir", "size": 0},
        ])
        out = gh.github_folder("x/y", path="src", recursive=False)
        assert out["entry_count"] == 2

    def test_max_files_without_include_content_is_an_error(self):
        out = gh.github_folder("x/y", path="src/", include_content=False, max_files=5)
        assert out["error"] == "invalid_arguments"

    def test_save_path_dir_without_include_content_is_an_error(self):
        out = gh.github_folder("x/y", path="src/", include_content=False, save_path_dir="/tmp/x")
        assert out["error"] == "invalid_arguments"

    def test_max_chars_and_max_size_together_is_an_error(self):
        out = gh.github_folder("x/y", path="src/", include_content=True, max_chars=100, max_size="1kb")
        assert out["error"] == "invalid_arguments"

    @mock.patch("scout_it.github_extract.requests.request")
    def test_include_content_without_max_files_fetches_all(self, mock_request):
        def side_effect(method, url, headers=None, params=None, timeout=None):
            if url.endswith("/repos/x/y"):
                return _FakeResp(200, {"default_branch": "main"})
            if "/git/trees/" in url:
                return _FakeResp(200, {"tree": [
                    {"path": "src/a.py", "type": "blob", "size": 10},
                    {"path": "src/b.py", "type": "blob", "size": 10},
                    {"path": "src/c.py", "type": "blob", "size": 10},
                ]})
            if "/contents/" in url:
                return _FakeResp(200, {"encoding": "base64", "content": base64.b64encode(b"x").decode(),
                                        "path": "src/a.py", "sha": "s", "size": 1, "download_url": "u", "html_url": "u"})
            return _FakeResp(404, {})
        mock_request.side_effect = side_effect
        out = gh.github_folder("x/y", path="src/", include_content=True)  # no max_files given
        assert out["files_fetched"] == 3  # all files, no default cap
        assert out["files_truncated"] is False

    @mock.patch("scout_it.github_extract.requests.request")
    def test_max_chars_truncates_content(self, mock_request):
        def side_effect(method, url, headers=None, params=None, timeout=None):
            if url.endswith("/repos/x/y"):
                return _FakeResp(200, {"default_branch": "main"})
            if "/git/trees/" in url:
                return _FakeResp(200, {"tree": [{"path": "src/a.py", "type": "blob", "size": 100}]})
            if "/contents/" in url:
                long_content = "x" * 1000
                return _FakeResp(200, {"encoding": "base64", "content": base64.b64encode(long_content.encode()).decode(),
                                        "path": "src/a.py", "sha": "s", "size": 1000, "download_url": "u", "html_url": "u"})
            return _FakeResp(404, {})
        mock_request.side_effect = side_effect
        out = gh.github_folder("x/y", path="src/", include_content=True, max_chars=50)
        assert len(out["files"][0]["content"]) == 50
        assert out["files"][0]["content_truncated"] is True

    @mock.patch("scout_it.github_extract.requests.request")
    def test_detected_file_type(self, mock_request):
        def side_effect(method, url, headers=None, params=None, timeout=None):
            if url.endswith("/repos/x/y"):
                return _FakeResp(200, {"default_branch": "main"})
            if "/git/trees/" in url:
                return _FakeResp(200, {"tree": [{"path": "src/a.py", "type": "blob", "size": 10}]})
            if "/contents/" in url:
                return _FakeResp(200, {"encoding": "base64", "content": base64.b64encode(b"x").decode(),
                                        "path": "src/a.py", "sha": "s", "size": 1, "download_url": "u", "html_url": "u"})
            return _FakeResp(404, {})
        mock_request.side_effect = side_effect
        out = gh.github_folder("x/y", path="src/", include_content=True)
        assert out["files"][0]["detected_type"] == "python"

    def test_detect_file_type_helper(self):
        assert gh._detect_file_type("a.py") == "python"
        assert gh._detect_file_type("README.md") == "markdown"
        assert gh._detect_file_type("config.yaml") == "yaml"
        assert gh._detect_file_type("data.json") == "json"
        assert gh._detect_file_type("Dockerfile") == "dockerfile"
        assert gh._detect_file_type("noextension") == "unknown"

    @mock.patch("scout_it.github_extract.requests.request")
    def test_save_path_dir_writes_files_preserving_tree(self, mock_request):
        import tempfile, shutil
        tmpdir = tempfile.mkdtemp()
        try:
            def side_effect(method, url, headers=None, params=None, timeout=None):
                if url.endswith("/repos/x/y"):
                    return _FakeResp(200, {"default_branch": "main"})
                if "/git/trees/" in url:
                    return _FakeResp(200, {"tree": [{"path": "src/a.py", "type": "blob", "size": 5}]})
                if "/contents/" in url:
                    return _FakeResp(200, {"encoding": "base64", "content": base64.b64encode(b"hello").decode(),
                                            "path": "src/a.py", "sha": "s", "size": 5, "download_url": "u", "html_url": "u"})
                return _FakeResp(404, {})
            mock_request.side_effect = side_effect
            out = gh.github_folder("x/y", path="src/", include_content=True, save_path_dir=tmpdir)
            assert out["files_saved_to_disk"] == 1
            saved_file = Path(tmpdir) / "src" / "a.py"
            assert saved_file.exists()
            assert saved_file.read_text() == "hello"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestTelegramSearch:
    def test_finds_channels_from_site_search(self):
        fake_ddg_results = [
            {"href": "https://t.me/s/pythondev/123", "title": "t"},
            {"href": "https://t.me/pythondev", "title": "t2"},  # duplicate channel, should dedupe
            {"href": "https://t.me/s/anotherchan", "title": "t3"},
        ]
        with mock.patch("scout_it.extraction._ddgs_list_search_with_retry", return_value=(fake_ddg_results, {})), \
             mock.patch.object(social, "telegram_channel", return_value={"channel": "pythondev", "title": "Python Dev", "post_count_returned": 1, "posts": []}):
            out = social.telegram_search("python")
            assert out["channel_count"] == 2  # deduped to 2 unique channels

    def test_empty_query(self):
        out = social.telegram_search("")
        assert out["error"] == "invalid_query"

    def test_no_matches_returns_helpful_note(self):
        with mock.patch("scout_it.extraction._ddgs_list_search_with_retry", return_value=([], {})):
            out = social.telegram_search("extremely obscure query with no results")
            assert out["channel_count"] == 0
            assert "note" in out


class TestConfig:
    def test_credential_status_reports_env_var_source(self):
        from scout_it import config as ds_config
        os.environ["GITHUB_TOKEN"] = "faketoken123"
        try:
            with mock.patch.object(ds_config, "load_credentials_file", return_value={}):
                status = {c["key"]: c for c in ds_config.credential_status()}
                assert status["GITHUB_TOKEN"]["configured"] is True
                assert status["GITHUB_TOKEN"]["source"] == "environment variable"
        finally:
            del os.environ["GITHUB_TOKEN"]

    def test_credential_status_unconfigured(self):
        from scout_it import config as ds_config
        os.environ.pop("SERPAPI_KEY", None)
        with mock.patch.object(ds_config, "load_credentials_file", return_value={}):
            status = {c["key"]: c for c in ds_config.credential_status()}
            assert status["SERPAPI_KEY"]["configured"] is False

    def test_save_and_load_roundtrip(self):
        from scout_it import config as ds_config
        import tempfile
        tmpdir = tempfile.mkdtemp()
        fake_file = Path(tmpdir) / "credentials.json"
        with mock.patch.object(ds_config, "CREDENTIALS_FILE", fake_file), \
             mock.patch.object(ds_config, "CONFIG_DIR", Path(tmpdir)):
            ds_config.save_credentials_file({"GITHUB_TOKEN": "abc123"})
            loaded = ds_config.load_credentials_file()
            assert loaded == {"GITHUB_TOKEN": "abc123"}

    def test_env_var_takes_precedence_over_stored_file(self):
        from scout_it import config as ds_config
        os.environ["BRAVE_API_KEY"] = "from_env"
        try:
            with mock.patch.object(ds_config, "load_credentials_file", return_value={"BRAVE_API_KEY": "from_file"}):
                ds_config.load_stored_credentials_into_env()
                assert os.environ["BRAVE_API_KEY"] == "from_env"
        finally:
            os.environ.pop("BRAVE_API_KEY", None)

    def test_stored_file_loads_when_no_env_var(self):
        from scout_it import config as ds_config
        os.environ.pop("GOOGLE_CSE_ID", None)
        with mock.patch.object(ds_config, "load_credentials_file", return_value={"GOOGLE_CSE_ID": "from_file"}):
            ds_config.load_stored_credentials_into_env()
            assert os.environ.get("GOOGLE_CSE_ID") == "from_file"
        os.environ.pop("GOOGLE_CSE_ID", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
