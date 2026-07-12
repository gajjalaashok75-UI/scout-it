#!/usr/bin/env python3
"""
🌐 DNS RESILIENCE — DNS-over-HTTPS fallback when system DNS fails
========================================================================

**Needs live verification** — same caveat as `tls_fingerprint.py`: built
against the documented Cloudflare/Google DoH JSON APIs, no live network here
to confirm behavior against a real broken-DNS scenario. Please test and
report back.

Some networks (misconfigured local resolvers, some VPNs, some captive
portals) fail DNS resolution for a domain that's actually reachable by IP.
When a `fetch_resilient` attempt fails with what looks like a DNS-related
error, this resolves the hostname via a DNS-over-HTTPS provider (which
travels over regular HTTPS, so it works even when the system's UDP/TCP DNS
path doesn't) and retries directly against the resolved IP with the
original ``Host`` header preserved (so TLS SNI / virtual hosting still
works correctly).

No new dependency — DoH here just means an HTTPS GET to a JSON API,
handled by the `requests` library already in use everywhere else.
"""

import socket
import threading
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

import requests

DOH_PROVIDERS = [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
]

_cache_lock = threading.Lock()
_resolution_cache: Dict[str, Any] = {}  # hostname -> {"ip": str, "resolved_at": float}
_CACHE_TTL_SECONDS = 300


def looks_like_dns_error(exc: Exception) -> bool:
    """Heuristic: does this exception look like a DNS resolution failure
    specifically, as opposed to some other connection problem? Checked
    against exception message text since the underlying exception classes
    across requests/urllib3/socket for this vary by platform and Python
    version."""
    text = str(exc).lower()
    markers = (
        "name or service not known", "nodename nor servname",
        "temporary failure in name resolution", "getaddrinfo failed",
        "name resolution", "dns lookup failed",
    )
    return any(m in text for m in markers)


def resolve_via_doh(hostname: str, timeout: int = 5) -> Optional[str]:
    """Resolve *hostname* to an IPv4 address via DNS-over-HTTPS. Returns
    None if every provider fails (never raises). Cached in-memory for
    ``_CACHE_TTL_SECONDS`` to avoid repeat lookups within a run."""
    with _cache_lock:
        cached = _resolution_cache.get(hostname)
        if cached is not None and (time.time() - cached["resolved_at"]) < _CACHE_TTL_SECONDS:
            return cached["ip"]

    for provider in DOH_PROVIDERS:
        try:
            resp = requests.get(
                provider,
                params={"name": hostname, "type": "A"},
                headers={"Accept": "application/dns-json"},
                timeout=timeout,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            answers = data.get("Answer", [])
            for answer in answers:
                # Type 1 = A record (IPv4). Skip CNAME (type 5) etc.
                if answer.get("type") == 1:
                    ip = answer.get("data")
                    if ip:
                        with _cache_lock:
                            _resolution_cache[hostname] = {"ip": ip, "resolved_at": time.time()}
                        return ip
        except Exception:
            continue
    return None


def resolve_with_system_fallback(hostname: str, timeout: int = 5) -> Optional[str]:
    """Try the system resolver first (fast, normal path); only fall back to
    DoH if that fails. This is the entry point ``fetch_resilient`` should
    use -- DoH is a fallback, not a replacement for normal DNS."""
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return resolve_via_doh(hostname, timeout=timeout)


def build_resolved_url_and_host_header(url: str, timeout: int = 5) -> Optional[Dict[str, str]]:
    """For a URL whose hostname failed normal resolution, resolve via DoH
    and return a dict with a resolved-IP URL plus the ``Host`` header
    needed to preserve correct TLS SNI / virtual-hosting behavior:

        {"resolved_url": "https://1.2.3.4/path", "host_header": "example.com"}

    Returns None if DoH resolution also fails.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return None

    ip = resolve_via_doh(hostname, timeout=timeout)
    if not ip:
        return None

    port_part = f":{parsed.port}" if parsed.port else ""
    netloc = f"{ip}{port_part}"
    resolved = parsed._replace(netloc=netloc)

    return {
        "resolved_url": urlunparse(resolved),
        "host_header": hostname,
    }


def clear_cache() -> None:
    with _cache_lock:
        _resolution_cache.clear()
