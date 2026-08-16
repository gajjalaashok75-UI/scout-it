"""
📡 REDDIT PROVIDER — RSS-first, tier 1 (reliable, no auth).

Reddit's old anonymous ``.json`` endpoints now return 403 for most requests
(anti-bot rules; official API closed self-service registration). This provider
therefore uses Reddit's **public RSS/Atom feeds** (``.rss``) as the primary
path -- these are served for RSS readers without the aggressive 403 blocking
that hits ``.json``, and cover virtually every page:

  * front page           -> https://www.reddit.com/.rss
  * subreddit            -> https://www.reddit.com/r/{sub}.rss
  * combined subreddits  -> https://www.reddit.com/r/{a}+{b}.rss
  * user activity        -> https://www.reddit.com/user/{name}.rss
  * domain               -> https://www.reddit.com/domain/{domain}.rss
  * search               -> https://www.reddit.com/search?q={q}.rss
  * comments on a post   -> {permalink}.rss
  * sort                 -> append ?sort=new|hot|top|relevance

Flow (mirrors the web/news-search RSS pattern):
  1. Fetch the relevant feed(s).
  2. Parse Atom entries -> snippets (title, author, link, published, content).
  3. Rank by relevance to the query (with a score/recency boost) and cap at
     ``--max`` (default 20).
  4. Optionally extract the full post page for the top results and clean it.

The old ``.json`` search path is kept as a secondary fallback when a feed
fetch is rate-limited/blocked, so the public ``reddit_search()`` API name and
its behaviour are preserved.

Capabilities: ``query`` (site-wide search), ``subreddit`` (one or more
subreddits), ``user`` (a user's posts/comments). Helper logic (random-UA
session, retry/backoff, comment-tree extraction) ported from
datavorous/yars (https://github.com/datavorous/yars).
"""

from __future__ import annotations

import html as _html
import os
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import requests

from .base import (
    CAP_QUERY,
    CAP_SUBREDDIT,
    CAP_USER,
    SocialProvider,
    normalize_item,
    provider_result,
)

# Rotating User-Agents (ported from datavorous/yars RandomUserAgentSession +
# the-ai-entrepreneur-ai-hub/telegram-channel-scraper). Reddit blocks bare
# python-requests UAs, so always send a browser-shaped one.
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _ua() -> str:
    import random
    return random.choice(_USER_AGENTS)


def _reddit_headers() -> Dict[str, str]:
    headers = {"User-Agent": _ua(), "Accept": "application/atom+xml,application/rss+xml,text/xml"}
    cookie = os.environ.get("REDDIT_COOKIE")
    if cookie:
        headers["Cookie"] = cookie
    return headers


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from Reddit's HTML content.
    Unescape first (the XML parser may have already decoded some entities),
    then strip any resulting real tags."""
    if not text:
        return ""
    text = _html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    return _html.unescape(text).strip()


def _extract_link_from_content(content_html: str, fallback: str) -> str:
    """Pull the external [link] URL out of Reddit's content HTML, falling
    back to the entry's own <link>."""
    if not content_html:
        return fallback
    # Reddit wraps the linked URL in <a href="...">[link]</a>.
    m = re.search(r'href="([^"]+)"[^>]*>\s*\[link\]', content_html)
    if m:
        return m.group(1)
    return fallback


