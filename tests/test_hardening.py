"""Tests for scout_it.header_profiles, scout_it.canary_probe, scout_it.proxy_pool."""
import os
from unittest import mock

import pytest

from scout_it import header_profiles as hp
from scout_it import canary_probe as canary
from scout_it import proxy_pool as pp


class TestHeaderProfiles:
    def test_get_profile_returns_full_bundle(self):
        profile = hp.get_profile("chrome-windows")
        assert "User-Agent" in profile
        assert "Accept-Language" in profile
        assert "Chrome" in profile["User-Agent"]

    def test_random_profile_when_no_name(self):
        profile = hp.get_profile()
        assert "User-Agent" in profile

    def test_unknown_name_falls_back_to_random(self):
        profile = hp.get_profile("nonexistent-profile-xyz")
        assert "User-Agent" in profile

    def test_profiles_are_internally_consistent_bundles(self):
        """Each profile's User-Agent browser family should match its
        sec-ch-ua field where present (never mixed)."""
        for name in hp.profile_names():
            profile = hp.get_profile(name)
            if "sec-ch-ua" in profile:
                if "Firefox" in profile["User-Agent"]:
                    assert False, "Firefox profile shouldn't have sec-ch-ua (not a Chromium header)"
                if "Edg/" in profile["User-Agent"]:
                    assert "Edge" in profile["sec-ch-ua"]
                elif "Chrome" in profile["User-Agent"]:
                    assert "Chrome" in profile["sec-ch-ua"] or "Chromium" in profile["sec-ch-ua"]

    def test_returned_dict_is_a_copy_not_shared_reference(self):
        p1 = hp.get_profile("chrome-windows")
        p1["User-Agent"] = "tampered"
        p2 = hp.get_profile("chrome-windows")
        assert p2["User-Agent"] != "tampered"

    def test_get_profile_with_name_includes_name(self):
        result = hp.get_profile_with_name("safari-macos")
        assert result["name"] == "safari-macos"
        assert "headers" in result
        assert "name" not in result["headers"]


class TestCanaryProbe:
    def test_reachable_and_not_blocked(self):
        fake_resp = mock.Mock(status_code=200)
        with mock.patch("scout_it.canary_probe.requests.head", return_value=fake_resp):
            result = canary.probe("https://example.com")
            assert result["reachable"] is True
            assert result["looks_blocked"] is False
            assert result["status_code"] == 200

    def test_403_looks_blocked(self):
        fake_resp = mock.Mock(status_code=403)
        with mock.patch("scout_it.canary_probe.requests.head", return_value=fake_resp):
            result = canary.probe("https://example.com")
            assert result["looks_blocked"] is True

    def test_head_failure_falls_back_to_ranged_get(self):
        fake_get_resp = mock.Mock(status_code=200, text="normal page content")
        with mock.patch("scout_it.canary_probe.requests.head", side_effect=Exception("HEAD not allowed")), \
             mock.patch("scout_it.canary_probe.requests.get", return_value=fake_get_resp):
            result = canary.probe("https://example.com")
            assert result["reachable"] is True
            assert result["method"] == "GET"

    def test_challenge_page_signature_detected_via_get(self):
        fake_get_resp = mock.Mock(status_code=200, text="Checking your browser before accessing example.com")
        with mock.patch("scout_it.canary_probe.requests.head", side_effect=Exception("no head")), \
             mock.patch("scout_it.canary_probe.requests.get", return_value=fake_get_resp):
            result = canary.probe("https://example.com")
            assert result["looks_blocked"] is True

    def test_total_unreachability_reported_not_raised(self):
        with mock.patch("scout_it.canary_probe.requests.head", side_effect=Exception("dns fail")), \
             mock.patch("scout_it.canary_probe.requests.get", side_effect=Exception("dns fail")):
            result = canary.probe("https://nonexistent.invalid")
            assert result["reachable"] is False
            assert "error" in result

    def test_should_trust_cached_strategy_true_when_fine(self):
        fake_resp = mock.Mock(status_code=200)
        with mock.patch("scout_it.canary_probe.requests.head", return_value=fake_resp):
            assert canary.should_trust_cached_strategy("https://example.com") is True

    def test_should_trust_cached_strategy_false_when_blocked(self):
        fake_resp = mock.Mock(status_code=403)
        with mock.patch("scout_it.canary_probe.requests.head", return_value=fake_resp):
            assert canary.should_trust_cached_strategy("https://example.com") is False

    def test_unreachable_probe_does_not_invalidate_cache(self):
        with mock.patch("scout_it.canary_probe.requests.head", side_effect=Exception("x")), \
             mock.patch("scout_it.canary_probe.requests.get", side_effect=Exception("x")):
            # Can't tell either way -- shouldn't force re-exploration over noise.
            assert canary.should_trust_cached_strategy("https://example.com") is True


class TestProxyPool:
    def test_no_proxies_configured_degrades_to_direct(self):
        pool = pp.ProxyPool(proxies=[])
        assert pool.configured is False
        result = pool.get()
        assert result["proxy_id"] == pp.DIRECT
        assert result["requests_proxies"] is None

    def test_configured_pool_rotates(self):
        pool = pp.ProxyPool(proxies=["http://u:p@proxy1.example:8080", "http://u:p@proxy2.example:8080"])
        assert pool.configured is True
        result = pool.get()
        assert result["proxy_id"] in ("proxy1.example:8080", "proxy2.example:8080")
        assert result["requests_proxies"] is not None

    def test_mark_failed_benches_proxy_temporarily(self):
        pool = pp.ProxyPool(proxies=["http://u:p@onlyproxy.example:8080"])
        result = pool.get()
        pid = result["proxy_id"]
        pool.mark_failed(pid, cooldown_seconds=100)
        # Only proxy is now benched -- should degrade to direct rather than
        # returning an unhealthy proxy or raising.
        result2 = pool.get()
        assert result2["proxy_id"] == pp.DIRECT

    def test_mark_success_clears_cooldown(self):
        pool = pp.ProxyPool(proxies=["http://u:p@onlyproxy.example:8080"])
        result = pool.get()
        pid = result["proxy_id"]
        pool.mark_failed(pid, cooldown_seconds=100)
        pool.mark_success(pid)
        result2 = pool.get()
        assert result2["proxy_id"] == pid

    def test_available_ids_always_includes_direct(self):
        pool = pp.ProxyPool(proxies=["http://u:p@proxy1.example:8080"])
        ids = pool.available_ids()
        assert pp.DIRECT in ids

    def test_preferred_id_honored_when_healthy(self):
        pool = pp.ProxyPool(proxies=["http://u:p@proxy1.example:8080", "http://u:p@proxy2.example:8080"])
        result = pool.get(preferred_id="proxy1.example:8080")
        assert result["proxy_id"] == "proxy1.example:8080"

    def test_credentials_not_leaked_into_proxy_id(self):
        pool = pp.ProxyPool(proxies=["http://secretuser:secretpass@proxy1.example:8080"])
        result = pool.get()
        assert "secretuser" not in result["proxy_id"]
        assert "secretpass" not in result["proxy_id"]

    def test_default_pool_degrades_gracefully_with_no_env_var(self):
        os.environ.pop("PROXY_LIST", None)
        pool = pp.get_default_pool()
        assert pool.configured is False
        result = pool.get()
        assert result["proxy_id"] == pp.DIRECT


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
