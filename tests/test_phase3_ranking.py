"""Tests for Phase 3: unified ranking + bandit source selection.

Covers:
  - Authority table (seeded scores, bandit refinement, persistence)
  - Composite scorer (relevance + authority + freshness + diversity)
  - Source-selection bandit (query classification, Thompson sampling, outcome recording)
  - Orchestrator integration (composite rerank + bandit source selection)
  - CLI integration (--auto-sources flag)
"""

import json
import math
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest

# ─── Authority table ────────────────────────────────────────────────────────


class TestAuthorityTable:
    """Tests for scout_it.semantic.authority_table."""

    def test_seeded_domains_get_seed_score(self):
        from scout_it.semantic.authority_table import get_authority_score
        assert get_authority_score("https://arxiv.org/abs/1234") == 0.95
        assert get_authority_score("https://github.com/user/repo") == 0.92
        assert get_authority_score("https://en.wikipedia.org/wiki/X") == 0.85

    def test_unknown_domain_gets_default(self):
        from scout_it.semantic.authority_table import get_authority_score, DEFAULT_AUTHORITY
        assert get_authority_score("https://totally-unknown-domain-xyz.com/page") == DEFAULT_AUTHORITY

    def test_empty_url_gets_default(self):
        from scout_it.semantic.authority_table import get_authority_score, DEFAULT_AUTHORITY
        assert get_authority_score("") == DEFAULT_AUTHORITY
        assert get_authority_score(None) == DEFAULT_AUTHORITY

    def test_strips_www_prefix(self):
        from scout_it.semantic.authority_table import get_authority_score
        # Both should give the same score (www. stripped)
        assert get_authority_score("https://www.arxiv.org/abs/1234") == get_authority_score("https://arxiv.org/abs/1234")

    def test_bare_domain_works(self):
        from scout_it.semantic.authority_table import get_authority_score
        assert get_authority_score("arxiv.org") == 0.95

    def test_record_outcome_adjusts_score(self):
        from scout_it.semantic.authority_table import (
            get_authority_score, record_domain_outcome, reset_authority, _cache
        )
        reset_authority("test-adjust.example")
        base = get_authority_score("test-adjust.example")

        # Record many successes
        for _ in range(20):
            record_domain_outcome("test-adjust.example", success=True)
        adjusted = get_authority_score("test-adjust.example")
        assert adjusted > base, f"Score should increase after successes: {adjusted} vs {base}"

        reset_authority("test-adjust.example")

    def test_record_failures_decreases_score(self):
        from scout_it.semantic.authority_table import (
            get_authority_score, record_domain_outcome, reset_authority
        )
        reset_authority("test-fail.example")

        # Record many failures
        for _ in range(20):
            record_domain_outcome("test-fail.example", success=False)
        adjusted = get_authority_score("test-fail.example")
        assert adjusted < 0.5, f"Score should decrease after failures: {adjusted}"

        reset_authority("test-fail.example")

    def test_authority_table_returns_all_domains(self):
        from scout_it.semantic.authority_table import get_authority_table, reset_authority
        reset_authority()
        table = get_authority_table()
        assert "arxiv.org" in table
        assert "github.com" in table
        assert "nature.com" in table
        assert table["arxiv.org"] == 0.95

    def test_reset_all_clears_adjustments(self):
        from scout_it.semantic.authority_table import (
            record_domain_outcome, reset_authority, get_authority_score, _cache
        )
        record_domain_outcome("reset-all-test.example", success=True)
        n = reset_authority()
        assert n >= 0
        # After reset, should be back to default
        assert get_authority_score("reset-all-test.example") == 0.5

    def test_score_clamped_to_0_1(self):
        from scout_it.semantic.authority_table import (
            get_authority_score, record_domain_outcome, reset_authority
        )
        reset_authority("clamp-test.example")
        # Record extreme successes — should still be <= 1.0
        for _ in range(100):
            record_domain_outcome("clamp-test.example", success=True)
        assert get_authority_score("clamp-test.example") <= 1.0

        reset_authority("clamp-test2.example")
        for _ in range(100):
            record_domain_outcome("clamp-test2.example", success=False)
        assert get_authority_score("clamp-test2.example") >= 0.0

        reset_authority("clamp-test.example")
        reset_authority("clamp-test2.example")


# ─── Composite score ──────────────────────────────────────────────────────


