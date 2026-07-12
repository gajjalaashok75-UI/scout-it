#!/usr/bin/env python3
"""
💾 RESPONSE CACHE — disk-backed fetch cache with stale-if-error
======================================================================

The fastest and most polite request is the one you don't have to make at
all, and the most resilient failure mode is "return the last good answer
with a clear staleness flag" rather than nothing.

Cache files live under ``.scout-it/cache/`` (matching the existing
``.scout-it/`` directory convention already used for credentials and the
strategy cache), keyed by a hash of the URL (+ relevant query params).

- ``get(url)`` — fresh hit only (respects TTL); returns None on miss/expired
- ``get_stale(url)`` — returns the cached entry regardless of TTL, for the
  stale-if-error path, with an explicit ``stale: True`` marker
- ``set(url, content, content_type)`` — TTL is chosen per *content_type*
  (news articles vs. static reference pages have very different freshness
  needs)
- Content-hash dedup: ``set()`` reports back if it wrote an actual change or
  just refreshed the timestamp on identical content, so callers can skip
  reprocessing pages whose content hasn't changed
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, parse_qsl

from .config import CONFIG_DIR

CACHE_DIR = CONFIG_DIR / "cache"

# Default TTLs (seconds) per content type -- news is time-sensitive, static
# reference pages (docs, repo file contents, etc.) age much more slowly.
DEFAULT_TTLS: Dict[str, int] = {
    "news": 60 * 30,          # 30 minutes
    "web": 60 * 60 * 6,       # 6 hours
    "static": 60 * 60 * 24,   # 24 hours
    "default": 60 * 60 * 2,   # 2 hours
}


def _cache_key(url: str, relevant_params: Optional[list] = None) -> str:
    """Stable cache key from a URL (+ optionally only specific query params,
    so tracking-parameter noise like utm_* doesn't fragment the cache)."""
    parsed = urlparse(url)
    if relevant_params is not None:
        kept = sorted((k, v) for k, v in parse_qsl(parsed.query) if k in relevant_params)
        query = urlencode(kept)
    else:
        query = parsed.query
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{query}" if query else f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def _cache_path(key: str, cache_dir: Optional[Path] = None) -> Path:
    return (cache_dir or CACHE_DIR) / f"{key}.json"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]


def get(url: str, relevant_params: Optional[list] = None, cache_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Fresh cache hit only -- returns None if missing or past its TTL."""
    entry = _read_entry(url, relevant_params, cache_dir)
    if entry is None:
        return None
    age = time.time() - entry["cached_at"]
    if age > entry["ttl_seconds"]:
        return None
    entry["stale"] = False
    entry["age_seconds"] = round(age, 1)
    return entry


def get_stale(url: str, relevant_params: Optional[list] = None, cache_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Return the cached entry regardless of TTL (stale-if-error path).
    Always marks ``stale: True`` if the entry is in fact past its TTL."""
    entry = _read_entry(url, relevant_params, cache_dir)
    if entry is None:
        return None
    age = time.time() - entry["cached_at"]
    entry["stale"] = age > entry["ttl_seconds"]
    entry["age_seconds"] = round(age, 1)
    return entry


def _read_entry(url: str, relevant_params: Optional[list], cache_dir: Optional[Path]) -> Optional[Dict[str, Any]]:
    key = _cache_key(url, relevant_params)
    path = _cache_path(key, cache_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def set(
    url: str,
    content: str,
    content_type: str = "default",
    ttl_seconds: Optional[int] = None,
    relevant_params: Optional[list] = None,
    cache_dir: Optional[Path] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write (or refresh) a cache entry. Returns
    ``{"written": bool, "content_changed": bool, "key": str}`` -- callers can
    use ``content_changed=False`` to skip reprocessing identical content even
    though the fetch itself succeeded again."""
    key = _cache_key(url, relevant_params)
    path = _cache_path(key, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    new_hash = _content_hash(content)
    existing = _read_entry(url, relevant_params, cache_dir)
    content_changed = existing is None or existing.get("content_hash") != new_hash

    entry = {
        "url": url,
        "content": content,
        "content_type": content_type,
        "content_hash": new_hash,
        "ttl_seconds": ttl_seconds if ttl_seconds is not None else DEFAULT_TTLS.get(content_type, DEFAULT_TTLS["default"]),
        "cached_at": time.time(),
    }
    if extra:
        entry["extra"] = extra

    path.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
    return {"written": True, "content_changed": content_changed, "key": key}


def clear(url: str, relevant_params: Optional[list] = None, cache_dir: Optional[Path] = None) -> bool:
    key = _cache_key(url, relevant_params)
    path = _cache_path(key, cache_dir)
    if path.exists():
        path.unlink()
        return True
    return False


def clear_all(cache_dir: Optional[Path] = None) -> int:
    """Remove every cached entry. Returns count removed."""
    directory = cache_dir or CACHE_DIR
    if not directory.exists():
        return 0
    count = 0
    for f in directory.glob("*.json"):
        f.unlink()
        count += 1
    return count


def stats(cache_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Summary for `scout-it doctor` / general introspection."""
    directory = cache_dir or CACHE_DIR
    if not directory.exists():
        return {"entry_count": 0, "total_size_bytes": 0, "cache_dir": str(directory)}
    files = list(directory.glob("*.json"))
    total_size = sum(f.stat().st_size for f in files)
    return {"entry_count": len(files), "total_size_bytes": total_size, "cache_dir": str(directory)}
