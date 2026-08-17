"""Tests for the API search source plugins (Tavily, Exa, Firecrawl).

All tests are offline — SDK calls and HTTP requests are mocked. No real API
keys or network access are needed.
"""
import os
from unittest import mock

import pytest

from scout_it.sources.api_search_base import (
    ApiSearchSource,
    SourceMessageCollector,
    source_messages,
)
from scout_it.sources.plugins.tavily import TavilyPlugin, _classify_tavily_error
from scout_it.sources.plugins.exa import ExaPlugin, _classify_exa_error
from scout_it.sources.plugins.firecrawl import FirecrawlPlugin


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_messages():
    """Clear the shared message collector before and after each test."""
    source_messages.drain()
    yield
    source_messages.drain()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure no API keys leak from the real environment into tests."""
    for k in ("TAVILY_API_KEY", "EXA_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(k, raising=False)


class _FakeResp:
    """Minimal mock for requests.Response."""

    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data
        self.text = text or ""

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


# ─── SourceMessageCollector ──────────────────────────────────────────────────


class TestSourceMessageCollector:
    def test_skip_and_drain(self):
        c = SourceMessageCollector()
        c.skip("tavily", "no key")
        msgs = c.drain()
        assert len(msgs) == 1
        assert msgs[0]["source"] == "tavily"
        assert msgs[0]["type"] == "skip"
        # drain clears
        assert c.drain() == []

    def test_error(self):
        c = SourceMessageCollector()
        c.error("firecrawl", "rate limited")
        msgs = c.drain()
        assert msgs[0]["type"] == "error"
        assert "rate limited" in msgs[0]["reason"]

    def test_thread_safe(self):
        import threading

        c = SourceMessageCollector()

        def add_errors():
            for i in range(100):
                c.error("s", f"e{i}")

        threads = [threading.Thread(target=add_errors) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(c.drain()) == 500

    def test_has_messages(self):
        c = SourceMessageCollector()
        assert not c.has_messages()
        c.skip("x", "y")
        assert c.has_messages()


# ─── Base class behaviour ────────────────────────────────────────────────────


class TestApiSearchSource:
    def test_search_no_key_skips_with_message(self):
        plugin = TavilyPlugin()
        # No key set → is_available False, search returns [] + skip message
        assert not plugin.is_available()
        results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert len(msgs) == 1
        assert msgs[0]["type"] == "skip"
        assert "TAVILY_API_KEY" in msgs[0]["reason"]

    def test_search_unsupported_type_returns_empty(self, monkeypatch):
        """Exa doesn't support image search — should skip silently."""
        monkeypatch.setenv("EXA_API_KEY", "fake-key")
        plugin = ExaPlugin()
        results = plugin.search("query", max_results=5, search_type="image")
        assert results == []
        # No skip/error message for unsupported type (silent skip)
        assert source_messages.drain() == []

    def test_search_catches_api_key_error(self, monkeypatch):
        from scout_it.sources.api_search_base import _ApiKeyError
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
        plugin = TavilyPlugin()

        with mock.patch.object(plugin, "_raw_search", side_effect=_ApiKeyError("401 Unauthorized")):
            results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert len(msgs) == 1
        assert msgs[0]["type"] == "error"
        assert "authentication" in msgs[0]["reason"]

    def test_search_catches_rate_limit_error(self, monkeypatch):
        from scout_it.sources.api_search_base import _RateLimitError
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
        plugin = TavilyPlugin()

        with mock.patch.object(plugin, "_raw_search", side_effect=_RateLimitError("429 Too Many Requests")):
            results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "rate limit" in msgs[0]["reason"].lower() or "credit" in msgs[0]["reason"].lower()

    def test_search_catches_network_error(self, monkeypatch):
        from scout_it.sources.api_search_base import _NetworkError
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
        plugin = TavilyPlugin()

        with mock.patch.object(plugin, "_raw_search", side_effect=_NetworkError("Connection timeout")):
            results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "network" in msgs[0]["reason"].lower()

    def test_search_catches_generic_error(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
        plugin = TavilyPlugin()

        with mock.patch.object(plugin, "_raw_search", side_effect=ValueError("something weird")):
            results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "unexpected" in msgs[0]["reason"].lower()


# ─── Tavily ──────────────────────────────────────────────────────────────────


class TestTavilyPlugin:
    def test_supported_types(self):
        plugin = TavilyPlugin()
        assert "web" in plugin.SUPPORTED_SEARCH_TYPES
        assert "news" in plugin.SUPPORTED_SEARCH_TYPES
        assert "image" in plugin.SUPPORTED_SEARCH_TYPES
        assert "multi" in plugin.SUPPORTED_SEARCH_TYPES

    @mock.patch("scout_it.sources.plugins.tavily.TavilyClient")
    def test_web_search_normalizes_results(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = {
            "answer": "AI answer text",
            "results": [
                {
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "content": "Full content here, not truncated.",
                    "score": 0.95,
                }
            ],
        }

        plugin = TavilyPlugin()
        results = plugin.search("test", max_results=5, search_type="web")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "tavily"
        assert r["url"] == "https://example.com/article"
        assert r["title"] == "Test Article"
        assert r["content"] == "Full content here, not truncated."
        assert r["metadata"]["tavily_answer"] == "AI answer text"

    @mock.patch("scout_it.sources.plugins.tavily.TavilyClient")
    def test_news_search_passes_topic(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = {"results": []}

        plugin = TavilyPlugin()
        plugin.search("news query", max_results=5, search_type="news")

        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["topic"] == "news"

    @mock.patch("scout_it.sources.plugins.tavily.TavilyClient")
    def test_image_search_returns_images(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = {
            "results": [],
            "images": [
                {"url": "https://img.example.com/1.jpg", "description": "A cat"},
                "https://img.example.com/2.jpg",
            ],
        }

        plugin = TavilyPlugin()
        results = plugin.search("cats", max_results=5, search_type="image")

        assert len(results) == 2
        assert results[0]["url"] == "https://img.example.com/1.jpg"
        assert results[0]["content_type"] == "media"
        assert results[0]["metadata"]["is_image"] is True
        assert results[1]["url"] == "https://img.example.com/2.jpg"

    @mock.patch("scout_it.sources.plugins.tavily.TavilyClient")
    def test_multi_search_flags(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.return_value = {"results": [], "images": []}

        plugin = TavilyPlugin()
        plugin.search("query", max_results=5, search_type="multi")

        call_kwargs = mock_client.search.call_args.kwargs
        assert call_kwargs["include_images"] is True
        assert call_kwargs["include_image_descriptions"] is True
        assert call_kwargs["include_favicon"] is True
        assert call_kwargs["include_usage"] is True

    def test_classify_tavily_error_auth(self):
        with pytest.raises(Exception) as exc_info:
            _classify_tavily_error(Exception("401 Unauthorized"))
        assert exc_info.value.__class__.__name__ == "_ApiKeyError"

    def test_classify_tavily_error_rate_limit(self):
        with pytest.raises(Exception) as exc_info:
            _classify_tavily_error(Exception("429 rate limit exceeded"))
        assert exc_info.value.__class__.__name__ == "_RateLimitError"


# ─── Exa ─────────────────────────────────────────────────────────────────────


class TestExaPlugin:
    def test_supported_types_no_image(self):
        plugin = ExaPlugin()
        assert "web" in plugin.SUPPORTED_SEARCH_TYPES
        assert "news" in plugin.SUPPORTED_SEARCH_TYPES
        assert "multi" in plugin.SUPPORTED_SEARCH_TYPES
        assert "image" not in plugin.SUPPORTED_SEARCH_TYPES

    @mock.patch("scout_it.sources.plugins.exa.Exa")
    def test_web_search_normalizes_results(self, mock_exa_cls, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "exa-test")
        mock_exa = mock.MagicMock()
        mock_exa_cls.return_value = mock_exa

        result_obj = mock.MagicMock()
        result_obj.results = [
            mock.MagicMock(
                url="https://example.com",
                title="Exa Result",
                text="Full text content",
                highlights=["key highlight"],
                score=0.8,
                author="Author",
                published_date="2024-01-01",
                id="exa-id-1",
            )
        ]
        mock_exa.search.return_value = result_obj

        plugin = ExaPlugin()
        results = plugin.search("test", max_results=5, search_type="web")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "exa"
        assert r["url"] == "https://example.com"
        assert r["title"] == "Exa Result"
        assert r["content"] == "Full text content"
        assert r["timestamp"] == "2024-01-01"

    @mock.patch("scout_it.sources.plugins.exa.Exa")
    def test_news_search_passes_category(self, mock_exa_cls, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "exa-test")
        mock_exa = mock.MagicMock()
        mock_exa_cls.return_value = mock_exa
        result_obj = mock.MagicMock()
        result_obj.results = []
        mock_exa.search.return_value = result_obj

        plugin = ExaPlugin()
        plugin.search("news", max_results=5, search_type="news")

        call_kwargs = mock_exa.search.call_args.kwargs
        assert call_kwargs["category"] == "news"

    def test_classify_exa_error_auth(self):
        with pytest.raises(Exception) as exc_info:
            _classify_exa_error(Exception("403 Forbidden"))
        assert exc_info.value.__class__.__name__ == "_ApiKeyError"


# ─── Firecrawl ───────────────────────────────────────────────────────────────


class TestFirecrawlPlugin:
    def test_supported_types(self):
        plugin = FirecrawlPlugin()
        assert set(plugin.SUPPORTED_SEARCH_TYPES) == {"web", "news", "image", "multi"}

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_web_search_normalizes_results(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        mock_post.return_value = _FakeResp(200, json_data={
            "data": [
                {
                    "url": "https://example.com",
                    "title": "Firecrawl Result",
                    "markdown": "Full markdown content",
                    "description": "Short desc",
                }
            ]
        })

        plugin = FirecrawlPlugin()
        results = plugin.search("test", max_results=5, search_type="web")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "firecrawl"
        assert r["url"] == "https://example.com"
        assert r["content"] == "Full markdown content"

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_web_search_source_param(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        mock_post.return_value = _FakeResp(200, json_data={"data": []})

        plugin = FirecrawlPlugin()
        plugin.search("test", max_results=5, search_type="web")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["sources"] == ["web"]

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_news_search_source_param(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        mock_post.return_value = _FakeResp(200, json_data={"data": []})

        plugin = FirecrawlPlugin()
        plugin.search("test", max_results=5, search_type="news")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["sources"] == ["news"]

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_image_search_source_param(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        mock_post.return_value = _FakeResp(200, json_data={"data": []})

        plugin = FirecrawlPlugin()
        plugin.search("test", max_results=5, search_type="image")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["sources"] == ["images"]

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_multi_search_source_param(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        mock_post.return_value = _FakeResp(200, json_data={"data": []})

        plugin = FirecrawlPlugin()
        plugin.search("test", max_results=5, search_type="multi")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["sources"] == ["news", "web", "images"]

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_auth_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-bad")
        mock_post.return_value = _FakeResp(401, json_data={"error": "Unauthorized"}, text='{"error":"Unauthorized"}')

        plugin = FirecrawlPlugin()
        results = plugin.search("test", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "authentication" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_rate_limit_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        mock_post.return_value = _FakeResp(429, text="rate limited")

        plugin = FirecrawlPlugin()
        results = plugin.search("test", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "rate limit" in msgs[0]["reason"].lower() or "credit" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_network_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
        import requests as req_mod
        mock_post.side_effect = req_mod.ConnectionError("connection refused")

        plugin = FirecrawlPlugin()
        results = plugin.search("test", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "network" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.firecrawl.requests.post")
    def test_authorization_header_set(self, mock_post, monkeypatch):
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-secret")
        mock_post.return_value = _FakeResp(200, json_data={"data": []})

        plugin = FirecrawlPlugin()
        plugin.search("test", max_results=5, search_type="web")

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer fc-secret"
        assert headers["Content-Type"] == "application/json"


# ─── Registry + orchestrator integration ─────────────────────────────────────


class TestRegistryIntegration:
    def test_plugins_registered(self):
        from scout_it.sources.registry import get_plugin
        assert get_plugin("tavily") is not None
        assert get_plugin("exa") is not None
        assert get_plugin("firecrawl") is not None

    def test_api_sources_excluded_from_sources_plural_path(self):
        """API sources are --source (singular) only, not --sources (plural)."""
        from scout_it.sources.registry import list_available, list_plugins
        available = set(list_available())
        plugin_names = {p["name"] for p in list_plugins()}
        for name in ("tavily", "exa", "firecrawl"):
            assert name not in available, f"{name} should not be in --sources path"
            assert name not in plugin_names, f"{name} should not be in --sources listing"

    def test_plugin_search_skips_missing_key_with_message(self):
        """Direct plugin.search() records a skip message when key is absent."""
        from scout_it.sources.registry import get_plugin
        for name in ("tavily", "exa", "firecrawl"):
            plugin = get_plugin(name)
            results = plugin.search("test", search_type="web")
            assert results == []
        msgs = source_messages.drain()
        sources_skipped = {m["source"] for m in msgs if m["type"] == "skip"}
        assert sources_skipped == {"tavily", "exa", "firecrawl"}

    def test_plugin_search_passes_search_type(self, monkeypatch):
        """Verify search_type is forwarded to the plugin's search()."""
        from scout_it.sources.registry import get_plugin
        monkeypatch.setenv("TAVILY_API_KEY", "fake")
        plugin = get_plugin("tavily")
        call_types = []

        def spy_search(query, max_results=10, search_type="web", **kwargs):
            call_types.append(search_type)
            return []

        with mock.patch.object(plugin, "search", side_effect=spy_search):
            plugin.search("test", search_type="news")
        assert "news" in call_types

    def test_augment_excludes_api_sources(self):
        """augment_search_with_sources should not query API sources."""
        from scout_it.sources.orchestrator import augment_search_with_sources
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": "fake"}):
            # If augment tried to query tavily, it would call plugin.search;
            # since tavily is excluded, the spy should never be called.
            from scout_it.sources.registry import get_plugin
            plugin = get_plugin("tavily")
            call_types = []

            def spy_search(query, max_results=10, search_type="web", **kwargs):
                call_types.append(search_type)
                return []

            with mock.patch.object(plugin, "search", side_effect=spy_search):
                augment_search_with_sources(
                    "test",
                    regular_results=[{"title": "r", "url": "https://x.com"}],
                    sources="tavily",
                    search_type="image",
                )
            assert call_types == [], "API sources should not be queried via --sources"


# ─── Config integration ──────────────────────────────────────────────────────


class TestConfigIntegration:
    def test_credentials_listed_in_config(self):
        from scout_it.config import KNOWN_CREDENTIALS, KNOWN_KEYS
        assert "TAVILY_API_KEY" in KNOWN_KEYS
        assert "EXA_API_KEY" in KNOWN_KEYS
        assert "FIRECRAWL_API_KEY" in KNOWN_KEYS

    def test_api_sources_in_api_search_credentials(self):
        """API sources live in API_SEARCH_CREDENTIALS, not SOURCE_CREDENTIALS."""
        from scout_it.sources.source_config import (
            SOURCE_BY_NAME, API_SEARCH_CREDENTIALS,
        )
        # Excluded from --sources (plural) registry.
        for name in ("tavily", "exa", "firecrawl"):
            assert name not in SOURCE_BY_NAME
        # Present in the --source (singular) credential map.
        assert "tavily" in API_SEARCH_CREDENTIALS
        assert "exa" in API_SEARCH_CREDENTIALS
        assert "firecrawl" in API_SEARCH_CREDENTIALS
        assert API_SEARCH_CREDENTIALS["tavily"]["requires_key"] is True
        assert API_SEARCH_CREDENTIALS["exa"]["api_key_env"] == "EXA_API_KEY"
        assert API_SEARCH_CREDENTIALS["firecrawl"]["api_key_env"] == "FIRECRAWL_API_KEY"
