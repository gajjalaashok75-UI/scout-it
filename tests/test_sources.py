"""Tests for the Phase 2 source plugin system.

Tests cover:
  - Plugin registry (discovery, listing, enable/disable)
  - Source config (API key reading, enable/disable persistence)
  - Unified SearchResult schema (make_result factory)
  - Async fetch layer (sync wrappers, rate limiter)
  - Individual source plugins (mocked HTTP responses)
  - Multi-source search (gather all → semantic rank)
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


# ─── Plugin registry tests ──────────────────────────────────────────────────


class TestPluginRegistry:
    """Test plugin discovery, listing, and dispatch."""

    def test_all_plugins_discoverable(self):
        """All 17 source plugins should be registered after discovery."""
        from scout_it.sources import list_plugins
        plugins = list_plugins()
        names = {p["name"] for p in plugins}
        expected = {
            "openalex", "semantic_scholar", "arxiv", "crossref", "unpaywall",
            "core", "europe_pmc", "huggingface", "zenodo", "data_gov",
            "wikidata", "open_library", "gutenberg", "gdelt",
            "internet_archive", "listennotes", "openstreetmap",
        }
        assert expected.issubset(names), f"Missing plugins: {expected - names}"

    def test_get_plugin_returns_instance(self):
        from scout_it.sources import get_plugin
        from scout_it.sources.base import SourcePlugin
        plugin = get_plugin("openalex")
        assert plugin is not None
        assert isinstance(plugin, SourcePlugin)
        assert plugin.name == "openalex"

    def test_get_plugin_unknown_returns_none(self):
        from scout_it.sources import get_plugin
        assert get_plugin("nonexistent_source") is None

    def test_list_plugins_has_required_fields(self):
        from scout_it.sources import list_plugins
        for p in list_plugins():
            assert "name" in p
            assert "display_name" in p
            assert "content_type" in p
            assert "requires_key" in p
            assert "available" in p
            assert "enabled" in p

    def test_each_plugin_has_correct_content_type(self):
        from scout_it.sources import list_plugins
        content_types = {p["name"]: p["content_type"] for p in list_plugins()}
        assert content_types["openalex"] == "academic"
        assert content_types["huggingface"] == "dataset"
        assert content_types["wikidata"] == "knowledge"
        assert content_types["open_library"] == "book"
        assert content_types["gdelt"] == "event"
        assert content_types["listennotes"] == "podcast"
        assert content_types["openstreetmap"] == "geo"


# ─── Source config tests ────────────────────────────────────────────────────


class TestSourceConfig:
    """Test per-source configuration management."""

    def test_source_credentials_registry_complete(self):
        from scout_it.sources.source_config import SOURCE_CREDENTIALS, SOURCE_NAMES
        assert len(SOURCE_CREDENTIALS) >= 17
        assert "openalex" in SOURCE_NAMES
        assert "arxiv" in SOURCE_NAMES

    def test_get_source_config_defaults(self):
        from scout_it.sources.source_config import get_source_config
        cfg = get_source_config("openalex")
        assert cfg["enabled"] is True
        assert "api_key" in cfg
        assert "base_url" in cfg

    def test_get_source_config_unknown_source(self):
        from scout_it.sources.source_config import get_source_config
        cfg = get_source_config("nonexistent")
        assert cfg["enabled"] is True  # default

    def test_enable_disable_source_persists(self, tmp_path, monkeypatch):
        from scout_it.sources import source_config as sc
        monkeypatch.setattr(sc, "SOURCES_FILE", tmp_path / "sources.json")
        sc.enable_source("test_source")
        assert sc.is_source_enabled("test_source")
        sc.disable_source("test_source")
        assert not sc.is_source_enabled("test_source")

    def test_set_source_config_api_key(self, tmp_path, monkeypatch):
        from scout_it.sources import source_config as sc
        monkeypatch.setattr(sc, "SOURCES_FILE", tmp_path / "sources.json")
        sc.set_source_config("test_source", api_key="test_key_123")
        cfg = sc.get_source_config("test_source")
        assert cfg["api_key"] == "test_key_123"

    def test_source_status_returns_all_sources(self):
        from scout_it.sources.source_config import source_status
        statuses = source_status()
        assert len(statuses) >= 17
        for s in statuses:
            assert "name" in s
            assert "configured" in s
            assert "enabled" in s

    def test_env_var_overrides_stored_key(self, monkeypatch, tmp_path):
        from scout_it.sources import source_config as sc
        monkeypatch.setattr(sc, "SOURCES_FILE", tmp_path / "sources.json")
        monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "env_key_456")
        sc.set_source_config("semantic_scholar", api_key="stored_key")
        cfg = sc.get_source_config("semantic_scholar")
        assert cfg["api_key"] == "env_key_456"  # env wins


# ─── SearchResult schema tests ──────────────────────────────────────────────


class TestSearchResult:
    """Test the unified result schema factory."""

    def test_make_result_basic(self):
        from scout_it.sources.base import make_result
        r = make_result(
            id="123",
            source="openalex",
            url="https://example.com/123",
            title="Test Paper",
            snippet="A test abstract",
        )
        assert r["id"] == "123"
        assert r["source"] == "openalex"
        assert r["url"] == "https://example.com/123"
        assert r["title"] == "Test Paper"
        assert r["snippet"] == "A test abstract"
        assert r["content"] == ""
        assert r["content_type"] == "academic"
        assert r["authority_score"] == 0.0
        assert r["relevance_score"] == 0.0
        assert r["lang"] == "en"
        assert r["metadata"] == {}

    def test_make_result_with_all_fields(self):
        from scout_it.sources.base import make_result
        r = make_result(
            id="W123",
            source="wikidata",
            url="https://wikidata.org/wiki/Q42",
            title="Douglas Adams",
            snippet="English author",
            content="Full text here",
            content_type="knowledge",
            timestamp="1952-03-11",
            authority_score=0.9,
            relevance_score=0.8,
            lang="en",
            metadata={"qid": "Q42"},
        )
        assert r["content"] == "Full text here"
        assert r["content_type"] == "knowledge"
        assert r["timestamp"] == "1952-03-11"
        assert r["authority_score"] == 0.9
        assert r["metadata"]["qid"] == "Q42"

    def test_make_result_invalid_content_type_defaults_to_academic(self):
        from scout_it.sources.base import make_result
        r = make_result(
            id="1", source="test", url="https://x.com", title="T",
            content_type="invalid_type",
        )
        assert r["content_type"] == "academic"

    def test_make_result_strips_whitespace(self):
        from scout_it.sources.base import make_result
        r = make_result(
            id="1", source="test", url="https://x.com",
            title="  Spaced Title  ",
            snippet="  Spaced snippet  ",
        )
        assert r["title"] == "Spaced Title"
        assert r["snippet"] == "Spaced snippet"

    def test_make_result_handles_none_values(self):
        from scout_it.sources.base import make_result
        r = make_result(
            id="1", source="test", url="https://x.com",
            title=None, snippet=None, content=None,
        )
        assert r["title"] == ""
        assert r["snippet"] == ""
        assert r["content"] == ""


# ─── Async fetch layer tests ────────────────────────────────────────────────


class TestAsyncFetch:
    """Test the HTTP fetch layer."""

    def test_sync_fetch_json_failure_returns_none(self):
        from scout_it.sources.async_fetch import sync_fetch_json
        result = sync_fetch_json("https://nonexistent.invalid.url.example")
        assert result is None

    def test_sync_fetch_text_failure_returns_none(self):
        from scout_it.sources.async_fetch import sync_fetch_text
        result = sync_fetch_text("https://nonexistent.invalid.url.example")
        assert result is None

    def test_rate_limiter_initialization(self):
        from scout_it.sources.async_fetch import RateLimiter
        rl = RateLimiter(rate_per_sec=2.0)
        assert rl._min_interval == 0.5

    def test_rate_limiter_zero_rate_no_wait(self):
        from scout_it.sources.async_fetch import RateLimiter
        rl = RateLimiter(rate_per_sec=0)
        assert rl._min_interval == 0


# ─── Individual plugin tests (with mocked HTTP) ─────────────────────────────


class TestOpenAlexPlugin:
    """Test OpenAlex plugin with mocked API response."""

    MOCK_OPENALEX = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "doi": "https://doi.org/10.1234/test",
                "title": "Test Paper on Transformers",
                "abstract_inverted_index": {"This": [0], "is": [1], "a": [2], "test": [3]},
                "publication_date": "2023-01-15",
                "cited_by_count": 150,
                "language": "en",
                "authorships": [{"author": {"display_name": "Jane Doe"}}],
                "type": "article",
                "open_access": {"is_oa": True, "oa_url": "https://example.com/oa"},
                "concepts": [{"display_name": "Machine learning"}],
            }
        ]
    }

    def test_openalex_search_parses_results(self):
        from scout_it.sources.plugins.openalex import OpenAlexPlugin
        plugin = OpenAlexPlugin()
        with mock.patch(
            "scout_it.sources.plugins.openalex.sync_fetch_json",
            return_value=self.MOCK_OPENALEX,
        ):
            results = plugin.search("transformers", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "openalex"
        assert r["title"] == "Test Paper on Transformers"
        assert r["url"] == "https://doi.org/10.1234/test"
        assert r["snippet"] == "This is a test"
        assert r["content_type"] == "academic"
        assert r["timestamp"] == "2023-01-15"
        assert r["authority_score"] > 0
        assert r["metadata"]["doi"] == "10.1234/test"
        assert r["metadata"]["cited_by_count"] == 150
        assert r["metadata"]["is_oa"] is True

    def test_openalex_reconstructs_abstract_from_inverted_index(self):
        from scout_it.sources.plugins.openalex import OpenAlexPlugin
        inverted = {"Hello": [0], "world": [1], "test": [3], "a": [2]}
        text = OpenAlexPlugin._reconstruct_abstract(inverted)
        assert text == "Hello world a test"

    def test_openalex_empty_response(self):
        from scout_it.sources.plugins.openalex import OpenAlexPlugin
        plugin = OpenAlexPlugin()
        with mock.patch("scout_it.sources.plugins.openalex.sync_fetch_json", return_value=None):
            results = plugin.search("test")
        assert results == []

    def test_openalex_no_api_key_needed(self):
        from scout_it.sources.plugins.openalex import OpenAlexPlugin
        plugin = OpenAlexPlugin()
        assert plugin.is_available() is True
        assert plugin.config.requires_api_key is False


class TestArxivPlugin:
    """Test arXiv plugin with mocked Atom XML."""

    MOCK_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Test Paper on Attention Mechanisms</title>
    <summary>This is a test abstract about attention.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <updated>2024-01-02T00:00:00Z</updated>
    <author><name>Test Author</name></author>
    <link href="http://arxiv.org/abs/2401.00001v1" type="text/html"/>
    <link href="http://arxiv.org/pdf/2401.00001v1" title="pdf" type="application/pdf"/>
    <category term="cs.AI"/>
  </entry>
</feed>"""

    def test_arxiv_search_parses_xml(self):
        from scout_it.sources.plugins.arxiv import ArxivPlugin
        plugin = ArxivPlugin()
        with mock.patch(
            "scout_it.sources.plugins.arxiv.sync_fetch_text",
            return_value=self.MOCK_ARXIV_XML,
        ):
            results = plugin.search("attention", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "arxiv"
        assert r["title"] == "Test Paper on Attention Mechanisms"
        assert "attention" in r["snippet"]
        assert r["url"] == "http://arxiv.org/abs/2401.00001v1"
        assert r["metadata"]["arxiv_id"] == "2401.00001v1"
        assert r["metadata"]["pdf_url"] == "http://arxiv.org/pdf/2401.00001v1"
        assert "Test Author" in r["metadata"]["authors"]
        assert "cs.AI" in r["metadata"]["categories"]

    def test_arxiv_empty_response(self):
        from scout_it.sources.plugins.arxiv import ArxivPlugin
        plugin = ArxivPlugin()
        with mock.patch("scout_it.sources.plugins.arxiv.sync_fetch_text", return_value=None):
            assert plugin.search("test") == []

    def test_arxiv_no_api_key_needed(self):
        from scout_it.sources.plugins.arxiv import ArxivPlugin
        plugin = ArxivPlugin()
        assert plugin.is_available() is True


class TestSemanticScholarPlugin:
    """Test Semantic Scholar plugin."""

    MOCK_RESPONSE = {
        "data": [
            {
                "paperId": "abc123",
                "title": "Attention Is All You Need",
                "abstract": "We propose a new architecture...",
                "url": "https://www.semanticscholar.org/paper/abc123",
                "year": 2017,
                "citationCount": 50000,
                "influentialCitationCount": 1000,
                "authors": [{"name": "Ashish Vaswani"}],
                "tldr": {"text": "Introduces the Transformer architecture"},
                "openAccessPdf": {"url": "https://example.com/attention.pdf"},
                "externalIds": {"DOI": "10.5555/3295222.3295349"},
                "publicationDate": "2017-06-12",
            }
        ]
    }

    def test_semantic_scholar_search(self):
        from scout_it.sources.plugins.semantic_scholar import SemanticScholarPlugin
        plugin = SemanticScholarPlugin()
        with mock.patch(
            "scout_it.sources.plugins.semantic_scholar.sync_fetch_json",
            return_value=self.MOCK_RESPONSE,
        ):
            results = plugin.search("transformer", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Attention Is All You Need"
        assert r["metadata"]["citation_count"] == 50000
        assert r["metadata"]["tldr"] == "Introduces the Transformer architecture"
        assert r["metadata"]["oa_pdf_url"] == "https://example.com/attention.pdf"
        assert r["authority_score"] > 0

    def test_semantic_scholar_available_without_key(self):
        """Semantic Scholar works without a key (just rate-limited)."""
        from scout_it.sources.plugins.semantic_scholar import SemanticScholarPlugin
        plugin = SemanticScholarPlugin()
        assert plugin.is_available() is True


class TestHuggingFacePlugin:
    """Test HuggingFace datasets plugin."""

    MOCK_RESPONSE = [
        {
            "id": "imdb",
            "downloads": 1000000,
            "likes": 500,
            "cardData": {"description": "IMDB movie review dataset"},
            "tags": ["task_categories:text-classification", "language:en"],
            "lastModified": "2024-01-01",
        }
    ]

    def test_huggingface_search(self):
        from scout_it.sources.plugins.huggingface import HuggingFacePlugin
        plugin = HuggingFacePlugin()
        with mock.patch(
            "scout_it.sources.plugins.huggingface.sync_fetch_json",
            return_value=self.MOCK_RESPONSE,
        ):
            results = plugin.search("imdb", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "huggingface"
        assert r["title"] == "imdb"
        assert r["content_type"] == "dataset"
        assert r["url"] == "https://huggingface.co/datasets/imdb"
        assert r["metadata"]["downloads"] == 1000000
        assert "text-classification" in r["metadata"]["task_categories"]


class TestWikidataPlugin:
    """Test Wikidata plugin."""

    MOCK_RESPONSE = {
        "search": [
            {
                "id": "Q42",
                "label": "Douglas Adams",
                "description": "English author and humorist (1952-2001)",
                "concepturi": "http://www.wikidata.org/entity/Q42",
            }
        ]
    }

    def test_wikidata_search(self):
        from scout_it.sources.plugins.wikidata import WikidataPlugin
        plugin = WikidataPlugin()
        with mock.patch(
            "scout_it.sources.plugins.wikidata.sync_fetch_json",
            return_value=self.MOCK_RESPONSE,
        ):
            results = plugin.search("Douglas Adams", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "wikidata"
        assert r["title"] == "Douglas Adams"
        assert r["content_type"] == "knowledge"
        assert r["metadata"]["qid"] == "Q42"


class TestUnpaywallPlugin:
    """Test Unpaywall plugin (requires email)."""

    def test_unpaywall_unavailable_without_email(self):
        from scout_it.sources.plugins.unpaywall import UnpaywallPlugin
        plugin = UnpaywallPlugin()
        with mock.patch.object(plugin, "get_api_key", return_value=None):
            assert plugin.is_available() is False

    def test_unpaywall_available_with_email(self):
        from scout_it.sources.plugins.unpaywall import UnpaywallPlugin
        plugin = UnpaywallPlugin()
        with mock.patch.object(plugin, "get_api_key", return_value="user@example.com"):
            assert plugin.is_available() is True


class TestGutenbergPlugin:
    """Test Project Gutenberg plugin."""

    MOCK_RESPONSE = {
        "results": [
            {
                "id": 1342,
                "title": "Pride and Prejudice",
                "authors": [{"name": "Austen, Jane"}],
                "subjects": ["Fiction", "Love stories"],
                "download_count": 50000,
                "formats": {"text/html": "https://gutenberg.org/1342.html"},
                "languages": ["en"],
            }
        ]
    }

    def test_gutenberg_search(self):
        from scout_it.sources.plugins.gutenberg import GutenbergPlugin
        plugin = GutenbergPlugin()
        with mock.patch(
            "scout_it.sources.plugins.gutenberg.sync_fetch_json",
            return_value=self.MOCK_RESPONSE,
        ):
            results = plugin.search("pride prejudice", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Pride and Prejudice"
        assert r["content_type"] == "book"
        assert r["url"] == "https://www.gutenberg.org/ebooks/1342"
        assert r["metadata"]["text_url"] == "https://gutenberg.org/1342.html"


class TestZenodoPlugin:
    """Test Zenodo plugin."""

    MOCK_RESPONSE = {
        "hits": {
            "hits": [
                {
                    "id": 12345,
                    "metadata": {
                        "title": "Test Dataset",
                        "description": "<p>A test research dataset</p>",
                        "publication_date": "2024-01-01",
                        "doi": "10.5281/zenodo.12345",
                        "creators": [{"name": "Test Researcher"}],
                        "keywords": ["climate", "data"],
                        "resource_type": {"title": "Dataset"},
                        "license": {"id": "CC-BY-4.0"},
                    },
                    "files": [{"key": "data.csv", "downloads": 500}],
                }
            ]
        }
    }

    def test_zenodo_search(self):
        from scout_it.sources.plugins.zenodo import ZenodoPlugin
        plugin = ZenodoPlugin()
        with mock.patch(
            "scout_it.sources.plugins.zenodo.sync_fetch_json",
            return_value=self.MOCK_RESPONSE,
        ):
            results = plugin.search("climate data", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["title"] == "Test Dataset"
        assert r["content_type"] == "dataset"
        assert r["snippet"] == "A test research dataset"  # HTML stripped
        assert r["metadata"]["doi"] == "10.5281/zenodo.12345"
        assert r["metadata"]["resource_type"] == "Dataset"


# ─── Multi-source search tests ──────────────────────────────────────────────


class TestMultiSourceSearch:
    """Test the multi-source search pipeline."""

    def test_search_source_returns_normalized_results(self):
        from scout_it.sources import search_source
        with mock.patch(
            "scout_it.sources.plugins.openalex.sync_fetch_json",
            return_value=TestOpenAlexPlugin.MOCK_OPENALEX,
        ):
            results = search_source("openalex", "test query")
        assert len(results) > 0
        for r in results:
            assert "source" in r
            assert r["source"] == "openalex"

    def test_search_all_with_mocked_sources(self):
        from scout_it.sources import search_all
        with mock.patch(
            "scout_it.sources.plugins.openalex.sync_fetch_json",
            return_value=TestOpenAlexPlugin.MOCK_OPENALEX,
        ), mock.patch(
            "scout_it.sources.plugins.arxiv.sync_fetch_text",
            return_value=TestArxivPlugin.MOCK_ARXIV_XML,
        ):
            grouped = search_all("test", sources=["openalex", "arxiv"], max_results_per_source=5)
        assert "openalex" in grouped
        assert "arxiv" in grouped
        assert len(grouped["openalex"]) > 0
        assert len(grouped["arxiv"]) > 0

    def test_search_all_unknown_source_skipped(self):
        from scout_it.sources import search_all
        grouped = search_all("test", sources=["nonexistent_source"])
        assert grouped == {} or "nonexistent_source" not in grouped

    def test_source_search_deduplicates_by_url(self):
        from scout_it.sources import source_search
        # Both plugins return the same URL.
        dup_result = {
            "id": "1", "source": "a", "url": "https://dup.com",
            "title": "Dup", "snippet": "s",
        }
        with mock.patch("scout_it.sources.registry.search_all", return_value={
            "openalex": [dup_result, {"id": "2", "source": "b", "url": "https://unique.com", "title": "U", "snippet": "s"}],
            "arxiv": [{"id": "3", "source": "c", "url": "https://dup.com", "title": "Dup2", "snippet": "s"}],
        }), mock.patch("scout_it.sources.registry._rerank", side_effect=lambda x, *a, **k: x, create=True):
            results = source_search("test", semantic_rerank=False)
        urls = [r["url"] for r in results]
        assert len(urls) == len(set(urls)), "Results should be deduped by URL"

    def test_source_search_empty_results(self):
        from scout_it.sources import source_search
        with mock.patch("scout_it.sources.registry.search_all", return_value={}):
            results = source_search("test", semantic_rerank=False)
        assert results == []

    def test_source_search_preserves_metadata(self):
        from scout_it.sources import source_search
        test_result = {
            "id": "1", "source": "openalex", "url": "https://example.com",
            "title": "Test", "snippet": "Test snippet",
            "metadata": {"doi": "10.1234/test", "cited_by_count": 42},
        }
        with mock.patch("scout_it.sources.registry.search_all", return_value={"openalex": [test_result]}):
            results = source_search("test", semantic_rerank=False)
        assert len(results) == 1
        assert results[0]["metadata"]["doi"] == "10.1234/test"


# ─── Plugin availability tests ──────────────────────────────────────────────


class TestPluginAvailability:
    """Test plugin availability checks."""

    def test_free_sources_always_available(self):
        from scout_it.sources import get_plugin
        free_sources = ["openalex", "arxiv", "crossref", "europe_pmc", "huggingface",
                        "zenodo", "wikidata", "open_library", "gutenberg", "openstreetmap"]
        for name in free_sources:
            plugin = get_plugin(name)
            assert plugin is not None
            assert plugin.is_available(), f"{name} should be available without a key"

    def test_key_sources_check_availability(self):
        from scout_it.sources import get_plugin
        # Sources requiring keys should respect key presence.
        for name in ["core", "listennotes"]:
            plugin = get_plugin(name)
            if plugin:
                with mock.patch.object(plugin, "get_api_key", return_value=None):
                    assert not plugin.is_available(), f"{name} should be unavailable without key"
                with mock.patch.object(plugin, "get_api_key", return_value="fake_key"):
                    assert plugin.is_available(), f"{name} should be available with key"
