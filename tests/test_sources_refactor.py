"""Tests for new no-auth source plugins, orchestrator, and CLI --sources flag.

These tests verify:
  - The 12 new source plugins (from public-apis) load, register, and parse responses
  - The orchestrator (merge_and_rank, augment_search_with_sources) works correctly
  - The --sources flag is wired into web-search, news-search, image-search,
    video-search, and multi-search CLI parsers
  - Backward compatibility: the old --source (singular) flag still works
  - The source-search command was removed
  - The sources command only accepts list (no subcommands)
"""

from unittest import mock
import pytest


# ─── New no-auth source plugin tests (public-apis additions) ────────────────


class TestNewSourcePlugins:
    """Test that the 12 new no-auth source plugins load and register."""

    NEW_SOURCES = [
        "hackernews", "stackexchange", "open_fda", "open_meteo",
        "usgs_earthquakes", "musicbrainz", "open_food_facts",
        "spaceflight_news", "art_institute_chicago", "met_museum",
        "jikan", "doaj",
    ]

    def test_all_new_plugins_registered(self):
        from scout_it.sources import list_plugins
        names = {p["name"] for p in list_plugins()}
        for src in self.NEW_SOURCES:
            assert src in names, f"{src} should be registered"

    def test_all_new_plugins_no_key(self):
        from scout_it.sources import get_plugin
        for name in self.NEW_SOURCES:
            plugin = get_plugin(name)
            assert plugin is not None, f"{name} plugin missing"
            assert not plugin.config.requires_api_key, f"{name} should not require a key"
            assert plugin.is_available(), f"{name} should be available without a key"

    def test_total_plugin_count(self):
        from scout_it.sources import list_plugins
        plugins = list_plugins()
        # 31 academic/data/code sources. API search sources (tavily, exa,
        # firecrawl) are excluded from the --sources (plural) listing — they
        # are queried directly via --source (singular).
        assert len(plugins) == 31, f"Expected 31 plugins, got {len(plugins)}"

    def test_new_source_content_types(self):
        from scout_it.sources import get_plugin
        type_map = {
            "hackernews": "event", "stackexchange": "knowledge",
            "open_fda": "knowledge", "open_meteo": "geo",
            "usgs_earthquakes": "event", "musicbrainz": "media",
            "open_food_facts": "knowledge", "spaceflight_news": "event",
            "art_institute_chicago": "media", "met_museum": "media",
            "jikan": "media", "doaj": "academic",
        }
        for name, expected_type in type_map.items():
            plugin = get_plugin(name)
            assert plugin.content_type == expected_type, (
                f"{name} should be {expected_type}, got {plugin.content_type}"
            )

    @mock.patch("scout_it.sources.plugins.hackernews.sync_fetch_json")
    def test_hackernews_parses_response(self, mock_fetch):
        mock_fetch.return_value = {
            "hits": [
                {
                    "objectID": "12345",
                    "title": "Show HN: A new Python framework",
                    "url": "https://github.com/example/repo",
                    "points": 500,
                    "num_comments": 120,
                    "author": "user1",
                    "created_at": "2024-01-15T10:00:00Z",
                }
            ]
        }
        from scout_it.sources.plugins.hackernews import HackerNewsPlugin
        results = HackerNewsPlugin().search("python", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "hackernews"
        assert r["title"] == "Show HN: A new Python framework"
        assert r["url"] == "https://github.com/example/repo"
        assert r["metadata"]["points"] == 500
        assert r["metadata"]["num_comments"] == 120
        assert r["metadata"]["hn_url"] == "https://news.ycombinator.com/item?id=12345"

    @mock.patch("scout_it.sources.plugins.stackexchange.sync_fetch_json")
    def test_stackexchange_parses_response(self, mock_fetch):
        mock_fetch.return_value = {
            "items": [
                {
                    "question_id": 999,
                    "title": "How to use list comprehension in Python",
                    "link": "https://stackoverflow.com/q/999",
                    "score": 250,
                    "answer_count": 5,
                    "view_count": 10000,
                    "is_answered": True,
                    "creation_date": 1700000000,
                    "tags": ["python", "list-comprehension"],
                    "body": "<p>How do I use list comprehension?</p>",
                    "owner": {"display_name": "user1"},
                }
            ]
        }
        from scout_it.sources.plugins.stackexchange import StackExchangePlugin
        results = StackExchangePlugin().search("list comprehension", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "stackexchange"
        assert r["title"] == "How to use list comprehension in Python"
        assert r["url"] == "https://stackoverflow.com/q/999"
        assert r["metadata"]["score"] == 250
        assert r["metadata"]["answer_count"] == 5
        assert "list-comprehension" in r["metadata"]["tags"]
        assert "How do I use list comprehension?" in r["snippet"]

    @mock.patch("scout_it.sources.plugins.open_fda.sync_fetch_json")
    def test_open_fda_parses_response(self, mock_fetch):
        mock_fetch.return_value = {
            "meta": {"results": {"total": 1}},
            "results": [
                {
                    "safetyreportid": "12345",
                    "receivedate": "20240115",
                    "patient": {
                        "patientonsetage": "45",
                        "patientsex": "1",
                        "drug": [{"medicinalproduct": "ASPIRIN"}],
                        "reaction": [{"reactionmeddrapt": "Headache"}],
                    },
                    "serious": "1",
                    "occurcountry": "US",
                }
            ],
        }
        from scout_it.sources.plugins.open_fda import OpenFdaPlugin
        results = OpenFdaPlugin().search("aspirin", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "open_fda"
        assert "ASPIRIN" in r["title"]
        assert r["metadata"]["safety_report_id"] == "12345"
        assert r["metadata"]["drugs"] == ["ASPIRIN"]
        assert "Headache" in r["metadata"]["reactions"]
        assert r["metadata"]["patient_sex"] == "male"

    @mock.patch("scout_it.sources.plugins.spaceflight_news.sync_fetch_json")
    def test_spaceflight_news_parses_response(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [
                {
                    "id": 1,
                    "title": "SpaceX launches Starlink",
                    "url": "https://example.com/spacex",
                    "summary": "SpaceX launched another batch of Starlink satellites.",
                    "published_at": "2024-01-15T10:00:00Z",
                    "news_site": "SpaceNews",
                    "image_url": "https://example.com/img.jpg",
                }
            ]
        }
        from scout_it.sources.plugins.spaceflight_news import SpaceflightNewsPlugin
        results = SpaceflightNewsPlugin().search("spacex", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "spaceflight_news"
        assert r["title"] == "SpaceX launches Starlink"
        assert r["url"] == "https://example.com/spacex"
        assert r["metadata"]["news_site"] == "SpaceNews"

    @mock.patch("scout_it.sources.plugins.jikan.sync_fetch_json")
    def test_jikan_parses_response(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [
                {
                    "mal_id": 1,
                    "title": "Cowboy Bebop",
                    "title_japanese": "カウボーイビバップ",
                    "synopsis": "A bounty hunter adventure.",
                    "score": 8.75,
                    "episodes": 26,
                    "status": "Finished Airing",
                    "year": 1998,
                    "type": "TV",
                    "genres": [{"name": "Action"}],
                    "studios": [{"name": "Sunrise"}],
                    "url": "https://myanimelist.net/anime/1",
                    "images": {"jpg": {"image_url": "https://example.com/img.jpg"}},
                }
            ]
        }
        from scout_it.sources.plugins.jikan import JikanPlugin
        results = JikanPlugin().search("cowboy bebop", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "jikan"
        assert r["title"] == "Cowboy Bebop"
        assert r["metadata"]["score"] == 8.75
        assert r["metadata"]["episodes"] == 26
        assert r["metadata"]["year"] == 1998
        assert "Action" in r["metadata"]["genres"]
        assert r["authority_score"] == pytest.approx(0.875)  # 8.75/10

    @mock.patch("scout_it.sources.plugins.doaj.sync_fetch_json")
    def test_doaj_parses_response(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [
                {
                    "id": "abc123",
                    "bibjson": {
                        "title": "Open Access Research Paper",
                        "abstract": "This paper discusses open access.",
                        "year": "2024",
                        "month": "01",
                        "identifier": {"doi": "10.1234/test"},
                        "author": [{"name": "Dr. Smith"}],
                        "journal": {"title": "Open Journal", "publisher": "Open Press"},
                        "keywords": ["open access", "research"],
                        "link": [{"type": "fulltext", "url": "https://example.com/paper.pdf"}],
                    },
                }
            ]
        }
        from scout_it.sources.plugins.doaj import DoajPlugin
        results = DoajPlugin().search("open access", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "doaj"
        assert r["title"] == "Open Access Research Paper"
        assert r["metadata"]["doi"] == "10.1234/test"
        assert r["metadata"]["authors"] == ["Dr. Smith"]
        assert r["metadata"]["journal"] == "Open Journal"
        assert r["metadata"]["pdf_url"] == "https://example.com/paper.pdf"

    @mock.patch("scout_it.sources.plugins.open_meteo.sync_fetch_json")
    def test_open_meteo_parses_response(self, mock_fetch):
        # Open-Meteo makes two calls: geocode then forecast.
        geocode_resp = {
            "results": [
                {
                    "id": 1850147,
                    "name": "Tokyo",
                    "country": "Japan",
                    "admin1": "Tokyo",
                    "latitude": 35.6895,
                    "longitude": 139.6917,
                }
            ]
        }
        forecast_resp = {
            "current": {
                "temperature_2m": 23.5,
                "relative_humidity_2m": 60,
                "apparent_temperature": 24.0,
                "weather_code": 1,
                "wind_speed_10m": 10.5,
                "time": "2024-01-15T10:00",
            },
            "daily": {
                "temperature_2m_max": [25.0, 26.0, 24.0],
                "temperature_2m_min": [18.0, 19.0, 17.0],
            },
        }
        mock_fetch.side_effect = [geocode_resp, forecast_resp]
        from scout_it.sources.plugins.open_meteo import OpenMeteoPlugin
        results = OpenMeteoPlugin().search("tokyo", max_results=5)
        assert len(results) == 1
        r = results[0]
        assert r["source"] == "open_meteo"
        assert "Tokyo" in r["title"]
        assert r["metadata"]["current_temp"] == 23.5
        assert r["metadata"]["humidity"] == 60
        assert r["metadata"]["country"] == "Japan"


# ─── Orchestrator / augment_search_with_sources tests ──────────────────────


class TestOrchestrator:
    """Test the orchestration logic that merges source results with regular results."""

    def test_normalize_regular_result_web(self):
        from scout_it.sources.orchestrator import normalize_regular_result
        regular = {
            "title": "Test Page",
            "href": "https://example.com/page",
            "snippet": "A test snippet",
            "source": "duckduckgo",
            "score": 50,
        }
        norm = normalize_regular_result(regular, default_source="web")
        assert norm["title"] == "Test Page"
        assert norm["url"] == "https://example.com/page"
        assert norm["snippet"] == "A test snippet"
        assert norm["source"] == "duckduckgo"  # preserves existing source
        assert norm["authority_score"] == 0.5  # 50/100

    def test_normalize_regular_result_uses_url_field(self):
        from scout_it.sources.orchestrator import normalize_regular_result
        regular = {"title": "Test", "url": "https://example.com", "body": "body text"}
        norm = normalize_regular_result(regular)
        assert norm["url"] == "https://example.com"
        assert norm["snippet"] == "body text"
        assert norm["source"] == "web"  # default

    def test_normalize_regular_result_preserves_metadata(self):
        from scout_it.sources.orchestrator import normalize_regular_result
        regular = {
            "title": "Test",
            "href": "https://example.com",
            "snippet": "snippet",
            "extra_field": "extra_value",
            "rank": 5,
        }
        norm = normalize_regular_result(regular)
        assert norm["metadata"]["extra_field"] == "extra_value"
        assert norm["metadata"]["rank"] == 5

    def test_merge_and_rank_deduplicates_by_url(self):
        from scout_it.sources.orchestrator import merge_and_rank
        regular = [
            {"title": "A", "href": "https://example.com/a", "snippet": "a"},
            {"title": "A dup", "href": "https://example.com/a", "snippet": "dup"},
        ]
        source_results = {
            "arxiv": [
                {"id": "1", "source": "arxiv", "url": "https://example.com/a",
                 "title": "A dup from arxiv", "snippet": "arxiv"},
            ],
        }
        merged = merge_and_rank("query", regular, source_results,
                                max_final=10, semantic_rerank=False)
        urls = [r["url"] for r in merged]
        assert urls.count("https://example.com/a") == 1  # deduped

    def test_merge_and_rank_returns_empty_for_empty_input(self):
        from scout_it.sources.orchestrator import merge_and_rank
        merged = merge_and_rank("query", [], {}, semantic_rerank=False)
        assert merged == []

    def test_merge_and_rank_respects_max_final(self):
        from scout_it.sources.orchestrator import merge_and_rank
        regular = [{"title": f"R{i}", "href": f"https://example.com/r{i}", "snippet": "x"} for i in range(10)]
        source_results = {
            "test": [{"id": str(i), "source": "test", "url": f"https://example.com/s{i}",
                      "title": f"S{i}", "snippet": "x", "authority_score": 0.5} for i in range(10)],
        }
        merged = merge_and_rank("query", regular, source_results,
                                max_final=5, semantic_rerank=False)
        assert len(merged) == 5

    def test_merge_and_rank_merges_both_pools(self):
        from scout_it.sources.orchestrator import merge_and_rank
        regular = [{"title": "Web", "href": "https://example.com/web", "snippet": "web"}]
        source_results = {
            "arxiv": [{"id": "1", "source": "arxiv", "url": "https://arxiv.org/1",
                       "title": "Paper", "snippet": "paper", "authority_score": 0.5}],
        }
        merged = merge_and_rank("query", regular, source_results,
                                max_final=10, semantic_rerank=False)
        assert len(merged) == 2
        sources = {r["source"] for r in merged}
        assert "arxiv" in sources
        assert "web" in sources

    def test_augment_returns_regular_when_no_sources(self):
        from scout_it.sources.orchestrator import augment_search_with_sources
        regular = [{"title": "R", "href": "https://example.com", "snippet": "x"}]
        result = augment_search_with_sources("query", regular, sources=None)
        assert result is regular

    def test_augment_returns_regular_when_empty_sources(self):
        from scout_it.sources.orchestrator import augment_search_with_sources
        regular = [{"title": "R", "href": "https://example.com", "snippet": "x"}]
        result = augment_search_with_sources("query", regular, sources="")
        assert result is regular

    @mock.patch("scout_it.sources.orchestrator.search_sources_parallel")
    def test_augment_returns_regular_when_no_source_results(self, mock_search):
        from scout_it.sources.orchestrator import augment_search_with_sources
        mock_search.return_value = {"arxiv": []}
        regular = [{"title": "R", "href": "https://example.com", "snippet": "x"}]
        result = augment_search_with_sources("query", regular, sources="arxiv",
                                             semantic_rerank=False)
        assert result is regular

    @mock.patch("scout_it.sources.orchestrator.search_sources_parallel")
    def test_augment_merges_and_ranks(self, mock_search):
        from scout_it.sources.orchestrator import augment_search_with_sources
        mock_search.return_value = {
            "arxiv": [
                {"id": "1", "source": "arxiv", "url": "https://arxiv.org/abs/1234",
                 "title": "ArXiv Paper", "snippet": "academic paper", "authority_score": 0.5},
            ],
        }
        regular = [{"title": "Web", "href": "https://example.com", "snippet": "web result"}]
        result = augment_search_with_sources("academic query", regular, sources="arxiv",
                                             semantic_rerank=False, max_final=10)
        assert len(result) == 2
        sources = {r["source"] for r in result}
        assert "arxiv" in sources
        assert "web" in sources

    @mock.patch("scout_it.sources.orchestrator.search_sources_parallel")
    def test_augment_parses_comma_separated_sources(self, mock_search):
        from scout_it.sources.orchestrator import augment_search_with_sources
        mock_search.return_value = {}
        regular = [{"title": "R", "href": "https://example.com", "snippet": "x"}]
        augment_search_with_sources("query", regular, sources="arxiv,crossref,wikidata",
                                    semantic_rerank=False)
        # Verify search_sources_parallel was called with the parsed list.
        call_args = mock_search.call_args
        assert call_args[0][1] == ["arxiv", "crossref", "wikidata"]


# ─── CLI --sources flag tests ───────────────────────────────────────────────


class TestCliSourcesFlag:
    """Test that the --sources flag is wired into the CLI parsers."""

    def _parse(self, argv):
        """Parse args and return the namespace."""
        from scout_it.cli import build_parser
        parser = build_parser()
        return parser.parse_args(argv)

    def test_web_search_has_sources_flag(self):
        args = self._parse(["web-search", "-q", "test", "--sources", "arxiv,openalex"])
        assert args.sources == "arxiv,openalex"

    def test_news_search_has_sources_flag(self):
        args = self._parse(["news-search", "-q", "test", "--sources", "gdelt,crossref"])
        assert args.sources == "gdelt,crossref"

    def test_image_search_has_sources_flag(self):
        args = self._parse(["image-search", "-q", "test", "--sources", "internet_archive"])
        assert args.sources == "internet_archive"

    def test_video_search_has_sources_flag(self):
        args = self._parse(["video-search", "-q", "test", "--sources", "listennotes"])
        assert args.sources == "listennotes"

    def test_multi_search_has_sources_flag(self):
        args = self._parse(["multi-search", "-q", "test", "--sources", "arxiv,wikidata"])
        assert args.sources == "arxiv,wikidata"

    def test_web_search_sources_defaults_none(self):
        args = self._parse(["web-search", "-q", "test"])
        assert args.sources is None

    def test_web_search_source_singular_still_works(self):
        """The old --source wikimedia flag (singular) should still work."""
        args = self._parse(["web-search", "-q", "test", "--source", "wikimedia"])
        assert args.source == "wikimedia"

    def test_news_search_source_singular_still_works(self):
        args = self._parse(["news-search", "-q", "test", "--source", "google-news"])
        assert args.source == "google-news"

    def test_multi_search_source_singular_still_works(self):
        args = self._parse(["multi-search", "-q", "test", "--source", "wikimedia"])
        assert args.source == "wikimedia"

    def test_sources_command_parses(self):
        """The sources command should parse without a subcommand."""
        args = self._parse(["sources"])
        assert args.command == "sources"

    def test_source_search_command_removed(self):
        """The source-search command should no longer exist."""
        with pytest.raises(SystemExit):
            self._parse(["source-search", "-q", "test"])

    def test_build_parser_returns_parser(self):
        """build_parser() should return a usable ArgumentParser."""
        from scout_it.cli import build_parser
        import argparse
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
