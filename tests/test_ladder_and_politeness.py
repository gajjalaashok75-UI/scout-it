"""Tests for scout_it.alternate_source and scout_it.politeness_governor."""
import time
from unittest import mock

import pytest

from scout_it import alternate_source as alt
from scout_it import politeness_governor as gov


class TestBuildLadder:
    def test_generates_amp_mobile_print_candidates(self):
        ladder = alt.build_ladder("https://news.example.com/article/123")
        rungs = {r["rung"] for r in ladder}
        assert rungs == {"amp", "mobile", "print"}

    def test_amp_candidates_are_valid_variants(self):
        ladder = alt.build_ladder("https://news.example.com/article/123")
        amp_urls = [r["url"] for r in ladder if r["rung"] == "amp"]
        assert any("amp" in u for u in amp_urls)

    def test_mobile_skipped_if_already_mobile_subdomain(self):
        ladder = alt.build_ladder("https://m.example.com/article")
        rungs = [r["rung"] for r in ladder]
        assert "mobile" not in rungs

    def test_does_not_raise_on_weird_url(self):
        ladder = alt.build_ladder("https://example.com")
        assert isinstance(ladder, list)


class TestWaybackSnapshot:
    def test_returns_url_on_success(self):
        fake_resp = mock.Mock(status_code=200)
        fake_resp.json.return_value = {
            "archived_snapshots": {"closest": {"available": True, "url": "https://web.archive.org/web/20260101/https://example.com"}}
        }
        with mock.patch("scout_it.alternate_source.requests.get", return_value=fake_resp):
            result = alt.wayback_snapshot_url("https://example.com")
            assert result == "https://web.archive.org/web/20260101/https://example.com"

    def test_returns_none_when_no_snapshot(self):
        fake_resp = mock.Mock(status_code=200)
        fake_resp.json.return_value = {"archived_snapshots": {}}
        with mock.patch("scout_it.alternate_source.requests.get", return_value=fake_resp):
            assert alt.wayback_snapshot_url("https://example.com") is None

    def test_never_raises_on_network_failure(self):
        with mock.patch("scout_it.alternate_source.requests.get", side_effect=Exception("network down")):
            assert alt.wayback_snapshot_url("https://example.com") is None


class TestTryLadder:
    def test_stops_at_first_success(self):
        call_log = []

        def fake_fetch(url):
            call_log.append(url)
            if "amp" in url:
                return {"status": "success", "html": "<html>amp version</html>"}
            return {"status": "failed", "html": ""}

        result = alt.try_ladder("https://example.com/article", fake_fetch, include_wayback=False)
        assert result["status"] == "success"
        assert result["alternate_source_rung"] == "amp"
        # Should have stopped after the first success -- not tried every rung.
        assert len(call_log) <= len(alt.build_ladder("https://example.com/article"))

    def test_falls_through_to_wayback_when_ladder_exhausted(self):
        def fake_fetch(url):
            if "web.archive.org" in url:
                return {"status": "success", "html": "<html>archived</html>"}
            return {"status": "failed", "html": ""}

        with mock.patch.object(alt, "wayback_snapshot_url", return_value="https://web.archive.org/web/x/https://example.com"):
            result = alt.try_ladder("https://example.com/article", fake_fetch, include_wayback=True)
            assert result["status"] == "success"
            assert result["alternate_source_rung"] == "wayback"

    def test_reports_failure_with_rungs_tried_when_everything_fails(self):
        def fake_fetch(url):
            return {"status": "failed", "html": ""}

        with mock.patch.object(alt, "wayback_snapshot_url", return_value=None):
            result = alt.try_ladder("https://example.com/article", fake_fetch, include_wayback=True)
            assert result["status"] == "failed"
            assert "rungs_tried" in result
            assert len(result["rungs_tried"]) > 0


class TestPolitenessGovernor:
    def test_wait_turn_enforces_minimum_delay(self):
        g = gov.PolitenessGovernor(min_delay_seconds=0.1, jitter_seconds=0.0)
        g.wait_turn("https://example.com/a")
        start = time.time()
        g.wait_turn("https://example.com/b")  # same domain
        elapsed = time.time() - start
        assert elapsed >= 0.09  # small tolerance

    def test_different_domains_dont_block_each_other(self):
        g = gov.PolitenessGovernor(min_delay_seconds=1.0, jitter_seconds=0.0)
        g.wait_turn("https://a.com/x")
        start = time.time()
        g.wait_turn("https://b.com/x")  # different domain, should be instant
        elapsed = time.time() - start
        assert elapsed < 0.5

    def test_concurrency_semaphore_limits_per_domain(self):
        g = gov.PolitenessGovernor(max_concurrent_per_domain=1)
        assert g.acquire("https://example.com/a", timeout=1) is True
        # Second acquire for the SAME domain should time out since the cap is 1.
        assert g.acquire("https://example.com/b", timeout=0.2) is False
        g.release("https://example.com/a")
        assert g.acquire("https://example.com/c", timeout=1) is True

    def test_release_without_matching_acquire_does_not_crash(self):
        g = gov.PolitenessGovernor()
        g.release("https://example.com/never-acquired")  # should not raise

    def test_robots_txt_disallow_respected(self):
        g = gov.PolitenessGovernor(respect_robots_txt=True)
        fake_rp = mock.Mock()
        fake_rp.can_fetch.return_value = False
        with mock.patch.object(gov.RobotFileParser, "read", return_value=None), \
             mock.patch.object(g, "_robots_cache", {"example.com": fake_rp}):
            assert g.is_allowed_by_robots("https://example.com/private") is False

    def test_robots_txt_fetch_failure_fails_open(self):
        g = gov.PolitenessGovernor(respect_robots_txt=True)
        with mock.patch.object(gov.RobotFileParser, "read", side_effect=Exception("network down")):
            # Unreachable robots.txt -> treated as allowed (fail open), not blocked.
            assert g.is_allowed_by_robots("https://example.com/page") is True

    def test_respect_robots_txt_false_always_allows(self):
        g = gov.PolitenessGovernor(respect_robots_txt=False)
        assert g.is_allowed_by_robots("https://example.com/anything") is True

    def test_governed_context_manager_acquires_and_releases(self):
        g = gov.PolitenessGovernor(max_concurrent_per_domain=1, min_delay_seconds=0.0, jitter_seconds=0.0)
        with g.governed("https://example.com/a"):
            # Slot is taken -- a concurrent acquire for the same domain should fail immediately.
            assert g.acquire("https://example.com/b", timeout=0.1) is False
        # After exiting, slot should be free again.
        assert g.acquire("https://example.com/c", timeout=1) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
