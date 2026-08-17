# scout-it — Agent Memory

## Project overview
CLI multi-source search/extraction tool (`scout-it`). 28 subcommands: web/news/image/video/YouTube search, single-URL fetch, multi-engine, Wikimedia, semantic index/search, GitHub extractors (12), unified social-search, source plugins (31, plus Tavily/Exa/Firecrawl API providers via `--source`), 5-tier content extraction.

## Key architecture
- **API search sources** (`scout_it/sources/api_search_base.py`): `ApiSearchSource` base class for credential-gated API providers (Tavily, Exa, Firecrawl). Centralizes API-key check (`is_available`), per-source error isolation (`_ApiKeyError`/`_RateLimitError`/`_NetworkError`), skip-message collection (`source_messages` singleton, `SourceMessageCollector`), and `search_type` dispatch (web/news/image/multi). Each plugin implements `_raw_search` + `_normalize_result`. Plugins: `plugins/tavily.py` (`tavily-python`), `plugins/exa.py` (`exa-py`), `plugins/firecrawl.py` (`requests` POST). Missing key → skipped with clear message; error → reported; other sources continue. CLI helper `_print_source_messages()` (cli.py) drains + prints these after `augment_search_with_sources`.
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

## Image search — DeviantArt RSS integration
- `image_search_feed.py` registry: `IMAGE_SEARCH_FEEDS` dict of category → list of `{url, notes}`. Flickr tag feeds via `flickr_tag_feed(tag)`, DeviantArt tag feeds via `deviantart_feed(tag)`.
- DeviantArt RSS URL pattern: `https://backend.deviantart.com/rss.xml?q=<tag>&type=deviation`. Returns Media RSS (MRSS) with `media:content`/`media:thumbnail` tags — parsed by `image_rss.py` `parse_image_feed()`.
- `deviantart_query_feeds(query)` scans the query for keywords in `DEVIANTART_KEYWORD_MAP` (97 keywords → DeviantArt tags). Longer phrases match first (`digital art` beats `art`), tags deduplicated. Fallback: raw query becomes the tag if no keyword matches. Empty query → `[]`.
- `image.py` discovery stream 2: when `include_rss=True`, fetches Flickr tag feed + DeviantArt keyword-matched feeds in parallel (via `fetch_image_feed_entries`), then ranks together with DuckDuckGo results using `rank_candidates_initial`.
- New art categories in `IMAGE_SEARCH_FEEDS`: `digital_art`, `fantasy_art`, `anime_art`, `concept_art`, `fan_art`, `photography` (each mixes DeviantArt + Flickr feeds).
- DeviantArt backend (`backend.deviantart.com`) is CloudFront-fronted and may 403 from some server IPs (datacenter ranges). The feed URL format is valid and works from normal client IPs. The RSS transport (`tech_crunch_rss._request_with_retry`) handles 403 gracefully (returns `None`, logged as `feed_fetch_failed`).
- Tests: 13 DeviantArt tests added to `tests/test_image_video_rss_pipeline.py` (offline, mocked transport). Total image RSS pipeline tests: 33.

## API search sources (Tavily, Exa, Firecrawl)
- 3 API-backed search providers, usable via `--source tavily`, `--source exa`, `--source firecrawl` (singular flag) on web/news/image/multi-search. They run as parallel discovery streams alongside DuckDuckGo, accepting comma-separated values (e.g. `--source tavily,exa`). Credentials: `TAVILY_API_KEY`, `EXA_API_KEY`, `FIRECRAWL_API_KEY` in `~/.scout-it/credentials.json` (set via `scout-it config`).
- **CRITICAL**: these are `--source` (singular), NOT `--sources` (plural). `--sources` runs source plugins through the BM25F+vector re-ranking pipeline; `--source` is a parallel discovery stream. The API sources are excluded from `list_plugins()`/`list_available()` (the `--sources` path) but still discoverable via `get_plugin()`. Their credential metadata lives in `API_SEARCH_CREDENTIALS` (not `SOURCE_CREDENTIALS`) in `source_config.py`.
- Base class: `ApiSearchSource` in `scout_it/sources/api_search_base.py`. Subclasses implement `_raw_search(query, max_results, search_type, api_key)` and `_normalize_result()`. Base handles: credential check, error classification (`_classify_*_error`), `source_messages` skip/error collection.
- Error isolation: `_ApiKeyError` (401/403), `_RateLimitError` (429/quota), `_NetworkError` (timeout/ConnectionError) are caught per-source → returns `[]` + records error message; other sources continue.
- Missing key → `is_available()` False → plugin.search() returns `[]` + records skip message.
- **Race condition guard**: the search handlers call `_discover()` in the main thread before spawning ThreadPoolExecutor workers, because `_discover()` sets `_discovered=True` before finishing registration (not thread-safe).
- `search_type` (web/news/image/multi) flows: for `--source` API providers, CLI handler → `_run_api_source` → `get_plugin(name).search(search_type=...)`. For `--sources` plugins, CLI handler → `augment_search_with_sources(search_type=...)` → `search_all(search_type=...)` → `_search_source_async(search_type=...)` → `plugin.search(search_type=...)`.
- Module-level SDK imports (try/except ImportError → None) so tests can patch `scout_it.sources.plugins.tavily.TavilyClient` / `exa.Exa` / `firecrawl.requests`.
- `_print_source_messages()` helper in cli.py drains the collector and prints ⏭️ skip / ⚠️ error lines for `--source` API providers (called in web/image/news/multi handlers). For the `--sources` path it is now a no-op since API sources are excluded from that path.
- Deps: `tavily-python>=0.5.0`, `exa-py>=1.0.0` added to requirements.txt (Firecrawl uses `requests`).
- Tests: `tests/test_api_search_sources.py` (38 tests, offline, mocked SDK + HTTP). Full suite: 898 passed, 40 skipped.

## Version control
- All work uncommitted in working tree (no commits made). Co-author: openhands <openhands@all-hands.dev>.
- Deps installed: scout-it-2.0.0, ddgs, fake-useragent, httpx, pytest, justext, + requirements.txt.
