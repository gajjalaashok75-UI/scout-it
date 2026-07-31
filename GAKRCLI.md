# GAKRCLI.md

This file provides guidance to GakrCLI Code (gakrcli.ai/code) when working with code in this repository.

## Project

**scout-it v1.5.0** — a Python package and CLI (`scout-it`) for AI-powered web search, content extraction, GitHub data extraction, and social platform scraping. Python >= 3.9, MIT license. Entry point is `scout_it/cli.py` (argparse, ~26 subcommands); public API is re-exported from `scout_it/__init__.py`.

This file replaces the old `AGENTS.md` (which has been deleted). It is the authoritative agent guide; it intentionally does not repeat the README.

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

- `news-search` supports `--sources google-news` (`google_news_source.py`, runs in parallel with the DDGS chain) and `--location <city>` which adds Times of India RSS (`toi_rss_source.py`, `LOCATION_FEEDS`). Behavior is simply additive — DDG + Google News + ToI all present; no priority rules. Location lookup is case-insensitive; feeds are newest-first and `publish_date` is preserved through the whole pipeline.
- `web-search` and `multi-search` support `--sources wikimedia`; there is also a dedicated `wikipedia-search` command (`wikimedia_source.py`, `SITE_MAP` has per-project site entries).

### GitHub and social

- `scout_it/github_extract.py` — 12 extractors (repos, commits, single commit+diff, PRs, PR+diff, issues, issue+comments, files, folders, code/repo search, discussions). Repo-wide commands take an optional GitHub URL or `owner/repo`. Rate-limit-sensitive; `github-discussions` and `github-search-code` require a token.
- `scout_it/social.py` — telegram-channel (public), discord-channel (needs `DISCORD_BOT_TOKEN`), reddit-search (best-effort, optional `REDDIT_COOKIE`).

### Credentials and state

- `scout_it/config.py` — `scout-it config` runs a wizard persisting keys to `~/.scout-it/credentials.json` (0600 on POSIX). `load_stored_credentials_into_env()` runs once at CLI startup; a real env var always wins over the stored file. Known keys are in `KNOWN_CREDENTIALS`.
- Playwright pages use a persistent browser profile (`browser_profile.py`); anti-bot sites that return HTTP 401 are paywalled at the source and unrecoverable without credentials.

## Testing

- ~430 tests across 11 files. **Run test files one at a time** (`pytest tests/test_resilience.py -v`), not the whole suite at once — the suite has cross-file state assumptions.
- **Prefer real CLI runs over pytest for verifying behavior.** `real-tests.md` documents a large matrix of real `scout-it ... --out ...` invocations (with logging to `terminal-logs.md`). For parallel CLI runs use unique `--out` filenames to avoid output collisions.
- CI (`.github/workflows/ci.yml`) runs **build-only** (matrix 3.9–3.12) plus the website build; it does not run tests. Tests run locally. Release workflow tags `v*.*.*` build Python distributions and create a GitHub Release — no PyPI publishing.
- After porting reference code or touching a shared function, verify the full end-to-end CLI pipeline and audit every call site (not just the function in isolation).

## Repository conventions

- Read-only (regenerated or historical, do not edit): `docs/`, `references/`, `dist/`, `build/`, `scout_it.egg-info/`, caches.
- `scout-it-website/` is a separate Vite/React/TS landing page (`npm ci && npm run build` — its own CI job).
- `scout-it-skill/` holds the `scout-it` agent skill (SKILL.md); update it when CLI flags/commands change.
- Commit messages follow Conventional Commits, include the agent name, and `CHANGELOG.md` is updated with date/time/version.
