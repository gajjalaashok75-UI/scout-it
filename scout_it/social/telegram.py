"""
📡 TELEGRAM PROVIDER — public channel previews (t.me/s/*), tier 0.

What works: public channel previews — posts, text, view counts, media links,
timestamps. Nothing else is needed: this is Telegram's official public web
preview, no login required.

Capabilities: ``query`` (search public channels by topic via a site:t.me web
search — there is no official Telegram-wide anonymous search API), and
``channel`` (fetch posts directly from a known channel username).
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .. import __version__ as _VERSION
from .base import (
    CAP_CHANNEL,
    CAP_QUERY,
    SocialProvider,
    normalize_item,
    provider_result,
)

# Rotating User-Agents (anti-Cloudflare courtesy, ported from
# the-ai-entrepreneur-ai-hub/telegram-channel-scraper).
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    f"scout-it/{_VERSION}",
]


def _ua() -> str:
    import random
    return random.choice(_USER_AGENTS)


def _convert_count(value: Optional[str]) -> Optional[int]:
    """Convert '1.2K'→1200, '3M'→3_000_000, '5,432'→5432 (ported from tchan)."""
    if value is None:
        return None
    v = value.strip().replace(" ", "").replace(",", "")
    if not v:
        return None
    try:
        mult = 1
        if v[-1] in "KkМм":
            mult, v = 1_000, v[:-1]
        elif v[-1] in "Mm":
            mult, v = 1_000_000, v[:-1]
        return int(float(v) * mult)
    except (ValueError, IndexError):
        return None


def _normalize_channel(channel: str) -> str:
    """Normalize @username, t.me/..., t.me/s/..., URLs to a bare username
    (ported from tchan.normalize_url + notoken.extract_channel_identifier)."""
    channel = str(channel or "").strip()
    if not channel:
        return ""
    if channel.startswith("@"):
        channel = channel[1:]
    if channel.startswith("http"):
        from urllib.parse import urlparse
        path = urlparse(channel).path or ""
        # /s/durov -> durov ; /durov -> durov ; /durov/123 -> durov
        channel = path.lstrip("/")
    # Bare-host input like "t.me/durov" (no scheme).
    channel = channel.split("t.me/")[-1]
    if channel.startswith("s/"):
        channel = channel[2:]
    channel = channel.strip("/").split("/")[0]
    return channel


# Markers Telegram returns when a channel does not exist / is private, even
# though the HTTP status is 200 (ported from AlexSaite/telegram_scrapper_notoken).
_NOT_FOUND_MARKERS = (
    "if you have <strong>telegram</strong>",
    "channel not found",
    "no posts",
)


def _looks_like_not_found(html: str, soup: BeautifulSoup) -> bool:
    if soup.select_one(".tgme_widget_message_wrap"):
        return False
    if soup.select_one(".tgme_channel_info_header_title"):
        # Channel exists but genuinely has no previewable posts.
        return False
    low = html.lower()
    return any(m in low for m in _NOT_FOUND_MARKERS)


def _parse_channel_meta(soup: BeautifulSoup) -> Dict[str, Any]:
    """Channel-level metadata (title/description/subscribers/verified/avatar)
    ported from tchan.parse_info + notoken channel_metadata extraction."""
    def _meta(prop: str) -> Optional[str]:
        tag = soup.select_one(f"meta[property='{prop}']")
        return tag.get("content") if tag else None

    title_el = soup.select_one(".tgme_channel_info_header_title")
    meta: Dict[str, Any] = {
        "title": (title_el.get_text(strip=True) if title_el else None) or _meta("og:title"),
        "description": _meta("og:description"),
        "image_url": _meta("og:image"),
        "subscribers": None,
        "verified": bool(soup.select_one(".tgme_channel_info_header i.verified-icon, "
                                          ".tgme_page_title i.verified-icon")),
    }
    # Subscriber / photos / videos / links counters.
    for counter in soup.select(".tgme_channel_info_counter"):
        val_el = counter.select_one(".counter_value")
        type_el = counter.select_one(".counter_type")
        if not val_el or not type_el:
            continue
        ctype = type_el.get_text(strip=True).lower()
        cval = _convert_count(val_el.get_text(strip=True))
        if cval is None:
            continue
        if "subscriber" in ctype or "member" in ctype:
            meta["subscribers"] = cval
        elif "photo" in ctype:
            meta["photos"] = cval
        elif "video" in ctype:
            meta["videos"] = cval
        elif "link" in ctype:
            meta["links"] = cval
    return meta


# =====================================================================
# Parsers (public t.me/s/<channel> HTML)
# =====================================================================

def _parse_telegram_primary(html: str, max_results: int) -> Dict[str, Any]:
    """Primary parser: fast, covers the common case."""
    soup = BeautifulSoup(html, "html.parser")

    posts = []
    for wrap in soup.select(".tgme_widget_message_wrap")[-max_results:]:
        msg = wrap.select_one(".tgme_widget_message")
        if not msg:
            continue
        text_el = msg.select_one(".tgme_widget_message_text")
        date_el = msg.select_one("time")
        views_el = msg.select_one(".tgme_widget_message_views")
        post_link = msg.get("data-post")
        posts.append({
            "id": post_link,
            "url": f"https://t.me/{post_link}" if post_link else None,
            "text": text_el.get_text("\n", strip=True) if text_el else "",
            "date": date_el.get("datetime") if date_el else None,
            "views": views_el.get_text(strip=True) if views_el else None,
            "views_count": _convert_count(views_el.get_text(strip=True) if views_el else None),
            "has_photo": bool(msg.select_one(".tgme_widget_message_photo_wrap")),
            "has_video": bool(msg.select_one(".tgme_widget_message_video_wrap")),
        })

    meta = _parse_channel_meta(soup)

    return {
        "title": meta["title"],
        "description": meta["description"],
        "subscribers": meta.get("subscribers"),
        "verified": meta.get("verified", False),
        "posts": list(reversed(posts)),
        "_soup": soup,
        "_meta": meta,
    }


def _parse_telegram_enhanced(html: str, max_results: int) -> Dict[str, Any]:
    """Alternate, more thorough parser used as a fallback when the primary
    parser finds 0 posts despite a successful fetch. Selector approach and
    field set (author, edited flag, message type, forwarded-from, og:meta
    channel info) inspired by PythonicCafe/tchan
    (https://github.com/PythonicCafe/tchan), adapted to BeautifulSoup so no
    new dependency (lxml) is required. Same public data source
    (``t.me/s/<channel>``) as the primary parser -- this is a second, richer
    opinion on parsing the same HTML, not an independent network source,
    since Telegram itself only exposes one public preview page."""
    soup = BeautifulSoup(html, "html.parser")

    seen_ids = set()
    posts = []
    candidates = soup.select(".tgme_widget_message_wrap .tgme_widget_message, .tgme_widget_message[data-post]")
    for msg in candidates:
        post_link = msg.get("data-post")
        if post_link in seen_ids:
            continue
        seen_ids.add(post_link)

        meta_el = msg.select_one(".tgme_widget_message_meta")
        edited = bool(meta_el and "edited" in meta_el.get_text(strip=True).lower())

        author_el = msg.select_one(".tgme_widget_message_from_author")
        forwarded_el = msg.select_one(".tgme_widget_message_forwarded_from_name")

        text_el = msg.select_one(".tgme_widget_message_text")
        text = text_el.get_text("\n", strip=True) if text_el else None

        msg_type = "text"
        if msg.select_one(".tgme_widget_message_poll"):
            msg_type = "poll"
        elif msg.select_one(".tgme_widget_message_sticker_wrap"):
            msg_type = "sticker"
        elif msg.select_one(".tgme_widget_message_roundvideo"):
            msg_type = "round-video"
        elif msg.select_one(".tgme_widget_message_video_wrap"):
            msg_type = "video"
        elif msg.select_one(".tgme_widget_message_photo_wrap"):
            msg_type = "photo"
        elif msg.select_one(".tgme_widget_message_document"):
            msg_type = "document"
        elif msg.select_one("audio"):
            msg_type = "audio"
        elif msg.select_one(".tgme_widget_message_location_wrap"):
            msg_type = "location"
        elif not text:
            msg_type = "service"

        date_el = msg.select_one("time")
        views_el = msg.select_one(".tgme_widget_message_views")

        preview_link_el = msg.select_one(".tgme_widget_message_link_preview")

        posts.append({
            "id": post_link,
            "url": f"https://t.me/{post_link}" if post_link else None,
            "type": msg_type,
            "text": text,
            "date": date_el.get("datetime") if date_el else None,
            "views": views_el.get_text(strip=True) if views_el else None,
            "views_count": _convert_count(views_el.get_text(strip=True) if views_el else None),
            "edited": edited,
            "author": author_el.get_text(strip=True) if author_el else None,
            "forwarded_from": forwarded_el.get_text(strip=True) if forwarded_el else None,
            "preview_url": preview_link_el.get("href") if preview_link_el else None,
            "has_photo": bool(msg.select_one(".tgme_widget_message_photo_wrap")),
            "has_video": bool(msg.select_one(".tgme_widget_message_video_wrap")),
        })

    meta = _parse_channel_meta(soup)

    return {
        "title": meta["title"],
        "description": meta["description"],
        "subscribers": meta.get("subscribers"),
        "verified": meta.get("verified", False),
        "posts": list(reversed(posts))[-max_results:] if max_results else list(reversed(posts)),
        "_soup": soup,
        "_meta": meta,
    }


# =====================================================================
# Core fetch functions (kept as module-level for backwards compatibility)
# =====================================================================

def telegram_channel(
    channel: str,
    max_results: int = 20,
    max_fetch_retries: int = 3,
) -> Dict[str, Any]:
    """Fetch recent posts from a **public** Telegram channel via its official
    web preview (``https://t.me/s/<channel>``) — no login required. Only
    works for public channels that have previews enabled (the vast
    majority do); private channels and DMs are out of scope entirely
    (Telegram doesn't expose those without the MTProto client API + login).

    Paginates backwards through ``?before=<id>`` pages (ported from
    PythonicCafe/tchan) so that ``max_results`` larger than a single preview
    page (~20 posts) actually returns more posts. Distinguishes a missing /
    private channel from an empty-but-existing one by inspecting the body
    (ported from AlexSaite/telegram_scrapper_notoken): t.me replies HTTP 200
    with a "If you have Telegram" stub when a channel does not exist.

    Retries the fetch+parse cycle up to *max_fetch_retries* times (some
    pages transiently render a "no messages" placeholder under load). If
    every attempt's primary parse still comes back with 0 posts despite a
    successful fetch, one more attempt re-parses the same HTML with a
    richer, more defensive parser (see ``_parse_telegram_enhanced``) before
    giving up — different selector strategy, same underlying public page.
    """
    from ..extraction import fetch_resilient  # local import avoids a cycle at module load

    channel = _normalize_channel(channel)
    if not channel:
        return {"error": "invalid_channel", "error_message": "Provide a channel username, e.g. 'durov' or 't.me/durov'."}

    base_url = f"https://t.me/s/{channel}"
    last_html: Optional[str] = None
    last_errors: List[str] = []
    not_found = False
    blocked = False

    url = base_url
    collected: List[Dict[str, Any]] = []
    channel_meta: Dict[str, Any] = {}
    parser_used = "none_found"

    pages = max(1, (max_results + 19) // 20) if max_results > 0 else 1
    for attempt in range(max(1, max_fetch_retries)):
        fetched_any_page = False
        for _page in range(pages):
            if len(collected) >= max_results:
                break
            outcome = fetch_resilient(url, timeout=15, max_retries=1)
            if outcome["status"] != "success":
                last_errors = outcome["errors"]
                if outcome.get("status_code") == 404:
                    not_found = True
                elif outcome.get("status_code") in (401, 403):
                    blocked = True
                break

            last_html = outcome["html"]
            fetched_any_page = True
            parsed = _parse_telegram_primary(last_html, max_results)
            soup = parsed.pop("_soup", None)
            channel_meta = parsed.get("_meta", channel_meta) or channel_meta
            parsed.pop("_meta", None)

            if soup is not None and _looks_like_not_found(last_html, soup):
                not_found = True
                break

            new_posts = parsed.get("posts", [])
            if new_posts:
                parser_used = "primary"
                existing_ids = {p["id"] for p in collected if p.get("id")}
                for p in new_posts:
                    if p.get("id") and p["id"] not in existing_ids:
                        collected.append(p)
                        existing_ids.add(p["id"])
                if not channel_meta:
                    channel_meta = {"title": parsed.get("title"),
                                    "description": parsed.get("description")}

                # Backwards pagination: fetch posts older than the oldest id
                # we currently hold (ported from tchan's ?before= logic).
                min_id = _min_post_id(collected)
                before_link = None
                if soup is not None:
                    more = soup.select_one("a.tme_messages_more")
                    if more and more.get("href"):
                        before_link = more["href"]
                if not before_link and soup is not None:
                    for a in soup.select("a[href]"):
                        if "?before=" in a["href"]:
                            before_link = a["href"]
                            break
                if not before_link and min_id:
                    url = f"{base_url}?before={min_id}"
                elif before_link:
                    from urllib.parse import urljoin
                    url = urljoin("https://t.me", before_link)
                    if "?before=" not in url:
                        url = f"{base_url}?before={min_id}" if min_id else None
                else:
                    url = None
                if not url:
                    break
            else:
                # 0 posts but fetch succeeded -- retry the fetch on the next
                # outer attempt (page may have transiently rendered a
                # placeholder) before falling back to the enhanced parser.
                break

        if collected or not_found or blocked:
            break
        time.sleep(0.5 * (attempt + 1))

    if not_found:
        return {"error": "channel_not_found",
                "error_message": f"Channel '@{channel}' does not exist, is private, or has no public preview."}
    if blocked:
        return {"error": "blocked",
                "error_message": f"Telegram returned a block/error page for '@{channel}' (Cloudflare/rate-limit). Try again later."}

    if not collected and last_html is not None:
        # Primary parser found 0 posts across every retry -- fall back to the
        # richer parser on the last HTML we did successfully fetch.
        enhanced = _parse_telegram_enhanced(last_html, max_results)
        enhanced.pop("_soup", None)
        channel_meta = enhanced.get("_meta", channel_meta) or channel_meta
        enhanced.pop("_meta", None)
        collected = enhanced.get("posts", [])
        parser_used = "enhanced_fallback" if collected else "none_found"
        if not channel_meta:
            channel_meta = {"title": enhanced.get("title"),
                            "description": enhanced.get("description")}

    if not collected:
        # A channel that exists (has a preview header) but genuinely has no
        # posts is NOT a fetch failure -- return its metadata with 0 posts so
        # callers can tell this apart from an unreachable page. Only when we
        # never got any HTML at all is it a real fetch failure.
        if channel_meta and channel_meta.get("title") is not None:
            return {
                "channel": channel,
                "title": channel_meta.get("title"),
                "description": channel_meta.get("description"),
                "subscribers": channel_meta.get("subscribers"),
                "verified": channel_meta.get("verified", False),
                "post_count_returned": 0,
                "posts": [],
                "parser_used": "none_found",
            }
        return {"error": "fetch_failed",
                "error_message": f"Could not load posts for {base_url} after {max_fetch_retries} attempts: " + "; ".join(last_errors[-3:])}

    collected = collected[:max_results] if max_results else collected
    return {
        "channel": channel,
        "title": channel_meta.get("title"),
        "description": channel_meta.get("description"),
        "subscribers": channel_meta.get("subscribers"),
        "verified": channel_meta.get("verified", False),
        "post_count_returned": len(collected),
        "posts": collected,
        "parser_used": parser_used,
    }


def _min_post_id(posts: List[Dict[str, Any]]) -> Optional[int]:
    """Smallest numeric message id in *posts* (used for ``?before=``)."""
    ids = []
    for p in posts:
        pid = p.get("id")
        if pid and "/" in pid:
            try:
                ids.append(int(pid.split("/")[-1]))
            except ValueError:
                pass
    return min(ids) if ids else None


_TME_CHANNEL_RE = re.compile(r't\.me/(?:s/)?([A-Za-z0-9_]{5,32})/?$')


def telegram_search(
    query: str,
    max_channels: int = 10,
    posts_per_channel: int = 3,
    max_fetch_retries: int = 3,
) -> Dict[str, Any]:
    """Find **public** Telegram channels matching a topic.

    There is no official Telegram-wide public search API — Telegram's own
    global search requires the MTProto client API with a logged-in user.
    What this uses instead is a legitimate, commonly-used technique: public
    ``t.me`` channel preview pages ARE indexed by regular search engines, so
    a search scoped to ``site:t.me`` surfaces public channels whose preview
    pages match your query. This reuses the existing DuckDuckGo search
    engine (no ToS issue — it's an ordinary web search), extracts unique
    channel usernames from the result URLs, then pulls a quick preview
    (title + a couple of recent posts) of each via ``telegram_channel()``.

    Coverage is inherently partial (only channels DuckDuckGo has indexed,
    and only what's changed recently enough to be reflected), not an
    exhaustive channel directory.
    """
    from ..extraction import _ddgs_list_search_with_retry

    query = str(query or "").strip()
    if not query:
        return {"error": "invalid_query", "error_message": "Provide a search query."}

    ddg_results, _stats = _ddgs_list_search_with_retry(
        'text', query=f"site:t.me {query}", max_results=max_channels * 3,
        options={'region': 'us-en', 'safesearch': 'moderate'},
    )

    seen_channels = []
    for r in ddg_results:
        url = r.get('href', '') or r.get('url', '')
        match = _TME_CHANNEL_RE.search(url)
        if match:
            username = match.group(1)
            if username not in seen_channels and username.lower() not in ('s', 'joinchat'):
                seen_channels.append(username)
        if len(seen_channels) >= max_channels:
            break

    if not seen_channels:
        return {
            "query": query, "channel_count": 0, "channels": [],
            "note": "No public t.me channels found matching this query in search results. Try a broader query, "
                    "or use --channel directly if you already know the channel's username.",
        }

    channels = []
    for username in seen_channels:
        preview = telegram_channel(username, max_results=posts_per_channel, max_fetch_retries=max_fetch_retries)
        if "error" in preview:
            channels.append({"channel": username, "error": preview["error_message"]})
        else:
            channels.append(preview)

    return {"query": query, "channel_count": len(channels), "channels": channels}


# =====================================================================
# Provider (capability-aware wrapper)
# =====================================================================

class TelegramProvider(SocialProvider):
    platform = "telegram"
    SUPPORTED_CAPABILITIES = {CAP_QUERY, CAP_CHANNEL}

    def _execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        max_results = params.get("max_results", 20)
        max_fetch_retries = params.get("max_fetch_retries", 3)

        if capability == CAP_CHANNEL:
            channel = params["channel"]
            raw = telegram_channel(channel, max_results=max_results,
                                   max_fetch_retries=max_fetch_retries)

            # Channel-failure -> query fallback (user-requested behaviour):
            # if the named channel doesn't exist / is private / blocked /
            # returned no posts, fall back to public query search instead of
            # returning an empty result. Use the explicit --query if given;
            # otherwise derive a query from the channel name itself so the
            # user still gets relevant public channels.
            if "error" in raw or not raw.get("posts"):
                fallback_query = params.get("query") or channel
                fb = telegram_search(
                    fallback_query, max_channels=max_results,
                    posts_per_channel=params.get("posts_per_channel", 3),
                    max_fetch_retries=max_fetch_retries,
                )
                fb_items: List[Dict[str, Any]] = []
                for ch in fb.get("channels", []):
                    if "error" in ch:
                        continue
                    for p in ch.get("posts", []):
                        fb_items.append(normalize_item(
                            self.platform,
                            author=ch.get("channel"),
                            content=(p.get("text") or "")[:1000],
                            url=p.get("url"),
                            timestamp=p.get("date"),
                            metadata={
                                "channel": ch.get("channel"),
                                "title": ch.get("title"),
                                "subscribers": ch.get("subscribers"),
                                "views": p.get("views"),
                                "views_count": p.get("views_count"),
                                "type": p.get("type"),
                                "id": p.get("id"),
                            },
                        ))
                note = (f"channel @{channel} not found/empty; fell back to "
                        f"query search '{fallback_query}'")
                caps = [CAP_CHANNEL, CAP_QUERY]
                if fb_items:
                    return provider_result(self.platform, query=fallback_query,
                                           results=fb_items, capabilities_used=caps,
                                           raw=fb, note=note)
                # Neither channel nor fallback yielded anything.
                err = raw.get("error", "no_posts") if "error" in raw else "no_posts"
                errmsg = (raw.get("error_message") if "error" in raw
                          else f"Channel '@{channel}' returned no posts.")
                return provider_result(self.platform, query=fallback_query, error=err,
                                       error_message=errmsg + f" Query fallback for '{fallback_query}' also returned nothing.",
                                       capabilities_used=caps, raw={"channel_attempt": raw, "query_attempt": fb},
                                       note=note)

            items = [normalize_item(
                self.platform,
                author=raw.get("channel"),
                content=(p.get("text") or "")[:1000],
                url=p.get("url"),
                timestamp=p.get("date"),
                metadata={
                    "channel": raw.get("channel"),
                    "title": raw.get("title"),
                    "subscribers": raw.get("subscribers"),
                    "verified": raw.get("verified"),
                    "views": p.get("views"),
                    "views_count": p.get("views_count"),
                    "type": p.get("type"),
                    "has_photo": p.get("has_photo"),
                    "has_video": p.get("has_video"),
                    "id": p.get("id"),
                },
            ) for p in raw.get("posts", [])]
            return provider_result(self.platform, query=None, results=items,
                                   capabilities_used=[CAP_CHANNEL], raw=raw,
                                   note=f"channel @{raw.get('channel')}")

        # capability == CAP_QUERY
        posts_per_channel = params.get("posts_per_channel", 3)
        raw = telegram_search(
            params["query"], max_channels=max_results,
            posts_per_channel=posts_per_channel, max_fetch_retries=max_fetch_retries,
        )
        if "error" in raw:
            return provider_result(self.platform, query=params["query"], error=raw["error"],
                                   error_message=raw["error_message"],
                                   capabilities_used=[CAP_QUERY], raw=raw)
        items: List[Dict[str, Any]] = []
        for ch in raw.get("channels", []):
            if "error" in ch:
                continue
            for p in ch.get("posts", []):
                items.append(normalize_item(
                    self.platform,
                    author=ch.get("channel"),
                    content=(p.get("text") or "")[:1000],
                    url=p.get("url"),
                    timestamp=p.get("date"),
                    metadata={
                        "channel": ch.get("channel"),
                        "title": ch.get("title"),
                        "subscribers": ch.get("subscribers"),
                        "views": p.get("views"),
                        "views_count": p.get("views_count"),
                        "type": p.get("type"),
                        "id": p.get("id"),
                    },
                ))
        return provider_result(self.platform, query=params["query"], results=items,
                               capabilities_used=[CAP_QUERY], raw=raw)
