#!/usr/bin/env python3
"""
🌐 MULTI-ENGINE SEARCH — pluggable search engine registry
===========================================================

Honesty first: there is no legitimate, free, zero-config way to scrape
Google/Bing/Yahoo/Opera/etc. search result pages directly. Those sites
actively fingerprint and block scrapers, and doing it anyway violates their
Terms of Service. What *does* exist, and what this module implements, are
each engine's **official API**:

    Engine          Tier  Needs                              Free tier?
    --------------  ----  ---------------------------------  ------------------
    DuckDuckGo      0     nothing (existing ``ddgs`` engine)  yes, unlimited-ish
    Brave Search    1     BRAVE_API_KEY                       yes (2k queries/mo)
    Bing Web Search 1     BING_API_KEY (Azure)                limited trial
    Google CSE      1     GOOGLE_API_KEY + GOOGLE_CSE_ID       yes (100/day)
    SerpAPI         1     SERPAPI_KEY                          yes (100/mo)
                          (SerpAPI itself proxies Google, Bing,
                           Yahoo, Baidu, Yandex, etc. — pass
                           ``serpapi_engine="yahoo"`` and so on)

"Yahoo" and "Opera" don't have independent public search APIs of their own
(Yahoo's web results have been powered by Bing since 2019; Opera has no
search index of its own and delegates to Google/Bing/Yandex depending on
region/settings) — the closest legitimate route to either is via SerpAPI's
``engine=yahoo`` proxy, which is why it's offered as an option above rather
than a fake "YahooEngine"/"OperaEngine" that would just silently fail.

Tier-1 engines are automatically skipped (not treated as errors) when their
API key isn't configured, so ``multi_engine_search()`` degrades gracefully
to whatever's actually usable.
"""

import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import requests


class SearchEngineBase(ABC):
    """Common interface every pluggable search engine implements."""

    name: str = "base"
    tier: int = 1  # 0 = zero-config, 1 = needs an API key/credential

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether the credentials this engine needs are present."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Return a list of ``{title, url, snippet, source}`` dicts."""
        raise NotImplementedError

    def setup_hint(self) -> str:
        return f"No setup hint available for '{self.name}'."


class DuckDuckGoEngine(SearchEngineBase):
    """Zero-config default engine — wraps the existing ddgs-backed search."""

    name = "duckduckgo"
    tier = 0

    def is_configured(self) -> bool:
        return True

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        from .extraction import _ddgs_list_search_with_retry

        region = kwargs.get('region', 'us-en')
        safesearch = kwargs.get('safesearch', 'moderate')
        results, _stats = _ddgs_list_search_with_retry(
            'text',
            query=query,
            max_results=max_results,
            options={'region': region, 'safesearch': safesearch},
        )
        out = []
        for r in results:
            out.append({
                'title': r.get('title', ''),
                'url': r.get('href', '') or r.get('url', ''),
                'snippet': r.get('body', '') or r.get('description', ''),
                'source': self.name,
            })
        return out

    def setup_hint(self) -> str:
        return "No setup needed — works out of the box."


