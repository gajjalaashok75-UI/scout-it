"""Tests for scout_it.retry_classifier and scout_it.response_cache."""
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from scout_it import retry_classifier as rc
from scout_it import response_cache as rcache


class TestClassifyStatus:
    def test_transient_codes(self):
        for code in [408, 429, 500, 502, 503, 504]:
            assert rc.classify_status(code) == "transient"

    def test_permanent_codes(self):
        for code in [400, 401, 403, 404, 410, 451]:
            assert rc.classify_status(code) == "permanent"

    def test_success_codes(self):
        assert rc.classify_status(200) == "success"
        assert rc.classify_status(201) == "success"

    def test_unlisted_4xx_defaults_permanent(self):
        assert rc.classify_status(418) == "permanent"

    def test_unlisted_5xx_defaults_transient(self):
        assert rc.classify_status(599) == "transient"


class TestClassifyException:
    def test_connection_error_is_transient(self):
        class ConnectionError(Exception):
            pass
        assert rc.classify_exception(ConnectionError("x")) == "transient"

    def test_random_exception_defaults_permanent(self):
        class SomeWeirdError(Exception):
            pass
        assert rc.classify_exception(SomeWeirdError("x")) == "permanent"


class TestRetryAfterParsing:
    def test_parses_seconds(self):
        assert rc.parse_retry_after({"Retry-After": "30"}) == 30.0

    def test_parses_http_date(self):
        from email.utils import format_datetime
        from datetime import datetime, timedelta, timezone
        future = datetime.now(timezone.utc) + timedelta(seconds=10)
        header = {"Retry-After": format_datetime(future, usegmt=True)}
        wait = rc.parse_retry_after(header)
        assert wait is not None
        assert 5 <= wait <= 15

    def test_missing_header_returns_none(self):
        assert rc.parse_retry_after({}) is None

    def test_garbage_value_returns_none(self):
        assert rc.parse_retry_after({"Retry-After": "not-a-value"}) is None


class TestRateLimitReset:
    def test_parses_future_timestamp(self):
        future_ts = time.time() + 20
        wait = rc.parse_rate_limit_reset({"X-RateLimit-Reset": str(future_ts)})
        assert wait is not None
        assert 15 <= wait <= 25

    def test_missing_returns_none(self):
        assert rc.parse_rate_limit_reset({}) is None


class TestComputeWaitSeconds:
    def test_prefers_retry_after_over_backoff(self):
        wait = rc.compute_wait_seconds({"Retry-After": "5"}, attempt=3, base_backoff=10)
        assert wait == 5.0

    def test_falls_back_to_exponential_backoff(self):
        wait = rc.compute_wait_seconds({}, attempt=2, base_backoff=1.5)
        assert wait == 1.5 * 3

    def test_caps_at_max_wait(self):
        wait = rc.compute_wait_seconds({"Retry-After": "9999"}, attempt=0, max_wait=60)
        assert wait == 60


class TestClassifyAttempt:
    def test_transient_status_should_retry(self):
        result = rc.classify_attempt(status_code=503)
        assert result["classification"] == "transient"
        assert result["should_retry"] is True
        assert result["wait_seconds"] is not None

    def test_permanent_status_should_not_retry(self):
        result = rc.classify_attempt(status_code=404)
        assert result["classification"] == "permanent"
        assert result["should_retry"] is False
        assert result["wait_seconds"] is None


@pytest.fixture
def tmp_cache_dir():
    d = Path(tempfile.mkdtemp())
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


