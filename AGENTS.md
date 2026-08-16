# scout-it — Agent Memory

## Project overview
CLI multi-source search/extraction tool (`scout-it`). 28 subcommands: web/news/image/video/YouTube search, single-URL fetch, multi-engine, Wikimedia, semantic index/search, GitHub extractors (12), unified social-search, source plugins (30+), 5-tier content extraction.

## Key architecture
- **social-search**: unified command replacing `telegram-channel`/`reddit-search`/`discord-channel`. `scout_it/social/` package: `base.py` (SocialProvider + capability constants + unified schema), `registry.py`, `telegram.py`, `reddit.py`, `discord.py`, `instagram.py`. Capability-based fallback: unsupported source arg → query search. Platforms: telegram, reddit, discord, instagram.
- **Capability constants** (base.py): `CAP_QUERY`, `CAP_CHANNEL`, `CAP_CHANNEL_ID`, `CAP_SUBREDDIT`, `CAP_PROFILE`, `CAP_USER`.
- **fetch_resilient** (`scout_it/extraction/fetcher.py`): `(url, session=None, timeout=25, max_retries=3, enable_js_fallback=...)`. Success dict has `html`, `final_url`, `status`, `tier`, `attempts`, `errors`. NO `headers` param (manages own UA rotation). Does NOT include `status_code` in success.
- **cleaner.py**: use `advanced_clean_text(text, url)` for HTML→text cleaning. No `clean_content` function exists. `process_results(results)` for batch.
- RSS parsing pattern lives in `scout_it/google_news_source.py` (`_parse_rss_items`, `_parse_rss_date`).

## Reddit provider (RSS-first, post-enhancement)
- Primary path: public `.rss` Atom feeds (`r/{sub}.rss`, `user/{name}.rss`, `search.rss?q=`). `.json` is secondary fallback (often 403 in 2026).
- Reddit RSS = Atom feed: `<entry>` with `<author><name>` (e.g. `/u/name`), `<content type="html">`, `<link href>`, `<published>`, `<title>`, `<id>`.
- Capabilities: `query`, `subreddit`, `user`. Subreddit/user listings do NOT require a query (the feed IS the listing). Combined subreddits via `+`.
- Reddit aggressively rate-limits (429) on repeated hits from same IP during testing — space out requests.
- `_fetch_feed` returns `{xml, status, status_code, errors}`. If RSS yields 0 posts (blocked/parse-fail), falls back to `_reddit_json_search`.

## Discord provider (enhanced, post-TASK-004)
- Capabilities: `channel-id` (bot API) + `query` (DDGS + bot guild search). `FALLBACK_CAPABILITY = CAP_QUERY` (was None).
- No-token path: DDGS web search (`site:discord.com <q>` + `discord <q>`), dedup by URL, rank by relevance. Finds public Discord servers/invites/message pages indexed by DuckDuckGo.
- Token path: `discord_bot_search()` lists guilds (`/users/@me/guilds`) → channels (`/guilds/{id}/channels`, type 0) → messages (`/channels/{id}/messages`), filters by query substring. Merged with DDGS results.
- `discord_channel_messages()` paginates via `before=<last_id>` when max > 100. Richer metadata (embeds, reactions, guild/channel names).
- `_api_get()` shared helper handles 429 (Retry-After), 401/403/404, retries.
- DDGS usage pattern: `from ddgs import DDGS; with DDGS() as ddgs: list(ddgs.text(keywords=q, max_results=n))` — try multiple call shapes (keywords= positional).
- Note surfaced to user when no token: "DISCORD_BOT_TOKEN is not set — results are from public web search only. Set it for full message search."
- No self-bot/user-token usage (TOS violation) — all reference repos that used selfbots (southbridge-fur, dfrnoch, theAbdoSabbagh, KanekiWeb) were noted but NOT used; only bot-token approach (ArvinJA) + DDGS adopted.

## Instagram provider (post-TASK-005)
- Capabilities: `profile` + `query`. `FALLBACK_CAPABILITY = CAP_QUERY`.
- No-login query path: DDGS web search (`site:instagram.com <q>` + `instagram <q>`), dedup by URL, rank by relevance (whole-phrase title/body bonus). DuckDuckGo indexes public IG profiles/posts/hashtags.
- Profile path: 3-tier fallback — (1) requests with browser-like headers + optional `INSTAGRAM_SESSION_ID` cookie, extract JSON-LD `<script>` blocks; (2) Playwright headless render if requests hits login wall/302; (3) DDGS fallback (`site:instagram.com {username}`).
- Optional `INSTAGRAM_SESSION_ID` (via `scout-it config`): session cookie for more reliable profile access. Note surfaced when not set.
- Proxy support: `INSTAGRAM_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` (HTTP + SOCKS5).
- `--extract-full` support: best-effort full-page extraction of DDGS-discovered IG URLs.
- References (approach only, not code): drawrowfly/instagram-scraper (session+proxy), instaloader (Profile/Post/GraphQL structure), data-scrape/instagram-account-scraper (no-login public scraping).
- Tests: `tests/test_social_search.py` Instagram section (22 tests) — DDGS ranking, dedup, profile tiered fallback, proxy, session cookie, capability dispatch, registry integration.

## Testing
- `python -m pytest -q` — all tests (854 pass, 26 skip; 7 Playwright sync-API infra failures in browser_pool tests, previously skipped before playwright installed — unrelated to Instagram). ~110s.
- Social tests: `tests/test_social_search.py` (175 tests) + `tests/test_new_sources.py`.
- Tests mock `requests.get` and `requests.utils.quote` for the `.json` path; mock `_fetch_feed` for the RSS path.
- `_FakeResp(status_code, json_data, headers, text)` test helper in test_social_search.py.
- ElementTree: use `elem is not None` not truthiness (deprecated). Handle namespaced tags via `c.tag.split("}")[-1]`.
- Playwright note: installing `playwright` exposes browser_pool tests that were previously `importorskip`-skipped. Tests that mock `requests.get` but not `fetch_resilient` (TestRawHtml, TestJsonOutputValidity) must also patch `scout_it.commands.url._playwright_available` to `False` to avoid launching a real browser.

## Version control
- All work uncommitted in working tree (no commits made). Co-author: openhands <openhands@all-hands.dev>.
- Deps installed: scout-it-2.0.0, ddgs, fake-useragent, httpx, pytest, justext, + requirements.txt.
