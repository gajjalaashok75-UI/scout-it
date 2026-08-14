"""Persistent vector store + semantic query cache (Mode B — indexed search).

The store backs the optional ``index`` / ``semantic-search`` workflow: users
who want a persistent corpus (for RAG, repeated queries, or building a
knowledge base) fetch+extract+chunk+embed content into LanceDB, then query
with hybrid retrieval.

Two capabilities:

  1. ``SemanticIndex`` — a LanceDB-backed document store. Documents are
     chunked, embedded, and persisted to ``~/.scout-it/semantic/lancedb/``.
     ``search()`` does hybrid BM25+vector retrieval over the indexed corpus.

  2. ``QueryCache`` — a SQLite-backed semantic cache: if a past query is
     cosine-similar above ``QUERY_CACHE_THRESHOLD``, reuse its result set
     instead of re-running retrieval. Lives at
     ``~/.scout-it/semantic/query_cache.db``.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional

try:
    import numpy as np  # only needed by the optional vector path
except ImportError:  # pragma: no cover - graceful degradation
    np = None

from . import config
from . import embeddings

logger = logging.getLogger(__name__)

# Default chunk size for splitting long documents before embedding.
CHUNK_SIZE = 500  # characters
CHUNK_OVERLAP = 50  # characters


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split *text* into overlapping character chunks."""
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


class SemanticIndex:
    """LanceDB-backed persistent document + vector store.

    Usage::

        idx = SemanticIndex()
        idx.add_documents([{"title": ..., "content": ..., "url": ...}, ...])
        results = idx.search("query", top_k=5)
    """

    def __init__(self, table_name: str = "documents"):
        self._table_name = table_name
        self._db = None
        self._table = None
        self._dim = None

    def _ensure_db(self):
        """Lazily connect to LanceDB and open/create the table."""
        if self._db is not None:
            return
        try:
            import lancedb
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "lancedb is required for the semantic index. "
                "Install it with: pip install lancedb"
            ) from exc
        config.ensure_dirs()
        self._db = lancedb.connect(str(config.LANCEDB_DIR))
        self._dim = embeddings.get_embedding_dim()
        existing = self._db.list_tables() if hasattr(self._db, "list_tables") else self._db.table_names()
        if self._table_name in existing:
            self._table = self._db.open_table(self._table_name)
        else:
            # Create with a single empty row to set the schema.
            import pyarrow as pa

            schema = pa.schema([
                pa.field("id", pa.string()),
                pa.field("chunk_idx", pa.int32()),
                pa.field("vector", pa.list_(pa.float32(), self._dim)),
                pa.field("text", pa.string()),
                pa.field("title", pa.string()),
                pa.field("url", pa.string()),
                pa.field("source", pa.string()),
                pa.field("content_hash", pa.string()),
                pa.field("indexed_at", pa.float64()),
            ])
            self._table = self._db.create_table(self._table_name, schema=schema)

    def add_documents(self, docs: List[Dict[str, Any]], source: str = "unknown") -> int:
        """Chunk + embed + persist *docs* into the index.

        Each doc dict should have at least ``content``; ``title`` and ``url``
        are stored as metadata. Returns the number of chunks added.
        """
        self._ensure_db()
        rows = []
        for doc in docs:
            content = doc.get("content") or doc.get("snippet") or ""
            title = doc.get("title") or ""
            url = doc.get("url") or doc.get("link") or ""
            content_hash = hashlib.md5(content.encode()).hexdigest()
            chunks = _chunk_text(content)
            if not chunks:
                continue
            vecs = embeddings.embed_texts(chunks)
            for ci, (chunk, vec) in enumerate(zip(chunks, vecs)):
                rows.append({
                    "id": hashlib.md5(f"{url}:{ci}".encode()).hexdigest(),
                    "chunk_idx": ci,
                    "vector": vec.tolist(),
                    "text": chunk,
                    "title": title,
                    "url": url,
                    "source": doc.get("source", source),
                    "content_hash": content_hash,
                    "indexed_at": time.time(),
                })
        if rows:
            self._table.add(rows)
        logger.info("Indexed %d chunks from %d documents.", len(rows), len(docs))
        return len(rows)

    def search(
        self, query: str, top_k: int = 10, *, fuse_bm25: bool = True
    ) -> List[Dict[str, Any]]:
        """Hybrid vector+BM25F search over the indexed corpus.

        Uses BM25F (multi-field: title, snippet, content, url) for the
        sparse retrieval component, fused with dense vector scores via RRF.
        Facets (domain, date, source) are attached to each result.
        """
        self._ensure_db()
        query_vec = embeddings.embed_query(query)[0]

        # Vector search via LanceDB.
        try:
            vec_results = (
                self._table.search(query_vec.tolist())
                .limit(top_k * 3)
                .to_list()
            )
        except Exception as exc:
            logger.warning("Vector search failed (%s); returning empty.", exc)
            return []

        if not fuse_bm25:
            return self._dedupe_chunks(vec_results[:top_k])

        # BM25F over the retrieved candidate chunks (re-rank candidates).
        from .bm25f import build_index as build_bm25f_index
        from .retrieval import _argsort_desc, _rrf_fuse
        from .facets import compute_facets

        # Build field-mapped docs for BM25F.
        bm25f_docs = [
            {
                "title": r.get("title") or "",
                "snippet": r.get("text") or "",
                "content": r.get("text") or "",
                "url": r.get("url") or "",
            }
            for r in vec_results
        ]
        bm25f_idx = build_bm25f_index(bm25f_docs)
        bm25f_results = bm25f_idx.search(query, top_k=len(bm25f_docs))
        bm25_scores = [0.0] * len(vec_results)
        for doc_idx, score, _ in bm25f_results:
            bm25_scores[doc_idx] = score
        bm25_rank = _argsort_desc(bm25_scores)
        vec_rank = list(range(len(vec_results)))  # already by vector score
        fused = _rrf_fuse([bm25_rank, vec_rank])
        ordered = [vec_results[i] for i in fused[:top_k]]
        results = self._dedupe_chunks(ordered)

        # Attach facets.
        if results:
            facets = compute_facets(results)
            for r in results:
                r["_facets"] = facets

        return results

    @staticmethod
    def _dedupe_chunks(chunks: List[Dict]) -> List[Dict]:
        """Collapse multiple chunks from the same URL into one result."""
        seen_urls: set = set()
        out: List[Dict] = []
        for c in chunks:
            url = c.get("url") or ""
            if url in seen_urls:
                continue
            seen_urls.add(url)
            out.append({
                "url": url,
                "title": c.get("title") or "",
                "snippet": c.get("text") or "",
                "content": c.get("text") or "",
                "source": c.get("source") or "",
                "score": c.get("_distance", 0.0),
            })
        return out

    def count(self) -> int:
        """Return the number of chunks in the index."""
        self._ensure_db()
        try:
            return self._table.count_rows()
        except Exception:
            return 0


