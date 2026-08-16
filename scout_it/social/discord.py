"""
📡 DISCORD PROVIDER — bot REST API (with token) + DDGS web discovery (no token).

Discord has no anonymous/public read API by design, so the provider uses a
tiered strategy to maximize results across both the authenticated and
anonymous cases:

  1. ``--channel-id`` + token  -> real Bot REST API: fetch channel message
     history with pagination (multiple pages when ``--max`` > 100) and richer
     metadata (embeds, reactions, replies, attachments). Tier 1, reliable.

  2. ``--query`` + token        -> bot guild message search: list every guild
     the bot is a member of, enumerate text channels, fetch recent messages,
     and filter by the query (substring on content). This is the "search
     across the bot's accessible servers" path — real Discord messages without
     the closed search API. Combined with DDGS discovery (step 3) so channels
     the bot is NOT in are still surfaced via the public web.

  3. ``--query`` (no token)     -> DDGS web search for public Discord content
     (``site:discord.com <query>`` + ``discord <query>``). DuckDuckGo indexes
     public Discord message pages, server invites, and channel pages, so this
     yields related snippets/titles/links even without credentials. Limited but
     real "related results" — and a clear note tells the user to set
     ``DISCORD_BOT_TOKEN`` for full message search.

Flow mirrors the web/news-search workflow: parallel snippet extraction
(titles/content/links) -> rank by query relevance -> cap at ``--max`` ->
optionally extract top result pages and clean them.

References (approach, not code):
  - ArvinJA/scrape_discord — bot-token guild+channel enumeration (the legit path).
  - KanekiWeb/Messages-Searcher — search a message across all channels in a guild.
  - discord/discord-api-spec — REST endpoints (/users/@me/guilds, /guilds/{id}/channels,
    /channels/{id}/messages).

Capabilities: ``channel-id`` (bot API) and ``query`` (DDGS + bot guild search).
The ``query`` capability is the public fallback, so this provider now falls
back to query search when an unsupported source arg is requested (e.g.
``--channel``), instead of hard-failing.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests

from .. import __version__ as _VERSION
from .base import (
    CAP_CHANNEL_ID,
    CAP_QUERY,
    SocialProvider,
    normalize_item,
    provider_result,
)

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"

# How many text channels to scan per guild when doing a bot guild search, and
# the per-channel message fetch size. Capped to stay within rate limits.
_GUILD_CHANNEL_SCAN_LIMIT = 25
_CHANNEL_MESSAGE_FETCH = 100


def _bot_headers() -> Dict[str, str]:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    return {"Authorization": f"Bot {token}",
            "User-Agent": f"scout-it/{_VERSION} (https://github.com)"}


def _has_token() -> bool:
    return bool(os.environ.get("DISCORD_BOT_TOKEN"))


def _api_get(url: str, params: Optional[Dict[str, Any]] = None,
             max_retries: int = 3) -> Dict[str, Any]:
    """Discord REST GET with rate-limit (429) + retry handling.

    Returns ``{ok, data, status_code, error}``."""
    headers = _bot_headers() if _has_token() else {}
    for attempt in range(max(1, max_retries)):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
        except Exception as e:
            if attempt + 1 >= max_retries:
                return {"ok": False, "data": None, "status_code": None,
                        "error": f"{type(e).__name__}: {e}"}
            time.sleep(0.5 * (attempt + 1))
            continue

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 1.0))
            time.sleep(min(retry_after, 5.0))
            continue
        if resp.status_code == 401:
            return {"ok": False, "data": None, "status_code": 401,
                    "error": "DISCORD_BOT_TOKEN is invalid or expired."}
        if resp.status_code == 403:
            return {"ok": False, "data": None, "status_code": 403,
                    "error": "Bot lacks access (not in the server, or missing permissions)."}
        if resp.status_code == 404:
            return {"ok": False, "data": None, "status_code": 404,
                    "error": "Not found."}
        if resp.status_code >= 400:
            return {"ok": False, "data": None, "status_code": resp.status_code,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        try:
            return {"ok": True, "data": resp.json(), "status_code": 200, "error": None}
        except ValueError:
            return {"ok": False, "data": None, "status_code": resp.status_code,
                    "error": "Discord did not return valid JSON."}
    return {"ok": False, "data": None, "status_code": None,
            "error": "request failed after retries (rate-limited)"}


def _normalize_message(m: Dict[str, Any], channel_id: Optional[str] = None,
                      guild_id: Optional[str] = None,
                      guild_name: Optional[str] = None,
                      channel_name: Optional[str] = None) -> Dict[str, Any]:
    """Normalize a raw Discord message dict into the provider's post schema."""
    author = (m.get("author") or {}).get("username")
    content = m.get("content") or ""
    embeds = m.get("embeds") or []
    if embeds and not content:
        # Use embed title+description as content when the message has no text.
        parts = []
        for e in embeds:
            if e.get("title"):
                parts.append(e["title"])
            if e.get("description"):
                parts.append(e["description"])
        content = "\n".join(parts)
    reactions = m.get("reactions") or []
    return {
        "id": m.get("id"),
        "author": author,
        "content": content,
        "timestamp": m.get("timestamp"),
        "edited_timestamp": m.get("edited_timestamp"),
        "attachments": [a.get("url") for a in (m.get("attachments") or [])],
        "embeds": embeds,
        "reactions": [{"emoji": (r.get("emoji") or {}).get("name"),
                       "count": r.get("count")} for r in reactions],
        "reply_to": (m.get("referenced_message") or {}).get("id") if m.get("referenced_message") else None,
        "channel_id": channel_id or m.get("channel_id"),
        "guild_id": guild_id,
        "guild_name": guild_name,
        "channel_name": channel_name,
    }


