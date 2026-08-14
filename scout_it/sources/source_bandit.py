"""Source-selection bandit — contextual Thompson sampling over source plugins.

Phase 3 extension of the existing bandit infrastructure.  Today the bandit
in :mod:`strategy_bandit` picks which **fetch tier** to try for a given
domain.  This module extends the same Thompson-sampling idea to pick which
**source plugins** to query for a given **query type**.

The intuition: academic queries do better on OpenAlex + arXiv, news queries
do better on GDELT + Hacker News, etc.  Instead of always querying all 29
sources (slow, rate-limit-prone) or guessing manually, the bandit *learns*
which sources produce the most useful results for each query type.

How it works
------------

1. **Classify the query** into a type: academic, news, event, media, geo,
   knowledge, web.  This is the *context* for the contextual bandit.

2. **For each (query_type, source) pair**, maintain a Beta(successes+1,
   failures+1) posterior — exactly like the fetch-strategy bandit.

3. At decision time, **sample** from each available source's posterior and
   pick the top-K sources with the highest samples.  This balances
   exploitation (sources that worked before) with exploration (sources with
   high uncertainty might still win a sample).

4. After results come back, **record the outcome**: a source "succeeds" if
   it returned results that ranked well (above a relevance threshold);
   it "fails" if it returned nothing or only low-relevance results.

The reward signal is designed to be **self-supervised** — no user feedback
needed.  The bandit learns from the quality of results the pipeline already
computes (semantic relevance scores).

Persistence: SQLite at ``~/.scout-it/source_bandit.db``, same pattern as
:mod:`strategy_cache`.  Thread-safe, auto-pruning.
"""

from __future__ import annotations

import logging
import random
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..config import CONFIG_DIR

logger = logging.getLogger(__name__)

DB_PATH = CONFIG_DIR / "source_bandit.db"

# ─── Query-type classification ──────────────────────────────────────────────
# Heuristic query → content-type mapping.  This determines the bandit's
# context (which posterior to sample from).

# Keyword patterns per content type.  Matched case-insensitively.
_QUERY_PATTERNS: List[Tuple[str, List[str]]] = [
    ("academic", [
        r"\b(paper|research|study|arxiv|doi|citation|preprint|journal|thesis)\b",
        r"\b(algorithm|model|neural|deep learning|machine learning)\b",
        r"\b(protein|gene|cell|molecule|quantum|physics)\b",
    ]),
    ("news", [
        r"\b(latest|today|breaking|news|update|happened|announced)\b",
        r"\b(this week|this month|just in)\b",
    ]),
    ("event", [
        r"\b(earthquake|launch|protest|election|disaster|incident|crisis)\b",
        r"\b(spaceflight|rocket|spacex|nasa launch)\b",
    ]),
    ("media", [
        r"\b(image|photo|picture|video|movie|anime|manga|art|painting)\b",
        r"\b(music|song|album|artist|recording)\b",
    ]),
    ("dataset", [
        r"\b(dataset|data|csv|statistics|census|demographics)\b",
        r"\b(kaggle|huggingface|zenodo)\b",
    ]),
    ("book", [
        r"\b(book|ebook|novel|literature|author|isbn)\b",
        r"\b(gutenberg|library|read)\b",
    ]),
    ("geo", [
        r"\b(map|location|place|city|country|latitude|weather|forecast)\b",
        r"\b(restaurant|hotel|nearby|directions)\b",
    ]),
    ("knowledge", [
        r"\b(what is|who is|definition|meaning|wiki|encyclopedia|fact)\b",
        r"\b(wikidata|entity|concept)\b",
    ]),
    ("code", [
        r"\b(code|function|class|api|library|package|github|stackoverflow)\b",
        r"\b(python|javascript|java|rust|golang|npm|pip)\b",
        r"\b(bug|error|exception|stack trace)\b",
    ]),
    ("podcast", [
        r"\b(podcast|episode|interview|listennotes)\b",
    ]),
]


def classify_query(query: str) -> str:
    """Classify a search query into a content-type context.

    Uses keyword matching to determine the dominant content type of the
    query.  Returns one of: academic, news, event, media, dataset, book,
    geo, knowledge, code, podcast, or "web" (general, no strong signal).
    """
    if not query:
        return "web"
    query_lower = query.lower()
    scores: Dict[str, int] = {}
    for content_type, patterns in _QUERY_PATTERNS:
        for pat in patterns:
            if re.search(pat, query_lower):
                scores[content_type] = scores.get(content_type, 0) + 1
    if not scores:
        return "web"
    # Return the content type with the most keyword matches.
    return max(scores, key=scores.get)


