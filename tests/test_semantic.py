"""Tests for the semantic retrieval layer (Phase 1).

Covers:
  - BM25 scoring (Lucene-style, always-positive idf)
  - RRF fusion
  - MinHash dedup
  - semantic_rerank full pipeline (BM25-only fallback when torch absent)
  - SemanticIndex + QueryCache (skipped if torch/lancedb unavailable)

The vector/cross-encoder tests are gated on optional deps (torch,
sentence-transformers, lancedb) so the suite passes in a minimal environment.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


# ── BM25 ────────────────────────────────────────────────────────────────────

def test_bm25_returns_positive_scores():
    from scout_it.semantic.retrieval import _bm25_scores

    docs = [
        "climate change coastal flooding",
        "how to bake cookies sugar butter",
        "hiking trails california yosemite",
    ]
    scores = _bm25_scores("climate flooding", docs)
    assert len(scores) == 3
    # Climate doc should score highest.
    assert scores[0] == max(scores)
    # All scores should be non-negative (Lucene idf is always positive).
    assert all(s >= 0 for s in scores)


def test_bm25_empty_inputs():
    from scout_it.semantic.retrieval import _bm25_scores

    assert _bm25_scores("query", []) == []
    assert _bm25_scores("", ["some doc"]) == [0.0]


def test_bm25_handles_unknown_query_terms():
    from scout_it.semantic.retrieval import _bm25_scores

    docs = ["climate change", "baking cookies"]
    scores = _bm25_scores("quantum physics", docs)
    # No matching terms → all zeros, not a crash.
    assert scores == [0.0, 0.0]


# ── RRF fusion ───────────────────────────────────────────────────────────────

def test_rrf_fuses_two_rankings():
    from scout_it.semantic.retrieval import _rrf_fuse

    # Two rankings: bm25=[0,1,2], vec=[1,0,2]
    # Doc 0 is rank-1 in bm25, rank-2 in vec → high fused score.
    # Doc 1 is rank-2 in bm25, rank-1 in vec → high fused score.
    # Doc 2 is rank-3 in both → lowest fused score.
    fused = _rrf_fuse([[0, 1, 2], [1, 0, 2]])
    # Doc 2 should be last (rank-3 in both).
    assert fused[-1] == 2
    # Docs 0 and 1 should be the top two (in either order).
    assert set(fused[:2]) == {0, 1}


def test_rrf_empty_input():
    from scout_it.semantic.retrieval import _rrf_fuse

    assert _rrf_fuse([]) == []


# ── MinHash dedup ───────────────────────────────────────────────────────────

def test_dedup_collapses_near_duplicates():
    from scout_it.semantic.dedup import deduplicate_results

    results = [
        {"title": "Breaking: Major earthquake hits Turkey",
         "url": "https://news.com/quake",
         "content": "A major earthquake struck Turkey today, causing widespread damage and injuries."},
        {"title": "Major earthquake hits Turkey",
         "url": "https://other-news.com/quake-syndicated",
         "content": "A major earthquake struck Turkey today, causing widespread damage and injuries."},
        {"title": "How to make pasta",
         "url": "https://cooking.com/pasta",
         "content": "Boil water, add pasta, cook for 10 minutes."},
    ]
    deduped = deduplicate_results(results)
    assert len(deduped) == 2
    # The survivor of the earthquake pair should list the collapsed duplicate URL.
    quake_survivor = [r for r in deduped if "earthquake" in r["title"].lower()][0]
    assert "duplicates" in quake_survivor
    # The survivor keeps its own URL; the duplicate's URL is in the list.
    all_urls = {r.get("url") for r in results}
    dup_urls = set(quake_survivor["duplicates"])
    assert dup_urls.issubset(all_urls)
    assert quake_survivor["url"] not in dup_urls


def test_dedup_keeps_distinct_results():
    from scout_it.semantic.dedup import deduplicate_results

    results = [
        {"title": "Climate change report", "url": "https://a.com", "content": "Climate change is real."},
        {"title": "Baking guide", "url": "https://b.com", "content": "How to bake bread at home."},
    ]
    deduped = deduplicate_results(results)
    assert len(deduped) == 2


def test_dedup_single_result():
    from scout_it.semantic.dedup import deduplicate_results

    results = [{"title": "Solo", "url": "https://a.com", "content": "Only one result here."}]
    assert deduplicate_results(results) == results


# ── semantic_rerank (BM25-only path, no torch needed) ───────────────────────

def test_semantic_rerank_bm25_only_fallback():
    """When torch/sentence-transformers are unavailable, rerank still works via BM25."""
    from scout_it.semantic import retrieval

    results = [
        {"title": "Cookie recipe sugar butter",
         "url": "https://a.com",
         "content": "bake cookies sugar butter flour eggs"},
        {"title": "Climate change coastal flooding",
         "url": "https://b.com",
         "content": "climate change sea level rise coastal flooding cities"},
        {"title": "Hiking trails california",
         "url": "https://c.com",
         "content": "hiking yosemite big sur california trails"},
    ]
    with mock.patch.object(retrieval.embeddings, "is_available", return_value=False):
        reranked = retrieval.semantic_rerank(results, "climate change coastal flooding", enable_reranker=False)
    assert len(reranked) == 3
    # BM25 should rank the climate doc #1.
    assert "climate" in reranked[0]["title"].lower()
    # Each result should have semantic_rank and semantic_score.
    assert "semantic_rank" in reranked[0]
    assert "semantic_score" in reranked[0]


def test_semantic_rerank_empty_results():
    from scout_it.semantic.retrieval import semantic_rerank

    assert semantic_rerank([], "query") == []


def test_semantic_rerank_single_result():
    from scout_it.semantic.retrieval import semantic_rerank

    results = [{"title": "Only", "url": "https://a.com", "content": "one result"}]
    reranked = semantic_rerank(results, "query", enable_reranker=False)
    assert len(reranked) == 1
    assert reranked[0]["semantic_rank"] == 1


def test_semantic_rerank_preserves_all_results():
    """Re-ranking should never drop results (except via dedup)."""
    from scout_it.semantic.retrieval import semantic_rerank

    results = [
        {"title": f"Result {i}", "url": f"https://example{i}.com",
         "content": f"content about topic {i}"}
        for i in range(10)
    ]
    reranked = semantic_rerank(results, "topic", enable_reranker=False, enable_dedup=False)
    assert len(reranked) == 10


# ── Config ──────────────────────────────────────────────────────────────────


# ── BM25F multi-field scoring ──────────────────────────────────────────────

def test_bm25f_field_boost_title_outranks_content():
    """Title matches should score higher than content matches (field boost)."""
    from scout_it.semantic.bm25f import build_index

    docs = [
        {"title": "Python tutorial", "content": "nothing relevant here", "url": "https://a.com"},
        {"title": "nothing relevant here", "content": "Learn Python programming today", "url": "https://b.com"},
    ]
    idx = build_index(docs)
    results = idx.search("python", top_k=2)
    assert results[0][0] == 0  # title match wins


def test_bm25f_typo_tolerance():
    """Query with a typo should still match the correct document."""
    from scout_it.semantic.bm25f import build_index

    docs = [
        {"title": "Climate change research", "content": "Climate change causes flooding", "url": "https://a.com"},
        {"title": "Cookie recipe", "content": "Baking cookies with sugar", "url": "https://b.com"},
    ]
    idx = build_index(docs)
    # "climat" (missing 'e') should still match "climate" via typo tolerance.
    results = idx.search("climat chang", top_k=2)
    assert results[0][0] == 0


def test_bm25f_prefix_matching():
    """Short query prefixes should match longer document terms."""
    from scout_it.semantic.bm25f import build_index

    docs = [{"title": "Computers and computing", "content": "Computer science", "url": "https://a.com"}]
    idx = build_index(docs)
    # "comp" is a prefix of "computers", "computing", "computer".
    results = idx.search("comp", top_k=1)
    assert len(results) > 0


def test_bm25f_exact_phrase_boost():
    """Exact contiguous phrase matches should score higher than scattered terms."""
    from scout_it.semantic.bm25f import build_index

    docs = [
        {"title": "Climate change is real", "content": "unrelated baking text", "url": "https://a.com"},
        {"title": "Climate and change separately", "content": "words about climate and change not together", "url": "https://b.com"},
    ]
    idx = build_index(docs)
    results = idx.search("climate change", top_k=2)
    # Doc 0 has "climate change" as a contiguous phrase → boosted.
    assert results[0][0] == 0


def test_bm25f_stemming():
    """Stemmed variants should match (running→run, computers→computer)."""
    from scout_it.semantic.bm25f import build_index, porter_stem

    assert porter_stem("running") == "run"
    assert porter_stem("computers") == "computer"

    docs = [
        {"title": "Machine learning models", "content": "Training models on data", "url": "https://a.com"},
        {"title": "Cookie baking", "content": "Baking cookies", "url": "https://b.com"},
    ]
    idx = build_index(docs)
    # "training" stems to "train", "models" to "model" — should still match.
    results = idx.search("trained model", top_k=2)
    assert results[0][0] == 0


def test_bm25f_empty_index():
    from scout_it.semantic.bm25f import BM25FIndex

    idx = BM25FIndex()
    assert idx.search("anything", top_k=10) == []
    assert idx.doc_count == 0


def test_bm25f_unicode_tokenization():
    """Tokenizer should handle non-ASCII (CJK, Cyrillic, accented chars)."""
    from scout_it.semantic.bm25f import tokenize

    # CJK
    assert len(tokenize("人工智能机器学习")) > 0
    # Cyrillic
    assert len(tokenize("машинное обучение")) > 0
    # Accented Latin
    assert len(tokenize("café résumé naïve")) >= 3


# ── Facets ──────────────────────────────────────────────────────────────────

def test_facets_domain_aggregation():
    from scout_it.semantic.facets import compute_facets

    results = [
        {"url": "https://www.github.com/repo1"},
        {"url": "https://github.com/repo2"},
        {"url": "https://stackoverflow.com/q/123"},
    ]
    facets = compute_facets(results)
    assert facets["domain"]["github.com"] == 2  # www stripped
    assert facets["domain"]["stackoverflow.com"] == 1


def test_facets_date_aggregation():
    from scout_it.semantic.facets import compute_facets

    results = [
        {"date": "2025-03-15"},
        {"date": "2025-03-20"},
        {"date": "2025-04-01"},
    ]
    facets = compute_facets(results)
    assert facets["date"]["2025-03"] == 2
    assert facets["date"]["2025-04"] == 1


def test_facets_filter_by_domain():
    from scout_it.semantic.facets import filter_by_facet

    results = [
        {"url": "https://github.com/repo1", "title": "A"},
        {"url": "https://stackoverflow.com/q/123", "title": "B"},
        {"url": "https://github.com/repo2", "title": "C"},
    ]
    filtered = filter_by_facet(results, "domain", "github.com")
    assert len(filtered) == 2
    assert filtered[0]["title"] == "A"


def test_facets_empty_results():
    from scout_it.semantic.facets import compute_facets

    facets = compute_facets([])
    assert all(len(v) == 0 for v in facets.values())


# ── BM25F in staged_ranker ─────────────────────────────────────────────────

def test_staged_ranker_uses_bm25f():
    """rank_candidates_initial should use BM25F and produce better ranking."""
    from scout_it.staged_ranker import rank_candidates_initial

    candidates = [
        {"title": "Climate change coastal flooding", "body": "Sea level rise", "url": "https://a.com"},
        {"title": "Cookie recipe", "body": "Baking cookies", "url": "https://b.com"},
        {"title": "Hiking trails", "body": "California trails", "url": "https://c.com"},
        {"title": "Sea level rise research", "body": "Climate change research", "url": "https://d.com"},
    ]
    ranked = rank_candidates_initial(candidates, "climate change coastal flooding", top_k=3)
    assert len(ranked) <= 3
    assert "initial_rank_score" in ranked[0]
    assert ranked[0].get("rank_method") == "bm25f"
    # Climate doc should be ranked #1.
    assert "climate" in ranked[0]["title"].lower()


def test_semantic_rerank_includes_facets():
    """semantic_rerank should attach _facets to each result."""
    from scout_it.semantic import semantic_rerank

    results = [
        {"title": "Climate change", "url": "https://climate.com", "content": "Sea level rise", "date": "2025-03-01", "source": "ddg"},
        {"title": "Cookies", "url": "https://food.com", "content": "Baking", "date": "2025-04-01", "source": "rss"},
    ]
    reranked = semantic_rerank(results, "climate", enable_reranker=False)
    assert "_facets" in reranked[0]
    assert "domain" in reranked[0]["_facets"]
    assert "date" in reranked[0]["_facets"]


# ── Config ──────────────────────────────────────────────────────────────────

def test_config_paths_under_home():
    from scout_it.semantic import config

    assert "semantic" in str(config.SEMANTIC_DIR)
    assert "lancedb" in str(config.LANCEDB_DIR)
    # The semantic dir must live under the home ~/.scout-it/ tree.
    assert str(config.SEMANTIC_DIR).startswith(str(Path.home()))


def test_config_model_resolution_from_env():
    from scout_it.semantic import config

    with mock.patch.dict(os.environ, {"SCOUT_SEMANTIC_MODEL": "test/model"}):
        assert config.get_embedding_model_name() == "test/model"


def test_config_ensure_dirs():
    from scout_it.semantic import config

    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(config, "SEMANTIC_DIR", Path(tmp) / "semantic"):
            with mock.patch.object(config, "LANCEDB_DIR", Path(tmp) / "semantic" / "lancedb"):
                config.ensure_dirs()
                assert (Path(tmp) / "semantic").exists()
                assert (Path(tmp) / "semantic" / "lancedb").exists()


# ── Embeddings availability check ────────────────────────────────────────────

def test_is_available_returns_bool():
    from scout_it.semantic.embeddings import is_available

    assert isinstance(is_available(), bool)


# ── Optional: vector + cross-encoder tests (require torch + sentence-transformers) ──

_torch_available = pytest.importorskip("torch", reason="torch not installed")
_st_available = pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")


@pytest.fixture(autouse=True)
def _use_fast_model(monkeypatch):
    """Use the tiny MiniLM model so tests don't download BGE-m3 (~2 GB)."""
    monkeypatch.setenv("SCOUT_SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    # Reset cached singletons so the new model name takes effect.
    from scout_it.semantic import embeddings
    embeddings.reset_singletons()


def test_vector_retrieval_ranks_relevant_first():
    """Full hybrid BM25+vector rerank ranks semantically-relevant docs on top."""
    from scout_it.semantic import semantic_rerank

    results = [
        {"title": "How to bake chocolate chip cookies",
         "url": "https://cooking.example.com/cookies",
         "content": "To bake chocolate chip cookies, mix flour sugar butter eggs and chocolate chips."},
        {"title": "Climate change impact on coastal cities",
         "url": "https://climate.example.com/coastal",
         "content": "Climate change is causing sea levels to rise, threatening coastal cities with flooding."},
        {"title": "Best hiking trails in California",
         "url": "https://travel.example.com/ca-trails",
         "content": "California offers diverse hiking from Yosemite to Big Sur."},
        {"title": "Sea level rise and coastal flooding research",
         "url": "https://research.example.com/sea-level",
         "content": "Research on how rising sea levels from climate change increase coastal flooding risk."},
    ]
    reranked = semantic_rerank(results, "climate change coastal cities flooding", enable_reranker=False)
    # Top result must be one of the two climate docs, NOT cookies or hiking.
    top_title = reranked[0]["title"].lower()
    assert "climate" in top_title or "sea level" in top_title
    assert "cookie" not in top_title


def test_cross_encoder_rerank():
    """Cross-encoder rerank runs and attaches the 'reranked' flag."""
    from scout_it.semantic import semantic_rerank

    results = [
        {"title": "Climate change impact on coastal cities",
         "url": "https://climate.example.com/coastal",
         "content": "Climate change is causing sea levels to rise, threatening coastal cities with flooding."},
        {"title": "Cookie recipe",
         "url": "https://cooking.example.com/cookies",
         "content": "Bake cookies with flour sugar butter eggs chocolate chips."},
    ]
    with mock.patch.dict(os.environ, {"SCOUT_RERANKER_MODEL": "cross-encoder/ms-marco-MiniLM-L-6-v2"}):
        from scout_it.semantic import embeddings
        embeddings.reset_singletons()
        reranked = semantic_rerank(results, "climate change coastal flooding", enable_reranker=True)
    assert len(reranked) == 2
    assert "climate" in reranked[0]["title"].lower()


# ── Optional: LanceDB store tests ──────────────────────────────────────────

_lancedb = pytest.importorskip("lancedb", reason="lancedb not installed")


def test_semantic_index_add_and_search(tmp_path, monkeypatch):
    from scout_it.semantic import config
    from scout_it.semantic.store import SemanticIndex

    monkeypatch.setattr(config, "SEMANTIC_DIR", tmp_path / "semantic")
    monkeypatch.setattr(config, "LANCEDB_DIR", tmp_path / "semantic" / "lancedb")
    config.ensure_dirs()

    idx = SemanticIndex()
    idx.add_documents([
        {"title": "Climate impacts",
         "url": "https://example.com/a",
         "content": "Climate change is causing sea levels to rise, threatening coastal cities with flooding."},
        {"title": "Cookie recipe",
         "url": "https://example.com/b",
         "content": "To bake chocolate chip cookies, mix flour sugar butter eggs."},
    ], source="test")
    assert idx.count() > 0

    hits = idx.search("coastal flooding climate", top_k=3)
    assert len(hits) > 0
    assert hits[0]["url"] == "https://example.com/a"


def test_semantic_query_cache(tmp_path, monkeypatch):
    from scout_it.semantic import config
    from scout_it.semantic.store import QueryCache
    from scout_it.semantic.embeddings import embed_query
    import numpy as np

    monkeypatch.setattr(config, "QUERY_CACHE_DB", str(tmp_path / "query_cache.db"))
    cache = QueryCache()
    qvec = embed_query("climate change")
    cache.store("climate change", qvec, [{"title": "cached result"}])
    hit = cache.lookup(qvec)
    assert hit is not None
    assert hit[0]["title"] == "cached result"