def _parse_reddit_feed(xml_text: str, max_results: int) -> List[Dict[str, Any]]:
    """Parse a Reddit Atom/RSS feed into a list of post dicts.

    Reddit serves Atom feeds (``<feed>``/``<entry>``); older paths may serve
    RSS 2.0 (``<rss>``/``<channel>``/``<item>``). Both are handled.
    """
    items: List[Dict[str, Any]] = []
    if not xml_text:
        return items
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # Atom: <entry> elements.
    entries = root.findall(f"{_ATOM_NS}entry")
    if entries:
        for entry in entries:
            if len(items) >= max_results:
                break
            title_el = entry.find(f"{_ATOM_NS}title")
            link_el = entry.find(f"{_ATOM_NS}link")
            author_el = entry.find(f"{_ATOM_NS}author")
            content_el = entry.find(f"{_ATOM_NS}content")
            pub_el = entry.find(f"{_ATOM_NS}published")
            if pub_el is None:
                pub_el = entry.find(f"{_ATOM_NS}updated")
            id_el = entry.find(f"{_ATOM_NS}id")

            link = link_el.get("href", "") if link_el is not None else ""
            content_html = content_el.text if content_el is not None else ""
            author = ""
            if author_el is not None:
                name_el = author_el.find(f"{_ATOM_NS}name")
                author = (name_el.text or "").strip() if name_el is not None else ""

            items.append({
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "author": author.lstrip("/u/"),
                "url": link,
                "external_url": _extract_link_from_content(content_html, link),
                "published": pub_el.text if pub_el is not None else None,
                "content_html": content_html or "",
                "selftext": _strip_html(content_html),
                "id": id_el.text if id_el is not None else None,
            })
        return items

    # RSS 2.0: <item> elements (root could be <rss> or <rdf:RDF>).
    rss_items = list(root.iter("item"))
    for item in rss_items:
        if len(items) >= max_results:
            break

        def _text(tag: str) -> str:
            # Match a tag with or without a namespace prefix; finds both
            # plain <title> and namespaced <dc:creator> / {ns}creator.
            el = item.find(tag)
            if el is None:
                # Try matching by local name (ignores namespace).
                for c in item:
                    if c.tag.split("}")[-1] == tag.split(":")[-1]:
                        el = c
                        break
            return (el.text or "").strip() if el is not None else ""

        title = _text("title")
        link = _text("link")
        desc = _text("description")
        author = _text("dc:creator") or _text("author")
        pub = _text("pubDate")
        guid = _text("guid")
        items.append({
            "title": title,
            "author": author.lstrip("/u/"),
            "url": link,
            "external_url": link,
            "published": pub,
            "content_html": desc,
            "selftext": _strip_html(desc),
            "id": guid,
        })
    return items


def _rank_posts(posts: List[Dict[str, Any]], query: Optional[str],
                max_results: int) -> List[Dict[str, Any]]:
    """Rank posts by query relevance (title > selftext) with a small recency
    boost, then cap at ``max_results``. Mirrors the top-ranking step of the
    web/news search flow."""
    if not posts:
        return posts
    q = (query or "").lower().strip()
    terms = [t for t in re.split(r"\s+", q) if len(t) > 1] if q else []

    def _score(p: Dict[str, Any]) -> float:
        title = (p.get("title") or "").lower()
        body = (p.get("selftext") or "").lower()
        if not terms:
            return 0.0
        score = 0.0
        for t in terms:
            if t in title:
                score += 3.0
            if t in body:
                score += 1.0
            # whole-phrase match bonus
        if q and q in title:
            score += 5.0
        return score

    scored = sorted(posts, key=lambda p: (-_score(p), p.get("published") or ""), )
    return scored[:max_results]


def _fetch_feed(url: str, timeout: int = 15,
                max_retries: int = 3) -> Dict[str, Any]:
    """Fetch a Reddit RSS feed with retry/backoff (ported from yars's Retry
    adapter). Returns ``{xml, status, status_code, errors}``."""
    errs: List[str] = []
    last_status: Optional[int] = None
    for attempt in range(max(1, max_retries)):
        try:
            resp = requests.get(url, headers=_reddit_headers(), timeout=timeout)
        except Exception as e:
            errs.append(f"{type(e).__name__}: {e}")
            time.sleep(0.5 * (attempt + 1))
            continue
        last_status = resp.status_code
        if resp.status_code == 200 and resp.text:
            return {"xml": resp.text, "status": "success",
                    "status_code": 200, "errors": errs}
        if resp.status_code in (429, 503):
            # Rate-limited -- back off and retry.
            errs.append(f"HTTP {resp.status_code} (rate-limited)")
            time.sleep(1.0 * (attempt + 1) * 1.5)
            continue
        if resp.status_code == 403:
            errs.append("HTTP 403 (blocked)")
            # 403 is persistent for this IP; no point retrying the same UA.
            break
        errs.append(f"HTTP {resp.status_code}")
        break
    return {"xml": "", "status": "failed", "status_code": last_status, "errors": errs}


def _build_feed_url(*, query: Optional[str] = None, subreddit: Optional[str] = None,
                    user: Optional[str] = None, sort: str = "relevance") -> Optional[str]:
    """Build the Reddit RSS feed URL for the given source args.

    Only one of query/subreddit/user is used (subreddit > user > query), to
    match the capability selection in ``RedditProvider``.
    """
    sort_param = f"?sort={sort}" if sort and sort != "relevance" else ""
    if subreddit:
        # Support combined subreddits: "python+programming".
        subs = subreddit.strip().lstrip("r/").strip("/")
        return f"https://www.reddit.com/r/{subs}/.rss{sort_param}"
    if user:
        u = user.strip().lstrip("u/").lstrip("@")
        return f"https://www.reddit.com/user/{u}/.rss{sort_param}"
    if query:
        return f"https://www.reddit.com/search.rss?q={quote_plus(query)}{('&sort=' + sort) if sort and sort != 'relevance' else ''}"
    return None


