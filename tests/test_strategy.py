"""Tests for scout_it.strategy_cache and scout_it.strategy_bandit."""
import tempfile
from pathlib import Path

import pytest

from scout_it import strategy_cache as cache
from scout_it import strategy_bandit as bandit


@pytest.fixture
def tmp_db():
    fd_path = Path(tempfile.mkdtemp()) / "test_strategy_cache.db"
    yield fd_path
    try:
        fd_path.unlink(missing_ok=True)
    except Exception:
        pass


class TestDomainOf:
    def test_extracts_domain(self):
        assert cache.domain_of("https://example.com/path?q=1") == "example.com"

    def test_strips_port(self):
        assert cache.domain_of("https://example.com:8080/path") == "example.com"

    def test_lowercases(self):
        assert cache.domain_of("https://EXAMPLE.com/") == "example.com"

    def test_handles_garbage_gracefully(self):
        # Should not raise even on a non-URL input.
        assert cache.domain_of("not a url") is not None


class TestRecordAndQuery:
    def test_record_and_get_arms(self, tmp_db):
        cache.record_outcome("https://example.com/a", "requests", True, db_path=tmp_db)
        cache.record_outcome("https://example.com/b", "requests", False, db_path=tmp_db)
        cache.record_outcome("https://example.com/c", "playwright", True, db_path=tmp_db)

        arms = cache.get_arms("example.com", db_path=tmp_db)
        by_tier = {a["tier"]: a for a in arms}
        assert by_tier["requests"]["successes"] == 1
        assert by_tier["requests"]["failures"] == 1
        assert by_tier["playwright"]["successes"] == 1

    def test_distinct_proxy_and_fingerprint_are_separate_arms(self, tmp_db):
        cache.record_outcome("https://x.com/a", "requests", True, proxy_id="proxyA", db_path=tmp_db)
        cache.record_outcome("https://x.com/b", "requests", True, proxy_id="proxyB", db_path=tmp_db)
        arms = cache.get_arms("x.com", db_path=tmp_db)
        assert len(arms) == 2
        proxy_ids = {a["proxy_id"] for a in arms}
        assert proxy_ids == {"proxyA", "proxyB"}

    def test_unknown_domain_returns_empty(self, tmp_db):
        assert cache.get_arms("never-seen.example", db_path=tmp_db) == []

    def test_get_domain_stats_unknown(self, tmp_db):
        stats = cache.get_domain_stats("never-seen.example", db_path=tmp_db)
        assert stats["known"] is False

    def test_get_domain_stats_known(self, tmp_db):
        for _ in range(5):
            cache.record_outcome("https://good.com/a", "requests", True, latency_ms=100, db_path=tmp_db)
        cache.record_outcome("https://good.com/a", "playwright", True, latency_ms=2000, db_path=tmp_db)

        stats = cache.get_domain_stats("good.com", db_path=tmp_db)
        assert stats["known"] is True
        assert stats["total_attempts"] == 6
        assert stats["best_arm"]["tier"] == "requests"  # both succeed 100%, but requests has lower latency... actually tie on rate
        assert stats["overall_success_rate"] == 1.0

    def test_reset_domain(self, tmp_db):
        cache.record_outcome("https://x.com/a", "requests", True, db_path=tmp_db)
        assert cache.get_arms("x.com", db_path=tmp_db) != []
        removed = cache.reset_domain("x.com", db_path=tmp_db)
        assert removed == 1
        assert cache.get_arms("x.com", db_path=tmp_db) == []

    def test_all_known_domains(self, tmp_db):
        cache.record_outcome("https://a.com/x", "requests", True, db_path=tmp_db)
        cache.record_outcome("https://b.com/x", "requests", True, db_path=tmp_db)
        domains = cache.all_known_domains(db_path=tmp_db)
        assert set(domains) == {"a.com", "b.com"}

    def test_export_all(self, tmp_db):
        cache.record_outcome("https://a.com/x", "requests", True, db_path=tmp_db)
        export = cache.export_all(db_path=tmp_db)
        assert export["domain_count"] == 1
        assert "a.com" in export["domains"]


class TestBanditChoosesStrategy:
    def test_no_history_returns_default(self, tmp_db):
        choice = bandit.choose_strategy("https://never-seen.example/page", db_path=tmp_db)
        assert choice["source"] == "default"
        assert choice["tier"] == bandit.DEFAULT_TIER_ORDER[0]

    def test_too_little_history_returns_default(self, tmp_db):
        bandit.record("https://x.com/a", "requests", True, db_path=tmp_db)
        choice = bandit.choose_strategy("https://x.com/b", db_path=tmp_db)
        assert choice["source"] == "default"  # below MIN_ATTEMPTS_BEFORE_BANDIT

    def test_sufficient_history_uses_bandit(self, tmp_db):
        for _ in range(10):
            bandit.record("https://x.com/a", "requests", True, db_path=tmp_db)
        choice = bandit.choose_strategy("https://x.com/b", db_path=tmp_db)
        assert choice["source"] == "bandit"
        assert choice["tier"] == "requests"

    def test_strongly_favors_reliable_arm_over_unreliable_one(self, tmp_db):
        # requests: 20/20 success. playwright: 2/20 success.
        for _ in range(20):
            bandit.record("https://x.com/a", "requests", True, db_path=tmp_db)
        for i in range(20):
            bandit.record("https://x.com/a", "playwright", i < 2, db_path=tmp_db)

        # Sample many times -- the reliable arm should win the overwhelming majority.
        wins = {"requests": 0, "playwright": 0}
        for _ in range(200):
            choice = bandit.choose_strategy(
                "https://x.com/b",
                available_tiers=["requests", "playwright"],
                db_path=tmp_db,
            )
            wins[choice["tier"]] = wins.get(choice["tier"], 0) + 1
        assert wins["requests"] > wins["playwright"] * 3

    def test_restricts_to_available_proxies(self, tmp_db):
        bandit.record("https://x.com/a", "requests", True, proxy_id="gone-proxy", db_path=tmp_db)
        for _ in range(10):
            bandit.record("https://x.com/a", "requests", True, proxy_id="gone-proxy", db_path=tmp_db)
        choice = bandit.choose_strategy(
            "https://x.com/b", available_proxies=["direct"], db_path=tmp_db,
        )
        # 'gone-proxy' arm should be filtered out since it's not in available_proxies;
        # falls back to default since no usable arm has enough history.
        assert choice["proxy_id"] == "direct"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
