"""Tests for Phase 4 multi-content + real-time source plugins.

Covers GitLab, Bitbucket, and integration tests for the pre-existing
Phase 4 sources (Internet Archive, GDELT, ListenNotes, OpenStreetMap).
"""

import json
from unittest import mock

import pytest

# ─── GitLab ────────────────────────────────────────────────────────────────


class TestGitLabPlugin:
    """Tests for the GitLab source plugin."""

    SAMPLE_RESPONSE = [
        {
            "id": 278964,
            "name": "gitlab",
            "path_with_namespace": "gitlab-org/gitlab",
            "web_url": "https://gitlab.com/gitlab-org/gitlab",
            "description": "GitLab is an open source end-to-end software development platform.",
            "star_count": 2500,
            "forks_count": 600,
            "open_issues_count": 10000,
            "default_branch": "master",
            "visibility": "public",
            "last_activity_at": "2026-08-10T12:00:00Z",
            "namespace": {"full_path": "gitlab-org"},
        },
        {
            "id": 12345,
            "name": "small-project",
            "path_with_namespace": "user/small-project",
            "web_url": "https://gitlab.com/user/small-project",
            "description": "",
            "star_count": 5,
            "forks_count": 1,
            "open_issues_count": 2,
            "default_branch": "main",
            "visibility": "public",
            "last_activity_at": "2026-07-01T10:00:00Z",
            "namespace": {"full_path": "user"},
        },
    ]

    def test_plugin_registered(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("gitlab")
        assert plugin is not None
        assert plugin.name == "gitlab"
        assert plugin.content_type == "code"

    def test_plugin_available_without_key(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("gitlab")
        assert plugin.is_available() is True

    def test_search_parses_results(self):
        from scout_it.sources.plugins.gitlab import GitLabPlugin
        plugin = GitLabPlugin()
        with mock.patch("scout_it.sources.plugins.gitlab.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("gitlab", max_results=10)
        assert len(results) == 2
        r = results[0]
        assert r["source"] == "gitlab"
        assert r["content_type"] == "code"
        assert r["url"] == "https://gitlab.com/gitlab-org/gitlab"
        assert r["title"] == "gitlab"
        assert "GitLab" in r["snippet"]
        assert r["authority_score"] > 0
        assert r["metadata"]["stars"] == 2500

    def test_search_empty_response(self):
        from scout_it.sources.plugins.gitlab import GitLabPlugin
        plugin = GitLabPlugin()
        with mock.patch("scout_it.sources.plugins.gitlab.sync_fetch_json",
                        return_value=None):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []

    def test_search_fetch_error_returns_empty(self):
        from scout_it.sources.plugins.gitlab import GitLabPlugin
        plugin = GitLabPlugin()
        with mock.patch("scout_it.sources.plugins.gitlab.sync_fetch_json",
                        return_value=None):
            results = plugin.search("test", max_results=5)
        assert results == []

    def test_authority_from_stars(self):
        from scout_it.sources.plugins.gitlab import GitLabPlugin
        plugin = GitLabPlugin()
        with mock.patch("scout_it.sources.plugins.gitlab.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("test", max_results=10)
        # 2500 stars → 2500/500 = 1.0, clamped
        assert results[0]["authority_score"] == 1.0
        # 5 stars → 5/500 = 0.01
        assert results[1]["authority_score"] < 0.1

    def test_description_fallback_snippet(self):
        from scout_it.sources.plugins.gitlab import GitLabPlugin
        plugin = GitLabPlugin()
        with mock.patch("scout_it.sources.plugins.gitlab.sync_fetch_json",
                        return_value=[self.SAMPLE_RESPONSE[1]]):
            results = plugin.search("test", max_results=5)
        # Empty description → fallback snippet with full_path and stats
        assert "small-project" in results[0]["snippet"]

    def test_result_has_timestamp(self):
        from scout_it.sources.plugins.gitlab import GitLabPlugin
        plugin = GitLabPlugin()
        with mock.patch("scout_it.sources.plugins.gitlab.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("test", max_results=5)
        assert results[0]["timestamp"] == "2026-08-10T12:00:00Z"


# ─── Bitbucket ─────────────────────────────────────────────────────────────


class TestBitbucketPlugin:
    """Tests for the Bitbucket source plugin."""

    SAMPLE_REPO = {
        "uuid": "{repo-uuid-1}",
        "name": "atlassian-python-api",
        "full_name": "atlassian/atlassian-python-api",
        "description": "Atlassian Python API wrapper for Jira, Confluence, Bitbucket.",
        "links": {"html": {"href": "https://bitbucket.org/atlassian/atlassian-python-api"}},
        "language": "Python",
        "created_on": "2020-01-15T08:00:00Z",
        "updated_on": "2026-08-01T12:00:00Z",
        "owner": {"display_name": "Atlassian"},
        "scm": "git",
    }

    SAMPLE_REPO_2 = {
        "uuid": "{repo-uuid-2}",
        "name": "test-repo",
        "full_name": "user/test-repo",
        "description": "",
        "links": {"html": {"href": "https://bitbucket.org/user/test-repo"}},
        "language": "",
        "created_on": "2025-06-01T00:00:00Z",
        "updated_on": "2026-07-15T10:00:00Z",
        "owner": {"display_name": "Test User"},
        "scm": "git",
    }

    def _make_fetch_response(self, repos):
        """Simulate sync_fetch_json: returns values for first workspace, None for rest."""
        responses = [{"values": repos}] + [None] * 10
        return responses

    def test_plugin_registered(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("bitbucket")
        assert plugin is not None
        assert plugin.name == "bitbucket"
        assert plugin.content_type == "code"

    def test_plugin_available_without_key(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("bitbucket")
        assert plugin.is_available() is True

    def test_search_parses_results(self):
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        responses = self._make_fetch_response([self.SAMPLE_REPO])
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        side_effect=responses):
            results = plugin.search("atlassian", max_results=10)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "bitbucket"
        assert r["content_type"] == "code"
        assert r["url"] == "https://bitbucket.org/atlassian/atlassian-python-api"
        assert r["title"] == "atlassian-python-api"
        assert "Atlassian Python API" in r["snippet"]
        assert r["metadata"]["language"] == "Python"
        assert r["metadata"]["owner"] == "Atlassian"

    def test_search_empty_response(self):
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        return_value=None):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []

    def test_search_no_values(self):
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        return_value={"values": []}):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []

    def test_authority_higher_with_description_and_language(self):
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        responses = self._make_fetch_response([self.SAMPLE_REPO, self.SAMPLE_REPO_2])
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        side_effect=responses):
            results = plugin.search("test", max_results=10)
        # Repo with description + language should have higher authority
        assert results[0]["authority_score"] > results[1]["authority_score"]

    def test_description_fallback_snippet(self):
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        responses = self._make_fetch_response([self.SAMPLE_REPO_2])
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        side_effect=responses):
            results = plugin.search("test", max_results=5)
        # Empty description → fallback snippet with full_name
        assert "test-repo" in results[0]["snippet"]

    def test_result_has_timestamp(self):
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        responses = self._make_fetch_response([self.SAMPLE_REPO])
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        side_effect=responses):
            results = plugin.search("test", max_results=5)
        assert results[0]["timestamp"] == "2026-08-01T12:00:00Z"

    def test_searches_multiple_workspaces(self):
        """Should fetch from multiple workspaces and merge results."""
        from scout_it.sources.plugins.bitbucket import BitbucketPlugin
        plugin = BitbucketPlugin()
        # First workspace returns one repo, second returns another
        responses = [
            {"values": [self.SAMPLE_REPO]},
            {"values": [self.SAMPLE_REPO_2]},
            None, None, None,
        ]
        with mock.patch("scout_it.sources.plugins.bitbucket.sync_fetch_json",
                        side_effect=responses) as mock_fetch:
            results = plugin.search("test", max_results=10)
        assert len(results) == 2
        # Should have called multiple workspaces
        assert mock_fetch.call_count >= 2


# ─── Internet Archive ──────────────────────────────────────────────────────


class TestInternetArchivePlugin:
    """Tests for the Internet Archive source plugin."""

    SAMPLE_RESPONSE = {
        "response": {
            "docs": [
                {
                    "identifier": "ways-of-seeing-berger",
                    "title": "Ways of Seeing",
                    "description": "<p>John Berger's seminal work on art criticism.</p>",
                    "mediatype": "texts",
                    "date": "1972-01-01",
                    "downloads": 12000,
                    "creator": "Berger, John",
                    "language": "eng",
                },
                {
                    "identifier": "old-radio-broadcast",
                    "title": ["Old Time Radio Broadcast"],
                    "description": ["Vintage radio episode"],
                    "mediatype": "audio",
                    "date": "1950-05-15",
                    "downloads": 300,
                    "creator": "Unknown",
                    "language": "eng",
                },
            ]
        }
    }

    def test_plugin_registered(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("internet_archive")
        assert plugin is not None
        assert plugin.name == "internet_archive"
        assert plugin.content_type == "media"

    def test_plugin_available(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("internet_archive")
        assert plugin.is_available() is True

    def test_search_parses_results(self):
        from scout_it.sources.plugins.internet_archive import InternetArchivePlugin
        plugin = InternetArchivePlugin()

        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = self.SAMPLE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        with mock.patch("scout_it.sources.plugins.internet_archive.requests.get",
                        return_value=mock_resp):
            results = plugin.search("ways of seeing", max_results=10)

        assert len(results) == 2
        r = results[0]
        assert r["source"] == "internet_archive"
        assert r["content_type"] == "media"
        assert r["url"] == "https://archive.org/details/ways-of-seeing-berger"
        assert r["title"] == "Ways of Seeing"
        # HTML tags stripped from description
        assert "<p>" not in r["snippet"]
        assert "Berger" in r["snippet"]
        assert r["authority_score"] > 0  # 12000 downloads
        assert r["metadata"]["mediatype"] == "texts"

    def test_search_handles_list_fields(self):
        """IA sometimes returns title/description as lists."""
        from scout_it.sources.plugins.internet_archive import InternetArchivePlugin
        plugin = InternetArchivePlugin()

        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = self.SAMPLE_RESPONSE
        mock_resp.raise_for_status.return_value = None
        with mock.patch("scout_it.sources.plugins.internet_archive.requests.get",
                        return_value=mock_resp):
            results = plugin.search("test", max_results=10)
        # Second result has list title/description
        assert results[1]["title"] == "Old Time Radio Broadcast"
        assert "Vintage radio" in results[1]["snippet"]

    def test_search_empty_response(self):
        from scout_it.sources.plugins.internet_archive import InternetArchivePlugin
        plugin = InternetArchivePlugin()

        mock_resp = mock.MagicMock()
        mock_resp.json.return_value = {"response": {"docs": []}}
        mock_resp.raise_for_status.return_value = None
        with mock.patch("scout_it.sources.plugins.internet_archive.requests.get",
                        return_value=mock_resp):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []

    def test_search_fetch_error_returns_empty(self):
        from scout_it.sources.plugins.internet_archive import InternetArchivePlugin
        plugin = InternetArchivePlugin()

        with mock.patch("scout_it.sources.plugins.internet_archive.requests.get",
                        side_effect=Exception("Network error")):
            results = plugin.search("test", max_results=5)
        assert results == []


# ─── GDELT ─────────────────────────────────────────────────────────────────


class TestGdeltPlugin:
    """Tests for the GDELT source plugin."""

    SAMPLE_RESPONSE = {
        "articles": [
            {
                "url": "https://example.com/news/article1",
                "title": "Breaking Event in Region X",
                "domain": "example.com",
                "language": "eng",
                "seendate": "20260811T120000Z",
                "socialimage": "https://example.com/image.jpg",
                "tone": "5.2,3.1,2.1,0",
                "sourcecountry": "United States",
            },
            {
                "url": "https://news.org/article2",
                "title": "Another Event Coverage",
                "domain": "news.org",
                "language": "eng",
                "seendate": "20260810T090000Z",
                "socialimage": "",
                "tone": -2.0,
                "sourcecountry": "United Kingdom",
            },
        ]
    }

    def test_plugin_registered(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("gdelt")
        assert plugin is not None
        assert plugin.name == "gdelt"
        assert plugin.content_type == "event"

    def test_plugin_available(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("gdelt")
        assert plugin.is_available() is True

    def test_search_parses_results(self):
        from scout_it.sources.plugins.gdelt import GdeltPlugin
        plugin = GdeltPlugin()
        with mock.patch("scout_it.sources.plugins.gdelt.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("breaking event", max_results=10)
        assert len(results) == 2
        r = results[0]
        assert r["source"] == "gdelt"
        assert r["content_type"] == "event"
        assert r["url"] == "https://example.com/news/article1"
        assert r["title"] == "Breaking Event in Region X"
        assert r["metadata"]["domain"] == "example.com"
        assert r["metadata"]["source_country"] == "United States"

    def test_tone_parsing_string(self):
        from scout_it.sources.plugins.gdelt import GdeltPlugin
        plugin = GdeltPlugin()
        with mock.patch("scout_it.sources.plugins.gdelt.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("test", max_results=10)
        # First article tone is "5.2,3.1,2.1,0" → tone_val = 5.2
        assert results[0]["metadata"]["tone_val"] == 5.2

    def test_tone_parsing_float(self):
        from scout_it.sources.plugins.gdelt import GdeltPlugin
        plugin = GdeltPlugin()
        with mock.patch("scout_it.sources.plugins.gdelt.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("test", max_results=10)
        # Second article tone is -2.0 (float)
        assert results[1]["metadata"]["tone_val"] == -2.0

    def test_search_empty_response(self):
        from scout_it.sources.plugins.gdelt import GdeltPlugin
        plugin = GdeltPlugin()
        with mock.patch("scout_it.sources.plugins.gdelt.sync_fetch_json",
                        return_value=None):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []

    def test_search_no_articles(self):
        from scout_it.sources.plugins.gdelt import GdeltPlugin
        plugin = GdeltPlugin()
        with mock.patch("scout_it.sources.plugins.gdelt.sync_fetch_json",
                        return_value={}):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []


# ─── ListenNotes ───────────────────────────────────────────────────────────


class TestListenNotesPlugin:
    """Tests for the ListenNotes source plugin."""

    SAMPLE_RESPONSE = {
        "results": [
            {
                "id": "episode-123",
                "title_original": "Understanding Machine Learning",
                "podcast_title_original": "AI Today",
                "link": "https://listennotes.com/e/episode-123/",
                "audio": "https://cdn.listennotes.com/audio.mp3",
                "description_original": "<p>An in-depth discussion about ML.</p>",
                "pub_date_ms": 1723000000000,
                "audio_length_sec": 1800,
                "image": "https://example.com/image.jpg",
                "podcast_id": "pod-456",
                "podcast_publisher_original": "AI Media",
            }
        ]
    }

    def test_plugin_registered(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("listennotes")
        assert plugin is not None
        assert plugin.name == "listennotes"
        assert plugin.content_type == "podcast"

    def test_plugin_not_available_without_key(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("listennotes")
        # Without LISTENNOTES_API_KEY set, should not be available
        import os
        old = os.environ.pop("LISTENNOTES_API_KEY", None)
        try:
            assert plugin.is_available() is False
        finally:
            if old:
                os.environ["LISTENNOTES_API_KEY"] = old

    def test_search_without_key_returns_empty(self):
        from scout_it.sources.plugins.listennotes import ListenNotesPlugin
        plugin = ListenNotesPlugin()
        import os
        old = os.environ.pop("LISTENNOTES_API_KEY", None)
        try:
            results = plugin.search("machine learning", max_results=5)
        finally:
            if old:
                os.environ["LISTENNOTES_API_KEY"] = old
        assert results == []

    def test_search_with_key_parses_results(self):
        from scout_it.sources.plugins.listennotes import ListenNotesPlugin
        plugin = ListenNotesPlugin()
        import os
        os.environ["LISTENNOTES_API_KEY"] = "test-key-123"
        try:
            with mock.patch("scout_it.sources.plugins.listennotes.sync_fetch_json",
                            return_value=self.SAMPLE_RESPONSE):
                results = plugin.search("machine learning", max_results=5)
        finally:
            del os.environ["LISTENNOTES_API_KEY"]

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "listennotes"
        assert r["content_type"] == "podcast"
        assert "Understanding Machine Learning" in r["title"]
        assert "AI Today" in r["title"]
        # HTML stripped from description
        assert "<p>" not in r["snippet"]
        assert r["metadata"]["podcast_title"] == "AI Today"
        assert r["metadata"]["audio_length_sec"] == 1800

    def test_search_empty_response(self):
        from scout_it.sources.plugins.listennotes import ListenNotesPlugin
        plugin = ListenNotesPlugin()
        import os
        os.environ["LISTENNOTES_API_KEY"] = "test-key"
        try:
            with mock.patch("scout_it.sources.plugins.listennotes.sync_fetch_json",
                            return_value=None):
                results = plugin.search("test", max_results=5)
        finally:
            del os.environ["LISTENNOTES_API_KEY"]
        assert results == []


# ─── OpenStreetMap ─────────────────────────────────────────────────────────


class TestOpenStreetMapPlugin:
    """Tests for the OpenStreetMap source plugin."""

    SAMPLE_RESPONSE = [
        {
            "place_id": 12345,
            "osm_id": 67890,
            "osm_type": "way",
            "name": "Central Park",
            "display_name": "Central Park, Manhattan, New York, NY, USA",
            "lat": "40.7829",
            "lon": "-73.9654",
            "category": "park",
            "class": "leisure",
            "type": "park",
            "importance": 0.87,
            "address": {"city": "New York", "state": "NY", "country": "USA"},
            "extratags": {"wikidata": "Q160409"},
            "boundingbox": ["40.76", "40.81", "-73.98", "-73.95"],
        },
        {
            "place_id": 99999,
            "osm_id": 11111,
            "osm_type": "node",
            "name": "",
            "display_name": "Some Street, City, Country",
            "lat": "51.5074",
            "lon": "-0.1278",
            "category": "highway",
            "class": "highway",
            "type": "residential",
            "importance": 0.2,
            "address": {},
            "extratags": {},
            "boundingbox": [],
        },
    ]

    def test_plugin_registered(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("openstreetmap")
        assert plugin is not None
        assert plugin.name == "openstreetmap"
        assert plugin.content_type == "geo"

    def test_plugin_available(self):
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("openstreetmap")
        assert plugin.is_available() is True

    def test_search_parses_results(self):
        from scout_it.sources.plugins.openstreetmap import OpenStreetMapPlugin
        plugin = OpenStreetMapPlugin()
        with mock.patch("scout_it.sources.plugins.openstreetmap.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("Central Park", max_results=10)
        assert len(results) == 2
        r = results[0]
        assert r["source"] == "openstreetmap"
        assert r["content_type"] == "geo"
        assert r["title"] == "Central Park"
        assert "Manhattan" in r["snippet"]
        assert "openstreetmap.org" in r["url"]
        assert "40.7829" in r["url"]
        assert r["authority_score"] == 0.87
        assert r["metadata"]["lat"] == "40.7829"
        assert r["metadata"]["lon"] == "-73.9654"

    def test_empty_name_uses_display_name(self):
        from scout_it.sources.plugins.openstreetmap import OpenStreetMapPlugin
        plugin = OpenStreetMapPlugin()
        with mock.patch("scout_it.sources.plugins.openstreetmap.sync_fetch_json",
                        return_value=[self.SAMPLE_RESPONSE[1]]):
            results = plugin.search("some street", max_results=5)
        # Empty name → falls back to first part of display_name
        assert results[0]["title"] == "Some Street"

    def test_osm_id_prefix(self):
        from scout_it.sources.plugins.openstreetmap import OpenStreetMapPlugin
        plugin = OpenStreetMapPlugin()
        with mock.patch("scout_it.sources.plugins.openstreetmap.sync_fetch_json",
                        return_value=self.SAMPLE_RESPONSE):
            results = plugin.search("test", max_results=10)
        # Way → "W" prefix
        assert results[0]["id"].startswith("W")
        # Node → "N" prefix
        assert results[1]["id"].startswith("N")

    def test_search_empty_response(self):
        from scout_it.sources.plugins.openstreetmap import OpenStreetMapPlugin
        plugin = OpenStreetMapPlugin()
        with mock.patch("scout_it.sources.plugins.openstreetmap.sync_fetch_json",
                        return_value=None):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []

    def test_search_not_list_returns_empty(self):
        from scout_it.sources.plugins.openstreetmap import OpenStreetMapPlugin
        plugin = OpenStreetMapPlugin()
        with mock.patch("scout_it.sources.plugins.openstreetmap.sync_fetch_json",
                        return_value={"error": "bad request"}):
            results = plugin.search("nonexistent", max_results=5)
        assert results == []


# ─── Registry integration ─────────────────────────────────────────────────


class TestPhase4RegistryIntegration:
    """Tests that all Phase 4 sources are properly registered."""

    def test_all_phase4_sources_listed(self):
        from scout_it.sources.registry import list_plugins
        plugins = {p["name"] for p in list_plugins()}
        for name in ["internet_archive", "gdelt", "listennotes", "gitlab", "bitbucket", "openstreetmap"]:
            assert name in plugins, f"{name} not registered"

    def test_all_phase4_sources_in_config(self):
        from scout_it.sources.source_config import SOURCE_BY_NAME
        for name in ["internet_archive", "gdelt", "listennotes", "gitlab", "bitbucket", "openstreetmap"]:
            assert name in SOURCE_BY_NAME, f"{name} not in source config"

    def test_total_plugin_count(self):
        from scout_it.sources.registry import list_plugins
        plugins = list_plugins()
        # Should have 31 plugins total (29 + gitlab + bitbucket)
        assert len(plugins) >= 31

    def test_gitlab_bitbucket_are_code_type(self):
        from scout_it.sources.registry import get_plugin
        for name in ["gitlab", "bitbucket"]:
            plugin = get_plugin(name)
            assert plugin.content_type == "code"

    def test_code_query_type_recognized_by_bandit(self):
        """The source bandit should classify code queries to select GitLab/Bitbucket."""
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("python repository gitlab bitbucket code") == "code"
        assert classify_query("github repository open source code") == "code"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