# ─── SQLite persistence ─────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    success INTEGER NOT NULL,
    result_count INTEGER DEFAULT 0,
    avg_relevance REAL DEFAULT 0.0,
    timestamp REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_qtype ON source_outcomes(query_type);
CREATE INDEX IF NOT EXISTS idx_source_pair ON source_outcomes(query_type, source_name);
"""

_local = threading.local()
MAX_ROWS = 10_000


@contextmanager
def _connect(db_path: Optional[Path] = None):
    """Thread-local SQLite connection."""
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


def _prune(conn: sqlite3.Connection, max_rows: int = MAX_ROWS) -> None:
    """Cap the table size (same pattern as strategy_cache)."""
    total = conn.execute("SELECT COUNT(*) FROM source_outcomes").fetchone()[0]
    if total <= max_rows:
        return
    to_delete = total - max_rows
    conn.execute(
        "DELETE FROM source_outcomes WHERE id IN ("
        "  SELECT id FROM source_outcomes ORDER BY timestamp ASC, id ASC LIMIT ?"
        ")",
        (to_delete,),
    )


# ─── Bandit arms (Beta posteriors per query_type × source) ──────────────────


def _get_arms(query_type: str, db_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Return per-source Beta posterior stats for a query type.

    Returns: {source_name: {"successes": int, "failures": int, "avg_relevance": float}}
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT source_name, "
            "SUM(success) as successes, "
            "COUNT(*) - SUM(success) as failures, "
            "AVG(avg_relevance) as avg_relevance "
            "FROM source_outcomes WHERE query_type = ? "
            "GROUP BY source_name",
            (query_type,),
        ).fetchall()
    return {
        r[0]: {
            "successes": r[1] or 0,
            "failures": r[2] or 0,
            "avg_relevance": r[3] or 0.0,
        }
        for r in rows
    }


# ─── Selection: Thompson sampling ──────────────────────────────────────────

# Below this many total attempts for a query type, don't trust the bandit —
# return all available sources so we can gather data.
MIN_ATTEMPTS_BEFORE_BANDIT = 5

# Default number of sources to select when the bandit is active.
DEFAULT_TOP_K = 5


def choose_sources(
    query: str,
    available_sources: Sequence[str],
    top_k: int = DEFAULT_TOP_K,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Pick which source plugins to query for *query*.

    Uses Thompson sampling: for each available source, draw from its
    Beta(successes+1, failures+1) posterior for the query's content type,
    and pick the top-K with the highest samples.

    If there isn't enough history for the query type yet (< MIN_ATTEMPTS),
    returns all available sources (exploration phase).

    Args:
        query: the search query (classified into a content type).
        available_sources: source names that are enabled + have keys.
        top_k: how many sources to select.
        db_path: optional SQLite path override.

    Returns:
        ``{"sources": [names], "query_type": str, "source": "default"|"bandit",
        "confidence": float, "samples": {name: sample}}``
    """
    query_type = classify_query(query)
    available = list(available_sources)
    if not available:
        return {"sources": [], "query_type": query_type, "source": "default", "confidence": 0.0, "samples": {}}

    arms = _get_arms(query_type, db_path)
    total_attempts = sum(a["successes"] + a["failures"] for a in arms.values())

    # Not enough data — return all available (exploration).
    if total_attempts < MIN_ATTEMPTS_BEFORE_BANDIT or len(available) <= top_k:
        return {
            "sources": available,
            "query_type": query_type,
            "source": "default",
            "confidence": 0.0,
            "samples": {},
        }

    # Thompson sampling: draw from each available source's Beta posterior.
    samples: Dict[str, float] = {}
    for src in available:
        arm = arms.get(src)
        if arm and (arm["successes"] + arm["failures"]) > 0:
            alpha = arm["successes"] + 1
            beta = arm["failures"] + 1
            samples[src] = random.betavariate(alpha, beta)
        else:
            # Unseen source — uniform prior Beta(1,1) → sample from U(0,1).
            samples[src] = random.random()

    # Pick top-K by sampled value.
    ranked = sorted(samples, key=lambda s: -samples[s])
    selected = ranked[:top_k]

    # Confidence = how confident we are in the bandit (proportion of
    # attempts where the top source was actually the best historically).
    top_source = ranked[0] if ranked else ""
    top_arm = arms.get(top_source, {})
    top_n = top_arm.get("successes", 0) + top_arm.get("failures", 0)
    confidence = min(top_n / 20.0, 1.0) if top_n > 0 else 0.0

    return {
        "sources": selected,
        "query_type": query_type,
        "source": "bandit",
        "confidence": round(confidence, 3),
        "samples": {s: round(samples[s], 4) for s in selected},
    }


