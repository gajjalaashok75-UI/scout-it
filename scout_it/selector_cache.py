#!/usr/bin/env python3
"""
🎯 SELECTOR CACHE — "structural memory" per domain
==========================================================

Once a site's article container is identified successfully (by CSS
selector), remember that selector for the domain and try it first on the
next scrape, before falling back to the full multi-engine cascade
(trafilatura -> justext -> boilerpy3 -> readability -> heuristic). Cheap,
deterministic, no model dependency.

Stored in the same SQLite file as the strategy cache (different table) to
avoid multiplying the number of files under ``~/.scout-it/``.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import CONFIG_DIR
from .strategy_cache import domain_of

DB_PATH = CONFIG_DIR / "strategy_cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS selector_memory (
    domain TEXT PRIMARY KEY,
    selector TEXT NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_updated REAL NOT NULL
);
"""

_local = threading.local()


@contextmanager
def _connect(db_path: Optional[Path] = None):
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    key = f"selconn_{path}"
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


def get_selector(url: str, db_path: Optional[Path] = None) -> Optional[str]:
    """The remembered selector for this domain, or None if we've never
    successfully identified one."""
    domain = domain_of(url)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT selector FROM selector_memory WHERE domain = ?", (domain,)
        ).fetchone()
    return row[0] if row else None


def record_success(url: str, selector: str, db_path: Optional[Path] = None) -> None:
    import time
    domain = domain_of(url)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO selector_memory (domain, selector, success_count, failure_count, last_updated) "
            "VALUES (?, ?, 1, 0, ?) "
            "ON CONFLICT(domain) DO UPDATE SET "
            "  selector = excluded.selector, "
            "  success_count = success_count + 1, "
            "  last_updated = excluded.last_updated",
            (domain, selector, time.time()),
        )
        conn.commit()


def record_failure(url: str, db_path: Optional[Path] = None) -> None:
    """Selector stopped working (site layout changed) -- increment the
    failure counter; if it fails too many times in a row, forget it so the
    full cascade takes over again instead of repeatedly trying a dead selector."""
    import time
    domain = domain_of(url)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE selector_memory SET failure_count = failure_count + 1, last_updated = ? WHERE domain = ?",
            (time.time(), domain),
        )
        row = conn.execute(
            "SELECT failure_count FROM selector_memory WHERE domain = ?", (domain,)
        ).fetchone()
        if row and row[0] >= 3:
            conn.execute("DELETE FROM selector_memory WHERE domain = ?", (domain,))
        conn.commit()


def try_cached_selector(url: str, html: str, db_path: Optional[Path] = None) -> Optional[str]:
    """Attempt extraction using the domain's remembered selector, if any.
    Returns the extracted text (joined, whitespace-normalized) or None if
    there's no cached selector or it no longer matches anything."""
    selector = get_selector(url, db_path)
    if not selector:
        return None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        node = soup.select_one(selector)
        if node is None:
            return None
        text = node.get_text("\n", strip=True)
        return text if len(text) > 100 else None
    except Exception:
        return None


def forget_domain(url: str, db_path: Optional[Path] = None) -> bool:
    domain = domain_of(url)
    with _connect(db_path) as conn:
        cur = conn.execute("DELETE FROM selector_memory WHERE domain = ?", (domain,))
        conn.commit()
        return cur.rowcount > 0
