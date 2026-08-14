"""Composite ranking: relevance + authority + freshness + diversity.

Phase 3 of scout-it's ranking evolution.  After the semantic reranker
(BM25F + vectors + RRF + cross-encoder) produces a relevance ordering,
this module applies a **composite score** that blends four signals:

    final_score = w1·relevance + w2·authority + w3·freshness + w4·diversity

Each signal is normalised to [0, 1] before weighting.  The weights are
**content-type aware**: a news query weights freshness highly, an academic
query weights authority highly, a diverse multi-source query weights
diversity highly.

Signals
-------

**Relevance** — from the hybrid retrieval + cross-encoder stage
(``semantic_score`` on each result, already in [0, 1] after normalisation).

**Authority** — domain reputation from :mod:`authority_table`, seeded with
known authoritative domains and refined by the bandit over time.

**Freshness** — time-decay from the result's ``timestamp``.  Matters for
news/events (decay over hours/days), less for academic/book (timeless).

**Diversity** — penalises results that belong to the same MinHash cluster
as an earlier (higher-ranked) result, so the top-10 isn't five copies of
the same story.  Uses the existing :mod:`dedup` clustering but, instead of
*removing* duplicates, *penalises* them (soft diversity).
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from .authority_table import get_authority_score
from .dedup import _minhash_for, _shingles, _result_fingerprint, THRESHOLD

logger = logging.getLogger(__name__)


# ─── Default weights per content-type context ──────────────────────────────
# (relevance, authority, freshness, diversity)
# These sum to 1.0 and represent how much each signal contributes to the
# final ranking for a given query type.

DEFAULT_WEIGHTS: Dict[str, Tuple[float, float, float, float]] = {
    # Academic: authority matters most (is this a reputable source?),
    # then relevance. Freshness barely matters (papers are timeless).
    # Diversity matters to avoid 5 papers from the same author/group.
    "academic":  (0.35, 0.40, 0.05, 0.20),
    # News: freshness is king, then relevance. Authority matters (is this
    # Reuters or a random blog?). Diversity prevents 5 copies of the same
    # syndicated story.
    "news":      (0.30, 0.20, 0.35, 0.15),
    "event":     (0.25, 0.15, 0.40, 0.20),
    # Datasets: authority (is this a trusted repository?) and relevance.
    # Freshness matters for "latest data" but less than news.
    "dataset":   (0.35, 0.35, 0.10, 0.20),
    # Books/literature: authority and relevance. Freshness irrelevant.
    "book":      (0.40, 0.35, 0.05, 0.20),
    # Media (images/video/audio): relevance and diversity. Authority less
    # critical (museums are trusted, but so are many archives).
    "media":     (0.35, 0.20, 0.10, 0.35),
    # Geo: relevance and authority (official sources matter).
    "geo":       (0.40, 0.35, 0.10, 0.15),
    # Knowledge (Wikidata etc.): authority and relevance.
    "knowledge": (0.35, 0.40, 0.05, 0.20),
    # Podcast: relevance and freshness (new episodes).
    "podcast":   (0.35, 0.20, 0.25, 0.20),
    # Code: authority (is this the official repo?) and relevance.
    "code":      (0.30, 0.40, 0.10, 0.20),
    # General/web (default): balanced, slight relevance emphasis.
    "web":       (0.40, 0.25, 0.15, 0.20),
}

# Default weights when no content-type hint is given.
GENERAL_WEIGHTS: Tuple[float, float, float, float] = (0.40, 0.25, 0.15, 0.20)


# ─── Signal 1: Relevance ───────────────────────────────────────────────────


def _normalise_relevance(results: List[Dict[str, Any]]) -> List[float]:
    """Normalise ``semantic_score`` to [0, 1].

    The semantic reranker attaches ``semantic_score`` (an RRF fusion score)
    to each result.  These are not inherently bounded, so we min-max
    normalise across the result set.  If no scores are present, fall back
    to a uniform 0.5 (neutral).
    """
    scores = []
    for r in results:
        s = r.get("semantic_score") or r.get("relevance_score") or 0.0
        try:
            scores.append(float(s))
        except (ValueError, TypeError):
            scores.append(0.0)

    if not scores:
        return []

    lo = min(scores)
    hi = max(scores)
    if hi - lo < 1e-9:
        # All scores equal — neutral.
        return [0.5] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


# ─── Signal 2: Authority ───────────────────────────────────────────────────


def _authority_scores(results: List[Dict[str, Any]]) -> List[float]:
    """Get authority score [0, 1] for each result from the domain table."""
    out = []
    for r in results:
        url = r.get("url") or r.get("href") or r.get("link") or ""
        # If the result already has an authority_score from the plugin,
        # use that as the floor and let the domain table override upward.
        plugin_score = r.get("authority_score", 0.0) or 0.0
        domain_score = get_authority_score(url) if url else 0.0
        out.append(max(plugin_score, domain_score))
    return out


# ─── Signal 3: Freshness ────────────────────────────────────────────────────


# Half-life in hours per content-type.  After one half-life, freshness
# drops to 0.5.  Academic papers have a half-life of ~years (we use a large
# number so time-decay is negligible); news has a half-life of ~2 days.
_FRESHNESS_HALFLIFE_HOURS: Dict[str, float] = {
    "academic":  87600.0,   # 10 years — papers are timeless
    "book":      87600.0,   # 10 years
    "dataset":   43800.0,   # 5 years
    "code":      17520.0,   # 2 years
    "knowledge": 43800.0,   # 5 years
    "geo":       87600.0,   # 10 years (places don't change often)
    "media":     8760.0,    # 1 year
    "podcast":   720.0,     # 30 days
    "news":      48.0,      # 2 days
    "event":     24.0,      # 1 day
    "web":       720.0,     # 30 days (general web content)
}

_DEFAULT_HALFLIFE = 720.0  # 30 days


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 or common date string into a timezone-aware datetime."""
    if not ts:
        return None
    # Try several common formats.
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",           # compact (openFDA: "20240115")
    ):
        try:
            dt = datetime.strptime(ts[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, IndexError):
            continue
    # Last resort: regex for YYYY-MM-DD anywhere in the string.
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ts)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _freshness_score(
    timestamp: str,
    content_type: str = "web",
    now: Optional[datetime] = None,
) -> float:
    """Compute a freshness score [0, 1] using exponential time-decay.

    score = 0.5^(age_hours / halflife_hours)

    A result published right now scores 1.0; after one half-life it drops
    to 0.5; after two half-lives, 0.25, etc.  If no timestamp is available,
    returns a neutral 0.5 (we can't judge freshness, so don't penalise).
    """
    if not timestamp:
        return 0.5  # neutral — no signal
    dt = _parse_timestamp(timestamp)
    if dt is None:
        return 0.5
    if now is None:
        now = datetime.now(timezone.utc)
    age_hours = (now - dt).total_seconds() / 3600.0
    if age_hours < 0:
        # Future timestamp (clock skew) — treat as fresh.
        return 1.0
    halflife = _FRESHNESS_HALFLIFE_HOURS.get(content_type, _DEFAULT_HALFLIFE)
    return 0.5 ** (age_hours / halflife)