# ─── Outcome recording ──────────────────────────────────────────────────────


def record_source_outcome(
    query: str,
    source_name: str,
    results: List[Dict[str, Any]],
    relevance_threshold: float = 0.1,
    db_path: Optional[Path] = None,
) -> None:
    """Record the outcome of querying *source_name* for *query*.

    A source "succeeds" if it returned at least one result whose relevance
    score (or semantic score) is above *relevance_threshold*.  This makes
    the bandit self-supervised: it learns from the quality of results the
    pipeline already computes, without needing user feedback.

    Args:
        query: the search query (classified into a content type).
        source_name: the source plugin that was queried.
        results: the results returned by the source.
        relevance_threshold: minimum relevance score for a "useful" result.
        db_path: optional SQLite path override.
    """
    query_type = classify_query(query)
    result_count = len(results)

    # Compute average relevance from the results.
    relevances = []
    for r in results:
        rel = r.get("semantic_score") or r.get("relevance_score") or r.get("authority_score") or 0.0
        try:
            relevances.append(float(rel))
        except (ValueError, TypeError):
            relevances.append(0.0)
    avg_relevance = sum(relevances) / len(relevances) if relevances else 0.0

    # Success if the source returned at least one useful result.
    success = result_count > 0 and any(r >= relevance_threshold for r in relevances)

    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO source_outcomes (query_type, source_name, success, result_count, avg_relevance, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (query_type, source_name, int(success), result_count, avg_relevance, time.time()),
        )
        _prune(conn)
        conn.commit()


def record_source_outcomes(
    query: str,
    source_results: Dict[str, List[Dict[str, Any]]],
    relevance_threshold: float = 0.1,
    db_path: Optional[Path] = None,
) -> None:
    """Record outcomes for multiple sources at once (convenience wrapper)."""
    for source_name, results in source_results.items():
        record_source_outcome(query, source_name, results, relevance_threshold, db_path)


# ─── Inspection / stats ────────────────────────────────────────────────────


def get_source_stats(query_type: Optional[str] = None, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return bandit stats for inspection (the `scout-it stats` command).

    Args:
        query_type: if given, only return stats for that query type.
            If None, return stats for all query types.

    Returns:
        ``{query_type: {source_name: {successes, failures, avg_relevance, total}}}``
    """
    if query_type:
        arms = _get_arms(query_type, db_path)
        return {query_type: {
            src: {
                "successes": a["successes"],
                "failures": a["failures"],
                "avg_relevance": round(a["avg_relevance"], 4),
                "total": a["successes"] + a["failures"],
            }
            for src, a in arms.items()
        }}

    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT query_type, source_name, "
            "SUM(success) as successes, "
            "COUNT(*) - SUM(success) as failures, "
            "AVG(avg_relevance) as avg_relevance "
            "FROM source_outcomes GROUP BY query_type, source_name"
        ).fetchall()

    out: Dict[str, Any] = {}
    for qt, src, succ, fail, avg_rel in rows:
        out.setdefault(qt, {})[src] = {
            "successes": succ or 0,
            "failures": fail or 0,
            "avg_relevance": round(avg_rel or 0.0, 4),
            "total": (succ or 0) + (fail or 0),
        }
    return out


def reset_bandit(query_type: Optional[str] = None, db_path: Optional[Path] = None) -> int:
    """Reset bandit history for a query type (or all).

    Returns the number of rows deleted.
    """
    with _connect(db_path) as conn:
        if query_type:
            cur = conn.execute("DELETE FROM source_outcomes WHERE query_type = ?", (query_type,))
        else:
            cur = conn.execute("DELETE FROM source_outcomes")
        conn.commit()
        return cur.rowcount
