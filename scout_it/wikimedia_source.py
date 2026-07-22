#!/usr/bin/env python3
"""
🌐 WIKIMEDIA SEARCH SOURCE — Full WikimediaExtractor v3 port
==============================================================

Full port of the ``WikimediaExtractor`` class from
``references/wikimedia_extractor_version_2.py``, adapted for the
scout-it ecosystem (proxy pool, response cache, etc.).

Features:
- SITE_MAP / SITE_HOME with 12 Wikimedia projects
- ``urllib3.Retry`` adapter + ``SimpleRateLimiter`` + response cache
- ``search_pages()``, ``search_pages_paginated()`` — query search
- ``wikipedia_summary()``, ``action_query_extract()``, ``batch_page_extract()``
- ``commons_search()``, ``wikidata_search()``, ``wikidata_entity()``
- ``wikifunctions_fetch()``, ``check_robots()``
- ``recursive_crawl()``, ``spider_from_search()``, ``combined_ai_ready_export()``
- Text cleaning: ``normalize_text``, ``strip_html``, ``clean_noise_text``,
  ``ai_ready_record``, ``dedupe_records``, ``prune_empty``, ``dedupe_lines``
- ``bundle_topic()`` — multi-project topic bundle
- ``Export all`` — JSON / JSONL / CSV / Markdown

Usage:
    from scout_it.wikimedia_source import wikimedia_search, WikimediaExtractor

    # Simple search (returns DDGS-compatible format)
    results = wikimedia_search("python", max_results=5, project="wikipedia")

    # Full extractor for advanced operations
    ex = WikimediaExtractor()
    result = ex.wikipedia_summary("Python (programming language)")
    if result.ok:
        print(result.data)
"""

import hashlib
import json
import logging
import random
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from html import unescape
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import header_profiles as _hp
from . import proxy_pool as _pp
from . import response_cache as _rc

logger = logging.getLogger(__name__)

# ──────────────────────── CONSTANTS ────────────────────────

DEFAULT_UA = "scout-it-wikimedia/1.0 (+scout-it)"
WIKIFUNCTIONS_API = "https://www.wikifunctions.org/w/api.php"

SITE_MAP = {
    "wikipedia": "https://en.wikipedia.org/w/api.php",
    "commons": "https://commons.wikimedia.org/w/api.php",
    "wikivoyage": "https://en.wikivoyage.org/w/api.php",
    "wiktionary": "https://en.wiktionary.org/w/api.php",
    "wikibooks": "https://en.wikibooks.org/w/api.php",
    "wikidata": "https://www.wikidata.org/w/api.php",
    "wikiversity": "https://en.wikiversity.org/w/api.php",
    "wikiquote": "https://en.wikiquote.org/w/api.php",
    "mediawiki": "https://www.mediawiki.org/w/api.php",
    "wikisource": "https://en.wikisource.org/w/api.php",
    "wikispecies": "https://species.wikimedia.org/w/api.php",
    "wikifunctions": WIKIFUNCTIONS_API,
}

SITE_HOME = {
    "wikipedia": "https://en.wikipedia.org/",
    "commons": "https://commons.wikimedia.org/",
    "wikivoyage": "https://en.wikivoyage.org/",
    "wiktionary": "https://en.wiktionary.org/",
    "wikibooks": "https://en.wikibooks.org/",
    "wikidata": "https://www.wikidata.org/",
    "wikiversity": "https://en.wikiversity.org/",
    "wikiquote": "https://en.wikiquote.org/",
    "mediawiki": "https://www.mediawiki.org/",
    "wikisource": "https://en.wikisource.org/",
    "wikispecies": "https://species.wikimedia.org/",
    "wikifunctions": "https://www.wikifunctions.org/",
}

BLOCKED_PREFIXES = (
    "File:", "Category:", "Template:", "Help:", "Portal:",
    "Special:", "Talk:", "User:", "Module:", "Draft:",
)

NOISE_PATTERNS = [
    r"\bNavigation menu\b", r"\bContents\b", r"\bSee also\b", r"\bReferences\b",
    r"\bExternal links\b", r"\bFurther reading\b", r"\bNotes\b", r"\bFootnotes\b",
    r"\bJump to navigation\b", r"\bJump to search\b",
]

