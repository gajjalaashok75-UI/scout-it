"""Tests for scout_it.tls_fingerprint, scout_it.dns_resilience, scout_it.browser_profile.

None of these can be fully validated without live network/curl_cffi/a real
browser farm -- see each module's docstring. These tests cover the parts
that ARE deterministically testable offline: graceful-degradation paths,
URL/host-header construction, caching behavior, and error handling.
"""
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from scout_it import tls_fingerprint as tls
from scout_it import dns_resilience as dns
from scout_it import browser_profile as bp


class TestTlsFingerprint:
    def test_is_available_false_when_not_installed(self):
        try:
            import curl_cffi  # noqa: F401
            pytest.skip("curl_cffi is installed -- cannot test the not-installed path")
        except ImportError:
            pass
        assert tls.is_available() is False

    def test_fetch_reports_clear_error_when_unavailable(self):
        try:
            import curl_cffi  # noqa: F401
            pytest.skip("curl_cffi is installed -- cannot test the not-installed path")
        except ImportError:
            pass
        result = tls.fetch("https://example.com")
        assert result["status"] == "failed"
        assert "curl_cffi" in result["error"]
        assert "pip install" in result["error"]

    def test_fetch_never_raises_even_when_unavailable(self):
        try:
            result = tls.fetch("https://example.com")
        except Exception as e:
            pytest.fail(f"fetch() raised instead of returning a failure dict: {e}")
        assert isinstance(result, dict)

    def test_available_profiles_nonempty(self):
        assert len(tls.available_profiles()) > 0
        assert tls.DEFAULT_PROFILE in tls.available_profiles()

    def test_fetch_success_path_with_mocked_curl_cffi(self):
        fake_module = mock.MagicMock()
        fake_resp = mock.Mock(status_code=200, text="page content", url="https://example.com/final")
        fake_module.requests.get.return_value = fake_resp

        with mock.patch.object(tls, "is_available", return_value=True), \
             mock.patch.dict("sys.modules", {"curl_cffi": fake_module, "curl_cffi.requests": fake_module.requests}):
            result = tls.fetch("https://example.com", impersonate="chrome124")
            assert result["status"] == "success"
            assert result["html"] == "page content"
            assert result["impersonate_profile"] == "chrome124"

    def test_fetch_handles_curl_cffi_exception_gracefully(self):
        fake_module = mock.MagicMock()
        fake_module.requests.get.side_effect = Exception("curl error 35")

        with mock.patch.object(tls, "is_available", return_value=True), \
             mock.patch.dict("sys.modules", {"curl_cffi": fake_module, "curl_cffi.requests": fake_module.requests}):
            result = tls.fetch("https://example.com")
            assert result["status"] == "failed"
            assert "curl error 35" in result["error"]

    def test_unknown_impersonate_profile_falls_back_to_default(self):
        fake_module = mock.MagicMock()
        fake_resp = mock.Mock(status_code=200, text="ok", url="https://example.com")
        fake_module.requests.get.return_value = fake_resp

        with mock.patch.object(tls, "is_available", return_value=True), \
             mock.patch.dict("sys.modules", {"curl_cffi": fake_module, "curl_cffi.requests": fake_module.requests}):
            result = tls.fetch("https://example.com", impersonate="totally-made-up-browser")
            assert result["impersonate_profile"] == tls.DEFAULT_PROFILE


