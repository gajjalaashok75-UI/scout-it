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
from scout_it.sources.plugins.linkup import LinkupPlugin
from scout_it.sources.plugins.langsearch import LangsearchPlugin
from scout_it.sources.plugins.serper import SerperPlugin


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
    for k in (
        "TAVILY_API_KEY", "EXA_API_KEY", "FIRECRAWL_API_KEY",
        "LINKUP_API_KEY", "LANGSEARCH_API_KEY", "SERPER_API_KEY",
    ):
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
        assert get_plugin("linkup") is not None
        assert get_plugin("langsearch") is not None
        assert get_plugin("serper") is not None

    def test_api_sources_excluded_from_sources_plural_path(self):
        """API sources are --source (singular) only, not --sources (plural)."""
        from scout_it.sources.registry import list_available, list_plugins
        available = set(list_available())
        plugin_names = {p["name"] for p in list_plugins()}
        for name in ("tavily", "exa", "firecrawl", "linkup", "langsearch", "serper"):
            assert name not in available, f"{name} should not be in --sources path"
            assert name not in plugin_names, f"{name} should not be in --sources listing"

    def test_plugin_search_skips_missing_key_with_message(self):
        """Direct plugin.search() records a skip message when key is absent."""
        from scout_it.sources.registry import get_plugin
        for name in ("tavily", "exa", "firecrawl", "linkup", "langsearch", "serper"):
            plugin = get_plugin(name)
            results = plugin.search("test", search_type="web")
            assert results == []
        msgs = source_messages.drain()
        sources_skipped = {m["source"] for m in msgs if m["type"] == "skip"}
        assert sources_skipped == {"tavily", "exa", "firecrawl", "linkup", "langsearch", "serper"}

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
        assert "LINKUP_API_KEY" in KNOWN_KEYS
        assert "LANGSEARCH_API_KEY" in KNOWN_KEYS
        assert "SERPER_API_KEY" in KNOWN_KEYS

    def test_api_sources_in_api_search_credentials(self):
        """API sources live in API_SEARCH_CREDENTIALS, not SOURCE_CREDENTIALS."""
        from scout_it.sources.source_config import (
            SOURCE_BY_NAME, API_SEARCH_CREDENTIALS,
        )
        # Excluded from --sources (plural) registry.
        for name in ("tavily", "exa", "firecrawl", "linkup", "langsearch", "serper"):
            assert name not in SOURCE_BY_NAME
        # Present in the --source (singular) credential map.
        assert "tavily" in API_SEARCH_CREDENTIALS
        assert "exa" in API_SEARCH_CREDENTIALS
        assert "firecrawl" in API_SEARCH_CREDENTIALS
        assert API_SEARCH_CREDENTIALS["tavily"]["requires_key"] is True
        assert API_SEARCH_CREDENTIALS["exa"]["api_key_env"] == "EXA_API_KEY"
        assert API_SEARCH_CREDENTIALS["firecrawl"]["api_key_env"] == "FIRECRAWL_API_KEY"
        assert API_SEARCH_CREDENTIALS["linkup"]["api_key_env"] == "LINKUP_API_KEY"
        assert API_SEARCH_CREDENTIALS["langsearch"]["api_key_env"] == "LANGSEARCH_API_KEY"
        assert API_SEARCH_CREDENTIALS["serper"]["api_key_env"] == "SERPER_API_KEY"
        for name in ("linkup", "langsearch", "serper"):
            assert API_SEARCH_CREDENTIALS[name]["requires_key"] is True


# ─── Linkup ──────────────────────────────────────────────────────────────────