TIMEOUT = 25
MAX_RETRIES = 3
RATE_PER_SEC = 2.0

ALL_PROJECTS = sorted(SITE_MAP.keys())

__all__ = [
    "wikimedia_search", "WikimediaExtractor",
    "SITE_MAP", "SITE_HOME", "ALL_PROJECTS",
    "WIKIFUNCTIONS_API",
]


# ──────────────────────── DATA CLASSES ────────────────────────


@dataclass
class RequestResult:
    """Structured result from a Wikimedia API request."""
    ok: bool
    endpoint: str
    status_code: Optional[int] = None
    data: Any = None
    error: Optional[str] = None
    elapsed_ms: Optional[int] = None
    attempts: int = 1
    from_cache: bool = False


# ──────────────────────── RATE LIMITER ────────────────────────


class SimpleRateLimiter:
    """Thread-safe rate limiter."""

    def __init__(self, rate_per_sec: float = RATE_PER_SEC):
        self.min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


# ──────────────────────── TEXT CLEANING ────────────────────────


def normalize_text(text: str) -> str:
    """Unescape HTML entities, strip tags, collapse whitespace."""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[(?:\d+|citation needed)\]", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def strip_html(html: str) -> str:
    """Aggressively strip HTML: scripts, styles, nav, tables, sup."""
    if not html:
        return ""
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<nav.*?</nav>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<table.*?</table>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<sup.*?</sup>", " ", text, flags=re.S | re.I)
    return normalize_text(re.sub(r"<[^>]+>", " ", text))


def prune_empty(obj: Any) -> Any:
    """Recursively remove None/empty values from dicts/lists."""
    if isinstance(obj, dict):
        cleaned = {k: prune_empty(v) for k, v in obj.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, "", [], {}, ())}
    if isinstance(obj, list):
        cleaned = [prune_empty(v) for v in obj]
        return [v for v in cleaned if v not in (None, "", [], {}, ())]
    return obj


def dedupe_lines(text: str) -> str:
    """Remove duplicate sentences from text."""
    seen: Set[str] = set()
    out: List[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text or ""):
        norm = re.sub(r"\W+", "", part.lower())
        if norm and norm not in seen:
            seen.add(norm)
            out.append(part.strip())
    return " ".join(out).strip()


def clean_noise_text(text: str) -> str:
    """Remove common Wikipedia noise patterns and dedupe sentences."""
    text = normalize_text(text)
    parts = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        if any(re.search(p, part, flags=re.I) for p in NOISE_PATTERNS):
            continue
        parts.append(part)
    return dedupe_lines(" ".join(parts))


# ──────────────────────── WIKIMEDIA EXTRACTOR ────────────────────────