# ── Semantic query cache ───────────────────────────────────────────────────

class QueryCache:
    """SQLite-backed semantic query cache.

    If a past query's embedding is cosine-similar above the threshold, return
    the cached result set instead of re-running retrieval.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._path = db_path or str(config.QUERY_CACHE_DB)
        self._init_db()

    def _init_db(self):
        config.ensure_dirs()
        conn = sqlite3.connect(self._path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                query_vec BLOB NOT NULL,
                results_json TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def lookup(self, query_vec) -> Optional[List[Dict]]:
        """Return cached results if a similar past query exists, else None."""
        if not embeddings.is_available() or np is None:
            return None
        import pickle

        conn = sqlite3.connect(self._path)
        try:
            rows = conn.execute(
                "SELECT query_vec, results_json FROM query_cache ORDER BY timestamp DESC LIMIT 100"
            ).fetchall()
            for vec_blob, results_json in rows:
                cached_vec = pickle.loads(vec_blob)
                sim = float(np.dot(cached_vec.flatten(), np.asarray(query_vec).flatten()))
                if sim >= config.QUERY_CACHE_THRESHOLD:
                    import json
                    logger.info("Semantic cache hit (sim=%.3f).", sim)
                    return json.loads(results_json)
        except Exception as exc:
            logger.debug("Query cache lookup failed: %s", exc)
        finally:
            conn.close()
        return None

    def store(self, query: str, query_vec, results: List[Dict]) -> None:
        """Persist a query + its result set for future semantic reuse."""
        import pickle, json

        conn = sqlite3.connect(self._path)
        try:
            conn.execute(
                "INSERT INTO query_cache (query, query_vec, results_json, timestamp) VALUES (?, ?, ?, ?)",
                (query, pickle.dumps(query_vec), json.dumps(results), time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def clear(self) -> int:
        """Delete all cached queries. Returns the number deleted."""
        conn = sqlite3.connect(self._path)
        cur = conn.execute("DELETE FROM query_cache")
        conn.commit()
        deleted = cur.rowcount
        conn.close()
        return deleted