class TestResponseCache:
    def test_set_and_get(self, tmp_cache_dir):
        rcache.set("https://example.com/a", "hello world", content_type="web", cache_dir=tmp_cache_dir)
        entry = rcache.get("https://example.com/a", cache_dir=tmp_cache_dir)
        assert entry is not None
        assert entry["content"] == "hello world"
        assert entry["stale"] is False

    def test_get_miss_returns_none(self, tmp_cache_dir):
        assert rcache.get("https://never-cached.example/x", cache_dir=tmp_cache_dir) is None

    def test_expired_entry_not_returned_by_get(self, tmp_cache_dir):
        rcache.set("https://example.com/a", "content", ttl_seconds=0, cache_dir=tmp_cache_dir)
        time.sleep(0.05)
        assert rcache.get("https://example.com/a", cache_dir=tmp_cache_dir) is None

    def test_get_stale_returns_expired_entry_with_flag(self, tmp_cache_dir):
        rcache.set("https://example.com/a", "content", ttl_seconds=0, cache_dir=tmp_cache_dir)
        time.sleep(0.05)
        entry = rcache.get_stale("https://example.com/a", cache_dir=tmp_cache_dir)
        assert entry is not None
        assert entry["content"] == "content"
        assert entry["stale"] is True

    def test_content_hash_dedup_detects_unchanged_content(self, tmp_cache_dir):
        r1 = rcache.set("https://example.com/a", "same content", cache_dir=tmp_cache_dir)
        assert r1["content_changed"] is True
        r2 = rcache.set("https://example.com/a", "same content", cache_dir=tmp_cache_dir)
        assert r2["content_changed"] is False

    def test_content_hash_dedup_detects_changed_content(self, tmp_cache_dir):
        rcache.set("https://example.com/a", "version 1", cache_dir=tmp_cache_dir)
        r2 = rcache.set("https://example.com/a", "version 2", cache_dir=tmp_cache_dir)
        assert r2["content_changed"] is True

    def test_clear_removes_entry(self, tmp_cache_dir):
        rcache.set("https://example.com/a", "content", cache_dir=tmp_cache_dir)
        assert rcache.clear("https://example.com/a", cache_dir=tmp_cache_dir) is True
        assert rcache.get("https://example.com/a", cache_dir=tmp_cache_dir) is None

    def test_clear_all(self, tmp_cache_dir):
        rcache.set("https://a.com/x", "1", cache_dir=tmp_cache_dir)
        rcache.set("https://b.com/x", "2", cache_dir=tmp_cache_dir)
        removed = rcache.clear_all(cache_dir=tmp_cache_dir)
        assert removed == 2

    def test_stats(self, tmp_cache_dir):
        rcache.set("https://a.com/x", "content", cache_dir=tmp_cache_dir)
        s = rcache.stats(cache_dir=tmp_cache_dir)
        assert s["entry_count"] == 1
        assert s["total_size_bytes"] > 0

    def test_content_type_ttl_defaults_differ(self, tmp_cache_dir):
        rcache.set("https://a.com/news", "x", content_type="news", cache_dir=tmp_cache_dir)
        rcache.set("https://a.com/static", "x", content_type="static", cache_dir=tmp_cache_dir)
        news_entry = rcache.get("https://a.com/news", cache_dir=tmp_cache_dir)
        static_entry = rcache.get("https://a.com/static", cache_dir=tmp_cache_dir)
        assert news_entry["ttl_seconds"] < static_entry["ttl_seconds"]