# =====================================================================
# Core fetch functions (module-level for backwards compatibility)
# =====================================================================

def reddit_search(
    query: str,
    subreddit: Optional[str] = None,
    max_results: int = 20,
    sort: str = "relevance",
    user: Optional[str] = None,
    extract_full: bool = False,
) -> Dict[str, Any]:
    """Search Reddit via public RSS/Atom feeds (primary, reliable path) with
    the old anonymous ``.json`` endpoint as a secondary fallback.

    Source selection (one is used):
      * ``subreddit`` -> ``r/{sub}.rss`` (supports combined ``a+b``)
      * ``user``      -> ``user/{name}.rss`` (that user's posts + comments)
      * ``query``     -> ``search.rss?q={query}`` (site-wide search)

    Flow mirrors the web/news-search RSS pattern: fetch feed -> parse entries
    -> rank by query relevance -> cap at ``max_results`` -> optionally extract
    full post content for the top results.

    ``extract_full=True`` triggers a best-effort full-page extraction of each
    top result's permalink via the project's resilient fetcher (the "extract
    full page content and clean" step). Off by default for speed; the RSS
    ``<content>`` already carries the post selftext.

    The ``.json`` fallback runs only when every RSS attempt is blocked/
    rate-limited, so the previous behaviour is preserved for callers that
    relied on it.
    """
    if not any([query, subreddit, user]):
        return {"error": "no_input",
                "error_message": "Provide a --query, --subreddit, or --user for Reddit."}

    feed_url = _build_feed_url(query=query, subreddit=subreddit, user=user, sort=sort)
    feed_outcome = _fetch_feed(feed_url) if feed_url else None

    posts: List[Dict[str, Any]] = []
    source_used = "rss"
    feed_errors: List[str] = []

    if feed_outcome and feed_outcome["status"] == "success":
        posts = _parse_reddit_feed(feed_outcome["xml"], max_results * 2)
        # If this is a subreddit/user feed (not a search), rank by query.
        if subreddit or user:
            posts = _rank_posts(posts, query, max_results)
        else:
            posts = posts[:max_results]

    # If RSS didn't yield posts (fetch failed, blocked, or the body wasn't a
    # parseable feed -- e.g. an interstitial), fall back to the .json path.
    if not posts:
        if feed_outcome and feed_outcome.get("status") != "success":
            feed_errors = feed_outcome.get("errors", [])
        source_used = "json_fallback"
        json_res = _reddit_json_search(query, subreddit=subreddit,
                                       max_results=max_results, sort=sort)
        if "error" in json_res:
            return {**json_res,
                    "query": query, "subreddit": subreddit, "user": user,
                    "source_used": source_used,
                    "feed_errors": feed_errors}
        posts = json_res.get("posts", [])

    if not posts:
        return {"query": query, "subreddit": subreddit, "user": user,
                "result_count": 0, "posts": [], "source_used": source_used,
                "note": ("RSS feed returned no entries. Reddit may be rate-limiting this IP "
                         "(429) or the subreddit/user does not exist.") if source_used == "rss"
                        else "No results found via the .json fallback either.",
                "feed_errors": feed_errors}

    # Optional full-content extraction for the top results (the "extract full
    # page content and clean" step from the web/news-search flow).
    if extract_full and posts:
        posts = _enrich_with_full_content(posts, max_results)

    return {"query": query, "subreddit": subreddit, "user": user,
            "result_count": len(posts), "posts": posts, "source_used": source_used,
            "feed_errors": feed_errors}


def _reddit_json_search(
    query: str,
    subreddit: Optional[str] = None,
    max_results: int = 20,
    sort: str = "relevance",
) -> Dict[str, Any]:
    """Legacy anonymous ``.json`` search (secondary fallback). Often 403 as of
    2026; kept so the public API name/behaviour is preserved."""
    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = f"?q={quote_plus(query)}&restrict_sr=1&sort={sort}&limit={min(max_results, 100)}"
    else:
        url = "https://www.reddit.com/search.json"
        params = f"?q={quote_plus(query)}&sort={sort}&limit={min(max_results, 100)}"

    try:
        resp = requests.get(url + params, headers=_reddit_headers(), timeout=15)
    except Exception as e:
        return {"error": "network_error", "error_message": f"{type(e).__name__}: {e}"}

    if resp.status_code == 403:
        return {"error": "blocked",
                "error_message": ("Reddit returned 403 for both RSS and .json (anonymous access "
                                  "blocked from this IP). Options: (1) set REDDIT_COOKIE to a "
                                  "logged-in session's Cookie header, (2) retry later, or "
                                  "(3) apply for official API access at https://www.reddit.com/prefs/apps.")}
    if resp.status_code >= 400:
        return {"error": "api_error", "error_message": f"HTTP {resp.status_code}"}

    try:
        data = resp.json()
    except ValueError:
        return {"error": "parse_error", "error_message": "Reddit did not return valid JSON."}

    children = ((data.get("data") or {}).get("children")) or []
    posts = []
    for c in children[:max_results]:
        p = c.get("data", {})
        permalink = p.get("permalink")
        posts.append({
            "title": p.get("title"),
            "author": p.get("author"),
            "subreddit": p.get("subreddit"),
            "url": f"https://www.reddit.com{permalink}" if permalink else p.get("url"),
            "external_url": p.get("url"),
            "score": p.get("score"),
            "num_comments": p.get("num_comments"),
            "published": p.get("created_utc"),
            "selftext": (p.get("selftext") or "")[:2000],
            "id": p.get("id"),
        })
    return {"query": query, "subreddit": subreddit, "result_count": len(posts), "posts": posts}


