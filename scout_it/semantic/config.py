"""Configuration for the semantic retrieval layer.

Storage layout (follows the existing ~/.scout-it/ convention):

    ~/.scout-it/
    ├── strategy_cache.db      (existing — fetch-strategy memory)
    ├── domain_learning.json   (existing — domain routing)
    ├── credentials.json       (existing — API keys)
    └── semantic/              (NEW — this phase)
        ├── lancedb/           LanceDB vector store directory
        ├── query_cache.db     SQLite semantic query cache
        └── config.json        model names + tunables

The vector DB is persistent state (survives across runs, never re-embeds the
same content twice). User-facing search output still goes to ./.scout-it/ in
the cwd, exactly as before — semantic re-ranking only changes result *order*,
not the output format or location.
"""

import json
import os
from pathlib import Path

from ..config import CONFIG_DIR

# ── Paths ──────────────────────────────────────────────────────────────────
SEMANTIC_DIR = CONFIG_DIR / "semantic"
LANCEDB_DIR = SEMANTIC_DIR / "lancedb"
QUERY_CACHE_DB = SEMANTIC_DIR / "query_cache.db"
CONFIG_FILE = SEMANTIC_DIR / "config.json"

# ── Default models ─────────────────────────────────────────────────────────
# BGE-m3 is the recommended high-quality model (multilingual, strong on
# retrieval benchmarks, ~2 GB). all-MiniLM-L6-v2 is the lightweight fallback
# (~80 MB, CPU-friendly) used when the user wants speed or hasn't downloaded
# the large model. Both are configurable below / via env vars.
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
FAST_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# ── Tunables ───────────────────────────────────────────────────────────────
# RRF fusion constant (standard value from the original paper; 60 is the
# value used by Elasticsearch/Lucene mixed-queries — parameter-free).
RRF_K = 60

# Number of results to pass through the (expensive) cross-encoder reranker.
# Only the top-N candidates after BM25+vector fusion get cross-encoded.
RERANK_TOP_K = 20

# Semantic query-cache threshold: if a past query has cosine similarity above
# this, reuse its cached result set instead of re-running retrieval.
QUERY_CACHE_THRESHOLD = 0.92

# Vector dimension per model (used to size LanceDB tables). Filled lazily once
# the model loads; kept here so the store can be created before the first
# embedding.
_MODEL_DIMS = {
    "BAAI/bge-m3": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


def get_embedding_model_name() -> str:
    """Resolve the embedding model to use.

    Priority: SCOUT_SEMANTIC_MODEL env var > saved config.json > default.
    """
    env = os.environ.get("SCOUT_SEMANTIC_MODEL")
    if env:
        return env
    cfg = _load_config()
    return cfg.get("embedding_model", DEFAULT_EMBEDDING_MODEL)


def get_reranker_model_name() -> str:
    """Resolve the cross-encoder reranker model to use."""
    env = os.environ.get("SCOUT_RERANKER_MODEL")
    if env:
        return env
    cfg = _load_config()
    return cfg.get("reranker_model", DEFAULT_RERANKER_MODEL)


def get_embedding_dim() -> int:
    """Return the vector dimension for the configured embedding model."""
    name = get_embedding_model_name()
    return _MODEL_DIMS.get(name, 1024)


def _load_config() -> dict:
    """Load the persisted semantic config (or empty dict if absent)."""
    try:
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
    except Exception:
        pass
    return {}


def save_config(updates: dict) -> None:
    """Merge *updates* into the persisted config and write to disk."""
    cfg = _load_config()
    cfg.update(updates)
    SEMANTIC_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def ensure_dirs() -> None:
    """Create the semantic storage directory tree if it doesn't exist."""
    SEMANTIC_DIR.mkdir(parents=True, exist_ok=True)
    LANCEDB_DIR.mkdir(parents=True, exist_ok=True)