class TestFetchResilientWiring:
    """Integration tests for fetch_resilient's wiring of retry_classifier,
    header_profiles, proxy_pool, strategy_cache, and the Tier 4
    alternate-source ladder -- the highest-risk change in this round since
    it touches the core fetch path every command depends on."""

    class _FakeResp:
        def __init__(self, status_code=200, text="content " * 40, url="http://x/final", headers=None):
            self.status_code = status_code
            self.text = text
            self.url = url
            self.headers = headers or {}

    class _FakeSession:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = []

        def get(self, url, **kwargs):
            self.calls.append(kwargs)
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

    def test_retry_after_header_respected_over_backoff(self):
        import time
        import scout_it.extraction as ext
        sess = self._FakeSession([
            self._FakeResp(429, "rate limited", headers={"Retry-After": "0"}),
            self._FakeResp(200, "good content " * 40),
        ])
        start = time.time()
        out = ext.fetch_resilient("http://example.com", session=sess, max_retries=3,
                                    enable_js_fallback=False, enable_strategy_cache=False)
        elapsed = time.time() - start
        assert out["status"] == "success"
        assert elapsed < 1.0

    def test_permanent_status_short_circuits_tier1(self):
        import scout_it.extraction as ext
        sess = self._FakeSession([self._FakeResp(404, "not found")])
        out = ext.fetch_resilient("http://example.com", session=sess, max_retries=3,
                                    enable_js_fallback=False, enable_strategy_cache=False)
        assert out["status"] == "failed"
        assert len(sess.responses) == 0  # only 1 attempt made, not 3

    def test_proxy_pool_transparent_noop_when_unconfigured(self):
        import os
        import scout_it.extraction as ext
        os.environ.pop("PROXY_LIST", None)
        sess = self._FakeSession([self._FakeResp(200, "good content " * 40)])
        out = ext.fetch_resilient("http://example.com", session=sess, max_retries=1,
                                    enable_js_fallback=False, enable_strategy_cache=False)
        assert out["status"] == "success"
        assert sess.calls[0].get("proxies") is None

    def test_header_profile_bundle_used_not_bare_user_agent(self):
        import scout_it.extraction as ext
        sess = self._FakeSession([self._FakeResp(200, "good content " * 40)])
        ext.fetch_resilient("http://example.com", session=sess, max_retries=1,
                              enable_js_fallback=False, enable_strategy_cache=False)
        headers_used = sess.calls[0]["headers"]
        assert "User-Agent" in headers_used
        assert "Accept-Language" in headers_used

    def test_alternate_source_ladder_recovers_via_amp(self, tmp_strategy_db):
        import scout_it.extraction as ext

        class SmartSession:
            def get(self, url, **kwargs):
                if "/amp" in url or "output=amp" in url:
                    return TestFetchResilientWiring._FakeResp(200, "amp variant content " * 30, url)
                raise Exception("connection refused")

        out = ext.fetch_resilient(
            "https://news-site.test/article", session=SmartSession(), max_retries=1,
            enable_js_fallback=False, enable_alternate_source=True, enable_strategy_cache=False,
        )
        assert out["status"] == "success"
        assert out["tier"] == "alternate-source"
        assert out["alternate_source_rung"] == "amp"

    def test_alternate_source_ladder_disabled_by_default(self):
        import scout_it.extraction as ext

        class AlwaysFailsSession:
            def get(self, url, **kwargs):
                raise Exception("connection refused")

        out = ext.fetch_resilient(
            "https://always-fails.test/article", session=AlwaysFailsSession(), max_retries=1,
            enable_js_fallback=False, enable_strategy_cache=False,
        )
        assert out["status"] == "failed"
        assert "alternate_source_rung" not in out

    def test_strategy_cache_records_real_outcomes(self, tmp_strategy_db):
        import scout_it.extraction as ext
        import scout_it.strategy_cache as sc

        class OkSession:
            def get(self, url, **kwargs):
                return TestFetchResilientWiring._FakeResp(200, "content " * 40, url)

        out = ext.fetch_resilient("https://recorded-site.test/page", session=OkSession(), max_retries=1,
                                    enable_js_fallback=False, enable_strategy_cache=True)
        assert out["status"] == "success"
        arms = sc.get_arms("recorded-site.test", db_path=tmp_strategy_db)
        assert len(arms) == 1
        assert arms[0]["tier"] == "requests"
        assert arms[0]["successes"] == 1


    def test_dns_fallback_recovers_dns_looking_failure(self):
        import scout_it.extraction as ext

        class DnsFailThenIpSucceedsSession:
            def get(self, url, **kwargs):
                if "1.2.3.4" in url:
                    return TestFetchResilientWiring._FakeResp(200, "recovered via dns fallback " * 20)
                raise Exception("Temporary failure in name resolution")

        with mock.patch("scout_it.dns_resilience.build_resolved_url_and_host_header",
                         return_value={"resolved_url": "http://1.2.3.4/page", "host_header": "dns-fail.test"}):
            out = ext.fetch_resilient(
                "http://dns-fail.test/page", session=DnsFailThenIpSucceedsSession(), max_retries=1,
                enable_js_fallback=False, enable_strategy_cache=False,
            )
        assert out["status"] == "success"
        assert out["final_url"] == "http://dns-fail.test/page"  # reports the ORIGINAL url, not the raw IP

    def test_dns_fallback_disabled_does_not_attempt_doh(self):
        import scout_it.extraction as ext

        class AlwaysDnsFailSession:
            def get(self, url, **kwargs):
                raise Exception("Temporary failure in name resolution")

        with mock.patch("scout_it.dns_resilience.build_resolved_url_and_host_header") as mock_doh:
            out = ext.fetch_resilient(
                "http://dns-fail.test/page", session=AlwaysDnsFailSession(), max_retries=1,
                enable_js_fallback=False, enable_strategy_cache=False, enable_dns_fallback=False,
            )
            mock_doh.assert_not_called()
        assert out["status"] == "failed"

    def test_tls_impersonate_tier_recovers_blocked_tier1(self):
        import scout_it.extraction as ext

        class AlwaysBlockedSession:
            def get(self, url, **kwargs):
                return TestFetchResilientWiring._FakeResp(403, "blocked")

        fake_curl_module = mock.MagicMock()
        fake_curl_resp = mock.Mock(status_code=200, text="tls impersonation content " * 20, url="https://tls-test.example/page")
        fake_curl_module.requests.get.return_value = fake_curl_resp

        with mock.patch("scout_it.tls_fingerprint.is_available", return_value=True), \
             mock.patch.dict("sys.modules", {"curl_cffi": fake_curl_module, "curl_cffi.requests": fake_curl_module.requests}):
            out = ext.fetch_resilient(
                "https://tls-test.example/page", session=AlwaysBlockedSession(), max_retries=1,
                enable_js_fallback=False, enable_strategy_cache=False, enable_tls_impersonate=True,
            )
        assert out["status"] == "success"
        assert out["tier"] == "tls-impersonate"

    def test_tls_impersonate_disabled_by_default(self):
        import scout_it.extraction as ext

        class AlwaysBlockedSession:
            def get(self, url, **kwargs):
                return TestFetchResilientWiring._FakeResp(403, "blocked")

        with mock.patch("scout_it.tls_fingerprint.is_available", return_value=True) as mock_available:
            ext.fetch_resilient(
                "https://tls-test.example/page", session=AlwaysBlockedSession(), max_retries=1,
                enable_js_fallback=False, enable_strategy_cache=False,  # enable_tls_impersonate left at default False
            )
            mock_available.assert_not_called()

    def test_persistent_profile_used_for_tier2_when_enabled(self):
        import scout_it.extraction as ext

        with mock.patch("playwright.sync_api.sync_playwright") as mock_pw_ctor, \
             mock.patch("scout_it.browser_profile.launch_persistent") as mock_launch_persistent:
            fake_page = mock.Mock()
            fake_page.content.return_value = "<html>" + ("persistent profile content " * 30) + "</html>"
            fake_page.url = "https://profile-test.example/page"
            fake_context = mock.Mock()
            fake_context.new_page.return_value = fake_page
            mock_launch_persistent.return_value = fake_context

            fake_pw = mock.Mock()
            fake_pw.__enter__ = mock.Mock(return_value=fake_pw)
            fake_pw.__exit__ = mock.Mock(return_value=False)
            mock_pw_ctor.return_value = fake_pw

            out = ext.fetch_resilient(
                "https://profile-test.example/page", force_js=True, max_retries=1,
                enable_strategy_cache=False, enable_persistent_profile=True, browser_profile_name="mytest",
            )
            assert out["status"] == "success"
            assert out["tier"] == "playwright"
            mock_launch_persistent.assert_called_once()
            assert "mytest" in str(mock_launch_persistent.call_args)
            fake_context.close.assert_called_once()

    def test_bandit_reordering_skips_tier1_for_playwright_favored_domain(self, tmp_strategy_db):
        import scout_it.extraction as ext
        import scout_it.strategy_cache as sc

        for _ in range(10):
            sc.record_outcome("https://bandit-test.example/page", "playwright", True, db_path=tmp_strategy_db)
        for _ in range(10):
            sc.record_outcome("https://bandit-test.example/page", "requests", False, db_path=tmp_strategy_db)

        class ShouldNeverBeCalledSession:
            def get(self, url, **kwargs):
                raise AssertionError("tier1 (requests) should have been skipped by the bandit!")

        with mock.patch("playwright.sync_api.sync_playwright") as mock_pw_ctor:
            fake_page = mock.Mock()
            fake_page.content.return_value = "<html>" + ("playwright rendered content " * 30) + "</html>"
            fake_page.url = "https://bandit-test.example/page"
            fake_browser = mock.Mock()
            fake_browser.new_page.return_value = fake_page
            fake_pw = mock.Mock()
            fake_pw.chromium.launch.return_value = fake_browser
            fake_pw.__enter__ = mock.Mock(return_value=fake_pw)
            fake_pw.__exit__ = mock.Mock(return_value=False)
            mock_pw_ctor.return_value = fake_pw

            out = ext.fetch_resilient(
                "https://bandit-test.example/page", session=ShouldNeverBeCalledSession(),
                max_retries=1, enable_strategy_cache=False, enable_bandit=True,
            )
        assert out["status"] == "success"
        assert out["tier"] == "playwright"

    def test_bandit_disabled_by_default_uses_normal_tier1(self, tmp_strategy_db):
        import scout_it.extraction as ext
        import scout_it.strategy_cache as sc

        for _ in range(10):
            sc.record_outcome("https://bandit-off-test.example/page", "playwright", True, db_path=tmp_strategy_db)

        sess = self._FakeSession([self._FakeResp(200, "normal tier1 content " * 30)])
        out = ext.fetch_resilient(
            "https://bandit-off-test.example/page", session=sess, max_retries=1,
            enable_js_fallback=False, enable_strategy_cache=False,  # enable_bandit left at default False
        )
        assert out["status"] == "success"
        assert out["tier"] == "requests"


@pytest.fixture
def tmp_strategy_db():
    import tempfile
    from unittest import mock as _mock
    from pathlib import Path as _Path
    import scout_it.strategy_cache as sc
    db = _Path(tempfile.mkdtemp()) / "test.db"
    with _mock.patch.object(sc, "DB_PATH", db):
        yield db


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