class TestCompositeScore:
    """Tests for scout_it.semantic.composite_score."""

    def _make_results(self, n=3):
        return [
            {
                "title": f"Result {i}",
                "url": f"https://example{i}.com/page{i}",
                "snippet": f"Content for result {i}",
                "semantic_score": 1.0 - i * 0.2,
                "timestamp": "2026-08-01",
                "content_type": "web",
            }
            for i in range(n)
        ]

    def test_composite_score_adds_breakdown(self):
        from scout_it.semantic.composite_score import composite_score
        results = self._make_results()
        scored = composite_score(results, "test query")
        for r in scored:
            assert "composite_score" in r
            assert "score_breakdown" in r
            bd = r["score_breakdown"]
            assert "relevance" in bd
            assert "authority" in bd
            assert "freshness" in bd
            assert "diversity" in bd

    def test_composite_score_empty_results(self):
        from scout_it.semantic.composite_score import composite_score
        assert composite_score([], "test") == []

    def test_relevance_normalization(self):
        from scout_it.semantic.composite_score import composite_score
        results = [
            {"title": "A", "url": "https://a.com", "semantic_score": 0.9, "content_type": "web"},
            {"title": "B", "url": "https://b.com", "semantic_score": 0.1, "content_type": "web"},
        ]
        scored = composite_score(results, "test")
        # A should have higher relevance than B
        assert scored[0]["score_breakdown"]["relevance"] > scored[1]["score_breakdown"]["relevance"]

    def test_authority_from_domain_table(self):
        from scout_it.semantic.composite_score import composite_score
        results = [
            {"title": "A", "url": "https://arxiv.org/abs/1234", "semantic_score": 0.5, "content_type": "academic"},
            {"title": "B", "url": "https://unknown-blog.example.com/post", "semantic_score": 0.5, "content_type": "academic"},
        ]
        scored = composite_score(results, "test")
        # arxiv should have higher authority
        auth_scores = {r["title"]: r["score_breakdown"]["authority"] for r in scored}
        assert auth_scores["A"] > auth_scores["B"]

    def test_freshness_time_decay(self):
        from scout_it.semantic.composite_score import _freshness_score
        # Recent timestamp = high freshness
        now = datetime.now(timezone.utc)
        recent = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        old = (now - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S")

        recent_score = _freshness_score(recent, "news")
        old_score = _freshness_score(old, "news")
        assert recent_score > old_score
        assert recent_score > 0.9  # very fresh
        assert old_score < 0.1   # very old for news

    def test_freshness_content_type_aware(self):
        from scout_it.semantic.composite_score import _freshness_score
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")

        # For news, 30 days old = very stale
        news_fresh = _freshness_score(old_ts, "news")
        # For academic, 30 days old = basically fresh (10-year half-life)
        academic_fresh = _freshness_score(old_ts, "academic")
        assert academic_fresh > news_fresh

    def test_freshness_no_timestamp_is_neutral(self):
        from scout_it.semantic.composite_score import _freshness_score
        assert _freshness_score("", "news") == 0.5
        assert _freshness_score(None, "news") == 0.5

    def test_freshness_compact_date_format(self):
        """openFDA uses YYYYMMDD format."""
        from scout_it.semantic.composite_score import _freshness_score, _parse_timestamp
        dt = _parse_timestamp("20260115")
        assert dt is not None
        assert dt.year == 2026

    def test_diversity_penalizes_duplicates(self):
        from scout_it.semantic.composite_score import _diversity_scores
        # Two near-duplicate results (same title+domain)
        results = [
            {"title": "Breaking News Update", "url": "https://reuters.com/article1",
             "snippet": "The same story about something important happening today", "content_type": "news"},
            {"title": "Breaking News Update", "url": "https://reuters.com/article2",
             "snippet": "The same story about something important happening today", "content_type": "news"},
            {"title": "Completely Different Topic", "url": "https://other.com/post",
             "snippet": "A totally unrelated article about cooking", "content_type": "news"},
        ]
        scores = _diversity_scores(results)
        # First of the duplicates should have higher diversity than second
        assert scores[0] >= scores[1]
        # Unique result should have high diversity
        assert scores[2] == 1.0

    def test_diversity_single_result(self):
        from scout_it.semantic.composite_score import _diversity_scores
        scores = _diversity_scores([{"title": "Only one", "url": "https://x.com"}])
        assert scores == [1.0]

    def test_composite_rerank_sorts_by_score(self):
        from scout_it.semantic.composite_score import composite_rerank
        results = [
            {"title": "Low", "url": "https://unknown.com/x", "semantic_score": 0.1, "timestamp": "2010-01-01", "content_type": "web"},
            {"title": "High", "url": "https://arxiv.org/abs/123", "semantic_score": 0.9, "timestamp": "2026-08-01", "content_type": "academic"},
        ]
        ranked = composite_rerank(results, "test", content_type_hint="academic")
        assert ranked[0]["title"] == "High"
        assert ranked[0]["composite_score"] >= ranked[1]["composite_score"]

    def test_composite_rerank_max_final(self):
        from scout_it.semantic.composite_score import composite_rerank
        results = self._make_results(5)
        ranked = composite_rerank(results, "test", max_final=2)
        assert len(ranked) == 2

    def test_weights_override(self):
        from scout_it.semantic.composite_score import composite_score
        results = self._make_results(2)
        # With 100% relevance weight, composite should equal normalised relevance
        scored = composite_score(results, "test", weights=(1.0, 0.0, 0.0, 0.0))
        for r in scored:
            assert abs(r["composite_score"] - r["score_breakdown"]["relevance"]) < 0.001

    def test_news_weights_emphasize_freshness(self):
        from scout_it.semantic.composite_score import DEFAULT_WEIGHTS
        news_w = DEFAULT_WEIGHTS["news"]
        academic_w = DEFAULT_WEIGHTS["academic"]
        # News has higher freshness weight than academic
        assert news_w[2] > academic_w[2]  # freshness index = 2
        # Academic has higher authority weight than news
        assert academic_w[1] > news_w[1]  # authority index = 1

    def test_weights_sum_to_one(self):
        from scout_it.semantic.composite_score import DEFAULT_WEIGHTS, GENERAL_WEIGHTS
        for name, w in DEFAULT_WEIGHTS.items():
            assert abs(sum(w) - 1.0) < 0.01, f"Weights for {name} don't sum to 1: {w}"
        assert abs(sum(GENERAL_WEIGHTS) - 1.0) < 0.01


# ─── Source-selection bandit ──────────────────────────────────────────────


class TestSourceBandit:
    """Tests for scout_it.sources.source_bandit."""

    def test_classify_academic(self):
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("neural network deep learning paper") == "academic"
        assert classify_query("quantum physics research") == "academic"

    def test_classify_news(self):
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("breaking news today latest") == "news"

    def test_classify_code(self):
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("python function error stacktrace") == "code"

    def test_classify_event(self):
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("earthquake disaster crisis") == "event"

    def test_classify_geo(self):
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("weather forecast city location") == "geo"

    def test_classify_general_web(self):
        from scout_it.sources.source_bandit import classify_query
        assert classify_query("hello world") == "web"
        assert classify_query("") == "web"

    def test_choose_sources_no_history_returns_all(self):
        from scout_it.sources.source_bandit import choose_sources
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        available = ["arxiv", "openalex", "hackernews"]
        result = choose_sources("test query", available, top_k=2, db_path=db)
        assert result["source"] == "default"
        # With no history, returns all available (exploration)
        assert set(result["sources"]) == set(available)

    def test_choose_sources_empty_returns_empty(self):
        from scout_it.sources.source_bandit import choose_sources
        result = choose_sources("test", [])
        assert result["sources"] == []
        assert result["query_type"] == "web"

    def test_choose_sources_bandit_picks_best(self):
        from scout_it.sources.source_bandit import choose_sources, record_source_outcome
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        # Record outcomes: arxiv always succeeds, hackernews always fails
        for _ in range(20):
            record_source_outcome("machine learning research", "arxiv",
                                  [{"semantic_score": 0.9}], db_path=db)
            record_source_outcome("machine learning research", "hackernews",
                                  [], db_path=db)
            record_source_outcome("machine learning research", "openalex",
                                  [{"semantic_score": 0.5}], db_path=db)

        result = choose_sources("machine learning research",
                                ["arxiv", "hackernews", "openalex"],
                                top_k=2, db_path=db)
        assert result["source"] == "bandit"
        # arxiv should be selected (high success rate)
        assert "arxiv" in result["sources"]
        # hackernews should NOT be selected (always failed)
        assert "hackernews" not in result["sources"]

    def test_record_outcome_success(self):
        from scout_it.sources.source_bandit import record_source_outcome, get_source_stats
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        record_source_outcome("research paper", "arxiv",
                              [{"semantic_score": 0.8}], db_path=db)
        stats = get_source_stats("academic", db_path=db)
        assert "arxiv" in stats.get("academic", {})
        assert stats["academic"]["arxiv"]["successes"] == 1
        assert stats["academic"]["arxiv"]["total"] == 1

    def test_record_outcome_failure(self):
        from scout_it.sources.source_bandit import record_source_outcome, get_source_stats
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        record_source_outcome("research paper", "hackernews", [], db_path=db)
        stats = get_source_stats("academic", db_path=db)
        assert stats["academic"]["hackernews"]["successes"] == 0
        assert stats["academic"]["hackernews"]["failures"] == 1

    def test_record_outcomes_batch(self):
        from scout_it.sources.source_bandit import record_source_outcomes, get_source_stats
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        record_source_outcomes("test query", {
            "arxiv": [{"semantic_score": 0.7}],
            "hackernews": [],
        }, db_path=db)
        stats = get_source_stats("web", db_path=db)
        assert "arxiv" in stats.get("web", {})
        assert "hackernews" in stats.get("web", {})

    def test_reset_bandit_all(self):
        from scout_it.sources.source_bandit import record_source_outcome, reset_bandit, get_source_stats
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        record_source_outcome("test", "arxiv", [{"semantic_score": 0.5}], db_path=db)
        n = reset_bandit(db_path=db)
        assert n >= 1
        stats = get_source_stats(db_path=db)
        assert all(len(sources) == 0 for sources in stats.values())

    def test_reset_bandit_one_type(self):
        from scout_it.sources.source_bandit import record_source_outcome, reset_bandit, get_source_stats
        import tempfile
        db = Path(tempfile.mktemp(suffix=".db"))
        record_source_outcome("research paper", "arxiv", [{"semantic_score": 0.5}], db_path=db)
        record_source_outcome("breaking news", "gdelt", [{"semantic_score": 0.5}], db_path=db)
        n = reset_bandit(query_type="academic", db_path=db)
        assert n >= 1
        stats = get_source_stats(db_path=db)
        # academic should be empty, news should still have data
        assert "academic" not in stats or len(stats.get("academic", {})) == 0
        assert "news" in stats and "gdelt" in stats.get("news", {})


# ─── Orchestrator integration ─────────────────────────────────────────────


class TestOrchestratorIntegration:
    """Tests that composite rerank + bandit integrate with the orchestrator."""

    def test_merge_and_rank_applies_composite(self):
        from scout_it.sources.orchestrator import merge_and_rank
        regular = [
            {"title": "Web result", "url": "https://example.com/1", "snippet": "A web page about python",
             "source": "web"},
        ]
        source_results = {
            "hackernews": [
                {"title": "HN result", "url": "https://news.ycombinator.com/item?id=1",
                 "snippet": "A hacker news post about python", "source": "hackernews",
                 "content_type": "web", "authority_score": 0.78},
            ],
        }
        ranked = merge_and_rank("python", regular, source_results, max_final=10,
                                semantic_rerank=False, composite_rerank=True)
        assert len(ranked) >= 1
        for r in ranked:
            assert "composite_score" in r

    def test_merge_and_rank_without_composite(self):
        from scout_it.sources.orchestrator import merge_and_rank
        regular = [{"title": "R1", "url": "https://a.com", "snippet": "test", "source": "web"}]
        source_results = {"arxiv": [{"title": "S1", "url": "https://arxiv.org/abs/1",
                                     "snippet": "paper", "source": "arxiv", "content_type": "academic"}]}
        ranked = merge_and_rank("test", regular, source_results, max_final=10,
                                semantic_rerank=False, composite_rerank=False)
        # Without composite, no composite_score
        for r in ranked:
            assert "composite_score" not in r

    def test_augment_with_composite_rerank(self):
        from scout_it.sources.orchestrator import augment_search_with_sources
        regular = [
            {"title": "Python tutorial", "url": "https://example.com/python",
             "snippet": "Learn Python programming", "source": "web"},
        ]
        ranked = augment_search_with_sources(
            "python programming", regular, "hackernews",
            max_final=10, max_per_source=5,
            semantic_rerank=False, composite_rerank=True,
        )
        assert len(ranked) >= 1
        for r in ranked:
            assert "composite_score" in r


# ─── CLI integration ──────────────────────────────────────────────────────


class TestCLIIntegration:
    """Tests that --auto-sources flag works in the CLI."""

    def test_auto_sources_flag_exists(self):
        from scout_it.cli import build_parser
        parser = build_parser()
        for cmd in ["web-search", "news-search", "image-search", "video-search", "multi-search"]:
            args = parser.parse_args([cmd, "-q", "test", "--auto-sources"])
            assert args.auto_sources is True, f"{cmd} should have --auto-sources"

    def test_auto_sources_defaults_false(self):
        from scout_it.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["web-search", "-q", "test"])
        assert args.auto_sources is False

    def test_sources_and_auto_sources_independent(self):
        from scout_it.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["web-search", "-q", "test", "--sources", "arxiv"])
        assert args.sources == "arxiv"
        assert args.auto_sources is False

        args2 = parser.parse_args(["web-search", "-q", "test", "--auto-sources"])
        assert args2.auto_sources is True
        assert args2.sources is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
