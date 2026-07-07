#!/usr/bin/env python3
"""
📡 SOCIAL / PLATFORM EXTRACTION — Telegram, Discord, Reddit
================================================================

Same honesty policy as ``engines.py``: implement what genuinely works, and
say plainly what doesn't rather than shipping something that silently fails.

    Platform    Tier  What works                          Needs
    ----------  ----  ----------------------------------  --------------------------
    Telegram    0     Public channel previews (t.me/s/*)   nothing — official public
                       — posts, text, view counts,          web preview, no login
                       media links, timestamps.             required.
    Discord     1     Channel message history               DISCORD_BOT_TOKEN, and the
                       via the real Discord REST API.        bot must already be a
                                                              member of the target server
                                                              with "Read Message
                                                              History" permission.
    Reddit      2     Best-effort only.                      No zero-config path exists
                       Reddit's old anonymous .json           as of mid-2026 — anonymous
                       endpoints now return 403 for            .json requests are blocked
                       most requests; this function            by anti-bot rules, and the
                       tries anyway (some IPs/UAs still        official API closed
                       occasionally get through) and           self-service registration.
                       reports the real failure reason          If you have a logged-in
                       instead of pretending it worked.         session cookie, pass it via
                                                                 REDDIT_COOKIE for a better
                                                                 chance of success.

Twitter/X, Instagram, TikTok, Facebook, LinkedIn, WeChat, etc. are not
implemented here for the same reason: none of them offer a working
zero-config or cheap-API path anymore (all require either a paid official
API tier or a logged-in browser session, which this library doesn't manage
cookies/sessions for). Wiring one of these up for real would mean either
buying API access or driving an authenticated Playwright session yourself.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


# =====================================================================
# Telegram — public channel preview (t.me/s/<channel>), tier 0
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
            "has_photo": bool(msg.select_one(".tgme_widget_message_photo_wrap")),
            "has_video": bool(msg.select_one(".tgme_widget_message_video_wrap")),
        })

    channel_title_el = soup.select_one(".tgme_channel_info_header_title")
    channel_desc_el = soup.select_one(".tgme_channel_info_description")

    return {
        "title": channel_title_el.get_text(strip=True) if channel_title_el else None,
        "description": channel_desc_el.get_text(strip=True) if channel_desc_el else None,
        "posts": list(reversed(posts)),
    }


def _parse_telegram_enhanced(html: str, max_results: int) -> Dict[str, Any]:
    """Alternate, more thorough parser used as a fallback when the primary
    parser finds 0 posts despite a successful fetch. Selector approach and
    field set (author, edited flag, message type, forwarded-from, og:meta
    channel info) inspired by PythonicCafe/tchan
    (https://github.com/PythonicCafe/tchan), adapted to BeautifulSoup so no
    new dependency (lxml) is required. Same public data source
    (``t.me/s/<channel>``) as the primary parser -- this is a second,
    richer opinion on parsing the same HTML, not an independent network
    source, since Telegram itself only exposes one public preview page."""
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
            "edited": edited,
            "author": author_el.get_text(strip=True) if author_el else None,
            "forwarded_from": forwarded_el.get_text(strip=True) if forwarded_el else None,
            "preview_url": preview_link_el.get("href") if preview_link_el else None,
            "has_photo": bool(msg.select_one(".tgme_widget_message_photo_wrap")),
            "has_video": bool(msg.select_one(".tgme_widget_message_video_wrap")),
        })

    def _meta(prop: str) -> Optional[str]:
        tag = soup.select_one(f"meta[property='{prop}']")
        return tag.get("content") if tag else None

    return {
        "title": _meta("og:title"),
        "description": _meta("og:description"),
        "image_url": _meta("og:image"),
        "posts": list(reversed(posts))[-max_results:] if max_results else list(reversed(posts)),
    }


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

    Retries the fetch+parse cycle up to *max_fetch_retries* times (some
    pages transiently render a "no messages" placeholder under load). If
    every attempt's primary parse still comes back with 0 posts despite a
    successful fetch, one more attempt re-parses the same HTML with a
    richer, more defensive parser (see ``_parse_telegram_enhanced``) before
    giving up — different selector strategy, same underlying public page.
    """
    from .extraction import fetch_resilient  # local import avoids a cycle at module load

    channel = str(channel or "").strip().lstrip("@")
    channel = channel.split("t.me/")[-1].split("t.me/s/")[-1].strip("/")
    if not channel:
        return {"error": "invalid_channel", "error_message": "Provide a channel username, e.g. 'durov' or 't.me/durov'."}

    url = f"https://t.me/s/{channel}"
    last_html = None
    last_errors: List[str] = []

    for attempt in range(max(1, max_fetch_retries)):
        outcome = fetch_resilient(url, timeout=15, max_retries=1)
        if outcome["status"] != "success":
            last_errors = outcome["errors"]
            continue

        last_html = outcome["html"]
        parsed = _parse_telegram_primary(last_html, max_results)
        if parsed["posts"]:
            return {
                "channel": channel,
                "title": parsed["title"],
                "description": parsed["description"],
                "post_count_returned": len(parsed["posts"]),
                "posts": parsed["posts"],
                "parser_used": "primary",
            }
        # 0 posts but fetch succeeded -- retry the fetch (page may have
        # transiently rendered a placeholder) before giving up on this tier.
        time.sleep(0.5 * (attempt + 1))

    if last_html is None:
        return {
            "error": "fetch_failed",
            "error_message": f"Could not load {url} after {max_fetch_retries} attempts: " + "; ".join(last_errors[-3:]),
        }

    # Primary parser found 0 posts across every retry -- fall back to the
    # richer parser on the last HTML we did successfully fetch.
    enhanced = _parse_telegram_enhanced(last_html, max_results)
    return {
        "channel": channel,
        "title": enhanced["title"],
        "description": enhanced["description"],
        "post_count_returned": len(enhanced["posts"]),
        "posts": enhanced["posts"],
        "parser_used": "enhanced_fallback" if enhanced["posts"] else "none_found",
    }


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
    from .extraction import _ddgs_list_search_with_retry

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
# Discord — real bot REST API, tier 1 (needs DISCORD_BOT_TOKEN)
# =====================================================================

DISCORD_API_BASE = "https://discord.com/api/v10"


def discord_channel_messages(
    channel_id: str,
    max_results: int = 50,
    before_message_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch recent messages from a Discord text channel using the real
    Discord Bot REST API. Requires DISCORD_BOT_TOKEN, and the bot must
    already be a member of the server that channel belongs to, with the
    "Read Message History" permission on that channel — Discord has no
    anonymous/public read API at all, by design.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        return {
            "error": "auth_required",
            "error_message": (
                "Set DISCORD_BOT_TOKEN (create an application + bot at "
                "https://discord.com/developers/applications, invite it to the target "
                "server with 'Read Messages/View Channels' + 'Read Message History' "
                "permissions). Discord has no public/anonymous read API."
            ),
        }
    channel_id = str(channel_id or "").strip()
    if not channel_id.isdigit():
        return {"error": "invalid_channel_id", "error_message": "channel_id must be the numeric Discord channel ID."}

    headers = {"Authorization": f"Bot {token}", "User-Agent": "scout-it (https://github.com, 1.1.0)"}
    params = {"limit": min(max(max_results, 1), 100)}
    if before_message_id:
        params["before"] = before_message_id

    last_error = None
    for attempt in range(3):
        try:
            resp = requests.get(f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
                                 headers=headers, params=params, timeout=15)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(1.0 * (attempt + 1))
            continue

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 1.0))
            time.sleep(min(retry_after, 5.0))
            continue
        if resp.status_code == 401:
            return {"error": "unauthorized", "error_message": "DISCORD_BOT_TOKEN is invalid or expired."}
        if resp.status_code == 403:
            return {"error": "forbidden", "error_message": "Bot lacks access to this channel (not in the server, or missing 'Read Message History')."}
        if resp.status_code == 404:
            return {"error": "not_found", "error_message": f"Channel {channel_id} not found."}
        if resp.status_code >= 400:
            return {"error": "api_error", "error_message": f"HTTP {resp.status_code}: {resp.text[:200]}"}

        data = resp.json()
        messages = [{
            "id": m.get("id"),
            "author": (m.get("author") or {}).get("username"),
            "content": m.get("content"),
            "timestamp": m.get("timestamp"),
            "edited_timestamp": m.get("edited_timestamp"),
            "attachments": [a.get("url") for a in m.get("attachments", [])],
            "reply_to": (m.get("referenced_message") or {}).get("id") if m.get("referenced_message") else None,
        } for m in data]
        return {"channel_id": channel_id, "message_count": len(messages), "messages": messages}

    return {"error": "network_error", "error_message": last_error or "request failed after retries"}


