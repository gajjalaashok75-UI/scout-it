"""Domain authority table — seeded reputation scores, refined by bandit outcomes.

Every search result has a ``authority_score`` (0.0–1.0) representing the
trustworthiness / reputation of the domain it comes from.  This module
provides:

  - A **seeded** table of well-known authoritative domains (arxiv.org,
    nature.com, github.com, …) with hand-tuned starting scores.
  - **Persistent** per-domain adjustments stored in
    ``~/.scout-it/authority_scores.json`` so the bandit's learning survives
    across runs.
  - A simple **feedback** API: ``record_domain_outcome(domain, success)``
    nudges the stored score up (success) or down (failure) using a
    Beta-Binomial update, exactly like the strategy-cache pattern.

The final authority score for a domain is::

    authority = clamp(seed_score + bandit_adjustment, 0.0, 1.0)

where ``bandit_adjustment`` is the (posterior mean − prior) of the
Beta-Binomial model.  This lets the table start sensible (from the seed)
and drift toward observed reality without ever losing the prior entirely.
"""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ..config import CONFIG_DIR

logger = logging.getLogger(__name__)

AUTHORITY_FILE = CONFIG_DIR / "authority_scores.json"

# ─── Seeded authority scores ───────────────────────────────────────────────
# Hand-tuned starting scores for well-known domains.  These are priors —
# the bandit adjusts them over time based on observed outcomes.
#
# Scale: 0.0 (untrusted/spam) → 1.0 (gold-standard reference).
# Domains not listed here default to 0.5 (neutral).

_SEED_AUTHORITY: Dict[str, float] = {
    # ── Academic / reference ─────────────────────────────────────────────────
    "arxiv.org": 0.95,
    "doi.org": 0.95,
    "nature.com": 0.95,
    "science.org": 0.95,
    "sciencedirect.com": 0.90,
    "springer.com": 0.90,
    "wiley.com": 0.88,
    "pubmed.ncbi.nlm.nih.gov": 0.95,
    "ncbi.nlm.nih.gov": 0.93,
    "scholar.google.com": 0.92,
    "semanticscholar.org": 0.90,
    "openalex.org": 0.88,
    "crossref.org": 0.88,
    "europepmc.org": 0.90,
    "jstor.org": 0.88,
    "ieee.org": 0.88,
    "acm.org": 0.88,
    "plos.org": 0.87,
    "biorxiv.org": 0.87,
    "doaj.org": 0.85,
    # ── Code / developer ──────────────────────────────────────────────────────
    "github.com": 0.92,
    "gitlab.com": 0.85,
    "stackoverflow.com": 0.90,
    "stackexchange.com": 0.85,
    "npmjs.com": 0.82,
    "pypi.org": 0.85,
    "docs.python.org": 0.95,
    "developer.mozilla.org": 0.93,
    "kernel.org": 0.92,
    "crates.io": 0.80,
    # ── Encyclopedic / knowledge ──────────────────────────────────────────────
    "wikipedia.org": 0.85,
    "en.wikipedia.org": 0.85,
    "wikidata.org": 0.85,
    "wikimedia.org": 0.82,
    "britannica.com": 0.88,
    # ── News (mainstream, editorial standards) ───────────────────────────────
    "reuters.com": 0.92,
    "ap.org": 0.91,
    "bbc.com": 0.90,
    "bbc.co.uk": 0.90,
    "nytimes.com": 0.88,
    "theguardian.com": 0.87,
    "washingtonpost.com": 0.87,
    "economist.com": 0.88,
    "bloomberg.com": 0.87,
    "ft.com": 0.87,
    "wsj.com": 0.86,
    "npr.org": 0.87,
    "aljazeera.com": 0.82,
    "techcrunch.com": 0.80,
    "theverge.com": 0.78,
    "arstechnica.com": 0.80,
    "wired.com": 0.78,
    # ── Government / official ─────────────────────────────────────────────────
    "gov.uk": 0.92,
    "usa.gov": 0.92,
    "nasa.gov": 0.95,
    "europa.eu": 0.92,
    "cdc.gov": 0.95,
    "nih.gov": 0.95,
    "fda.gov": 0.93,
    "open.fda.gov": 0.93,
    "usgs.gov": 0.93,
    "noaa.gov": 0.92,
    # ── Data / datasets ───────────────────────────────────────────────────────
    "huggingface.co": 0.85,
    "zenodo.org": 0.87,
    "data.gov": 0.88,
    "kaggle.com": 0.80,
    "archive.org": 0.85,
    "internetarchive.org": 0.85,
    # ── Books / literature ─────────────────────────────────────────────────────
    "gutenberg.org": 0.88,
    "openlibrary.org": 0.82,
    "worldcat.org": 0.85,
    # ── Media / culture ────────────────────────────────────────────────────────
    "metmuseum.org": 0.90,
    "artic.edu": 0.88,
    "myanimelist.net": 0.75,
    "musicbrainz.org": 0.85,
    # ── Geo ───────────────────────────────────────────────────────────────────
    "openstreetmap.org": 0.85,
    # ── Events / real-time ─────────────────────────────────────────────────────
    "gdeltproject.org": 0.82,
    "news.ycombinator.com": 0.78,
    # ── Default for unknown domains ───────────────────────────────────────────
}