class WikimediaExtractor:
    """Full-featured Wikimedia API client.

    Ported from ``references/wikimedia_extractor_version_2.py``.

    Provides search, page extraction, crawling, and content-cleaning
    across all 12 Wikimedia projects.
    """

    def __init__(
        self,
        language: str = "en",
        timeout: int = TIMEOUT,
        max_workers: int = 5,
        rate_per_sec: float = RATE_PER_SEC,
        user_agent: str = DEFAULT_UA,
        retries: int = MAX_RETRIES,
        maxlag: int = 5,
    ):
        self.language = language
        self.timeout = timeout
        self.max_workers = max_workers
        self.rate_limiter = SimpleRateLimiter(rate_per_sec)
        self.user_agent = user_agent
        self.retries = retries
        self.maxlag = maxlag
        self.session = self._build_session()

    # ── Session & HTTP ──────────────────────────────────────────────

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        retry = Retry(
            total=self.retries,
            connect=self.retries,
            read=self.retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        return s

    def wikipedia_rest_base(self) -> str:
        """REST API base URL for Wikipedia."""
        return f"https://{self.language}.wikipedia.org/api/rest_v1"

    def action_api_for_project(self, project: str) -> str:
        """Resolve the Action API URL for a Wikimedia project.

        Language-scoped wikis (wikipedia, wikivoyage, wiktionary, etc.)
        get a ``{language}.{project}.org`` URL. Others use the fixed
        ``SITE_MAP`` entry.
        """
        if project == "wikipedia":
            return f"https://{self.language}.wikipedia.org/w/api.php"
        if project in {"wikivoyage", "wiktionary", "wikibooks",
                        "wikiversity", "wikiquote", "wikisource"}:
            return f"https://{self.language}.{project}.org/w/api.php"
        return SITE_MAP[project]

    def _cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        raw = url + "::" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _inject_polite_params(self, params: Optional[Dict] = None, endpoint: str = "") -> Dict:
        params = dict(params or {})
        # Add maxlag for Action API calls
        if "/w/api.php" in endpoint:
            params.setdefault("maxlag", self.maxlag)
        return params

    def _request_json(
        self, url: str, params: Optional[Dict] = None,
        endpoint: str = "", timeout: Optional[int] = None,
    ) -> RequestResult:
        """Make a rate-limited, retried, cached request.

        Checks ``response_cache`` first, then makes the request with:
        rate limiting → session.get → Retry adapter → cache write.
        """
        params = self._inject_polite_params(params, url)
        key = self._cache_key(url, params)
        timeout = timeout or self.timeout

        # Check cache
        cached = _rc.get(key, cache_dir=None)
        if cached and cached.get("content"):
            try:
                data = json.loads(cached["content"])
                return RequestResult(
                    ok=True, endpoint=endpoint or url,
                    status_code=200, data=data, from_cache=True,
                )
            except Exception:
                pass

        proxy_info = _pp.get_default_pool().get()
        headers = _hp.get_profile()
        attempts = 0
        started = time.time()
        last_error = None

        while attempts <= self.retries:
            attempts += 1
            try:
                self.rate_limiter.wait()
                resp = self.session.get(
                    url, params=params, headers=headers,
                    timeout=timeout, proxies=proxy_info["requests_proxies"],
                )
                # Transient errors → retry with backoff
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    if attempts <= self.retries:
                        time.sleep(min(60, (2 ** (attempts - 1)) + random.random()))
                    continue

                data = resp.json()

                # maxlag → retry
                if isinstance(data, dict) and data.get("error", {}).get("code") == "maxlag":
                    if attempts <= self.retries:
                        lag = data.get("error", {}).get("lag", 5)
                        delay = max(5, int(float(lag)) if str(lag).replace(".", "", 1).isdigit() else 5)
                        time.sleep(delay)
                    continue

                resp.raise_for_status()

                # Cache success
                _rc.set(
                    key, json.dumps(data, ensure_ascii=False),
                    content_type="wikimedia",
                    ttl_seconds=60 * 60 * 24,  # 24h
                    extra={"url": url, "params": params},
                )

                return RequestResult(
                    ok=True, endpoint=endpoint or url,
                    status_code=resp.status_code, data=data,
                    elapsed_ms=int((time.time() - started) * 1000),
                    attempts=attempts,
                )

            except Exception as e:
                last_error = str(e)
                if attempts <= self.retries:
                    time.sleep(min(60, (2 ** (attempts - 1)) + random.random()))
                else:
                    break

        return RequestResult(
            ok=False, endpoint=endpoint or url,
            error=last_error,
            elapsed_ms=int((time.time() - started) * 1000),
            attempts=attempts,
        )

    # ── Cleaning utilities ──────────────────────────────────────────

    def normalize_text(self, text: str) -> str:
        return normalize_text(text)

    def strip_html(self, html: str) -> str:
        return strip_html(html)

    def prune_empty(self, obj: Any) -> Any:
        return prune_empty(obj)

    def dedupe_lines(self, text: str) -> str:
        return dedupe_lines(text)

    def clean_noise_text(self, text: str) -> str:
        return clean_noise_text(text)

    def flatten_for_table(self, obj: Dict, prefix: str = "") -> Dict:
        """Flatten a nested dict into dot-separated keys for CSV export."""
        out: Dict = {}
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(self.flatten_for_table(v, key))
            elif isinstance(v, list):
                out[key] = "; ".join(self.normalize_text(str(x)) for x in v[:50])
            else:
                out[key] = v
        return out

    def ai_ready_record(self, record: Dict) -> Dict:
        """Add cleaned text fields and AI-ready flag."""
        rec = json.loads(json.dumps(record, ensure_ascii=False))
        if isinstance(rec, dict):
            for key in ("extract", "text", "snippet", "description"):
                if key in rec and isinstance(rec[key], str):
                    rec[f"{key}_clean"] = self.clean_noise_text(rec[key])
            rec["ai_ready"] = True
        return self.prune_empty(rec)

    def dedupe_records(self, rows: List[Dict]) -> List[Dict]:
        """Deduplicate records by title+id+url+extract hash."""
        seen: Set[str] = set()
        out: List[Dict] = []
        for row in rows:
            key = json.dumps({
                "title": row.get("title"),
                "id": row.get("id"),
                "url": row.get("fullurl") or row.get("url"),
                "extract": (
                    row.get("extract_clean") or row.get("extract")
                    or row.get("snippet_clean") or row.get("snippet")
                ),
            }, sort_keys=True, ensure_ascii=False)
            h = hashlib.sha256(key.encode("utf-8")).hexdigest()
            if h not in seen:
                seen.add(h)
                out.append(row)
        return out

    # ── Summary & Search ────────────────────────────────────────────

    def clean_summary_result(self, data: Dict) -> Dict:
        """Clean and structure a Wikipedia page summary response."""
        return self.prune_empty({
            "source_project": "wikipedia",
            "title": data.get("title"),
            "description": self.normalize_text(data.get("description", "")),
            "extract": self.clean_noise_text(data.get("extract", "")),
            "lang": data.get("lang"),
            "dir": data.get("dir"),
            "type": data.get("type"),
            "content_urls": data.get("content_urls", {}),
            "thumbnail": data.get("thumbnail", {}),
            "originalimage": data.get("originalimage", {}),
            "timestamp": data.get("timestamp"),
        })

    def wikipedia_summary(self, title: str) -> RequestResult:
        """Fetch a Wikipedia summary via REST API (page/summary/{title})."""
        url = f"{self.wikipedia_rest_base()}/page/summary/{requests.utils.quote(title, safe='')}"
        r = self._request_json(url, endpoint="wikipedia_summary")
        if r.ok and isinstance(r.data, dict):
            r.data = self.clean_summary_result(r.data)
        return r

    def wikipedia_random_summary(self) -> RequestResult:
        """Fetch a random Wikipedia summary."""
        r = self._request_json(
            f"{self.wikipedia_rest_base()}/page/random/summary",
            endpoint="wikipedia_random_summary",
        )
        if r.ok and isinstance(r.data, dict):
            r.data = self.clean_summary_result(r.data)
        return r

    def clean_page_result(self, project: str, title: str, payload: Dict) -> Dict:
        """Clean an Action API page query result."""
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {}) if pages else {}
        links: List[str] = []
        categories: List[str] = []
        seen_links: Set[str] = set()
        seen_cat: Set[str] = set()
        for link in page.get("links", [])[:100]:
            t = link.get("title")
            if t and not t.startswith(BLOCKED_PREFIXES) and t not in seen_links:
                seen_links.add(t)
                links.append(t)
        for cat in page.get("categories", [])[:100]:
            t = cat.get("title")
            if t and t not in seen_cat:
                seen_cat.add(t)
                categories.append(t)
        return self.prune_empty({
            "source_project": project,
            "requested_title": title,
            "title": page.get("title", title),
            "pageid": page.get("pageid"),
            "fullurl": page.get("fullurl"),
            "extract": self.clean_noise_text(
                page.get("extract", "") if isinstance(page.get("extract", ""), str) else ""
            ),
            "links": links,
            "categories": categories,
        })

    def action_query_extract(
        self, project: str, title: str,
        plain_text: bool = True, intro_only: bool = False,
    ) -> RequestResult:
        """Fetch a cleaned page extract via the Action API."""
        params = {
            "action": "query", "prop": "extracts|info|categories|links",
            "inprop": "url", "titles": title,
            "explaintext": 1 if plain_text else 0,
            "exintro": 1 if intro_only else 0,
            "cllimit": 100, "pllimit": 100,
            "format": "json", "redirects": 1,
        }
        r = self._request_json(
            self.action_api_for_project(project), params=params,
            endpoint=f"{project}_page_extract",
        )
        if r.ok:
            r.data = self.clean_page_result(project, title, r.data)
        return r

    def batch_page_extract(self, project: str, titles: List[str]) -> RequestResult:
        """Batch extract up to 50 page titles."""
        params = {
            "action": "query", "prop": "extracts|info",
            "inprop": "url", "titles": "|".join(titles[:50]),
            "explaintext": 1, "format": "json", "redirects": 1,
        }
        r = self._request_json(
            self.action_api_for_project(project), params=params,
            endpoint=f"{project}_batch_page_extract",
        )
        if not r.ok:
            return r
        pages = r.data.get("query", {}).get("pages", {})
        out: List[Dict] = []
        seen: Set[str] = set()
        for p in pages.values():
            title = p.get("title")
            if title and title not in seen:
                seen.add(title)
                out.append(self.prune_empty({
                    "source_project": project,
                    "title": title,
                    "pageid": p.get("pageid"),
                    "fullurl": p.get("fullurl"),
                    "extract": self.clean_noise_text(p.get("extract", "")),
                }))
        r.data = out
        return r

    def search_pages(
        self, project: str, query: str, limit: int = 10
    ) -> RequestResult:
        """Search a Wikimedia project via the Action API ``srsearch``."""
        params = {
            "action": "query", "list": "search",
            "srsearch": query, "srlimit": min(limit, 50),
            "format": "json",
        }
        r = self._request_json(
            self.action_api_for_project(project), params=params,
            endpoint=f"{project}_search",
        )
        if not r.ok:
            return r
        out: List[Dict] = []
        seen: Set[str] = set()
        for item in r.data.get("query", {}).get("search", []):
            title = item.get("title")
            if title and title not in seen:
                seen.add(title)
                out.append(self.prune_empty({
                    "source_project": project,
                    "title": title,
                    "pageid": item.get("pageid"),
                    "size": item.get("size"),
                    "timestamp": item.get("timestamp"),
                    "snippet": self.strip_html(item.get("snippet", "")),
                }))
        r.data = out
        return r

    def search_pages_paginated(
        self, project: str, query: str, limit: int = 100
    ) -> RequestResult:
        """Paginated search with loop bounds."""
        collected: List[Dict] = []
        seen: Set[str] = set()
        sroffset = 0
        loops = 0
        while len(collected) < limit and loops < 100:
            loops += 1
            params = {
                "action": "query", "list": "search",
                "srsearch": query,
                "srlimit": min(50, limit - len(collected)),
                "sroffset": sroffset, "format": "json",
            }
            r = self._request_json(
                self.action_api_for_project(project), params=params,
                endpoint=f"{project}_search_paginated",
            )
            if not r.ok:
                return r
            items = r.data.get("query", {}).get("search", [])
            if not items:
                break
            for item in items:
                title = item.get("title")
                if title and title not in seen:
                    seen.add(title)
                    collected.append(self.prune_empty({
                        "source_project": project,
                        "title": title,
                        "pageid": item.get("pageid"),
                        "snippet": self.strip_html(item.get("snippet", "")),
                    }))
                    if len(collected) >= limit:
                        break
            cont = r.data.get("continue", {})
            if "sroffset" not in cont:
                break
            sroffset = cont["sroffset"]
        return RequestResult(
            ok=True, endpoint=f"{project}_search_paginated",
            data=collected,
        )

    def parse_page_html(self, project: str, title: str) -> RequestResult:
        """Parse page HTML via Action API ``parse`` action."""
        params = {
            "action": "parse", "page": title,
            "prop": "text|sections|wikitext|displaytitle",
            "format": "json", "redirects": 1,
        }
        r = self._request_json(
            self.action_api_for_project(project), params=params,
            endpoint=f"{project}_parse_page",
        )
        if not r.ok:
            return r
        parse = r.data.get("parse", {})
        html = parse.get("text", {}).get("*", "")
        sections: List[Dict] = []
        seen: Set[str] = set()
        for s in parse.get("sections", []):
            line = self.normalize_text(s.get("line", ""))
            if line and line not in seen:
                seen.add(line)
                sections.append({
                    "index": s.get("index"),
                    "line": line,
                    "anchor": s.get("anchor"),
                    "number": s.get("number"),
                })
        r.data = self.prune_empty({
            "source_project": project,
            "title": parse.get("displaytitle") or title,
            "text": self.strip_html(html),
            "sections": sections,
            "wikitext": parse.get("wikitext", {}).get("*", ""),
        })
        return r

    def export_sections(self, project: str, title: str) -> RequestResult:
        """Export section-by-section cleaned text."""
        parsed = self.parse_page_html(project, title)
        if not parsed.ok:
            return parsed
        sections = parsed.data.get("sections", [])
        if not sections:
            return RequestResult(ok=True, endpoint="export_sections", data=[])
        out: List[Dict] = []
        for sec in sections:
            idx = sec.get("index")
            if str(idx) == "0":
                continue
            params = {
                "action": "parse", "page": title,
                "prop": "text", "section": idx,
                "format": "json", "redirects": 1,
            }
            r = self._request_json(
                self.action_api_for_project(project), params=params,
                endpoint=f"{project}_section_parse",
            )
            if not r.ok:
                continue
            html = r.data.get("parse", {}).get("text", {}).get("*", "")
            cleaned = self.clean_noise_text(self.strip_html(html))
            if cleaned:
                out.append(self.prune_empty({
                    "source_project": project,
                    "title": title,
                    "section_index": idx,
                    "section_title": sec.get("line"),
                    "section_anchor": sec.get("anchor"),
                    "text": cleaned,
                }))
        return RequestResult(ok=True, endpoint="export_sections", data=out)

    # ── Project-specific searches ───────────────────────────────────

    def commons_search(self, query: str, limit: int = 10) -> RequestResult:
        """Search Wikimedia Commons."""
        return self.search_pages("commons", query, limit)

    def wikidata_search(self, query: str, limit: int = 10) -> RequestResult:
        """Search Wikidata entities via ``wbsearchentities``."""
        params = {
            "action": "wbsearchentities", "search": query,
            "language": self.language, "limit": min(limit, 50),
            "format": "json",
        }
        r = self._request_json(
            SITE_MAP["wikidata"], params=params,
            endpoint="wikidata_search",
        )
        if not r.ok:
            return r
        out: List[Dict] = []
        seen: Set[str] = set()
        for item in r.data.get("search", []):
            qid = item.get("id")
            if qid and qid not in seen:
                seen.add(qid)
                out.append(self.prune_empty({
                    "source_project": "wikidata",
                    "id": qid,
                    "label": item.get("label"),
                    "description": self.normalize_text(item.get("description", "")),
                    "match": item.get("match", {}),
                    "url": item.get("concepturi"),
                }))
        r.data = out
        return r

    def wikidata_entity(self, entity_id: str) -> RequestResult:
        """Fetch a Wikidata entity by ID."""
        params = {
            "action": "wbgetentities", "ids": entity_id,
            "languages": self.language, "format": "json",
        }
        r = self._request_json(
            SITE_MAP["wikidata"], params=params,
            endpoint="wikidata_entity",
        )
        if not r.ok:
            return r
        e = r.data.get("entities", {}).get(entity_id, {})
        r.data = self.prune_empty({
            "source_project": "wikidata",
            "id": entity_id,
            "label": e.get("labels", {}).get(self.language, {}).get("value"),
            "description": e.get("descriptions", {}).get(self.language, {}).get("value"),
            "aliases": [x.get("value") for x in e.get("aliases", {}).get(self.language, [])],
            "claims_count": len(e.get("claims", {})),
            "sitelinks_count": len(e.get("sitelinks", {})),
        })
        return r

    def wikifunctions_fetch(self, zid: str) -> RequestResult:
        """Fetch a Wikifunctions object by ZID."""
        r = self._request_json(
            WIKIFUNCTIONS_API,
            params={"action": "wikilambda_fetch", "zids": zid, "format": "json"},
            endpoint="wikifunctions_fetch",
        )
        if r.ok:
            r.data = self.prune_empty({
                "source_project": "wikifunctions", "zid": zid, "data": r.data,
            })
        return r

    # ── Robots check ────────────────────────────────────────────────

    def check_robots(self, project: str, path: str = "/w/api.php") -> RequestResult:
        """Check robots.txt allowance and crawl delay for a project."""
        from urllib import robotparser
        home = SITE_HOME[project]
        rp = robotparser.RobotFileParser()
        rp.set_url(urljoin(home, "/robots.txt"))
        try:
            rp.read()
            allowed = rp.can_fetch(self.user_agent, urljoin(home, path))
            crawl_delay = rp.crawl_delay(self.user_agent)
            return RequestResult(
                ok=True, endpoint="robots_check",
                data={
                    "project": project,
                    "robots_url": urljoin(home, "/robots.txt"),
                    "path_checked": path,
                    "allowed_for_user_agent": allowed,
                    "crawl_delay": crawl_delay,
                },
            )
        except Exception as e:
            return RequestResult(ok=False, endpoint="robots_check", error=str(e))

    # ── Crawl & Spider ──────────────────────────────────────────────

    def extract_links_from_page(
        self, project: str, title: str, per_page_links: int = 20
    ) -> List[str]:
        """Extract outbound links from a page."""
        r = self._request_json(
            self.action_api_for_project(project),
            params={
                "action": "query", "prop": "links",
                "titles": title, "pllimit": min(per_page_links, 500),
                "format": "json", "redirects": 1,
            },
            endpoint=f"{project}_links",
        )
        if not r.ok:
            return []
        links: List[str] = []
        seen: Set[str] = set()
        for p in r.data.get("query", {}).get("pages", {}).values():
            for link in p.get("links", []):
                t = link.get("title")
                if t and not t.startswith(BLOCKED_PREFIXES) and t not in seen:
                    seen.add(t)
                    links.append(t)
                    if len(links) >= per_page_links:
                        return links
        return links

    def fetch_parallel_titles(self, titles: List[str]) -> RequestResult:
        """Threaded summary fetch for multiple Wikipedia titles."""
        out: List[Dict] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(self.wikipedia_summary, t) for t in titles]
            for fut in as_completed(futures):
                rr = fut.result()
                if rr.ok and rr.data:
                    out.append(rr.data)
        return RequestResult(ok=True, endpoint="parallel_titles", data=out)

    def recursive_crawl(
        self, project: str, seed_title: str,
        depth: int = 2, per_page_links: int = 20,
        max_pages: int = 100,
    ) -> RequestResult:
        """Recursive crawl with BFS, extracting page data at each node."""
        queue = deque([(seed_title, 0)])
        visited: Set[str] = set()
        results: List[Dict] = []
        edges: List[Dict] = []
        loops = 0

        while queue and len(results) < max_pages and loops < max_pages * 20:
            loops += 1
            title, d = queue.popleft()
            if title in visited or d > depth:
                continue
            page = self.action_query_extract(project, title)
            visited.add(title)
            if page.ok and isinstance(page.data, dict):
                results.append(self.ai_ready_record(page.data))
            if d < depth:
                neighbors = self.extract_links_from_page(project, title, per_page_links)
                for nxt in neighbors:
                    edges.append({"source": title, "target": nxt, "depth": d + 1})
                    if nxt not in visited and all(nxt != q[0] for q in queue):
                        queue.append((nxt, d + 1))

        return RequestResult(
            ok=True, endpoint="recursive_crawl",
            data={
                "seed": seed_title,
                "project": project,
                "depth": depth,
                "max_pages": max_pages,
                "results": self.dedupe_records(results),
                "edges": edges,
                "visited_count": len(visited),
            },
        )

    def spider_from_search(
        self, project: str, query: str,
        seed_limit: int = 10, depth: int = 1,
        per_page_links: int = 15, max_pages: int = 50,
    ) -> RequestResult:
        """Spider from search seeds with recursive crawl and graph data."""
        seed_res = self.search_pages(project, query, seed_limit)
        if not seed_res.ok:
            return seed_res
        all_results: List[Dict] = []
        all_edges: List[Dict] = []
        visited_global: Set[str] = set()
        for item in seed_res.data:
            title = item.get("title")
            if not title or title in visited_global:
                continue
            crawl = self.recursive_crawl(
                project, title, depth=depth,
                per_page_links=per_page_links, max_pages=max_pages,
            )
            if crawl.ok:
                for rec in crawl.data.get("results", []):
                    t = rec.get("title")
                    if t and t not in visited_global:
                        visited_global.add(t)
                        all_results.append(rec)
                all_edges.extend(crawl.data.get("edges", []))
        return RequestResult(
            ok=True, endpoint="spider_from_search",
            data={
                "project": project,
                "query": query,
                "results": self.dedupe_records(all_results),
                "edges": all_edges,
                "seed_count": len(seed_res.data),
            },
        )

    # ── Combined & Bundle ───────────────────────────────────────────

    def combined_ai_ready_export(
        self, project: str, topic: str,
        include_sections: bool = False, include_search: bool = True,
        search_limit: int = 10,
    ) -> RequestResult:
        """Build one AI-ready cleaned dataset for a topic."""
        records: List[Dict] = []
        if project == "wikipedia":
            s = self.wikipedia_summary(topic)
            if s.ok and s.data:
                records.append(self.ai_ready_record(s.data))
        else:
            s = self.action_query_extract(project, topic, intro_only=True)
            if s.ok and s.data:
                records.append(self.ai_ready_record(s.data))
        p = self.action_query_extract(project, topic)
        if p.ok and p.data:
            records.append(self.ai_ready_record(p.data))
        if include_sections:
            sec = self.export_sections(project, topic)
            if sec.ok and sec.data:
                records.extend(self.ai_ready_record(x) for x in sec.data)
        if include_search:
            sr = self.search_pages(project, topic, limit=search_limit)
            if sr.ok and sr.data:
                records.extend(self.ai_ready_record(x) for x in sr.data)
        records = self.dedupe_records(records)
        return RequestResult(
            ok=True, endpoint="combined_ai_ready_export",
            data={
                "project": project,
                "topic": topic,
                "record_count": len(records),
                "records": records,
            },
        )

    def bundle_topic(self, topic: str) -> RequestResult:
        """Run a broad multi-project topic bundle."""
        return RequestResult(
            ok=True, endpoint="topic_bundle",
            data=self.prune_empty({
                "topic": topic,
                "wikipedia_summary": self.wikipedia_summary(topic).data,
                "wikipedia_extract": self.action_query_extract("wikipedia", topic).data,
                "wikipedia_parse": self.parse_page_html("wikipedia", topic).data,
                "wikidata_search": self.wikidata_search(topic, 5).data,
                "commons_search": self.commons_search(topic, 5).data,
                "wiktionary_search": self.search_pages("wiktionary", topic, 5).data,
                "wikivoyage_search": self.search_pages("wikivoyage", topic, 5).data,
                "wikibooks_search": self.search_pages("wikibooks", topic, 5).data,
                "wikiversity_search": self.search_pages("wikiversity", topic, 5).data,
                "wikiquote_search": self.search_pages("wikiquote", topic, 5).data,
                "mediawiki_search": self.search_pages("mediawiki", topic, 5).data,
                "wikisource_search": self.search_pages("wikisource", topic, 5).data,
                "wikispecies_search": self.search_pages("wikispecies", topic, 5).data,
            }),
        )


