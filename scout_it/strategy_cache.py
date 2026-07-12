#!/usr/bin/env python3
"""
🧠 STRATEGY CACHE — persistent per-domain fetch-strategy memory
====================================================================

Backs the adaptive strategy layer: instead of retrying every domain in the
same fixed order (requests -> Playwright -> bare) every single time, this
remembers which {tier, proxy_id, fingerprint_profile} *combination* actually
worked for a given domain, and how well, so future requests can start from
a good guess instead of the cheapest guess.

Storage: a local SQLite file at ``~/.scout-it/strategy_cache.db`` (same
directory convention as ``config.py``'s credentials store). No network
calls, no external services -- this is pure local bookkeeping.

Schema is intentionally a *record of outcomes* (one row per attempt), not a
single mutable "current best" row -- that's what lets ``strategy_bandit.py``
do Thompson sampling over the accumulated successes/failures per arm rather
than just tracking a single point estimate that can't express uncertainty.
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .config import CONFIG_DIR

DB_PATH = CONFIG_DIR / "strategy_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    tier TEXT NOT NULL,
    proxy_id TEXT NOT NULL DEFAULT 'direct',
    fingerprint_profile TEXT NOT NULL DEFAULT 'default',
    success INTEGER NOT NULL,
    latency_ms INTEGER,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategy_domain ON strategy_outcomes(domain);
CREATE INDEX IF NOT EXISTS idx_strategy_arm ON strategy_outcomes(domain, tier, proxy_id, fingerprint_profile);
"""

_local = threading.local()


def domain_of(url: str) -> str:
    """Extract the registrable-ish domain (netloc, lowercased, no port) from a URL."""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.split(":")[0] or netloc
    except Exception:
        return url


@contextmanager
def _connect(db_path: Optional[Path] = None):
    """Thread-local SQLite connection, created on first use per thread."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    key = f"conn_{path}"
    conn = getattr(_local, key, None)
    if conn is None:
        conn = sqlite3.connect(str(path), timeout=10)
        conn.executescript(_SCHEMA)
        conn.commit()
        setattr(_local, key, conn)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise


def record_outcome(
    url: str,
    tier: str,
    success: bool,
    proxy_id: str = "direct",
    fingerprint_profile: str = "default",
    latency_ms: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Record one fetch attempt's outcome for a domain+arm. Called after every
    ``fetch_resilient()`` attempt (success or failure) -- this *is* the
    "extraction_method" signal already recorded per result, just persisted
    across runs instead of only within one process."""
    domain = domain_of(url)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO strategy_outcomes (domain, tier, proxy_id, fingerprint_profile, success, latency_ms, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (domain, tier, proxy_id, fingerprint_profile, int(success), latency_ms, time.time()),
        )
        conn.commit()


def get_arms(domain: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return every distinct {tier, proxy_id, fingerprint_profile} combination
    tried for *domain*, with aggregated success/failure counts -- exactly
    the shape ``strategy_bandit.py`` needs for Thompson sampling (Beta(successes+1,
    failures+1) per arm)."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT tier, proxy_id, fingerprint_profile, "
            "SUM(success) as successes, COUNT(*) - SUM(success) as failures, "
            "AVG(latency_ms) as avg_latency_ms, MAX(timestamp) as last_seen "
            "FROM strategy_outcomes WHERE domain = ? "
            "GROUP BY tier, proxy_id, fingerprint_profile",
            (domain,),
        ).fetchall()
    return [
        {
            "tier": r[0], "proxy_id": r[1], "fingerprint_profile": r[2],
            "successes": r[3] or 0, "failures": r[4] or 0,
            "avg_latency_ms": r[5], "last_seen": r[6],
        }
        for r in rows
    ]


def get_domain_stats(domain: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Per-domain summary for the `scout-it stats` command: overall success
    rate and the current best-performing arm by success rate (ties broken by
    lower average latency)."""
    arms = get_arms(domain, db_path)
    if not arms:
        return {"domain": domain, "known": False}

    total_success = sum(a["successes"] for a in arms)
    total_attempts = sum(a["successes"] + a["failures"] for a in arms)

    def _rate(a: Dict[str, Any]) -> float:
        n = a["successes"] + a["failures"]
        return a["successes"] / n if n else 0.0

    best = max(arms, key=lambda a: (_rate(a), -(a["avg_latency_ms"] or 0)))

    return {
        "domain": domain,
        "known": True,
        "total_attempts": total_attempts,
        "overall_success_rate": round(total_success / total_attempts, 3) if total_attempts else 0.0,
        "arm_count": len(arms),
        "best_arm": {
            "tier": best["tier"], "proxy_id": best["proxy_id"],
            "fingerprint_profile": best["fingerprint_profile"],
            "success_rate": round(_rate(best), 3),
            "avg_latency_ms": best["avg_latency_ms"],
        },
        "arms": arms,
    }


def all_known_domains(db_path: Optional[Path] = None) -> List[str]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT DISTINCT domain FROM strategy_outcomes ORDER BY domain").fetchall()
    return [r[0] for r in rows]


def reset_domain(domain: str, db_path: Optional[Path] = None) -> int:
    """Delete all recorded outcomes for a domain (``--strategy-cache-reset``),
    e.g. after a site's defenses change and the cached strategy has gone
    stale. Returns the number of rows removed."""
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM strategy_outcomes WHERE domain = ?", (domain,))
        conn.commit()
        return cur.rowcount


def export_all(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Full dump of the strategy cache for `--export-stats json`."""
    domains = all_known_domains(db_path)
    return {"domain_count": len(domains), "domains": {d: get_domain_stats(d, db_path) for d in domains}}