def _freshness_scores(
    results: List[Dict[str, Any]],
    content_type_hint: str = "web",
) -> List[float]:
    """Compute freshness scores for all results."""
    return [
        _freshness_score(
            r.get("timestamp") or r.get("publish_date") or r.get("date") or "",
            r.get("content_type", content_type_hint),
        )
        for r in results
    ]


# ─── Signal 4: Diversity ───────────────────────────────────────────────────


def _diversity_scores(
    results: List[Dict[str, Any]],
    threshold: float = THRESHOLD,
) -> List[float]:
    """Compute diversity scores [0, 1] using MinHash clustering.

    Results are clustered by content similarity (same MinHash approach as
    :mod:`dedup`).  The *first* result in each cluster gets diversity=1.0
    (it's unique so far).  Subsequent members of the same cluster get a
    penalty that decreases with cluster position::

        diversity = 1.0 - (cluster_rank / max_cluster_size)

    This is a *soft* diversity penalty: instead of removing duplicates (which
    :mod:`dedup` already does), it pushes them down in the ranking so the
    top results are diverse, but duplicates still appear lower if relevant.
    """
    n = len(results)
    if n <= 1:
        return [1.0] * n

    # Build MinHash signatures (same as dedup.py).
    fingerprints = [_result_fingerprint(r) for r in results]
    minhashes = [_minhash_for(_shingles(fp)) for fp in fingerprints]

    # Union-find clustering (same algorithm as dedup.py).
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if minhashes[i].jaccard(minhashes[j]) >= threshold:
                union(i, j)

    # Group results by cluster, preserving input order.
    clusters: Dict[int, List[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    # For each result, its diversity score depends on its position within
    # its cluster (first = best, subsequent = penalised).
    max_cluster = max(len(c) for c in clusters.values()) if clusters else 1
    scores = [1.0] * n
    for root, members in clusters.items():
        if len(members) <= 1:
            continue  # singleton — no penalty
        for rank_in_cluster, idx in enumerate(members):
            # Penalty grows with position in cluster.
            penalty = rank_in_cluster / max(max_cluster, 2)
            scores[idx] = max(0.0, 1.0 - penalty)
    return scores


# ─── Composite ranker ──────────────────────────────────────────────────────


def composite_score(
    results: List[Dict[str, Any]],
    query: str,
    content_type_hint: str = "web",
    *,
    weights: Optional[Tuple[float, float, float, float]] = None,
) -> List[Dict[str, Any]]:
    """Compute the composite score for each result (in place).

    Attaches ``composite_score``, ``score_breakdown``, and ``diversity_cluster``
    to each result dict.  Does NOT re-order — caller decides whether to sort.

    Args:
        results: list of result dicts (must have run through semantic_rerank
            first so ``semantic_score`` is present).
        query: the search query (unused for now, reserved for future
            query-dependent weighting).
        content_type_hint: the dominant content type of the query
            ("academic", "news", "event", "web", etc.).  Determines weights.
        weights: override the content-type weights with an explicit
            (w_relevance, w_authority, w_freshness, w_diversity) tuple.

    Returns:
        The same list of result dicts, each enriched with ``composite_score``
        and ``score_breakdown``.
    """
    if not results:
        return results

    w = weights or DEFAULT_WEIGHTS.get(content_type_hint, GENERAL_WEIGHTS)
    w_rel, w_auth, w_fresh, w_div = w

    # Compute the four signals.
    rel_scores = _normalise_relevance(results)
    auth_scores = _authority_scores(results)
    fresh_scores = _freshness_scores(results, content_type_hint)
    div_scores = _diversity_scores(results)

    for i, r in enumerate(results):
        rel = rel_scores[i]
        auth = auth_scores[i]
        fresh = fresh_scores[i]
        div = div_scores[i]

        final = w_rel * rel + w_auth * auth + w_fresh * fresh + w_div * div

        r["composite_score"] = round(final, 6)
        r["score_breakdown"] = {
            "relevance": round(rel, 4),
            "authority": round(auth, 4),
            "freshness": round(fresh, 4),
            "diversity": round(div, 4),
            "weights": {
                "relevance": w_rel,
                "authority": w_auth,
                "freshness": w_fresh,
                "diversity": w_div,
            },
        }

    return results


def composite_rerank(
    results: List[Dict[str, Any]],
    query: str,
    content_type_hint: str = "web",
    *,
    weights: Optional[Tuple[float, float, float, float]] = None,
    max_final: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Apply composite scoring and re-rank by the composite score.

    This is the main entry point for Phase 3.  It should be called *after*
    :func:`semantic_rerank` (which provides the relevance signal).

    Pipeline::

        semantic_rerank → composite_score → sort by composite_score

    Args:
        results: list of result dicts (post-semantic-rerank).
        query: the search query.
        content_type_hint: dominant content type ("academic", "news", …).
        weights: optional explicit weight override.
        max_final: max results to return (None = return all).

    Returns:
        Results sorted by composite_score (descending), each enriched
        with ``composite_score`` and ``score_breakdown``.
    """
    if not results:
        return []

    scored = composite_score(results, query, content_type_hint, weights=weights)
    scored.sort(key=lambda r: r.get("composite_score", 0.0), reverse=True)

    if max_final is not None:
        return scored[:max_final]
    return scored