class TestDnsResilience:
    def setup_each(self):
        dns.clear_cache()

    def test_looks_like_dns_error_detects_common_markers(self):
        self.setup_each()
        assert dns.looks_like_dns_error(Exception("Temporary failure in name resolution")) is True
        assert dns.looks_like_dns_error(Exception("getaddrinfo failed")) is True

    def test_looks_like_dns_error_false_for_unrelated_errors(self):
        self.setup_each()
        assert dns.looks_like_dns_error(Exception("connection refused")) is False

    def test_resolve_via_doh_success(self):
        self.setup_each()
        fake_resp = mock.Mock(status_code=200)
        fake_resp.json.return_value = {"Answer": [{"type": 1, "data": "93.184.216.34"}]}
        with mock.patch("scout_it.dns_resilience.requests.get", return_value=fake_resp):
            ip = dns.resolve_via_doh("example.com")
            assert ip == "93.184.216.34"

    def test_resolve_via_doh_caches_result(self):
        self.setup_each()
        fake_resp = mock.Mock(status_code=200)
        fake_resp.json.return_value = {"Answer": [{"type": 1, "data": "1.2.3.4"}]}
        with mock.patch("scout_it.dns_resilience.requests.get", return_value=fake_resp) as mock_get:
            dns.resolve_via_doh("cached.example.com")
            dns.resolve_via_doh("cached.example.com")
            assert mock_get.call_count == 1

    def test_resolve_via_doh_returns_none_when_all_providers_fail(self):
        self.setup_each()
        with mock.patch("scout_it.dns_resilience.requests.get", side_effect=Exception("network down")):
            assert dns.resolve_via_doh("unreachable.example.com") is None

    def test_resolve_via_doh_skips_cname_records(self):
        self.setup_each()
        fake_resp = mock.Mock(status_code=200)
        fake_resp.json.return_value = {"Answer": [
            {"type": 5, "data": "cname-target.example.com"},
            {"type": 1, "data": "5.6.7.8"},
        ]}
        with mock.patch("scout_it.dns_resilience.requests.get", return_value=fake_resp):
            ip = dns.resolve_via_doh("aliased.example.com")
            assert ip == "5.6.7.8"

    def test_build_resolved_url_preserves_host_header(self):
        self.setup_each()
        with mock.patch.object(dns, "resolve_via_doh", return_value="9.9.9.9"):
            result = dns.build_resolved_url_and_host_header("https://example.com/path?q=1")
            assert result["host_header"] == "example.com"
            assert "9.9.9.9" in result["resolved_url"]
            assert "/path" in result["resolved_url"]

    def test_build_resolved_url_returns_none_on_doh_failure(self):
        self.setup_each()
        with mock.patch.object(dns, "resolve_via_doh", return_value=None):
            assert dns.build_resolved_url_and_host_header("https://example.com/") is None

    def test_resolve_with_system_fallback_uses_system_first(self):
        self.setup_each()
        with mock.patch("scout_it.dns_resilience.socket.gethostbyname", return_value="10.0.0.1") as mock_gethostbyname, \
             mock.patch.object(dns, "resolve_via_doh") as mock_doh:
            ip = dns.resolve_with_system_fallback("example.com")
            assert ip == "10.0.0.1"
            mock_doh.assert_not_called()

    def test_resolve_with_system_fallback_falls_back_to_doh(self):
        self.setup_each()
        with mock.patch("scout_it.dns_resilience.socket.gethostbyname", side_effect=Exception("dns fail")), \
             mock.patch.object(dns, "resolve_via_doh", return_value="11.11.11.11") as mock_doh:
            ip = dns.resolve_with_system_fallback("example.com")
            assert ip == "11.11.11.11"
            mock_doh.assert_called_once()


class TestBrowserProfile:
    def test_profile_path_sanitizes_name(self):
        path = bp.profile_path("my profile!@#$")
        assert "/" not in path.name
        assert "!" not in str(path)

    def test_profile_path_default(self):
        path = bp.profile_path()
        assert path.name == bp.DEFAULT_PROFILE_NAME

    def test_list_profiles_empty_when_no_dir(self):
        with mock.patch.object(bp, "PROFILES_DIR", Path(tempfile.mkdtemp()) / "nonexistent"):
            assert bp.list_profiles() == []

    def test_list_and_clear_profile(self):
        tmp_profiles_dir = Path(tempfile.mkdtemp())
        with mock.patch.object(bp, "PROFILES_DIR", tmp_profiles_dir):
            path = bp.profile_path("test-profile")
            path.mkdir(parents=True)
            (path / "cookies.db").write_text("fake cookie data")

            assert "test-profile" in bp.list_profiles()
            assert bp.profile_size_bytes("test-profile") > 0

            assert bp.clear_profile("test-profile") is True
            assert "test-profile" not in bp.list_profiles()

    def test_clear_nonexistent_profile_returns_false(self):
        with mock.patch.object(bp, "PROFILES_DIR", Path(tempfile.mkdtemp())):
            assert bp.clear_profile("never-existed") is False

    def test_launch_persistent_calls_playwright_correctly(self):
        fake_pw = mock.Mock()
        fake_context = mock.Mock()
        fake_pw.chromium.launch_persistent_context.return_value = fake_context

        with mock.patch.object(bp, "PROFILES_DIR", Path(tempfile.mkdtemp())):
            result = bp.launch_persistent(fake_pw, profile_name="test", headless=True)
            assert result is fake_context
            fake_pw.chromium.launch_persistent_context.assert_called_once()
            call_kwargs = fake_pw.chromium.launch_persistent_context.call_args[1]
            assert call_kwargs["headless"] is True
            assert "test" in call_kwargs["user_data_dir"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
