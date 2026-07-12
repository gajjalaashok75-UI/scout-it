#!/usr/bin/env python3
"""
🔒 TLS FINGERPRINT — optional browser-accurate TLS/JA3 impersonation
==========================================================================

**Needs live verification** — this wraps the optional `curl_cffi` package
(not a hard dependency; nothing else in this project breaks if it's
missing). I built this against curl_cffi's documented API but have no
network access in my build/test environment to confirm it actually behaves
as expected against a real anti-bot service. Please test this against a
real site that's been blocking you and report back what you see —
`fetch_resilient(..., tier="tls-impersonate")` in the result, or an error,
either way tells us what to fix.

**Why this exists**: `requests`/`urllib3` produce a TLS ClientHello with a
JA3 fingerprint that's trivially distinguishable from a real browser's, even
when the HTTP headers (User-Agent, Accept, etc. — see `header_profiles.py`)
are a perfect match. Some anti-bot systems fingerprint at the TLS layer
specifically because header-spoofing is so easy. `curl_cffi` uses a patched
libcurl that reproduces real browsers' actual TLS handshakes (cipher suite
order, extensions, ALPN, etc.), not just an HTTP header string.

Install: `pip install scout-it[tls-impersonate]` (adds `curl_cffi`).
"""

from typing import Any, Dict, List, Optional

# curl_cffi's impersonate profiles as of the versions I could find documented
# publicly (curl_cffi >= 0.6). If a future curl_cffi renames/drops one of
# these, curl_cffi itself will raise on the impersonate= kwarg -- caught and
# reported below rather than silently falling through, since a "worked" that
# actually silently downgraded to no impersonation would be worse than an
# honest error.
IMPERSONATE_PROFILES = [
    "chrome124", "chrome123", "chrome120", "chrome110", "chrome99",
    "edge101", "safari17_0", "safari15_5",
]
DEFAULT_PROFILE = "chrome124"


def is_available() -> bool:
    try:
        import curl_cffi  # noqa: F401
        return True
    except ImportError:
        return False


def fetch(
    url: str,
    timeout: int = 25,
    impersonate: str = DEFAULT_PROFILE,
    proxies: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """One attempt via curl_cffi's browser-TLS-impersonating client.

    Returns the same outcome shape as a single `fetch_resilient` tier
    attempt: ``{"html": str, "final_url": str, "status": "success"|"failed",
    "status_code": int|None, "error": str|None}``. Never raises -- any
    problem (including curl_cffi not being installed) comes back as
    ``status: "failed"`` with a clear ``error`` message, so callers can
    always safely try this tier and fall through to the next one.
    """
    if not is_available():
        return {
            "html": "", "final_url": url, "status": "failed", "status_code": None,
            "error": "curl_cffi not installed -- run: pip install scout-it[tls-impersonate]",
        }

    try:
        from curl_cffi import requests as cffi_requests
    except ImportError as e:
        return {"html": "", "final_url": url, "status": "failed", "status_code": None, "error": str(e)}

    profile = impersonate if impersonate in IMPERSONATE_PROFILES else DEFAULT_PROFILE

    try:
        # curl_cffi's requests-compatible API: get(url, impersonate=..., ...).
        # proxies here follows the same {"http": ..., "https": ...} shape as
        # `requests`, matching what proxy_pool.get() already returns.
        resp = cffi_requests.get(
            url,
            impersonate=profile,
            timeout=timeout,
            proxies=proxies,
            headers=headers,
            allow_redirects=True,
        )
        status_code = resp.status_code
        if status_code < 400:
            return {
                "html": resp.text, "final_url": str(resp.url), "status": "success",
                "status_code": status_code, "error": None, "impersonate_profile": profile,
            }
        return {
            "html": "", "final_url": url, "status": "failed", "status_code": status_code,
            "error": f"HTTP {status_code}",
        }
    except Exception as e:
        return {
            "html": "", "final_url": url, "status": "failed", "status_code": None,
            "error": f"{type(e).__name__}: {e}",
        }


def available_profiles() -> List[str]:
    return list(IMPERSONATE_PROFILES)