DEFAULT_AUTHORITY = 0.5

# ─── Beta-Binomial bandit adjustment ───────────────────────────────────────
# Each domain tracks (alpha, beta) for a Beta posterior.  The adjustment
# applied to the seed score is (posterior_mean - 0.5), clamped so the
# final score stays in [0, 1].
#   alpha = 1 + successes
#   beta  = 1 + failures
#   posterior_mean = alpha / (alpha + beta)
# We start with a weak prior (alpha=beta=1 → mean=0.5) and let outcomes
# pull it toward the observed success rate.


def _extract_domain(url: str) -> str:
    """Extract the registered domain from a URL (lowercase, no www.)."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not host:
            # Maybe it's a bare domain
            host = url.split("/")[0]
        if host.startswith("www."):
            host = host[4:]
        return host.lower()
    except Exception:
        return ""


# ─── Persistent per-domain adjustments ─────────────────────────────────────

_cache: Optional[Dict[str, Any]] = None


def _load_adjustments() -> Dict[str, Any]:
    """Load per-domain bandit adjustments from disk (cached in memory)."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        if AUTHORITY_FILE.exists():
            _cache = json.loads(AUTHORITY_FILE.read_text())
        else:
            _cache = {}
    except Exception as exc:
        logger.warning("Could not load authority_scores.json: %s", exc)
        _cache = {}
    return _cache


def _save_adjustments(data: Dict[str, Any]) -> None:
    """Persist per-domain bandit adjustments to disk."""
    global _cache
    _cache = data
    try:
        AUTHORITY_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTHORITY_FILE.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        logger.warning("Could not save authority_scores.json: %s", exc)


def _bandit_adjustment(domain: str) -> float:
    """Return the bandit's posterior-mean adjustment for *domain*.

    Returns a delta in [-0.5, +0.5] that, when added to the seed score,
    nudges it toward the observed success rate.
    """
    adjustments = _load_adjustments()
    entry = adjustments.get(domain)
    if not entry:
        return 0.0
    alpha = entry.get("alpha", 1.0)
    beta = entry.get("beta", 1.0)
    posterior_mean = alpha / (alpha + beta)
    # The adjustment is how far the posterior mean deviates from the
    # neutral 0.5 baseline.  Scale it by the observation count so a
    # single outcome doesn't swing the score wildly.
    n = alpha + beta - 2  # subtract the prior (alpha=1, beta=1)
    if n <= 0:
        return 0.0
    # Confidence grows with observations (capped at ~20 for stability).
    confidence = min(n / 20.0, 1.0)
    return (posterior_mean - 0.5) * confidence


def get_authority_score(url_or_domain: str) -> float:
    """Get the authority score (0.0–1.0) for a URL or domain.

    Combines the seed table with bandit adjustments::

        score = clamp(seed + bandit_adjustment, 0.0, 1.0)
    """
    domain = _extract_domain(url_or_domain) or (url_or_domain or "").lower().strip()
    if not domain:
        return DEFAULT_AUTHORITY

    # Strip www. if it survived extraction
    if domain.startswith("www."):
        domain = domain[4:]

    seed = _SEED_AUTHORITY.get(domain, DEFAULT_AUTHORITY)
    adjustment = _bandit_adjustment(domain)
    return max(0.0, min(1.0, seed + adjustment))


def record_domain_outcome(
    url_or_domain: str,
    success: bool,
    *,
    weight: float = 1.0,
) -> None:
    """Record a success/failure outcome for a domain.

    This updates the Beta-Binomial posterior so future authority scores
    reflect observed quality.  A *success* means the result was useful
    (high relevance, clicked, not spam); a *failure* means it was poor
    (low relevance, spam, broken).

    Args:
        url_or_domain: the URL or bare domain to record for.
        success: True if the outcome was positive, False otherwise.
        weight: how much to weight this outcome (default 1.0).  Use
            higher weights for stronger signals (e.g. user click = 2.0).
    """
    domain = _extract_domain(url_or_domain) or (url_or_domain or "").lower().strip()
    if not domain:
        return
    if domain.startswith("www."):
        domain = domain[4:]

    adjustments = _load_adjustments()
    entry = adjustments.get(domain, {"alpha": 1.0, "beta": 1.0})
    if success:
        entry["alpha"] = entry.get("alpha", 1.0) + weight
    else:
        entry["beta"] = entry.get("beta", 1.0) + weight
    adjustments[domain] = entry
    _save_adjustments(adjustments)


def get_authority_table() -> Dict[str, float]:
    """Return the full authority table (seed + adjusted scores) for inspection."""
    out = dict(_SEED_AUTHORITY)
    adjustments = _load_adjustments()
    for domain in adjustments:
        out[domain] = get_authority_score(domain)
    return out


def reset_authority(domain: Optional[str] = None) -> int:
    """Reset bandit adjustments for a domain (or all domains).

    Args:
        domain: if given, reset only this domain's adjustments.
            If None, reset all adjustments (back to seed scores).

    Returns:
        Number of domains reset.
    """
    global _cache
    adjustments = _load_adjustments()
    if domain:
        if domain in adjustments:
            del adjustments[domain]
            _save_adjustments(adjustments)
            return 1
        return 0
    count = len(adjustments)
    _save_adjustments({})
    return count