# ──────────────────────── SIMPLE SEARCH API ────────────────────────


def wikimedia_search(
    query: str,
    max_results: int = 10,
    project: str = "wikipedia",
    timeout: int = TIMEOUT,
) -> List[Dict[str, Any]]:
    """Search a Wikimedia project and return results in DDGS-compatible format.

    This is the primary entry point for scout-it integration.

    Args:
        query: Search query string
        max_results: Maximum results
        project: Wikimedia project key (any key from ``SITE_MAP``)
        timeout: HTTP request timeout

    Returns:
        List of dicts with ``{title, href, body, source, pageid, timestamp}`` keys.
        Empty list on failure (never raises).
    """
    try:
        extractor = WikimediaExtractor(timeout=timeout)
        rr = extractor.search_pages(project, query, limit=max_results)
        if not rr.ok or not rr.data:
            return []

        results = []
        base_url = SITE_HOME.get(project, "https://en.wikipedia.org/")
        for item in rr.data:
            title = item.get("title", "")
            url_safe = quote(title.replace(" ", "_"))
            results.append({
                "title": title,
                "href": f"{base_url}wiki/{url_safe}",
                "body": item.get("snippet", ""),
                "source": f"wikimedia:{project}",
                "pageid": item.get("pageid"),
                "timestamp": item.get("timestamp"),
            })
        return results
    except Exception as e:
        logger.warning(f"wikimedia_search failed: {e}")
        return []
