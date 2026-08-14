"""scout_it.semantic — semantic retrieval layer (Phase 1).

Two modes of operation:

**Mode A — live semantic re-rank (default, no indexing required)::

    from scout_it.semantic import semantic_rerank

    results, stats = web_search("climate impact", max_results=20)
    reranked = semantic_rerank(results, "climate impact")
    # `reranked` has the same shape as `results`, just better-ordered.

**Mode B — indexed semantic search (persistent corpus / RAG)::

    from scout_it.semantic import SemanticIndex

    idx = SemanticIndex()
    idx.add_documents(results)                    # fetch+embed+persist
    hits = idx.search("coastal flooding", top_k=5)  # hybrid retrieval over corpus

Search strategies (ported from Orama, all pure-algorithmic, no LLM API):
    - BM25F multi-field scoring (title, snippet, content, url)
    - Typo tolerance (Levenshtein edit distance)
    - Prefix matching
    - Exact phrase boost
    - Porter stemming (English) + Unicode tokenization (30+ languages)
    - Facets (domain, date, source, language aggregations)
    - Dense vector cosine similarity (optional, needs sentence-transformers)
    - RRF fusion + cross-encoder rerank (optional)

Public API:
    - ``semantic_rerank``           — hybrid BM25F+vector re-rank + RRF + cross-encoder + dedup
    - ``composite_rerank``          — Phase 3 composite: relevance + authority + freshness + diversity
    - ``semantic_search_with_facets`` — same, but also returns facet aggregations
    - ``SemanticIndex``             — persistent LanceDB document store for indexed search
    - ``QueryCache``                — semantic query cache (reuse results for similar queries)
    - ``BM25FIndex`` / ``build_index`` — direct BM25F index access
    - ``compute_facets``           — facet aggregations over result sets
"""

from .retrieval import semantic_rerank, semantic_search_with_facets
from .composite_score import composite_score, composite_rerank, DEFAULT_WEIGHTS, GENERAL_WEIGHTS
from .store import SemanticIndex, QueryCache
from .embeddings import is_available, get_embedding_dim
from .bm25f import BM25FIndex, build_index as build_bm25f_index
from .facets import compute_facets, filter_by_facet
from . import config

__all__ = [
    "semantic_rerank",
    "composite_score",
    "composite_rerank",
    "DEFAULT_WEIGHTS",
    "GENERAL_WEIGHTS",
    "semantic_search_with_facets",
    "SemanticIndex",
    "QueryCache",
    "is_available",
    "get_embedding_dim",
    "BM25FIndex",
    "build_bm25f_index",
    "compute_facets",
    "filter_by_facet",
    "config",
]
