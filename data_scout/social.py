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
    """
    from .extraction import fetch_resilient  # local import avoids a cycle at module load

    channel = str(channel or "").strip().lstrip("@")
    channel = channel.split("t.me/")[-1].split("t.me/s/")[-1].strip("/")
    if not channel:
        return {"error": "invalid_channel", "error_message": "Provide a channel username, e.g. 'durov' or 't.me/durov'."}

    url = f"https://t.me/s/{channel}"
    outcome = fetch_resilient(url, timeout=15, max_retries=max_fetch_retries)
    if outcome["status"] != "success":
        return {
            "error": "fetch_failed",
            "error_message": f"Could not load {url}: " + "; ".join(outcome["errors"][-3:]),
        }

    soup = BeautifulSoup(outcome["html"], "html.parser")

    if soup.select_one(".tgme_page_context_link") is None and "tgme_channel_info" not in outcome["html"]:
        # Heuristic: the public preview page has a distinct wrapper class;
        # its total absence usually means the channel is private/nonexistent.
        pass  # not fatal on its own — fall through and report 0 posts if genuinely empty

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
        "channel": channel,
        "title": channel_title_el.get_text(strip=True) if channel_title_el else None,
        "description": channel_desc_el.get_text(strip=True) if channel_desc_el else None,
        "post_count_returned": len(posts),
        "posts": list(reversed(posts)),  # newest first
    }


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

    headers = {"Authorization": f"Bot {token}", "User-Agent": "data-scout (https://github.com, 1.1.0)"}
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