class TestLinkupPlugin:
    def test_supported_types(self):
        plugin = LinkupPlugin()
        assert "web" in plugin.SUPPORTED_SEARCH_TYPES
        assert "image" in plugin.SUPPORTED_SEARCH_TYPES
        assert "multi" in plugin.SUPPORTED_SEARCH_TYPES
        assert "news" not in plugin.SUPPORTED_SEARCH_TYPES
        assert "video" not in plugin.SUPPORTED_SEARCH_TYPES

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_web_search_normalizes_sources(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        # SourcedAnswer shape: answer + sources[{name,url,snippet,favicon}]
        sourced = mock.MagicMock()
        sourced.answer = "Lincoln was the 16th president."
        src = mock.MagicMock()
        src.name = "HISTORY"
        src.url = "https://example.com/lincoln"
        src.snippet = "Abraham Lincoln - Facts & Summary"
        src.favicon = "https://example.com/favicon.ico"
        sourced.sources = [src]
        sourced.images = []
        mock_client.search.return_value = sourced

        plugin = LinkupPlugin()
        results = plugin.search("lincoln", max_results=5, search_type="web")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "linkup"
        assert r["url"] == "https://example.com/lincoln"
        assert r["title"] == "HISTORY"
        assert r["snippet"] == "Abraham Lincoln - Facts & Summary"
        assert r["metadata"]["linkup_answer"] == "Lincoln was the 16th president."
        assert r["metadata"]["favicon"] == "https://example.com/favicon.ico"

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_web_search_passes_sourced_answer_params(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        sourced = mock.MagicMock()
        sourced.answer = ""
        sourced.sources = []
        sourced.images = []
        mock_client.search.return_value = sourced

        plugin = LinkupPlugin()
        plugin.search("query", max_results=7, search_type="web")

        kwargs = mock_client.search.call_args.kwargs
        assert kwargs["depth"] == "standard"
        assert kwargs["output_type"] == "sourcedAnswer"
        assert kwargs["include_images"] is False
        assert kwargs["include_inline_citations"] is True
        assert kwargs["max_results"] == 7

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_image_search_enables_images(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        sourced = mock.MagicMock()
        sourced.answer = ""
        sourced.sources = []
        img = mock.MagicMock()
        img.url = "https://img.example.com/1.jpg"
        img.name = "A cat"
        sourced.images = [img]
        mock_client.search.return_value = sourced

        plugin = LinkupPlugin()
        results = plugin.search("cats", max_results=5, search_type="image")

        kwargs = mock_client.search.call_args.kwargs
        assert kwargs["include_images"] is True
        # The image entry surfaces as a media result.
        assert len(results) == 1
        assert results[0]["content_type"] == "media"
        assert results[0]["metadata"]["is_image"] is True
        assert results[0]["url"] == "https://img.example.com/1.jpg"

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_multi_search_enables_images(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        sourced = mock.MagicMock()
        sourced.answer = ""
        sourced.sources = []
        sourced.images = []
        mock_client.search.return_value = sourced

        plugin = LinkupPlugin()
        plugin.search("query", max_results=5, search_type="multi")

        assert mock_client.search.call_args.kwargs["include_images"] is True

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_search_unsupported_type_silent(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-test")
        plugin = LinkupPlugin()
        # news/video not supported → silent empty return, no messages
        results = plugin.search("query", max_results=5, search_type="news")
        assert results == []
        assert source_messages.drain() == []
        mock_client_cls.assert_not_called()

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_auth_error_classified(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-bad")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.side_effect = Exception("401 Unauthorized")

        plugin = LinkupPlugin()
        results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "authentication" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.linkup.LinkupClient")
    def test_rate_limit_error_classified(self, mock_client_cls, monkeypatch):
        monkeypatch.setenv("LINKUP_API_KEY", "lu-test")
        mock_client = mock.MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.search.side_effect = Exception("429 rate limit exceeded")

        plugin = LinkupPlugin()
        results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "rate limit" in msgs[0]["reason"].lower() or "credit" in msgs[0]["reason"].lower()


# ─── LangSearch ──────────────────────────────────────────────────────────────


class TestLangsearchPlugin:
    def test_supported_types(self):
        plugin = LangsearchPlugin()
        assert set(plugin.SUPPORTED_SEARCH_TYPES) == {"web", "multi"}

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_web_search_normalizes_results(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-test")
        mock_post.return_value = _FakeResp(200, json_data={
            "code": 200,
            "data": {
                "_type": "SearchResponse",
                "webPages": {
                    "totalEstimatedMatches": 1,
                    "value": [
                        {
                            "id": "x1",
                            "name": "Apple ESG Report",
                            "url": "https://example.com/esg",
                            "displayUrl": "https://example.com/esg",
                            "snippet": "Apple cut emissions by 55%.",
                            "summary": "Apple's 2024 ESG report shows a 55% reduction in greenhouse gas emissions since 2015.",
                        }
                    ],
                },
            },
        })

        plugin = LangsearchPlugin()
        results = plugin.search("apple esg", max_results=5, search_type="web")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "langsearch"
        assert r["url"] == "https://example.com/esg"
        assert r["title"] == "Apple ESG Report"
        # summary is richer than snippet → preserved as content
        assert "55% reduction" in r["content"]

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_web_search_request_params(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-test")
        mock_post.return_value = _FakeResp(200, json_data={"data": {"webPages": {"value": []}}})

        plugin = LangsearchPlugin()
        plugin.search("query", max_results=8, search_type="web")

        call = mock_post.call_args
        payload = call.kwargs["json"]
        assert payload["query"] == "query"
        assert payload["freshness"] == "noLimit"
        assert payload["summary"] is True
        assert payload["count"] == 8
        headers = call.kwargs["headers"]
        assert headers["Authorization"] == "Bearer ls-test"
        assert headers["Content-Type"] == "application/json"

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_multi_search_uses_web_endpoint(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-test")
        mock_post.return_value = _FakeResp(200, json_data={"data": {"webPages": {"value": []}}})

        plugin = LangsearchPlugin()
        plugin.search("query", max_results=5, search_type="multi")
        # multi reuses the /v1/web-search endpoint
        assert mock_post.called

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_auth_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-bad")
        mock_post.return_value = _FakeResp(401, text='{"error":"unauthorized"}')

        plugin = LangsearchPlugin()
        results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert msgs[0]["type"] == "error"
        assert "authentication" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_rate_limit_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-test")
        mock_post.return_value = _FakeResp(429, text="rate limited")

        plugin = LangsearchPlugin()
        results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert "rate limit" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_network_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-test")
        import requests as req_mod
        mock_post.side_effect = req_mod.ConnectionError("connection refused")

        plugin = LangsearchPlugin()
        results = plugin.search("query", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert "network" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.langsearch.requests.post")
    def test_unsupported_type_silent(self, mock_post, monkeypatch):
        monkeypatch.setenv("LANGSEARCH_API_KEY", "ls-test")
        plugin = LangsearchPlugin()
        results = plugin.search("query", max_results=5, search_type="news")
        assert results == []
        assert source_messages.drain() == []
        mock_post.assert_not_called()


# ─── Serper ──────────────────────────────────────────────────────────────────


class TestSerperPlugin:
    def test_supported_types(self):
        plugin = SerperPlugin()
        assert set(plugin.SUPPORTED_SEARCH_TYPES) == {"web", "news", "image", "video", "multi"}

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_web_search_normalizes_organic(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        mock_post.return_value = _FakeResp(200, json_data={
            "organic": [
                {"title": "Rust vs Go", "link": "https://example.com/rust-go",
                 "snippet": "A comparison of Rust and Go.", "position": 1, "source": "blog"}
            ]
        })

        plugin = SerperPlugin()
        results = plugin.search("rust vs go", max_results=5, search_type="web")

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "serper"
        assert r["url"] == "https://example.com/rust-go"
        assert r["title"] == "Rust vs Go"
        assert r["snippet"] == "A comparison of Rust and Go."
        assert r["metadata"]["position"] == 1

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_web_search_hits_search_endpoint(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        mock_post.return_value = _FakeResp(200, json_data={"organic": []})

        plugin = SerperPlugin()
        plugin.search("q", max_results=5, search_type="web")

        url = mock_post.call_args.args[0]
        assert url == "https://google.serper.dev/search"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["q"] == "q"
        assert payload["num"] == 5
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["X-API-KEY"] == "sp-test"

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_news_search_hits_news_endpoint(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        mock_post.return_value = _FakeResp(200, json_data={"news": []})

        plugin = SerperPlugin()
        plugin.search("q", max_results=5, search_type="news")

        assert mock_post.call_args.args[0] == "https://google.serper.dev/news"

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_image_search_returns_media(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        mock_post.return_value = _FakeResp(200, json_data={
            "images": [
                {"title": "A cat", "imageUrl": "https://img.example.com/cat.jpg",
                 "image": "https://img.example.com/cat.jpg"}
            ]
        })

        plugin = SerperPlugin()
        results = plugin.search("cats", max_results=5, search_type="image")

        assert mock_post.call_args.args[0] == "https://google.serper.dev/images"
        assert len(results) == 1
        r = results[0]
        assert r["content_type"] == "media"
        assert r["metadata"]["is_image"] is True
        assert r["metadata"]["image_url"] == "https://img.example.com/cat.jpg"

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_video_search_returns_video(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        mock_post.return_value = _FakeResp(200, json_data={
            "videos": [
                {"title": "Rust tutorial", "link": "https://youtube.com/watch?v=abc",
                 "snippet": "Learn Rust basics", "date": "2 days ago",
                 "channel": "Ferris", "thumbnail": "https://img.example.com/t.jpg"}
            ]
        })

        plugin = SerperPlugin()
        results = plugin.search("rust", max_results=5, search_type="video")

        assert mock_post.call_args.args[0] == "https://google.serper.dev/videos"
        assert len(results) == 1
        r = results[0]
        assert r["url"] == "https://youtube.com/watch?v=abc"
        assert r["title"] == "Rust tutorial"
        assert r["content_type"] == "media"
        assert r["metadata"]["is_video"] is True
        assert r["metadata"]["channel"] == "Ferris"
        assert r["metadata"]["thumbnail"] == "https://img.example.com/t.jpg"
        assert r["timestamp"] == "2 days ago"

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_multi_search_batch_array_payload(self, mock_post, monkeypatch):
        """multi-search sends a JSON-array batch payload to /search."""
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        # batch response is a list of SERP objects
        mock_post.return_value = _FakeResp(200, json_data=[
            {"organic": [{"title": "T1", "link": "https://example.com/1", "snippet": "s1"}]}
        ])

        plugin = SerperPlugin()
        results = plugin.search("rust", max_results=10, search_type="multi")

        assert mock_post.call_args.args[0] == "https://google.serper.dev/search"
        payload = mock_post.call_args.kwargs["json"]
        assert isinstance(payload, list)
        assert payload[0]["q"] == "rust"
        assert payload[0]["num"] == 10
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/1"

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_auth_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-bad")
        mock_post.return_value = _FakeResp(403, text="forbidden")

        plugin = SerperPlugin()
        results = plugin.search("q", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert "authentication" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_rate_limit_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        mock_post.return_value = _FakeResp(429, text="rate limited")

        plugin = SerperPlugin()
        results = plugin.search("q", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert "rate limit" in msgs[0]["reason"].lower()

    @mock.patch("scout_it.sources.plugins.serper.requests.post")
    def test_network_error_classified(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")
        import requests as req_mod
        mock_post.side_effect = req_mod.Timeout("timed out")

        plugin = SerperPlugin()
        results = plugin.search("q", max_results=5, search_type="web")
        assert results == []
        msgs = source_messages.drain()
        assert "network" in msgs[0]["reason"].lower()


# ─── Video --source wiring ────────────────────────────────────────────────────


class TestVideoSourceWiring:
    """The video-search --source flag runs API sources as parallel streams."""

    def test_video_search_calls_serper_with_video_type(self, monkeypatch):
        """video_search(source='serper') queries the serper plugin with
        search_type='video' and merges results into candidates."""
        # DDGS returns nothing so we don't also hit YouTube fallback.
        from scout_it.commands import video as video_mod

        def _fake_ddgs(kind, **kwargs):
            return [], {"total": 0, "success": 0, "execution_time": 0.0}

        monkeypatch.setattr(video_mod, "_ddgs_list_search_with_retry", _fake_ddgs)
        # No YouTube fallback either → serper is the only contributor.
        monkeypatch.setattr(video_mod, "_youtube_search_fallback", lambda q, max_results=20: [])

        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("serper")

        captured = {}

        def _spy_search(query, max_results=10, search_type="web", **kwargs):
            captured["search_type"] = search_type
            captured["max_results"] = max_results
            return [{
                "source": "serper",
                "url": "https://youtube.com/watch?v=vid1",
                "title": "A Video",
                "snippet": "video snippet",
                "content_type": "media",
                "timestamp": "2024-01-01",
                "metadata": {"is_video": True, "thumbnail": "https://t/1.jpg", "channel": "Ch"},
            }]

        monkeypatch.setattr(plugin, "search", _spy_search)
        monkeypatch.setenv("SERPER_API_KEY", "sp-test")

        results, stats = video_mod.video_search("rust", max_results=5, source="serper")

        assert captured["search_type"] == "video"
        assert any(r["url"] == "https://youtube.com/watch?v=vid1" for r in results)
        assert stats["api_candidates"] == 1
        assert stats["api_sources"] == ["serper"]

    def test_video_search_skips_missing_key_silently(self, monkeypatch):
        """No SERPER_API_KEY → serper skipped, search still completes."""
        from scout_it.commands import video as video_mod

        def _fake_ddgs(kind, **kwargs):
            return [], {"total": 0, "success": 0, "execution_time": 0.0}

        monkeypatch.setattr(video_mod, "_ddgs_list_search_with_retry", _fake_ddgs)
        monkeypatch.setattr(video_mod, "_youtube_search_fallback", lambda q, max_results=20: [])
        # No env var set → serper is_available() is False.

        results, stats = video_mod.video_search("rust", max_results=5, source="serper")

        assert stats["api_candidates"] == 0
        # search did not raise
        assert isinstance(results, list)


# ─── Full API result preservation (no truncation) ────────────────────────────


class TestApiResultPreservation:
    """The FULL API-provided content + metadata must reach the output JSON
    untruncated, for exa/tavily/firecrawl/linkup/langsearch/serper.

    Previously the discovery layer mapped only ``snippet or content`` into the
    candidate ``body`` (truncating rich content) and dropped ``metadata``
    entirely. Now ``api_content`` + ``api_metadata`` flow through ranking →
    extraction → cleaning into the final output.
    """

    def test_web_snippets_preserves_tavily_full_content_and_metadata(self, monkeypatch):
        """web-search --snippets --source tavily → output has api_content (full)
        + api_metadata (tavily_answer, score) untruncated."""
        import importlib
        web_search_mod = importlib.import_module('.web-search.web_search', package='scout_it')
        full_content = "Tavily full extracted content. " * 50  # ~1.5KB, well over 400
        tavily_results = [{
            "source": "tavily",
            "url": "https://example.com/tavily-unique-1",
            "title": "Tavily Result",
            "snippet": "short snippet",
            "content": full_content,
            "metadata": {
                "score": 0.92,
                "tavily_answer": "The answer is 42. " * 20,  # ~280 chars
                "search_type": "web",
            },
            "authority_score": 0.92,
        }]
        # DDGS returns nothing so only the tavily candidate is in the pipeline.
        monkeypatch.setattr(web_search_mod, "_ddgs_list_search_with_retry",
                            lambda *a, **k: ([], {"total": 0, "success": 0, "execution_time": 0.0}))
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("tavily")
        monkeypatch.setattr(plugin, "search", lambda *a, **k: tavily_results)
        monkeypatch.setenv("TAVILY_API_KEY", "tv-test")

        results, stats = web_search_mod.web_search("query", max_results=5, source="tavily",
                                                    snippets_only=True)

        assert len(results) == 1
        r = results[0]
        assert r["source"] == "tavily"
        # Full content preserved, NOT truncated to 400 chars
        assert r["api_content"] == full_content
        assert len(r["api_content"]) > 400
        # Full metadata preserved (tavily_answer untruncated)
        assert r["api_metadata"]["score"] == 0.92
        assert r["api_metadata"]["tavily_answer"].startswith("The answer is 42.")
        assert r["api_authority_score"] == 0.92

    def test_web_snippets_preserves_exa_full_content_and_highlights(self, monkeypatch):
        import importlib
        web_search_mod = importlib.import_module('.web-search.web_search', package='scout_it')
        full_text = "Exa full text content. " * 60  # ~1.3KB
        exa_results = [{
            "source": "exa",
            "url": "https://example.com/exa-unique-1",
            "title": "Exa Result",
            "snippet": "exa highlight snippet",
            "content": full_text,
            "metadata": {
                "score": 0.88,
                "highlights": "highlight one\nhighlight two",
                "author": "jane",
                "search_type": "web",
            },
            "authority_score": 0.88,
            "timestamp": "2024-01-01",
        }]
        monkeypatch.setattr(web_search_mod, "_ddgs_list_search_with_retry",
                            lambda *a, **k: ([], {"total": 0, "success": 0, "execution_time": 0.0}))
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("exa")
        monkeypatch.setattr(plugin, "search", lambda *a, **k: exa_results)
        monkeypatch.setenv("EXA_API_KEY", "ex-test")

        results, stats = web_search_mod.web_search("query", max_results=5, source="exa",
                                                    snippets_only=True)

        assert len(results) == 1
        r = results[0]
        assert r["api_content"] == full_text
        assert len(r["api_content"]) > 400
        assert r["api_metadata"]["highlights"] == "highlight one\nhighlight two"
        assert r["api_metadata"]["author"] == "jane"
        assert r["api_authority_score"] == 0.88
        assert r["api_timestamp"] == "2024-01-01"

    def test_web_snippets_preserves_firecrawl_full_markdown(self, monkeypatch):
        import importlib
        web_search_mod = importlib.import_module('.web-search.web_search', package='scout_it')
        full_md = "# Firecrawl Page\n\nFull markdown content. " * 40
        fc_results = [{
            "source": "firecrawl",
            "url": "https://example.com/fc-unique-1",
            "title": "Firecrawl Result",
            "snippet": "fc description",
            "content": full_md,
            "metadata": {
                "search_type": "web",
                "favicon": "https://example.com/favicon.ico",
                "structured_json": {"title": "parsed", "items": [1, 2, 3]},
            },
        }]
        monkeypatch.setattr(web_search_mod, "_ddgs_list_search_with_retry",
                            lambda *a, **k: ([], {"total": 0, "success": 0, "execution_time": 0.0}))
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("firecrawl")
        monkeypatch.setattr(plugin, "search", lambda *a, **k: fc_results)
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")

        results, stats = web_search_mod.web_search("query", max_results=5, source="firecrawl",
                                                    snippets_only=True)

        assert len(results) == 1
        r = results[0]
        assert r["api_content"] == full_md
        assert len(r["api_content"]) > 400
        assert r["api_metadata"]["structured_json"]["items"] == [1, 2, 3]
        assert r["api_metadata"]["favicon"] == "https://example.com/favicon.ico"

    def test_web_full_extraction_preserves_api_metadata_through_cleaner(self, monkeypatch):
        """In full (non-snippets) mode, the cleaner output includes api_content +
        api_metadata untruncated, alongside the extracted cleaned_content."""
        import importlib
        web_search_mod = importlib.import_module('.web-search.web_search', package='scout_it')
        full_content = "Tavily full content for extraction test. " * 40
        tavily_results = [{
            "source": "tavily",
            "url": "https://example.com/tavily-extract-1",
            "title": "Tavily Result",
            "snippet": "snippet",
            "content": full_content,
            "metadata": {"score": 0.9, "tavily_answer": "answer blob"},
            "authority_score": 0.9,
        }]
        monkeypatch.setattr(web_search_mod, "_ddgs_list_search_with_retry",
                            lambda *a, **k: ([], {"total": 0, "success": 0, "execution_time": 0.0}))
        from scout_it.sources.registry import get_plugin
        plugin = get_plugin("tavily")
        monkeypatch.setattr(plugin, "search", lambda *a, **k: tavily_results)
        monkeypatch.setenv("TAVILY_API_KEY", "tv-test")

        # Stub the extraction engine so we don't hit the network. Verify the
        # EnterpriseResult carries api_content/api_metadata into asdict output.
        from dataclasses import dataclass, field
        from typing import List, Optional

        @dataclass
        class _FakeResult:
            position: int = 1
            title: str = ""
            url: str = ""
            snippet: str = ""
            source: str = "unknown"
            main_content: str = "Extracted full page content from the live URL."
            content_word_count: int = 7
            extraction_method: str = "requests (basic)"
            confidence_score: float = 0.8
            extraction_status: str = "success"
            publish_date: Optional[str] = None
            author: Optional[str] = None
            cleaned_html: Optional[str] = None
            errors: List[str] = field(default_factory=list)
            final_url: str = ""
            fetch_time: float = 0.1
            content_quality_score: float = 0.8
            api_content: str = ""
            api_metadata: dict = field(default_factory=dict)
            api_authority_score: float = 0.0
            api_timestamp: str = ""

            @classmethod
            def from_seed(cls, seed):
                return cls(
                    title=seed.get('title', ''),
                    url=seed.get('url', ''),
                    snippet=(seed.get('snippet') or seed.get('body') or '')[:400],
                    source=seed.get('source', 'unknown'),
                    final_url=seed.get('url', ''),
                    api_content=seed.get('api_content', ''),
                    api_metadata=seed.get('api_metadata', {}) or {},
                    api_authority_score=seed.get('api_authority_score', 0.0),
                    api_timestamp=seed.get('api_timestamp', ''),
                )

        class _FakeEngine:
            def __init__(self, *a, **k): pass
            stats = {}
            def execute_search_from_urls(self, seeds):
                return [_FakeResult.from_seed(s) for s in seeds]

        monkeypatch.setattr(web_search_mod, "EnterpriseSearchEngine", _FakeEngine)

        results, stats = web_search_mod.web_search("query", max_results=5, source="tavily",
                                                    snippets_only=False)

        assert len(results) == 1
        r = results[0]
        # The extracted content is present (from re-fetching the URL)
        assert r["cleaned_content"] == "Extracted full page content from the live URL."
        # AND the full API content + metadata are preserved untruncated
        assert r["api_content"] == full_content
        assert r["api_metadata"]["score"] == 0.9
        assert r["api_metadata"]["tavily_answer"] == "answer blob"
        assert r["api_authority_score"] == 0.9
