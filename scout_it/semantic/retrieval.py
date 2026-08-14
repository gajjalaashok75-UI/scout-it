"""Hybrid retrieval: BM25F + dense vectors, RRF fusion, cross-encoder rerank.

This is the core of Phase 1. It takes a list of search results (each a dict
with at least title/snippet/content) and a query, and re-ranks them by
semantic relevance rather than source order.

Pipeline (Mode A — live re-rank, no pre-indexing required):

    query + results
        │
        ├── BM25F over result fields            → bm25_rank   (sparse, multi-field)
        │   (title, snippet, content, url — each with per-field weights)
        │   (typo tolerance, prefix matching, phrase boost, stemming)
        ├── dense vector cosine similarity      → vec_rank    (semantic)
        │
        ▼
    RRF fusion (parameter-free)                 → fused_rank
        │
        ▼  top-K
    cross-encoder rerank (optional)             → final_rank
        │
        ▼
    MinHash dedup                               → output
    + facets (domain, date, source, language)

If the heavy ML deps (torch / sentence-transformers) are not installed, the
hybrid path gracefully degrades to BM25F-only (still better than source order
for relevance, and no crash).
"""

from __future__ import annotations

import logging
import math
import re
from typing import Dict, List, Optional, Tuple

try:
    import numpy as np  # only needed for the optional dense-vector path
except ImportError:  # pragma: no cover - graceful degradation, see module docstring
    np = None

from . import config, dedup, embeddings
from .bm25f import BM25FIndex, build_index as build_bm25f_index
from .facets import compute_facets

logger = logging.getLogger(__name__)


def _result_text(r: Dict) -> str:
    """Concatenate the searchable text fields of a result."""
    parts = [
        (r.get("title") or "").strip(),
        (r.get("snippet") or r.get("description") or "").strip(),
        (r.get("content") or "").strip()[:2000],
    ]
    return " ".join(p for p in parts if p)


