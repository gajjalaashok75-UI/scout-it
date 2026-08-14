"""Embedding model loading + encoding.

Heavy ML dependencies (torch, sentence-transformers) are imported LAZILY inside
the functions that need them, so the rest of scout-it works fine without these
installed. A clear RuntimeError is raised if they're missing and a semantic
feature is actually invoked.

Design:
  - A single ``_Embedder`` singleton wraps the SentenceTransformer model so the
    model loads once per process (loading takes seconds; encoding is then ms).
  - ``embed_texts`` returns L2-normalized vectors (so cosine similarity = dot).
  - ``embed_query`` is the same thing for a single string (convenience).
  - The cross-encoder reranker is loaded separately on demand, since it's only
    used for the top-K rerank step and is heavier to keep in memory.
"""

from __future__ import annotations

import logging
from typing import List, Optional

try:
    import numpy as np  # only required by the optional dense-vector path
except ImportError:  # pragma: no cover - graceful degradation
    np = None

from . import config

logger = logging.getLogger(__name__)

# Module-level singletons (populated on first use).
_embedder = None
_reranker = None


class _Embedder:
    """Wraps a SentenceTransformer bi-encoder for query/document embedding."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is required for semantic search. "
                "Install it with: pip install sentence-transformers torch"
            ) from exc
        logger.info("Loading embedding model %s …", model_name)
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        self._dim = config._MODEL_DIMS.get(model_name, -1)
        if self._dim < 0:
            # Infer dimension from a dummy encode if not in the lookup table.
            self._dim = int(self._model.encode(["dim"]).shape[1])
        logger.info("Embedding model ready (dim=%d).", self._dim)

    @property
    def dim(self) -> int:
        return self._dim

    def encode(self, texts: List[str]):
        """Encode texts to a (N, dim) matrix of L2-normalized float32 vectors."""
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32) if np is not None else []
        vecs = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32) if np is not None else vecs


class _CrossEncoderReranker:
    """Wraps a cross-encoder model for second-stage relevance reranking."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is required for cross-encoder reranking. "
                "Install it with: pip install sentence-transformers torch"
            ) from exc
        logger.info("Loading cross-encoder reranker %s …", model_name)
        self._model = CrossEncoder(model_name)
        logger.info("Cross-encoder reranker ready.")

    def score(self, query: str, documents: List[str]) -> List[float]:
        """Return a relevance score for each (query, document) pair."""
        if not documents:
            return []
        pairs = [(query, doc) for doc in documents]
        return [float(s) for s in self._model.predict(pairs)]


def _get_embedder() -> _Embedder:
    """Return the process-wide embedder singleton, loading on first call."""
    global _embedder
    if _embedder is None:
        _embedder = _Embedder(config.get_embedding_model_name())
    return _embedder


def _get_reranker() -> _CrossEncoderReranker:
    """Return the process-wide reranker singleton, loading on first call."""
    global _reranker
    if _reranker is None:
        _reranker = _CrossEncoderReranker(config.get_reranker_model_name())
    return _reranker


def embed_texts(texts: List[str]):
    """Embed a list of strings into L2-normalized vectors.

    Returns a (N, dim) float32 array. Empty input → (0, dim) array.
    Raises RuntimeError if sentence-transformers is not installed.
    """
    return _get_embedder().encode(texts)


def embed_query(query: str):
    """Embed a single query string → (1, dim) normalized vector."""
    return _get_embedder().encode([query])


def cross_encoder_scores(query: str, documents: List[str]) -> List[float]:
    """Score documents against *query* with the cross-encoder reranker."""
    return _get_reranker().score(query, documents)


def get_embedding_dim() -> int:
    """Return the embedding dimension for the configured model."""
    return _get_embedder().dim


def is_available() -> bool:
    """Check whether the heavy ML deps are importable (without loading a model)."""
    try:
        import sentence_transformers  # noqa: F401
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def reset_singletons() -> None:
    """Clear the cached singletons (used by tests to swap models)."""
    global _embedder, _reranker
    _embedder = None
    _reranker = None