def discord_channel_messages(
    channel_id: str,
    max_results: int = 50,
    before_message_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch recent messages from a Discord text channel using the real
    Discord Bot REST API. Requires ``DISCORD_BOT_TOKEN``; the bot must already
    be a member of the server that channel belongs to, with the "Read Message
    History" permission.

    Paginates automatically: when ``max_results`` exceeds 100 (the per-request
    cap), older pages are fetched via the ``before=<last_id>`` cursor until
    ``max_results`` is reached or the channel runs out of messages.
    """
    if not _has_token():
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
        return {"error": "invalid_channel_id",
                "error_message": "channel_id must be the numeric Discord channel ID."}

    # Resolve guild/channel metadata for richer results (best-effort, non-fatal).
    guild_id = guild_name = channel_name = None
    chan = _api_get(f"{DISCORD_API_BASE}/channels/{channel_id}")
    if chan["ok"] and isinstance(chan["data"], dict):
        channel_name = chan["data"].get("name")
        guild_id = chan["data"].get("guild_id")
        if guild_id:
            g = _api_get(f"{DISCORD_API_BASE}/guilds/{guild_id}")
            if g["ok"] and isinstance(g["data"], dict):
                guild_name = g["data"].get("name")

    all_messages: List[Dict[str, Any]] = []
    before = before_message_id
    remaining = max_results

    while remaining > 0:
        params = {"limit": min(max(remaining, 1), 100)}
        if before:
            params["before"] = before
        out = _api_get(f"{DISCORD_API_BASE}/channels/{channel_id}/messages", params=params)
        if not out["ok"]:
            if out["status_code"] == 401:
                return {"error": "unauthorized", "error_message": out["error"]}
            if out["status_code"] == 403:
                return {"error": "forbidden", "error_message": out["error"]}
            if out["status_code"] == 404:
                return {"error": "not_found", "error_message": out["error"]}
            return {"error": "api_error", "error_message": out["error"]}

        data = out["data"] or []
        if not data:
            break
        for m in data:
            all_messages.append(_normalize_message(m, channel_id, guild_id, guild_name, channel_name))
        if len(data) < 100:
            break  # exhausted channel history
        before = data[-1].get("id")
        remaining = max_results - len(all_messages)
        time.sleep(0.3)  # be gentle with rate limits across pages

    return {"channel_id": channel_id, "message_count": len(all_messages),
            "messages": all_messages[:max_results]}


# =====================================================================
# Bot guild message search (query capability, token required)
# =====================================================================

def _bot_list_guilds() -> List[Dict[str, Any]]:
    """List the guilds the bot is a member of."""
    out = _api_get(f"{DISCORD_API_BASE}/users/@me/guilds",
                   params={"limit": 200})
    if not out["ok"] or not isinstance(out["data"], list):
        return []
    return out["data"]


def _bot_list_channels(guild_id: str) -> List[Dict[str, Any]]:
    """List channels in a guild, returning only text channels (type 0)."""
    out = _api_get(f"{DISCORD_API_BASE}/guilds/{guild_id}/channels")
    if not out["ok"] or not isinstance(out["data"], list):
        return []
    return [c for c in out["data"] if c.get("type") == 0]


def discord_bot_search(
    query: str,
    max_results: int = 20,
) -> Dict[str, Any]:
    """Search for ``query`` across every guild the bot is a member of.

    Enumerates guilds -> text channels -> recent messages, filtering by a
    case-insensitive substring match of the query in message content (and
    embed title/description). This is the no-search-API "scan accessible
    servers" path, ported from ArvinJA/scrape_discord +
    KanekiWeb/Messages-Searcher patterns. Rate-limit aware.
    """
    if not _has_token():
        return {"error": "auth_required",
                "error_message": "DISCORD_BOT_TOKEN not set."}
    q = (query or "").lower().strip()
    if not q:
        return {"error": "no_input",
                "error_message": "A --query is required for Discord bot search."}

    guilds = _bot_list_guilds()
    matches: List[Dict[str, Any]] = []
    terms = [t for t in re.split(r"\s+", q) if len(t) > 1] or [q]

    for g in guilds:
        if len(matches) >= max_results:
            break
        guild_id = g.get("id")
        guild_name = g.get("name")
        channels = _bot_list_channels(guild_id)[:_GUILD_CHANNEL_SCAN_LIMIT]
        for c in channels:
            if len(matches) >= max_results:
                break
            channel_id = c.get("id")
            channel_name = c.get("name")
            out = _api_get(f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
                           params={"limit": _CHANNEL_MESSAGE_FETCH})
            if not out["ok"] or not isinstance(out["data"], list):
                continue
            for m in out["data"]:
                norm = _normalize_message(m, channel_id, guild_id, guild_name, channel_name)
                text = (norm["content"] or "").lower()
                if not text:
                    continue
                if q in text or any(t in text for t in terms):
                    matches.append(norm)
                    if len(matches) >= max_results:
                        break
            time.sleep(0.2)

    return {"query": query, "result_count": len(matches),
            "messages": matches, "guilds_scanned": len(guilds)}


# =====================================================================
# DDGS web discovery (query capability, NO token required)
# =====================================================================

def _ddgs_text(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Run a DDGS text search, tolerant of the installed ddgs API shape."""
    try:
        from ddgs import DDGS
    except Exception:
        try:
            from duckduckgo_search import DDGS
        except Exception:
            return []
    results: List[Dict[str, Any]] = []
    try:
        with DDGS(timeout=20) as ddgs:
            method = getattr(ddgs, "text", None)
            if not callable(method):
                return []
            call_patterns = [
                lambda: list(method(keywords=query, max_results=max_results)),
                lambda: list(method(query, max_results=max_results)),
                lambda: list(method(query))[:max_results],
            ]
            for call in call_patterns:
                try:
                    results = call()
                    break
                except TypeError:
                    continue
    except Exception as e:
        logger.debug("DDGS discord search failed: %s", e)
        return []
    return results or []


def discord_ddgs_search(
    query: str,
    max_results: int = 20,
) -> Dict[str, Any]:
    """No-token discovery: search the public web for Discord content related
    to ``query`` via DuckDuckGo. DuckDuckGo indexes public Discord message
    pages, server invites, and channel pages, so this yields related
    snippets/titles/links even without credentials.

    Searches both ``site:discord.com <query>`` (precise) and ``discord <query>``
    (broader), deduplicates by URL, and ranks by query relevance — mirroring
    the web/news-search snippet-extraction step.
    """
    q = (query or "").strip()
    if not q:
        return {"error": "no_input",
                "error_message": "A --query is required for Discord web search."}

    precise = _ddgs_text(f"site:discord.com {q}", max_results * 2)
    broad = _ddgs_text(f"discord {q}", max_results)
    seen: set = set()
    merged: List[Dict[str, Any]] = []
    for r in precise + broad:
        url = r.get("href") or r.get("url") or r.get("link") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        merged.append({
            "title": r.get("title") or "",
            "content": r.get("body") or r.get("snippet") or r.get("content") or "",
            "url": url,
            "source": "ddgs",
        })
    ranked = _rank_discord_results(merged, q, max_results)
    return {"query": query, "result_count": len(ranked), "results": ranked,
            "source": "ddgs_web"}


def _rank_discord_results(items: List[Dict[str, Any]], query: str,
                          max_results: int) -> List[Dict[str, Any]]:
    """Rank Discord results (messages or web snippets) by query relevance:
    title match > content match, whole-phrase bonus. Caps at ``max_results``."""
    if not items:
        return items
    q = (query or "").lower().strip()
    terms = [t for t in re.split(r"\s+", q) if len(t) > 1] if q else []

    def _score(it: Dict[str, Any]) -> float:
        title = (it.get("title") or it.get("content") or "").lower()
        body = (it.get("content") or "").lower()
        if not terms:
            return 0.0
        score = 0.0
        for t in terms:
            if t in title:
                score += 3.0
            if t in body:
                score += 1.0
        if q and q in body:
            score += 5.0
        return score

    ranked = sorted(items, key=lambda it: -_score(it))
    return ranked[:max_results]


def _enrich_discord_with_full_content(items: List[Dict[str, Any]],
                                       max_results: int) -> List[Dict[str, Any]]:
    """Best-effort full-page extraction for DDGS-discovered Discord URLs (the
    "extract full page content and clean" step). Only for web-discovery
    results; bot-API messages already have full content."""
    try:
        from ..extraction import fetch_resilient
        from ..cleaner import advanced_clean_text
    except Exception:
        return items
    for it in items[:max_results]:
        url = it.get("url")
        if not url or "discord.com" not in url:
            continue
        try:
            outcome = fetch_resilient(url, timeout=15, max_retries=1)
            if outcome.get("status") == "success" and outcome.get("html"):
                cleaned = advanced_clean_text(outcome["html"], url)
                if cleaned:
                    it["full_content"] = cleaned[:5000]
        except Exception:
            continue
    return items


# =====================================================================
# Provider (capability-aware wrapper)
# =====================================================================

class DiscordProvider(SocialProvider):
    platform = "discord"
    # channel-id = bot API message history; query = DDGS web discovery (+ bot
    # guild search when a token is present).
    SUPPORTED_CAPABILITIES = {CAP_CHANNEL_ID, CAP_QUERY}
    # DDGS gives a public discovery path, so we now fall back to query search
    # when an unsupported source arg (e.g. --channel) is requested.
    FALLBACK_CAPABILITY = CAP_QUERY

    def _execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        max_results = params.get("max_results", 50)
        extract_full = params.get("extract_full", False)

        if capability == CAP_CHANNEL_ID:
            return self._exec_channel_id(params, max_results)
        return self._exec_query(params, max_results, extract_full)

    # -- channel-id (bot API) ------------------------------------------------
    def _exec_channel_id(self, params: Dict[str, Any], max_results: int) -> Dict[str, Any]:
        channel_id = params.get("channel_id")
        if not channel_id:
            return provider_result(self.platform, error="no_input",
                                   error_message="Discord --channel-id is required for this mode.",
                                   capabilities_used=[CAP_CHANNEL_ID])
        raw = discord_channel_messages(
            channel_id, max_results=max_results,
            before_message_id=params.get("before"),
        )
        if "error" in raw:
            return provider_result(self.platform, error=raw["error"],
                                   error_message=raw["error_message"],
                                   capabilities_used=[CAP_CHANNEL_ID], raw=raw)
        items: List[Dict[str, Any]] = [normalize_item(
            self.platform,
            author=m.get("author"),
            content=m.get("content"),
            url=None,
            timestamp=m.get("timestamp"),
            metadata={
                "channel_id": m.get("channel_id"),
                "channel_name": m.get("channel_name"),
                "guild_id": m.get("guild_id"),
                "guild_name": m.get("guild_name"),
                "message_id": m.get("id"),
                "edited_timestamp": m.get("edited_timestamp"),
                "attachments": m.get("attachments"),
                "embeds": m.get("embeds"),
                "reactions": m.get("reactions"),
                "reply_to": m.get("reply_to"),
            },
        ) for m in raw.get("messages", [])]
        return provider_result(self.platform, results=items,
                               capabilities_used=[CAP_CHANNEL_ID], raw=raw,
                               note=f"channel {raw.get('channel_id')}")

    # -- query (DDGS web + optional bot guild search) ------------------------
    def _exec_query(self, params: Dict[str, Any], max_results: int,
                    extract_full: bool) -> Dict[str, Any]:
        query = (params.get("query") or "").strip()
        if not query:
            return provider_result(self.platform, error="no_input",
                                   error_message="Discord query search requires a --query.",
                                   capabilities_used=[CAP_QUERY])

        token = _has_token()
        items: List[Dict[str, Any]] = []
        raw: Dict[str, Any] = {"query": query}
        note_parts: List[str] = []
        sources_used: List[str] = []

        # 1. Bot guild message search (token only) — real Discord messages.
        if token:
            bot_res = discord_bot_search(query, max_results=max_results)
            raw["bot_search"] = bot_res
            if "error" not in bot_res:
                sources_used.append("bot_guild_search")
                for m in bot_res.get("messages", []):
                    items.append({
                        "title": "",
                        "content": m.get("content") or "",
                        "author": m.get("author"),
                        "url": None,
                        "timestamp": m.get("timestamp"),
                        "metadata": {
                            "channel_id": m.get("channel_id"),
                            "channel_name": m.get("channel_name"),
                            "guild_id": m.get("guild_id"),
                            "guild_name": m.get("guild_name"),
                            "message_id": m.get("id"),
                            "reactions": m.get("reactions"),
                            "attachments": m.get("attachments"),
                            "source": "bot_guild_search",
                        },
                    })
                note_parts.append(f"scanned {bot_res.get('guilds_scanned', 0)} guild(s) the bot is in.")
            elif bot_res.get("error") == "auth_required":
                note_parts.append("DISCORD_BOT_TOKEN is set but invalid.")
        else:
            note_parts.append(
                "DISCORD_BOT_TOKEN is not set — results are from public web search of "
                "Discord content only. Set DISCORD_BOT_TOKEN (via `scout-it config`) for "
                "full message search across the servers your bot can see."
            )

        # 2. DDGS web discovery (always — finds public Discord content the bot
        # can't reach, and is the only path when no token is set).
        ddgs_res = discord_ddgs_search(query, max_results=max_results)
        raw["ddgs_search"] = ddgs_res
        if "error" not in ddgs_res:
            sources_used.append("ddgs_web")
            for r in ddgs_res.get("results", []):
                items.append({
                    "title": r.get("title") or "",
                    "content": r.get("content") or "",
                    "author": None,
                    "url": r.get("url"),
                    "timestamp": None,
                    "metadata": {"source": "ddgs_web"},
                })

        # 3. Rank + cap (title > content, whole-phrase bonus).
        items = _rank_discord_results(items, query, max_results)

        # 4. Optional full-content extraction for DDGS-discovered URLs.
        if extract_full and items:
            _enrich_discord_with_full_content(items, max_results)

        normalized: List[Dict[str, Any]] = [normalize_item(
            self.platform,
            author=it.get("author"),
            content=(it.get("title") + "\n\n" + it.get("content")).strip()
                if it.get("title") else it.get("content"),
            url=it.get("url"),
            timestamp=it.get("timestamp"),
            metadata=it.get("metadata") or {},
        ) for it in items]

        raw["sources_used"] = sources_used
        note = " ".join(note_parts) if note_parts else None
        return provider_result(self.platform, query=query, results=normalized,
                               capabilities_used=[CAP_QUERY], raw=raw, note=note)
