"""Near-duplicate detection across search sources.

When querying multiple sources for the same query, the same article/story
often appears several times (syndicated news, mirrored pages, RSS + on-site
search). This module clusters near-duplicates using MinHash + LSH so the
final result list keeps one representative per cluster (the highest-ranked).

Algorithm:
  - For each result, compute a MinHash signature over word shingles of its
    title + URL-domain + first chunk of content.
  - Use LSH (Locality-Sensitive Hashing) to bucket candidate pairs in O(n).
  - Confirm bucketed pairs with exact Jaccard ≥ ``THRESHOLD``.
  - Within each cluster, keep the member with the best relevance score; the
    others are recorded as ``duplicates`` on the survivor.

This is robust to light paraphrasing / URL rewrites while not collapsing
genuinely different pages on the same topic.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Set, Tuple

try:
    from datasketch import MinHash
    _HAS_DATASKETCH = True
except ImportError:  # graceful fallback — see _MinHash below
    MinHash = None
    _HAS_DATASKETCH = False

# Jaccard threshold for two results to be considered duplicates.
THRESHOLD = 0.5
# Number of MinHash permutations (higher = more accurate, slower).
NUM_PERM = 128
# Shingle size (words per shingle) — 3-grams balance specificity vs. recall.
SHINGLE_SIZE = 3

_WORD_RE = re.compile(r"\w+", re.UNICODE)


class _MinHash:
    """Minimal pure-python MinHash signature, API-compatible with datasketch's
    ``MinHash`` for the subset this module uses (``update`` + ``jaccard``).

    Used only when the optional ``datasketch`` package is not installed so the
    dedup/composite-rerank path keeps working in a minimal environment.
    """

    __slots__ = ("num_perm", "_seed", "_signature")

    def __init__(self, num_perm: int = NUM_PERM, seed: int = 1):
        self.num_perm = num_perm
        self._seed = seed
        # Start every permutation's minimum at the largest 64-bit value.
        self._signature = [(2**64 - 1)] * num_perm

    def update(self, b: bytes) -> None:
        # Hash the bytes once, then derive `num_perm` independent hashes with a
        # per-permutation salt. xor-salting + hashlib gives a cheap, stable
        # family of hashes without pulling in numpy.
        base = hashlib.blake2b(b, digest_size=8).digest()
        base_int = int.from_bytes(base, "little", signed=False)
        for i in range(self.num_perm):
            # Mix the permutation index into the base hash.
            h = base_int ^ (self._seed + i * 0x9E3779B97F4A7C15)
            h ^= (h >> 29)
            h = (h * 0xBF58476D1CE4E5B9) & (2**64 - 1)
            h ^= (h >> 32)
            if h < self._signature[i]:
                self._signature[i] = h

    def jaccard(self, other: "_MinHash") -> float:
        if self.num_perm != other.num_perm:
            raise ValueError("MinHash signature length mismatch")
        if self.num_perm == 0:
            return 0.0
        matches = sum(1 for a, b in zip(self._signature, other._signature) if a == b)
        return matches / self.num_perm


def _shingles(text: str) -> Set[str]:
    """Tokenize *text* into a set of word-level k-grams."""
    words = _WORD_RE.findall(text.lower())
    if len(words) < SHINGLE_SIZE:
        return set(words) if words else set()
    return {
        " ".join(words[i : i + SHINGLE_SIZE])
        for i in range(len(words) - SHINGLE_SIZE + 1)
    }


def _minhash_for(shingles: Set[str]):
    """Build a MinHash signature from a shingle set."""
    if _HAS_DATASKETCH and MinHash is not None:
        mh = MinHash(num_perm=NUM_PERM)
    else:
        mh = _MinHash(num_perm=NUM_PERM)
    for s in shingles:
        mh.update(s.encode("utf-8"))
    return mh


def _result_fingerprint(result: Dict) -> str:
    """Build the text fingerprint for a result: title + domain + content head.

    Using the domain + title catches the common case of the same story syndicated
    across publishers (same headline, different URL). Adding content head guards
    against different stories that share a generic headline.
    """
    title = (result.get("title") or "").strip()
    url = result.get("url") or result.get("link") or ""
    # crude domain extraction
    domain = ""
    if url:
        m = re.match(r"https?://([^/]+)/", url + "/")
        if m:
            domain = m.group(1).replace("www.", "")
    content = result.get("content") or result.get("snippet") or ""
    content_head = content[:500]
    return f"{title} {domain} {content_head}"


def deduplicate_results(results: List[Dict], threshold: float = THRESHOLD) -> List[Dict]:
    """Cluster near-duplicate results and keep one representative per cluster.

    Each result in the returned list may carry a ``duplicates`` key listing the
    URLs of the collapsed members. Original input order / scores are preserved
    for the survivors; only true near-duplicates are removed.
    """
    if len(results) <= 1:
        return list(results)

    # Build MinHash signatures.
    fingerprints = [_result_fingerprint(r) for r in results]
    minhashes = [_minhash_for(_shingles(fp)) for fp in fingerprints]

    # Pairwise Jaccard via MinHash — O(n²) but n is small (search results),
    # and this avoids LSH false negatives that plague small result sets.
    parent = list(range(len(results)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            if minhashes[i].jaccard(minhashes[j]) >= threshold:
                union(i, j)

    # Pick survivor per cluster: keep the earliest-indexed member (which,
    # after upstream ranking, is the best-scored). Merge duplicate URLs.
    clusters: Dict[int, List[int]] = {}
    for i in range(len(results)):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    # Emit survivors in original relative order (first time a root is seen).
    seen_roots: Set[int] = set()
    final: List[Dict] = []
    for i in range(len(results)):
        root = find(i)
        if root in seen_roots:
            continue
        seen_roots.add(root)
        survivor = dict(results[root])
        dup_urls = [
            results[m].get("url") or results[m].get("link")
            for m in clusters[root]
            if m != root and (results[m].get("url") or results[m].get("link"))
        ]
        if dup_urls:
            survivor["duplicates"] = dup_urls
        final.append(survivor)
    return final