# =====================================================================
# Reddit — best-effort only, tier 2 (honestly unreliable as of 2026)
# =====================================================================

def reddit_search(
    query: str,
    subreddit: Optional[str] = None,
    max_results: int = 20,
    sort: str = "relevance",
) -> Dict[str, Any]:
    """Best-effort Reddit search via the old anonymous ``.json`` endpoints.

    **Read this before relying on it**: as of 2026, Reddit blocks the vast
    majority of anonymous ``.json`` requests with a 403 anti-bot response,
    and the official API closed self-service registration (manual approval
    only, rarely granted to individual scripts). There is no reliable
    zero-config path to Reddit data right now. This function tries anyway
    (some networks/IPs still get through intermittently) and — critically —
    reports the *real* failure reason on a 403 rather than returning an
    empty list that looks like "no results". If you have a logged-in
    session cookie, set REDDIT_COOKIE (the raw Cookie header value) to
    improve your odds.
    """
    from .extraction import fetch_resilient

    if subreddit:
        url = f"https://www.reddit.com/r/{subreddit}/search.json"
        params = f"?q={requests.utils.quote(query)}&restrict_sr=1&sort={sort}&limit={min(max_results, 100)}"
    else:
        url = "https://www.reddit.com/search.json"
        params = f"?q={requests.utils.quote(query)}&sort={sort}&limit={min(max_results, 100)}"

    headers = {"User-Agent": _USER_AGENT}
    cookie = os.environ.get("REDDIT_COOKIE")
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.get(url + params, headers=headers, timeout=15)
    except Exception as e:
        return {"error": "network_error", "error_message": f"{type(e).__name__}: {e}"}

    if resp.status_code == 403:
        return {
            "error": "blocked",
            "error_message": (
                "Reddit returned 403 (anonymous access blocked). This is expected as of "
                "2026 — Reddit has no reliable zero-config API path anymore. Options: "
                "(1) set REDDIT_COOKIE to a logged-in session's Cookie header for a better "
                "chance, (2) apply for official API access at "
                "https://www.reddit.com/prefs/apps (manual approval, not guaranteed), or "
                "(3) use a browser-automation tool that maintains a real logged-in session."
            ),
        }
    if resp.status_code >= 400:
        return {"error": "api_error", "error_message": f"HTTP {resp.status_code}"}

    try:
        data = resp.json()
    except ValueError:
        return {"error": "parse_error", "error_message": "Reddit did not return valid JSON (likely an interstitial/block page)."}

    children = ((data.get("data") or {}).get("children")) or []
    posts = []
    for c in children[:max_results]:
        p = c.get("data", {})
        posts.append({
            "title": p.get("title"),
            "subreddit": p.get("subreddit"),
            "author": p.get("author"),
            "score": p.get("score"),
            "num_comments": p.get("num_comments"),
            "url": p.get("url"),
            "permalink": f"https://www.reddit.com{p.get('permalink')}" if p.get("permalink") else None,
            "created_utc": p.get("created_utc"),
            "selftext": (p.get("selftext") or "")[:2000],
        })

    return {"query": query, "subreddit": subreddit, "result_count": len(posts), "posts": posts}
