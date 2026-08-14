"""BM25F: multi-field BM25 with Orama-style search strategies.

This module ports the key algorithmic search strategies from Orama
(https://github.com/oramasearch/orama) to pure Python — no external
service or LLM API required.

Strategies implemented:
  - **BM25F** (multi-field BM25): each field (title, snippet, content, url)
    gets its own BM25 score with per-field weights, then scores are summed.
    This is what Elasticsearch and Orama use instead of flat BM25.
  - **Typo tolerance**: Levenshtein edit distance with configurable max
    distance. Catches "climat" → "climate", "machne" → "machine".
  - **Prefix matching**: "comp" matches "computer", "computing".
  - **Exact phrase boost**: exact multi-word phrase matches get a score bonus.
  - **Porter stemming** (English): "running" → "run", "computers" → "computer".
    Improves recall by matching morphological variants.
  - **Unicode tokenization**: regex word boundaries work across 30+ languages.

All strategies are pure algorithmic — no ML model, no API call, no network.
They work on both live search results and the persistent LanceDB store.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ─── Configuration ─────────────────────────────────────────────────────────

# Per-field weights for BM25F. Title matches are worth 6x a content match,
# snippets 3x, url 1x. These are the same ratios Elasticsearch uses by
# default (title boost ≈ 5-10x).
DEFAULT_FIELD_WEIGHTS: Dict[str, float] = {
    "title": 6.0,
    "snippet": 3.0,
    "content": 1.5,
    "url": 1.0,
}

# BM25 parameters (Lucene/Elasticsearch defaults).
BM25_K1 = 1.2
BM25_B = 0.75

# Typo tolerance: max Levenshtein distance for fuzzy matching.
# 0 = exact match only; 1 = single-char typos; 2 = two-char typos.
DEFAULT_TYPO_TOLERANCE = 1

# Prefix matching: if a query term is a prefix of a document term, match it.
# "comp" → "computer", "computing". Only for query terms ≥ 4 chars to avoid
# noise from short prefixes like "a", "to".
DEFAULT_PREFIX_MIN_LENGTH = 4

# Exact phrase boost: if the full query phrase appears verbatim in a field,
# multiply that field's BM25 score by this factor.
DEFAULT_PHRASE_BOOST = 2.0


# ─── Porter Stemmer (simplified) ───────────────────────────────────────────
# A minimal Porter stemmer for English. Handles the most common suffixes
# (plural, past tense, gerund, etc.) without the full algorithmic complexity.
# For 30-language support, the Unicode tokenizer below handles CJK, Cyrillic,
# Arabic, etc. correctly; stemming is English-only (non-English passes through).

_STEM_RULES: List[Tuple[str, str, int]] = [
    # (suffix, replacement, min_stem_length)
    ("ational", "ate", 3),
    ("tional", "tion", 3),
    ("iveness", "ive", 3),
    ("fulness", "ful", 3),
    ("ousness", "ous", 3),
    ("ization", "ize", 3),
    ("isation", "ise", 3),
    ("fulness", "ful", 3),
    ("ousli", "ous", 3),
    ("entli", "ent", 3),
    ("ation", "ate", 3),
    ("alism", "al", 3),
    ("aliti", "al", 3),
    ("iviti", "ive", 3),
    ("biliti", "ble", 3),
    ("ous", "", 3),
    ("ies", "y", 2),
    ("ied", "y", 2),
    ("ing", "", 3),
    ("edly", "", 3),
    ("ed", "", 3),
    ("ly", "", 3),
    ("ful", "", 3),
    ("ness", "", 3),
    ("ment", "", 3),
    ("ents", "ent", 3),
    ("s", "", 3),
    ("e", "", 3),
]


def porter_stem(word: str) -> str:
    """Minimal Porter-style stemmer for English words.

    Non-ASCII words (CJK, Cyrillic, Arabic, etc.) pass through unchanged —
    Unicode tokenization handles them, but stemming is English-only.
    """
    if len(word) <= 3 or not word.isascii():
        return word
    lower = word.lower()
    for suffix, replacement, min_stem in _STEM_RULES:
        if lower.endswith(suffix) and len(lower) - len(suffix) >= min_stem:
            stem = lower[: -len(suffix)] + replacement
            # Porter step 1b: if "-ing"/"-ed" stripped and stem ends in a
            # doubled consonant (e.g., "runn" from "running"), remove the
            # extra letter ("runn" → "run"). Also fix "ie" → "y" ("dieing").
            if suffix in ("ing", "ed") and len(stem) >= 2 and stem[-1] == stem[-2]:
                if stem[-1] not in "lsz":  # "ll", "ss", "zz" are valid
                    stem = stem[:-1]
            elif suffix in ("ing", "ed") and len(stem) >= 2 and stem[-2:] == "ie":
                stem = stem[:-2] + "y"
            return stem
    return lower


# ─── Tokenization ──────────────────────────────────────────────────────────

# Unicode-aware word tokenizer: matches sequences of letters (including
# accented chars, CJK, Cyrillic, Arabic, Devanagari), digits, and underscores.
_WORD_RE = re.compile(
    r"[\w]+",
    re.UNICODE,
)


def tokenize(text: str, *, stem: bool = True) -> List[str]:
    """Tokenize text into lowercase terms.

    Works across 30+ languages via Unicode word boundaries.
    If *stem* is True, applies English Porter stemming to ASCII tokens.
    """
    if not text:
        return []
    tokens = _WORD_RE.findall(text.lower())
    if stem:
        return [porter_stem(t) if t.isascii() else t for t in tokens]
    return tokens


def tokenize_query(query: str) -> List[str]:
    """Tokenize a search query (with stemming)."""
    return tokenize(query, stem=True)


# ─── Levenshtein Distance (typo tolerance) ─────────────────────────────────


def _levenshtein(a: str, b: str, max_dist: int = 2) -> int:
    """Compute Levenshtein edit distance, early-exiting if it exceeds *max_dist*.

    Returns a large number (> max_dist) if the distance exceeds max_dist,
    so callers can use ``dist <= max_dist`` without computing the full
    matrix for very different strings.
    """
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1
    if a == b:
        return 0
    if la == 0:
        return lb
    if lb == 0:
        return la

    # Rolling two-row DP.
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i] + [0] * lb
        row_min = curr[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,        # deletion
                curr[j - 1] + 1,    # insertion
                prev[j - 1] + cost, # substitution
            )
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_dist:
            return max_dist + 1
        prev = curr
    return prev[lb]


# ─── BM25F Engine ───────────────────────────────────────────────────────────


class BM25FIndex:
    """Multi-field BM25 index with Orama-style search strategies.

    Each document has multiple fields (title, snippet, content, url). BM25F
    computes a separate BM25 score per field (with field-specific length
    normalization), then sums them with per-field weights.

    Additional strategies (all pure algorithmic, no ML):
      - **Typo tolerance**: query terms within *typo_tolerance* Levenshtein
        distance of a document term get a partial score.
      - **Prefix matching**: query terms that are prefixes of document terms
        get a partial score (e.g., "comp" → "computer").
      - **Exact phrase boost**: if the full query appears as a contiguous
        phrase in a field, that field's score is multiplied.
    """

    def __init__(
        self,
        field_weights: Optional[Dict[str, float]] = None,
        k1: float = BM25_K1,
        b: float = BM25_B,
        typo_tolerance: int = DEFAULT_TYPO_TOLERANCE,
        prefix_min_length: int = DEFAULT_PREFIX_MIN_LENGTH,
        phrase_boost: float = DEFAULT_PHRASE_BOOST,
    ):
        self._field_weights = field_weights or dict(DEFAULT_FIELD_WEIGHTS)
        self._k1 = k1
        self._b = b
        self._typo_tolerance = typo_tolerance
        self._prefix_min = prefix_min_length
        self._phrase_boost = phrase_boost

        # Per-field storage:
        # _fields[name] = {"tokens": [List[str]], "len": int, "tf": Counter, "idf": {term: idf}}
        self._fields: Dict[str, Dict] = {}
        self._N = 0
        # Per-field average document length.
        self._avgdl: Dict[str, float] = {}
        # Per-field document frequency: term → number of docs containing it.
        self._df: Dict[str, Dict[str, int]] = {}

    def add_documents(
        self,
        documents: Sequence[Dict[str, str]],
        *,
        fields: Optional[List[str]] = None,
    ) -> None:
        """Index a batch of documents.

        Args:
            documents: list of dicts. Each dict's values are the field texts.
                Keys not in *fields* (or not in the default field set) are
                ignored.
            fields: which dict keys to index. Defaults to the keys in
                DEFAULT_FIELD_WEIGHTS that are present.
        """
        if not documents:
            return

        field_names = fields or list(self._field_weights.keys())
        self._N = len(documents)

        # Initialize per-field storage.
        for name in field_names:
            self._fields[name] = {
                "tokens": [],
                "len": [],
                "tf": [],
                "raw_text": [],
            }
            self._df[name] = {}
            self._avgdl[name] = 0.0

        for doc in documents:
            for name in field_names:
                raw = (doc.get(name) or "").strip()
                tokens = tokenize(raw) if raw else []
                tf = Counter(tokens)
                self._fields[name]["tokens"].append(tokens)
                self._fields[name]["raw_text"].append(raw.lower())
                self._fields[name]["len"].append(len(tokens))
                self._fields[name]["tf"].append(tf)
                for term in tf:
                    self._df[name][term] = self._df[name].get(term, 0) + 1

        # Compute per-field idf (Lucene variant, always positive).
        for name in field_names:
            n = self._N
            self._avgdl[name] = (
                sum(self._fields[name]["len"]) / n if n > 0 else 0.0
            )
            self._fields[name]["idf"] = {
                term: math.log(1.0 + (n - df + 0.5) / (df + 0.5))
                for term, df in self._df[name].items()
            }

    def _field_bm25_score(
        self,
        field_name: str,
        doc_idx: int,
        query_terms: List[str],
    ) -> float:
        """BM25 score for one field of one document."""
        field = self._fields.get(field_name)
        if not field or doc_idx >= len(field["tf"]):
            return 0.0

        tf = field["tf"][doc_idx]
        idf_map = field["idf"]
        dl = field["len"][doc_idx]
        avgdl = self._avgdl[field_name] or 1.0

        score = 0.0
        matched_terms = set()

        for term in set(query_terms):
            if term in tf:
                # Exact term match.
                idf = idf_map.get(term, 0.0)
                freq = tf[term]
                denom = freq + self._k1 * (1 - self._b + self._b * dl / avgdl)
                score += idf * (freq * (self._k1 + 1)) / denom
                matched_terms.add(term)
            else:
                # Fuzzy: typo tolerance + prefix matching.
                fuzzy_score = self._fuzzy_match(
                    field_name, doc_idx, term
                )
                if fuzzy_score > 0:
                    score += fuzzy_score * 0.5  # discount fuzzy matches
                    matched_terms.add(term)

        # Exact phrase boost: check if the original (unstemmed) query phrase
        # appears verbatim in the original field text.
        if self._phrase_boost > 1.0 and len(query_terms) >= 2:
            # query_terms are stemmed; reconstruct the phrase from the
            # original query by joining with spaces and lowering.
            # We stored raw_text (lowercased original) at index time, so we
            # need the original query string — but we only have stemmed terms
            # here. Instead, check if ALL stemmed query terms appear
            # consecutively in the field's stemmed token stream.
            tokens_list = field["tokens"][doc_idx]
            q_set = list(query_terms)  # preserve order, may have dups
            for i in range(len(tokens_list) - len(q_set) + 1):
                if tokens_list[i : i + len(q_set)] == q_set:
                    score *= self._phrase_boost
                    break

        return score

    def _fuzzy_match(
        self,
        field_name: str,
        doc_idx: int,
        query_term: str,
    ) -> float:
        """Score a query term against document terms via typo tolerance + prefix.

        Returns the best partial BM25 score (already discounted by caller).
        """
        field = self._fields[field_name]
        tf = field["tf"][doc_idx]
        idf_map = field["idf"]
        dl = field["len"][doc_idx]
        avgdl = self._avgdl[field_name] or 1.0

        best = 0.0

        for doc_term, freq in tf.items():
            # Prefix match: query is a prefix of a doc term.
            if (
                len(query_term) >= self._prefix_min
                and doc_term.startswith(query_term)
                and doc_term != query_term
            ):
                idf = idf_map.get(doc_term, 0.0)
                denom = freq + self._k1 * (1 - self._b + self._b * dl / avgdl)
                s = idf * (freq * (self._k1 + 1)) / denom
                if s > best:
                    best = s

            # Typo tolerance: Levenshtein distance ≤ threshold.
            elif self._typo_tolerance > 0:
                dist = _levenshtein(query_term, doc_term, self._typo_tolerance)
                if dist <= self._typo_tolerance and dist > 0:
                    idf = idf_map.get(doc_term, 0.0)
                    denom = freq + self._k1 * (1 - self._b + self._b * dl / avgdl)
                    s = idf * (freq * (self._k1 + 1)) / denom
                    # Discount by similarity (closer = higher score).
                    max_len = max(len(query_term), len(doc_term))
                    similarity = 1.0 - (dist / max_len) if max_len > 0 else 0.0
                    s *= similarity
                    if s > best:
                        best = s

        return best

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        fields: Optional[List[str]] = None,
    ) -> List[Tuple[int, float, Dict[str, float]]]:
        """Search the index and return ranked results.

        Args:
            query: search query string.
            top_k: max results to return.
            fields: which fields to search (default: all indexed fields).

        Returns:
            List of ``(doc_index, total_score, field_scores)`` tuples,
            sorted by total_score descending.
        """
        if self._N == 0:
            return []

        query_terms = tokenize_query(query)
        if not query_terms:
            return []

        field_names = fields or list(self._fields.keys())
        scores: List[Tuple[int, float, Dict[str, float]]] = []

        for doc_idx in range(self._N):
            field_scores = {}
            total = 0.0
            for fname in field_names:
                if fname not in self._fields:
                    continue
                raw = self._field_bm25_score(fname, doc_idx, query_terms)
                weighted = raw * self._field_weights.get(fname, 1.0)
                field_scores[fname] = round(weighted, 6)
                total += weighted
            scores.append((doc_idx, round(total, 6), field_scores))

        scores.sort(key=lambda x: -x[1])
        return scores[:top_k]

    @property
    def doc_count(self) -> int:
        return self._N


def build_index(
    documents: Sequence[Dict],
    *,
    field_map: Optional[Dict[str, str]] = None,
    field_weights: Optional[Dict[str, float]] = None,
) -> BM25FIndex:
    """Convenience: build a BM25F index from result dicts.

    *field_map* translates result dict keys to BM25F field names.
    Default maps: title→title, snippet/description→snippet, content→content, url→url.
    """
    default_map = {
        "title": "title",
        "snippet": "snippet",
        "description": "snippet",
        "content": "content",
        "cleaned_content": "content",
        "url": "url",
    }
    fmap = field_map or default_map

    # Normalize documents to field-keyed dicts.
    normalized = []
    for doc in documents:
        nd = {}
        for src_key, dst_field in fmap.items():
            if src_key in doc and doc[src_key]:
                nd[dst_field] = str(doc[src_key])
        if nd:
            normalized.append(nd)

    idx = BM25FIndex(field_weights=field_weights)
    idx.add_documents(normalized, fields=list(set(fmap.values())))
    return idx
