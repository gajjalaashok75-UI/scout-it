# GAKRCLI.md

This file provides guidance to GakrCLI Code (gakrcli.ai/code) when working with code in this repository.

## Project

**scout-it v2.0.0** — a Python package and CLI (`scout-it`) for enterprise-grade web search, content extraction, GitHub data extraction, and social platform scraping. Python >= 3.9, MIT license. Entry point is `scout_it/cli.py` (argparse, 28 subcommands); public API is re-exported from `scout_it/__init__.py`.

This file replaces the old `AGENTS.md` (which has been deleted). It is the authoritative agent guide; it intentionally does not repeat the README.

### Latest Features (August 2026)

- **Unified extraction engine**: web-search and news-search now use identical `EnterpriseSearchEngine` with all resilience features
- **Browser pool optimization**: 3-5x faster extraction by reusing browser instances across URLs (3-8s → 0.5s per page)
- **Staged ranking**: Discovery-first pipeline (collect → rank → extract top N) for 70-85% faster news searches
- **Web search RSS feeds**: 65 RSS feeds across 13 categories (ai, engineering, cloud, devops, security, etc.)
- **Expanded news RSS**: 50+ sources across all news categories (cloud: 6, ai: 8, startups: 6, security: 6, all: 9)
- **Snippets mode**: `--snippets` flag returns ranked snippets only (~10x faster than full extraction)
- **Category support**: `--category` flag for web-search and news-search with RSS feed integration
- **Quality escalation**: Auto-retries with Playwright when requests tier yields low-quality extraction
- **Domain learning**: Per-domain strategy memory with Thompson sampling for optimal tier selection

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Optional runtime extras
pip install scout-it[js-render]      # Playwright fallback tier
pip install scout-it[tls-impersonate]  # curl_cffi TLS tier
playwright install chromium           # needed for --js-render

# Run the test suite — ONE FILE AT A TIME (see Testing section)
pytest tests/test_cli.py -v --tb=short
# Single test:
pytest tests/test_cli.py::test_web_search -v

# Build (this is all CI does)
python -m build