class BraveSearchEngine(SearchEngineBase):
    """Brave Search API (https://api.search.brave.com). Free tier available."""

    name = "brave"
    tier = 1
    API_URL = "https://api.search.brave.com/res/v1/web/search"

    def is_configured(self) -> bool:
        return bool(os.environ.get('BRAVE_API_KEY'))

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        api_key = os.environ.get('BRAVE_API_KEY', '')
        headers = {'Accept': 'application/json', 'X-Subscription-Token': api_key}
        params = {'q': query, 'count': min(max_results, 20)}
        resp = requests.get(self.API_URL, headers=headers, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in (data.get('web', {}) or {}).get('results', [])[:max_results]:
            out.append({
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'snippet': item.get('description', ''),
                'source': self.name,
            })
        return out

    def setup_hint(self) -> str:
        return (
            "Set BRAVE_API_KEY (free tier: https://api.search.brave.com/app/keys, "
            "~2,000 queries/month free)."
        )


class BingSearchEngine(SearchEngineBase):
    """Bing Web Search API (Azure Cognitive Services)."""

    name = "bing"
    tier = 1
    API_URL = "https://api.bing.microsoft.com/v7.0/search"

    def is_configured(self) -> bool:
        return bool(os.environ.get('BING_API_KEY'))

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        api_key = os.environ.get('BING_API_KEY', '')
        headers = {'Ocp-Apim-Subscription-Key': api_key}
        params = {'q': query, 'count': min(max_results, 50)}
        resp = requests.get(self.API_URL, headers=headers, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in (data.get('webPages', {}) or {}).get('value', [])[:max_results]:
            out.append({
                'title': item.get('name', ''),
                'url': item.get('url', ''),
                'snippet': item.get('snippet', ''),
                'source': self.name,
            })
        return out

    def setup_hint(self) -> str:
        return (
            "Set BING_API_KEY (Azure Cognitive Services 'Bing Search v7' resource; "
            "Azure offers a limited free trial tier)."
        )


class GoogleCSEEngine(SearchEngineBase):
    """Google Programmable Search Engine (Custom Search JSON API)."""

    name = "google"
    tier = 1
    API_URL = "https://www.googleapis.com/customsearch/v1"

    def is_configured(self) -> bool:
        return bool(os.environ.get('GOOGLE_API_KEY')) and bool(os.environ.get('GOOGLE_CSE_ID'))

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        api_key = os.environ.get('GOOGLE_API_KEY', '')
        cse_id = os.environ.get('GOOGLE_CSE_ID', '')
        out: List[Dict[str, Any]] = []
        # Google CSE returns max 10 results per call; page via `start`.
        start = 1
        while len(out) < max_results and start <= 91:
            params = {'key': api_key, 'cx': cse_id, 'q': query, 'start': start, 'num': min(10, max_results - len(out))}
            resp = requests.get(self.API_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            items = data.get('items', [])
            if not items:
                break
            for item in items:
                out.append({
                    'title': item.get('title', ''),
                    'url': item.get('link', ''),
                    'snippet': item.get('snippet', ''),
                    'source': self.name,
                })
            start += 10
        return out[:max_results]

    def setup_hint(self) -> str:
        return (
            "Set GOOGLE_API_KEY + GOOGLE_CSE_ID (Google Programmable Search Engine, "
            "https://programmablesearchengine.google.com — free tier: 100 queries/day)."
        )


class SerpApiEngine(SearchEngineBase):
    """SerpAPI (https://serpapi.com) — a paid aggregator that proxies real
    Google/Bing/Yahoo/Baidu/Yandex/DuckDuckGo result pages through one API.
    This is the realistic way to get genuine Google/Bing/Yahoo results
    without violating those sites' anti-scraping ToS."""

    name = "serpapi"
    tier = 1
    API_URL = "https://serpapi.com/search"
    SUPPORTED_UNDERLYING_ENGINES = (
        "google", "bing", "yahoo", "baidu", "yandex", "duckduckgo", "ecosia", "naver",
    )

    def is_configured(self) -> bool:
        return bool(os.environ.get('SERPAPI_KEY'))

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        api_key = os.environ.get('SERPAPI_KEY', '')
        underlying = kwargs.get('serpapi_engine', 'google')
        if underlying not in self.SUPPORTED_UNDERLYING_ENGINES:
            underlying = 'google'
        params = {'engine': underlying, 'q': query, 'api_key': api_key, 'num': max_results}
        resp = requests.get(self.API_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        out = []
        for item in data.get('organic_results', [])[:max_results]:
            out.append({
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'snippet': item.get('snippet', ''),
                'source': f"serpapi:{underlying}",
            })
        return out

    def setup_hint(self) -> str:
        return (
            "Set SERPAPI_KEY (https://serpapi.com — free tier: 100 searches/month). "
            "Pass serpapi_engine='yahoo'/'bing'/'baidu'/'yandex'/... to proxy other engines."
        )


class WikimediaEngine(SearchEngineBase):
    """Wikimedia / Wikipedia search — zero-config, no API key needed.

    Tier 0 because the MediaWiki Action API is open and free (rate limits apply
    but no auth required).  Used as a fallback source for ``web-search`` / ``multi-search``
    or directly via ``--sources wikimedia``.
    """

    name = "wikimedia"
    tier = 0

    def is_configured(self) -> bool:
        return True

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        from .wikimedia_source import wikimedia_search

        project = kwargs.get('project', 'wikipedia')
        results = wikimedia_search(query, max_results=max_results, project=project)
        out = []
        for r in results:
            out.append({
                'title': r.get('title', ''),
                'url': r.get('href', '') or r.get('url', ''),
                'snippet': r.get('body', ''),
                'source': f"wikimedia:{project}",
            })
        return out

    def setup_hint(self) -> str:
        return "No setup needed — Wikimedia API is open and free."


ENGINE_REGISTRY: Dict[str, type] = {
    'duckduckgo': DuckDuckGoEngine,
    'brave': BraveSearchEngine,
    'bing': BingSearchEngine,
    'google': GoogleCSEEngine,
    'serpapi': SerpApiEngine,
    'wikimedia': WikimediaEngine,
}


def list_engines() -> List[Dict[str, Any]]:
    """Report every registered engine's configuration status (for `--help`-style discovery)."""
    out = []
    for name, cls in ENGINE_REGISTRY.items():
        inst = cls()
        out.append({
            'name': name,
            'tier': inst.tier,
            'configured': inst.is_configured(),
            'setup_hint': inst.setup_hint(),
        })
    return out


def multi_engine_search(
    query: str,
    engines: Optional[List[str]] = None,
    max_results: int = 10,
    max_workers: int = 5,
    timeout: int = 15,
    dedupe: bool = True,
    **engine_kwargs,
) -> Dict[str, Any]:
    """Query multiple search engines in parallel and merge/dedupe results.

    Unconfigured tier-1 engines are skipped (reported in ``stats['skipped']``,
    not treated as failures). Unknown engine names are reported the same way.
    """
    engines = engines or ['duckduckgo']
    start_time = time.time()

    runnable = []
    skipped = []
    for name in engines:
        cls = ENGINE_REGISTRY.get(name)
        if cls is None:
            skipped.append({'engine': name, 'reason': 'unknown engine'})
            continue
        inst = cls(timeout=timeout)
        if not inst.is_configured():
            skipped.append({'engine': name, 'reason': f'not configured — {inst.setup_hint()}'})
            continue
        runnable.append(inst)

    per_engine_results: Dict[str, List[Dict[str, Any]]] = {}
    per_engine_errors: Dict[str, str] = {}

    def _run(engine: SearchEngineBase):
        try:
            return engine.name, engine.search(query, max_results=max_results, **engine_kwargs), None
        except Exception as e:
            return engine.name, [], f"{type(e).__name__}: {e}"

    if runnable:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(runnable))) as executor:
            futures = [executor.submit(_run, eng) for eng in runnable]
            for future in as_completed(futures):
                name, results, error = future.result()
                per_engine_results[name] = results
                if error:
                    per_engine_errors[name] = error

    merged: List[Dict[str, Any]] = []
    seen_urls = set()
    for name in engines:
        for item in per_engine_results.get(name, []):
            url = (item.get('url') or '').strip().rstrip('/')
            if dedupe and url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            merged.append(item)

    return {
        'query': query,
        'merged_results': merged,
        'per_engine': per_engine_results,
        'stats': {
            'engines_requested': engines,
            'engines_run': [e.name for e in runnable],
            'skipped': skipped,
            'errors': per_engine_errors,
            'total_before_dedupe': sum(len(v) for v in per_engine_results.values()),
            'total_after_dedupe': len(merged),
            'execution_time': time.time() - start_time,
        },
    }
