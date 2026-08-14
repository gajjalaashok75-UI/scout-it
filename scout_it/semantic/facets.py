"""Facets: aggregate search results by metadata fields.

Ports the "Facets" strategy from Orama. After a search, you can group
results by domain, date, source type, or language to enable filtering
and drill-down — the same way Elasticsearch aggregations and Orama facets
work.

Example::

    results = semantic_search(query)
    facets = compute_facets(results)
    # facets = {
    #     "domain": {"github.com": 5, "stackoverflow.com": 3, ...},
    #     "date": {"2025-01": 4, "2025-02": 7, ...},
    #     "source": {"duckduckgo": 8, "rss": 2, ...},
    # }
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Sequence
from urllib.parse import urlparse


def _extract_domain(url: str) -> str:
    """Extract the registered domain from a URL (strip www., keep TLD)."""
    if not url:
        return "unknown"
    try:
        parsed = urlparse(url)
        host = parsed.hostname or parsed.path.split("/")[0] if not parsed.hostname else parsed.hostname
        if not host:
            return "unknown"
        # Strip "www." prefix.
        if host.startswith("www."):
            host = host[4:]
        return host.lower()
    except Exception:
        return "unknown"


def _extract_month(date_str: str) -> str:
    """Extract a YYYY-MM key from a date string. Returns 'unknown' on failure."""
    if not date_str:
        return "unknown"
    # Try ISO 8601 and common news date formats.
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt)
            return f"{dt.year}-{dt.month:02d}"
        except ValueError:
            continue
    # Try regex for YYYY-MM anywhere in the string.
    match = re.search(r"(\d{4})-(\d{2})", date_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    return "unknown"


def _extract_language(result: Dict) -> str:
    """Best-effort language extraction from result metadata."""
    for key in ("language", "lang"):
        val = result.get(key)
        if val:
            return str(val).lower()[:2]
    return "unknown"


def compute_facets(
    results: Sequence[Dict],
    *,
    fields: Optional[List[str]] = None,
) -> Dict[str, Dict[str, int]]:
    """Compute facet counts (aggregations) over search results.

    Args:
        results: search result dicts.
        fields: which facets to compute. Default: domain, date, source, language.

    Returns:
        Dict mapping facet name → {value: count}, sorted by count descending.
    """
    facet_fields = fields or ["domain", "date", "source", "language"]
    facets: Dict[str, Counter] = {f: Counter() for f in facet_fields}

    for r in results:
        for f in facet_fields:
            if f == "domain":
                facets[f][_extract_domain(r.get("url", ""))] += 1
            elif f == "date":
                facets[f][_extract_month(r.get("date") or r.get("publish_date") or "")] += 1
            elif f == "source":
                src = r.get("source") or r.get("engine") or "unknown"
                facets[f][str(src).lower()] += 1
            elif f == "language":
                facets[f][_extract_language(r)] += 1

    # Convert Counters to sorted dicts (most frequent first).
    return {
        f: dict(facets[f].most_common(50))
        for f in facet_fields
    }


def filter_by_facet(
    results: List[Dict],
    facet: str,
    value: str,
) -> List[Dict]:
    """Filter results to only those matching a facet value.

    Useful for drill-down after computing facets.
    """
    out = []
    for r in results:
        if facet == "domain":
            if _extract_domain(r.get("url", "")) == value:
                out.append(r)
        elif facet == "date":
            if _extract_month(r.get("date") or r.get("publish_date") or "") == value:
                out.append(r)
        elif facet == "source":
            src = r.get("source") or r.get("engine") or "unknown"
            if str(src).lower() == value:
                out.append(r)
        elif facet == "language":
            if _extract_language(r) == value:
                out.append(r)
    return out