# Real CLI smoke tests (preferred over pytest for behavior — see Testing)
scout-it doctor
scout-it web-search --query "rust vs go" -m 5 --out smoke.json
scout-it fetch-url --url "https://example.com" --out smoke.json
```

## Architecture

### Core pipeline

```
CLI (scout_it/cli.py) → search engine → fetch_resilient() → ExtractionEngine → process_results() → output.py
```

1. **Search** — DuckDuckGo via the `ddgs` package (`scout_it/extraction.py`). `multi-search --engines` adds Brave/Bing/Google CSE/SerpAPI through the pluggable registry in `scout_it/engines.py` (tier-1 engines need API keys and are silently skipped when unconfigured).
2. **Fetch** — `fetch_resilient()` (`scout_it/extraction.py`) is the single fetch entry point used by every command. It runs a multi-tier chain (see below) and is the central integration point for the resilience modules.
3. **Extract** — `ExtractionEngine` (`scout_it/extraction.py`) runs a cascade: trafilatura → justext → boilerpy3 → readability → heuristic DOM scoring (`scout_it/heuristic_extract.py`). `scout_it/selector_cache.py` remembers a working CSS selector per domain and tries it first.
4. **Clean** — `process_results()` / `ContentCleaner` (`scout_it/cleaner.py`) structures results: confidence, quality, sentiment, `extraction_method`, `publish_date`. Result dicts are built here — when adding fields, trace the key name through every pipeline stage (search source → fetch → clean → output) or you get silent 0-result/empty-field bugs.
5. **Output** — `scout_it/output.py`. All CLI output routes to `.scout-it/` (bare `--out filenames.json` land there too). Long string values are chunked into ≤500-char arrays for line-length-safe JSON (`_NO_CHUNK_KEYS` excludes URLs/patches/raw_html). `--markdown` conflicts with an explicit `--out *.json`.

### Unified Extraction Engine (NEW)

Both `web-search` and `news-search` now use the identical `EnterpriseSearchEngine` from `extraction.py`:
- Eliminated 300 lines of duplicate code
- News-search gains 5 advanced features: alternate source, DNS fallback, TLS impersonation, persistent profile, bandit
- Google News /articles/ handling: automatically detects SPA URLs and forces Playwright rendering
- Error page detection: prevents returning 404 page text

### Browser Pool Optimization (NEW)

**3-5x faster extraction** via browser reuse:
- Launches browser ONCE at start (not per-URL)
- Reuses context across all URLs via `browser_pool.get_page()`
- Reduces overhead from 3-8s to 0.5s per page
- Quality escalation: auto-retries with Playwright for low-quality extractions (< 30 chars)

### Staged Ranking (NEW)

Discovery-first pipeline for **70-85% faster** searches:
1. **Collection** (< 3s): Each provider returns max 10 candidates (~40 total)
2. **Initial ranking** (< 1s): Fast metadata-only scoring
3. **Content extraction** (< 5s): Extract top 15 candidates only (not all 40)
4. **Final ranking** (< 1s): Re-rank with full content

Result: 10s total vs 30-60s before (92.5% fewer extractions)

### Snippets Mode (NEW)

`--snippets` flag returns ranked snippets only (~10x faster):
- Skips content extraction phase entirely
- Returns: rank, title, summary, url, source, score
- Default: 30 snippets in snippets mode, 10 full extractions in normal mode
- Use cases: quick browsing, candidate discovery

### Resilience fetch chain (`fetch_resilient`)

Tiered fallback: plain requests → TLS impersonation (`tls_fingerprint.py`, optional curl_cffi) → Playwright JS render (`browser_profile.py`) → strategy-bandit choice based on per-domain history → alternate sources (AMP/mobile/print/Wayback via `alternate_source.py`). The following modules feed into this chain and are read together with `extraction.py`:

- `strategy_cache.py` + `strategy_bandit.py` — persistent per-domain fetch-strategy memory (SQLite at `~/.scout-it/strategy_cache.db`) and Thompson-sampling arm selection
- `response_cache.py` — disk cache under `.scout-it/cache/` with stale-if-error
- `retry_classifier.py` — transient vs permanent failure classification
- `proxy_pool.py` — rotation via `PROXY_LIST` env var, never hard-fails unconfigured
- `dns_resilience.py` — DNS-over-HTTPS fallback
- `canary_probe.py` — cheap pre-fetch block-page check
- `politeness_governor.py` — per-domain concurrency caps + robots.txt
- `header_profiles.py` — internally-consistent browser header bundles

### News / dedicated sources

- `news-search` supports `--source google-news` (`google_news_source.py`, runs in parallel with the DDGS chain) and `--location <city>` which adds Times of India RSS (`toi_rss_source.py`, `LOCATION_FEEDS`). Behavior is simply additive — DDG + Google News + ToI all present; no priority rules. Location lookup is case-insensitive; feeds are newest-first and `publish_date` is preserved through the whole pipeline.
- `web-search` supports `--source wikimedia` (singular override) and `multi-search` supports `--source wikimedia` (shorthand for `--engines wikimedia`); there is also a dedicated `wikipedia-search` command (`wikimedia_source.py`, `SITE_MAP` has per-project site entries for all 12 Wikimedia projects).
- **Source plugins**: `--sources openalex,arxiv,...` (plural) on `web-search`, `news-search`, `image-search`, `video-search`, and `multi-search` merges 30+ free academic/dataset/knowledge source plugins (`scout_it/sources/`) with BM25F+vector re-ranking. `--auto-sources` lets the source-selection bandit pick. Run `scout-it sources` to list them; `scout-it stats --sources` shows bandit stats.
- **Semantic retrieval**: `scout-it index` builds a persistent LanceDB corpus at `~/.scout-it/semantic/lancedb/` (`scout_it.semantic.SemanticIndex`); `scout-it semantic-search` queries it with hybrid BM25+dense-vector retrieval. Needs `sentence-transformers torch lancedb`. `--semantic` on `web-search`/`news-search` re-ranks in-place.
- **Category support (NEW)**: Both `web-search` and `news-search` now support `--category` flag for RSS feed integration:
  - **Web search**: 65 RSS feeds across 13 categories (ai, engineering, cloud, devops, research, security, startups, all, etc.)
  - **News search**: 50+ RSS sources across categories (cloud: 6 feeds, ai: 8 feeds, startups: 6 feeds, security: 6 feeds, all: 9 feeds)
  - Categories run as parallel streams with DuckDuckGo, merging results before ranking
  - Example: `--category ai cloud` combines feeds from both categories

### GitHub and social

- `scout_it/github_extract.py` — 12 extractors (repos, commits, single commit+diff, PRs, PR+diff, issues, issue+comments, files, folders, code/repo search, discussions). Repo-wide commands take an optional GitHub URL or `owner/repo`. Rate-limit-sensitive; `github-discussions` and `github-search-code` require a token.
- `scout_it/social/` — unified `social-search` package: `base.py` (SocialProvider base + unified result schema), `registry.py` (provider registry, capability-based dispatch), `telegram.py` (query, channel — public `t.me/s/`), `reddit.py` (RSS-first: query, subreddit, user — public `.rss` feeds with `.json` fallback; optional `REDDIT_COOKIE`), `discord.py` (channel-id + query — bot REST API for message history with pagination when `DISCORD_BOT_TOKEN` set; DDGS web discovery of public Discord content for `--query` with no token, bot guild search across accessible servers with token), `instagram.py` (profile + query — DDGS web search for public Instagram content with no login; 3-tier profile scraping: requests → Playwright → DDGS fallback; optional `INSTAGRAM_SESSION_ID` for reliable profile access; proxy support via `INSTAGRAM_PROXY`/`HTTPS_PROXY`). Each provider declares `SUPPORTED_CAPABILITIES`; unsupported source args fall back to query search. Replaced the former `telegram-channel`, `discord-channel`, and `reddit-search` subcommands.

### Credentials and state

- `scout_it/config.py` — `scout-it config` runs a wizard persisting keys to `~/.scout-it/credentials.json` (0600 on POSIX). `load_stored_credentials_into_env()` runs once at CLI startup; a real env var always wins over the stored file. Known keys are in `KNOWN_CREDENTIALS`.
- Playwright pages use a persistent browser profile (`browser_profile.py`); anti-bot sites that return HTTP 401 are paywalled at the source and unrecoverable without credentials.

## Testing

- ~790 tests across 40 files. **Run test files one at a time** (`pytest tests/test_resilience.py -v`), not the whole suite at once — the suite has cross-file state assumptions.
- **Prefer real CLI runs over pytest for verifying behavior.** `real-tests.md` documents a large matrix of real `scout-it ... --out ...` invocations (with logging to `terminal-logs.md`). For parallel CLI runs use unique `--out` filenames to avoid output collisions.
- CI (`.github/workflows/ci.yml`) runs **build-only** (matrix 3.9–3.12) plus the website build; it does not run tests. Tests run locally. Release workflow tags `v*.*.*` build Python distributions and create a GitHub Release — no PyPI publishing.
- After porting reference code or touching a shared function, verify the full end-to-end CLI pipeline and audit every call site (not just the function in isolation).

### Key Test Files (NEW)

- **`test_browser_pool.py`**: Browser pool reuse, thread-local instances, cleanup
- **`test_browser_pool_integration.py`**: End-to-end browser pool integration
- **`test_domain_routing.py`**: Domain learning, strategy persistence, banned domains
- **`test_source_resolvers.py`**: MSN/Yahoo/AOL wrapper resolution
- **`test_staged_ranking.py`**: Two-stage ranking, metadata scoring, content re-ranking
- **`test_extraction_quality.py`**: Quality scoring, Playwright escalation
- **`test_extraction_concurrency.py`**: Thread safety, concurrent extraction
- **`test_complete_workflow.py`**: Full search → fetch → extract → clean → output
- **`test_expanded_rss_feeds.py`**: RSS expansion verification (50+ sources)
- **`test_web_search_rss_integration.py`**: Web RSS category integration

## Key Modules

### New Modules (August 2026)

- **`browser_pool.py`**: Thread-local Playwright browser pool — launches browser once, reuses context across URLs (3-5x faster)
- **`domain_routing.py`**: Per-domain strategy learning with Thompson sampling, tracks success rates, persists to SQLite
- **`extraction_quality.py`**: Content quality scoring (word/paragraph counts), automatic Playwright escalation for low-quality results
- **`source_resolvers.py`**: Resolves MSN/Yahoo/AOL wrapper URLs to original publisher URLs before extraction
- **`staged_ranker.py`**: Two-stage ranking — fast metadata scoring → extract top N → full-content re-ranking
- **`tech_crunch_rss.py`**: TechCrunch RSS aggregation (expanded to 50+ sources across categories)
- **`web_search_rss.py`**: Web search RSS provider (65 feeds across 13 categories)
- **`category_providers.py`**: Category-aware RSS provider registry for news-search
- **`web_category_providers.py`**: Category provider functions for web-search

### Critical Paths

1. **Unified extraction**: `extraction.py` → `EnterpriseSearchEngine` used by both web-search and news-search
2. **Browser pool**: `browser_pool.py` → passed to `fetch_resilient()` → reused across all URLs
3. **Domain learning**: `domain_routing.py` → tracks per-domain tier success → saves to `~/.scout-it/strategy_cache.db`
4. **Staged ranking**: `staged_ranker.py` → fast metadata rank → extract top 15 → full-content re-rank
5. **Quality escalation**: `extraction_quality.py` → detects low-quality extraction → retries with Playwright

## Repository conventions

- Read-only (regenerated or historical, do not edit): `docs/`, `references/`, `dist/`, `build/`, `scout_it.egg-info/`, caches.
- `scout-it-website/` is a separate Vite/React/TS landing page (`npm ci && npm run build` — its own CI job).
- `scout-it-skill/` holds the `scout-it` agent skill (SKILL.md); update it when CLI flags/commands change.
- Commit messages follow Conventional Commits, include the agent name, and `CHANGELOG.md` is updated with date/time/version.