def _tokenize(text: str) -> List[str]:
    """Lightweight whitespace+punct tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


class _BM25:
    """Minimal BM25 implementation with Lucene-style idf (always positive).

    The standard ``rank_bm25`` package clips idf to 0 when a term appears in
    ~50% of docs (common with small result sets: log(1)=0), which zeroes out
    all scores. Lucene/Elasticsearch avoid this by using
    ``idf = log(1 + (N - n + 0.5)/(n + 0.5))`` — always strictly positive —
    so even tiny corpora get meaningful relative scores. We implement that
    variant here and drop the external dependency.
    """

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self._k1 = k1
        self._b = b
        self._N = len(corpus)
        self._doc_len = [len(d) for d in corpus]
        self._avgdl = (sum(self._doc_len) / self._N) if self._N else 0.0
        # term → document frequency
        df: Dict[str, int] = {}
        # term → {doc_idx: term_freq}
        self._tf: Dict[str, Dict[int, int]] = {}
        for i, doc in enumerate(corpus):
            seen: Dict[str, int] = {}
            for term in doc:
                seen[term] = seen.get(term, 0) + 1
            for term, freq in seen.items():
                df[term] = df.get(term, 0) + 1
                self._tf.setdefault(term, {})[i] = freq
        # Lucene idf: always positive
        self._idf = {
            term: math.log(1.0 + (self._N - n + 0.5) / (n + 0.5))
            for term, n in df.items()
        }

    def get_scores(self, query_terms: List[str]) -> List[float]:
        if self._N == 0 or self._avgdl == 0:
            return [0.0] * self._N
        scores = [0.0] * self._N
        for term in set(query_terms):
            idf = self._idf.get(term, 0.0)
            if idf == 0.0:
                continue
            postings = self._tf.get(term, {})
            for doc_idx, freq in postings.items():
                dl = self._doc_len[doc_idx]
                denom = freq + self._k1 * (1 - self._b + self._b * dl / self._avgdl)
                scores[doc_idx] += idf * (freq * (self._k1 + 1)) / denom
        return scores


def _bm25_scores(query: str, docs: List[str]) -> List[float]:
    """Return BM25 relevance scores for *query* against each doc."""
    if not docs:
        return []
    tokenized = [_tokenize(d) for d in docs]
    bm25 = _BM25(tokenized)
    q_tokens = _tokenize(query)
    if not q_tokens:
        return [0.0] * len(docs)
    return [float(s) for s in bm25.get_scores(q_tokens)]


def _vector_scores(query_vec, doc_vecs) -> List[float]:
    """Cosine similarity (= dot product, since vectors are L2-normalized)."""
    if doc_vecs is None or len(doc_vecs) == 0:
        return []
    if np is None:  # numpy missing → dense path disabled, BM25F-only fallback
        return [0.0] * len(doc_vecs)
    arr = np.asarray(doc_vecs)
    if arr.size == 0:
        return []
    return (arr @ np.asarray(query_vec).flatten()).tolist()


def _rrf_fuse(rank_lists: List[List[int]], k: int = config.RRF_K) -> List[int]:
    """Reciprocal Rank Fusion over multiple ranked-orderings.

    *rank_lists* is a list of permutations (each a list of indices into the
    original result set, best-first). Returns a single fused ordering.
    RRF score for a doc = sum over rank lists of 1/(k + rank).
    """
    if not rank_lists:
        return []
    n = len(rank_lists[0])
    scores = [0.0] * n
    for ranking in rank_lists:
        for position, doc_idx in enumerate(ranking):
            scores[doc_idx] += 1.0 / (k + position + 1)
    return sorted(range(n), key=lambda i: -scores[i])


def _argsort_desc(scores: List[float]) -> List[int]:
    """Return indices that would sort *scores* descending."""
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def semantic_rerank(
    results: List[Dict],
    query: str,
    *,
    enable_reranker: bool = True,
    enable_dedup: bool = True,
    top_k_rerank: int = config.RERANK_TOP_K,
) -> List[Dict]:
    """Re-rank search results by hybrid BM25+vector relevance.

    This is the public entry point for Mode A (live re-rank). It accepts the
    raw keyword-search results and returns them re-ordered by semantic
    relevance, with near-duplicates collapsed.

    Args:
        results: list of result dicts (title/snippet/content fields).
        query: the original search query string.
        enable_reranker: if True (and deps available), run the cross-encoder
            over the top-K fused candidates for a final quality pass.
        enable_dedup: if True, collapse near-duplicates via MinHash+LSH.
        top_k_rerank: how many top fused candidates to cross-encode.

    Returns:
        The same result dicts, re-ordered and possibly de-duplicated. Each
        survivor may carry a ``duplicates`` list of collapsed URLs and a
        ``semantic_score`` field.
    """
    if not results:
        return []

    # ── Stage 1a: BM25F scores (multi-field: title, snippet, content, url) ──
    # BM25F gives each field its own BM25 score with per-field weights,
    # plus typo tolerance, prefix matching, phrase boost, and stemming.
    bm25f_idx = build_bm25f_index(results)
    bm25f_results = bm25f_idx.search(query, top_k=len(results))
    # Build a score array aligned with original result indices.
    bm25_scores = [0.0] * len(results)
    for doc_idx, score, _field_scores in bm25f_results:
        bm25_scores[doc_idx] = score
    bm25_rank = _argsort_desc(bm25_scores)

    # ── Stage 1b: dense vector scores (graceful fallback if no deps) ──
    rank_lists = [bm25_rank]
    vec_scores: List[float] = []
    if embeddings.is_available() and len(results) > 1:
        try:
            docs = [_result_text(r) for r in results]
            doc_vecs = embeddings.embed_texts(docs)
            query_vec = embeddings.embed_query(query)
            vec_scores = _vector_scores(query_vec, doc_vecs)
            vec_rank = _argsort_desc(vec_scores)
            rank_lists.append(vec_rank)
        except Exception as exc:
            logger.warning("Vector retrieval failed (%s); falling back to BM25F-only.", exc)

    # ── Stage 2: RRF fusion ──
    fused_order = _rrf_fuse(rank_lists)

    # Attach a composite score (fused RRF score) for transparency.
    def _fused_score(idx: int) -> float:
        s = 0.0
        for ranking in rank_lists:
            pos = ranking.index(idx)
            s += 1.0 / (config.RRF_K + pos + 1)
        return s

    # ── Stage 3: cross-encoder rerank (optional, top-K only) ──
    top_k = min(top_k_rerank, len(fused_order))
    candidate_idx = fused_order[:top_k]
    reranker_used = False
    if enable_reranker and embeddings.is_available() and top_k > 1:
        try:
            candidate_docs = [_result_text(results[i]) for i in candidate_idx]
            ce_scores = embeddings.cross_encoder_scores(query, candidate_docs)
            # Re-sort just the candidates by cross-encoder score.
            cand_sorted = sorted(
                range(top_k), key=lambda j: -ce_scores[j]
            )
            candidate_idx = [candidate_idx[j] for j in cand_sorted]
            reranker_used = True
        except Exception as exc:
            logger.warning("Cross-encoder rerank failed (%s); skipping.", exc)

    # Reassemble: reranked candidates first, then the rest in fused order.
    remaining = [i for i in fused_order if i not in set(candidate_idx)]
    final_order = candidate_idx + remaining

    out: List[Dict] = []
    for rank, idx in enumerate(final_order):
        r = dict(results[idx])
        r["semantic_rank"] = rank + 1
        r["semantic_score"] = round(_fused_score(idx), 6)
        if reranker_used and rank < top_k:
            r["reranked"] = True
        out.append(r)

    # ── Stage 4: MinHash dedup ──
    if enable_dedup and len(out) > 1:
        out = dedup.deduplicate_results(out)

    # Attach facets (domain, date, source, language aggregations).
    if out:
        _facets = compute_facets(out)
        for r in out:
            r["_facets"] = _facets

    return out


def semantic_search_with_facets(
    results: List[Dict],
    query: str,
    **kwargs,
) -> Tuple[List[Dict], Dict]:
    """Run semantic_rerank and return both results and facet aggregations.

    Convenience wrapper for callers that want the facets as a separate
    return value (e.g., for display in a UI).
    """
    reranked = semantic_rerank(results, query, **kwargs)
    facets = compute_facets(reranked) if reranked else {}
    return reranked, facets
