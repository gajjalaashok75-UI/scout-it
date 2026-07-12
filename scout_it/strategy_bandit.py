#!/usr/bin/env python3
"""
🎰 STRATEGY BANDIT — Thompson sampling over cached fetch strategies
========================================================================

Turns the raw success/failure counts in ``strategy_cache.py`` into an actual
decision: which {tier, proxy_id, fingerprint_profile} combination should
the *next* request for this domain try first?

Thompson sampling (Beta-Bernoulli): each arm's success rate is modeled as a
Beta(successes + 1, failures + 1) distribution. At decision time, one sample
is drawn from each known arm's distribution, and the arm with the highest
sample wins. This naturally balances "use what's worked" (arms with many
successes have a tight, high-valued distribution) against "keep a live read
on whether it's still working" (arms with few attempts have a wide
distribution and can still occasionally win the sample, providing
exploration) -- without a separate, hand-tuned epsilon.

Pure stdlib (``random.betavariate``) -- no new dependency, no network call,
no AI/model API of any kind.
"""

import random
from typing import Any, Dict, List, Optional, Tuple

from . import strategy_cache as cache

# The fixed order used today when a domain has no history at all -- this
# stays the default/fallback exactly as the spec requires ("keeping today's
# fixed-order behavior as the fallback when no cache entry exists yet").
DEFAULT_TIER_ORDER = ["requests", "playwright", "basic-fallback"]
DEFAULT_PROXY = "direct"
DEFAULT_FINGERPRINT = "default"

# Below this many total attempts for a domain, don't trust the bandit yet --
# fall back to the fixed default order (avoids over-committing to a single
# lucky/unlucky early result).
MIN_ATTEMPTS_BEFORE_BANDIT = 3


def _sample_arm(arm: Dict[str, Any]) -> float:
    successes = arm["successes"] + 1  # Beta prior: Beta(1,1) = uniform for an unseen arm
    failures = arm["failures"] + 1
    return random.betavariate(successes, failures)


def choose_strategy(
    url: str,
    available_tiers: Optional[List[str]] = None,
    available_proxies: Optional[List[str]] = None,
    available_fingerprints: Optional[List[str]] = None,
    db_path=None,
) -> Dict[str, Any]:
    """Pick a starting {tier, proxy_id, fingerprint_profile} for *url*.

    On a domain with no history (or too little), returns the cheapest
    default combination (Tier 1 / direct / default fingerprint) -- identical
    to today's fixed-order behavior. On a domain with enough history, samples
    from the learned Beta distribution over every combination actually tried
    before, restricted to what's currently available (e.g. don't recommend a
    proxy that's no longer configured).

    Returns ``{"tier": ..., "proxy_id": ..., "fingerprint_profile": ...,
    "source": "default" | "bandit", "confidence": float}``.
    """
    domain = cache.domain_of(url)
    arms = cache.get_arms(domain, db_path)

    available_tiers = available_tiers or DEFAULT_TIER_ORDER
    available_proxies = available_proxies or [DEFAULT_PROXY]
    available_fingerprints = available_fingerprints or [DEFAULT_FINGERPRINT]

    # Only consider arms that are still actually usable right now (e.g. a
    # proxy that's since been removed from config shouldn't win a sample).
    usable_arms = [
        a for a in arms
        if a["tier"] in available_tiers
        and a["proxy_id"] in available_proxies
        and a["fingerprint_profile"] in available_fingerprints
    ]
    total_attempts = sum(a["successes"] + a["failures"] for a in usable_arms)

    if total_attempts < MIN_ATTEMPTS_BEFORE_BANDIT:
        return {
            "tier": available_tiers[0],
            "proxy_id": available_proxies[0],
            "fingerprint_profile": available_fingerprints[0],
            "source": "default",
            "confidence": 0.0,
        }

    best_arm = None
    best_sample = -1.0
    for arm in usable_arms:
        sample = _sample_arm(arm)
        if sample > best_sample:
            best_sample = sample
            best_arm = arm

    n = best_arm["successes"] + best_arm["failures"]
    observed_rate = best_arm["successes"] / n if n else 0.0

    return {
        "tier": best_arm["tier"],
        "proxy_id": best_arm["proxy_id"],
        "fingerprint_profile": best_arm["fingerprint_profile"],
        "source": "bandit",
        "confidence": round(observed_rate, 3),
    }


def record(
    url: str,
    tier: str,
    success: bool,
    proxy_id: str = DEFAULT_PROXY,
    fingerprint_profile: str = DEFAULT_FINGERPRINT,
    latency_ms: Optional[int] = None,
    db_path=None,
) -> None:
    """Thin pass-through to strategy_cache.record_outcome -- kept here too so
    callers only need to import strategy_bandit for the whole choose/record
    cycle."""
    cache.record_outcome(url, tier, success, proxy_id, fingerprint_profile, latency_ms, db_path)
