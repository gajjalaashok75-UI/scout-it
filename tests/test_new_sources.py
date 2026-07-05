"""
Tests for the multi-source additions: data_scout.github_extract,
data_scout.engines, and data_scout.social. All HTTP calls are mocked —
no real network access needed.
"""
import base64
import json
import os
from unittest import mock

import pytest

from data_scout import github_extract as gh
from data_scout import engines as eng
from data_scout import social


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
    @mock.patch("data_scout.github_extract.requests.request")
    def test_happy_path(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "full_name": "psf/requests", "description": "HTTP for humans",
            "html_url": "https://github.com/psf/requests", "stargazers_count": 50000,
            "forks_count": 9000, "subscribers_count": 100, "open_issues_count": 5,
            "default_branch": "main", "language": "Python", "topics": ["http"],
            "license": {"spdx_id": "Apache-2.0"}, "fork": False, "archived": False,
            "created_at": "x", "updated_at": "x", "pushed_at": "x", "size": 1000,
            "owner": {"login": "psf", "type": "Organization"},
        })
        out = gh.github_repo("psf/requests")
        assert out["full_name"] == "psf/requests"
        assert out["stars"] == 50000
        assert out["language"] == "Python"

    @mock.patch("data_scout.github_extract.requests.request")
    def test_rate_limited(self, mock_request):
        mock_request.return_value = _FakeResp(403, {}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "999"})
        out = gh.github_repo("psf/requests")
        assert out["error"] == "rate_limited"
        assert "GITHUB_TOKEN" in out["error_message"]

    @mock.patch("data_scout.github_extract.requests.request")
    def test_not_found(self, mock_request):
        mock_request.return_value = _FakeResp(404, {})
        out = gh.github_repo("nonexistent/nonexistent")
        assert out["error"] == "not_found"

    def test_invalid_ref(self):
        out = gh.github_repo("")
        assert out["error"] == "invalid_ref"


class TestGithubCommit:
    @mock.patch("data_scout.github_extract.requests.request")
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

    @mock.patch("data_scout.github_extract.requests.request")
    def test_no_patch_option(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "sha": "abc", "html_url": "u", "commit": {"message": "m", "author": {}},
            "author": {}, "committer": {}, "parents": [],
            "stats": {}, "files": [{"filename": "a.py", "status": "modified", "patch": "@@ diff @@"}],
        })
        out = gh.github_commit("x/y", "abc", include_patch=False)
        assert "patch" not in out["files"][0]


class TestGithubFileContent:
    @mock.patch("data_scout.github_extract.requests.request")
    def test_decodes_base64_text_file(self, mock_request):
        mock_request.return_value = _FakeResp(200, {
            "encoding": "base64", "content": base64.b64encode(b"print('hi')").decode(),
            "path": "a.py", "sha": "s", "size": 11, "download_url": "u", "html_url": "u",
        })
        out = gh.github_file_content("x/y", "a.py")
        assert out["content"] == "print('hi')"
        assert out["is_binary_or_too_large"] is False

    @mock.patch("data_scout.github_extract.requests.request")
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
        with mock.patch("data_scout.extraction.fetch_resilient", return_value={
            "html": fake_html, "final_url": "u", "status": "success", "tier": "requests", "attempts": 1, "errors": [],
        }):
            out = social.telegram_channel("testchan")
            assert out["post_count_returned"] == 1
            assert out["posts"][0]["text"] == "Hello world post"
            assert out["title"] == "Test Channel"

    def test_fetch_failure_reported(self):
        with mock.patch("data_scout.extraction.fetch_resilient", return_value={
            "html": "", "final_url": "u", "status": "failed", "tier": "none", "attempts": 7, "errors": ["e1"],
        }):
            out = social.telegram_channel("testchan")
            assert out["error"] == "fetch_failed"

    def test_empty_channel_name(self):
        out = social.telegram_channel("")
        assert out["error"] == "invalid_channel"


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
            with mock.patch("data_scout.social.requests.get") as mock_get:
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
        with mock.patch("data_scout.social.requests.get") as mock_get:
            mock_get.return_value = _FakeResp(403)
            out = social.reddit_search("python")
            assert out["error"] == "blocked"
            assert "2026" in out["error_message"] or "REDDIT_COOKIE" in out["error_message"]

    def test_happy_path(self):
        with mock.patch("data_scout.social.requests.get") as mock_get:
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