def _enrich_with_full_content(posts: List[Dict[str, Any]],
                              max_results: int) -> List[Dict[str, Any]]:
    """Best-effort full-page extraction for the top Reddit posts (the
    "extract full page content and clean" step). Uses the project's resilient
    fetcher + cleaner on each permalink."""
    try:
        from ..extraction import fetch_resilient
        from ..cleaner import advanced_clean_text
    except Exception:
        return posts  # extraction optional; never block on missing imports

    for p in posts[:max_results]:
        url = p.get("url")
        if not url or "reddit.com" not in url:
            continue
        try:
            outcome = fetch_resilient(url, timeout=15, max_retries=1)
            if outcome.get("status") == "success" and outcome.get("html"):
                cleaned = advanced_clean_text(outcome["html"], url)
                if cleaned:
                    p["full_content"] = cleaned[:5000]
        except Exception:
            continue
    return posts


# =====================================================================
# Provider (capability-aware wrapper)
# =====================================================================

class RedditProvider(SocialProvider):
    platform = "reddit"
    SUPPORTED_CAPABILITIES = {CAP_QUERY, CAP_SUBREDDIT, CAP_USER}

    def _execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query") or ""
        subreddit = params.get("subreddit") if capability == CAP_SUBREDDIT else None
        user = params.get("user") if capability == CAP_USER else None
        sort = params.get("sort", "relevance")
        max_results = params.get("max_results", 20)
        extract_full = params.get("extract_full", False)

        # subreddit/user listing does not require a query (the feed itself is
        # the listing); only the query capability needs a query term.
        if capability == CAP_QUERY and not query:
            return provider_result(
                self.platform, error="no_input",
                error_message="Reddit query search requires a --query.",
                capabilities_used=[CAP_QUERY],
            )
        if capability == CAP_SUBREDDIT and not subreddit:
            return provider_result(
                self.platform, error="no_input",
                error_message="Reddit subreddit listing requires a --subreddit.",
                capabilities_used=[CAP_SUBREDDIT],
            )
        if capability == CAP_USER and not user:
            return provider_result(
                self.platform, error="no_input",
                error_message="Reddit user listing requires a --user.",
                capabilities_used=[CAP_USER],
            )

        raw = reddit_search(query, subreddit=subreddit, max_results=max_results,
                            sort=sort, user=user, extract_full=extract_full)
        cap_used = {CAP_SUBREDDIT: CAP_SUBREDDIT, CAP_USER: CAP_USER}.get(capability, CAP_QUERY)
        if "error" in raw:
            return provider_result(self.platform, query=query, error=raw["error"],
                                   error_message=raw["error_message"],
                                   capabilities_used=[cap_used], raw=raw)

        items: List[Dict[str, Any]] = [normalize_item(
            self.platform,
            author=p.get("author"),
            content=(p.get("title") or "") + (
                f"\n\n{p.get('selftext')}" if p.get("selftext") else ""),
            url=p.get("url"),
            timestamp=str(p.get("published")) if p.get("published") else None,
            metadata={
                "title": p.get("title"),
                "subreddit": p.get("subreddit") or subreddit,
                "user": user,
                "external_url": p.get("external_url"),
                "score": p.get("score"),
                "num_comments": p.get("num_comments"),
                "published": p.get("published"),
                "id": p.get("id"),
                "source": raw.get("source_used"),
            },
        ) for p in raw.get("posts", [])]

        note = None
        if raw.get("source_used") == "json_fallback":
            note = "RSS feed blocked/rate-limited; fell back to .json endpoint."
        elif raw.get("note"):
            note = raw["note"]

        return provider_result(self.platform, query=query, results=items,
                               capabilities_used=[cap_used], raw=raw, note=note)
