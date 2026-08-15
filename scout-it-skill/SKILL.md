---
name: scout-it
description: >-
  Multi-engine web search, content extraction, GitHub/social platform data
  extraction via the `scout-it` CLI. Use this whenever the user mentions
  DuckDuckGo search, web scraping, extracting content from URLs, searching
  for images/news/videos, fetching GitHub repo/PR/issue data, scraping
  Telegram/Discord/Reddit, cleaning web content, or fetching readable text
  from a webpage. This skill generates ready-to-run shell commands with the
  correct flags and explains what each subcommand does.
---

# scout-it: Multi-Engine Search + Content Extraction + Social Platform CLI

A Python CLI (`scout-it`) that wraps DuckDuckGo search (with Google/Brave/Bing/SerpAPI fallback via `multi-search`), web content extraction, GitHub data extraction, and social platform scraping into a single pipeline.

## How to invoke

```bash
scout-it <subcommand> [options]
```

## Subcommands overview

| Subcommand | Purpose |
|------------|---------|
| `web-search` | Web search with full content extraction and a multi-tier resilient fetch chain |
| `news-search` | News search with full article content extraction |
| `image-search` | Image search (with optional download) |
| `video-search` | Video search with duration/resolution filters |
| `fetch-url` | Extract readable content from a single URL |
| `video-extract` | Extract video transcripts/subtitles (YouTube) |
| `multi-search` | Search across DuckDuckGo + Brave/Bing/Google/SerpAPI/Wikimedia in parallel |
| `wikipedia-search` | Search any Wikimedia project (12 projects) via the MediaWiki Action API |
| `list-engines` | List available search engines and their config status |
| `sources` | List available academic/dataset/knowledge source plugins (30+) |
| `index` | Index results into the persistent semantic store (LanceDB) |
| `semantic-search` | Hybrid BM25+vector search over an indexed corpus |
| `config` | Set up API keys/tokens for all platforms |
| `stats` | Show per-domain fetch-strategy stats learned by the local strategy cache |
| `doctor` | Environment self-check: Playwright, proxy config, cache health, credentials, connectivity |
| `github-repo` | Get comprehensive GitHub repo details |
| `github-commits` | List commits in a GitHub repo |
| `github-commit` | Full details for one commit with unified diff (+ line numbers) |
| `github-pr` | Get PR with full diff and changed files |
| `github-prs` | List PRs in a repo |
| `github-folder` | List/fetch every file under a repo folder |
| `github-issues` | List issues in a repo |
| `github-issue` | Get one issue with body and comments |
| `github-file` | Fetch a single file's contents from a repo |
| `github-search-code` | Search code across GitHub (requires GITHUB_TOKEN) |
| `github-search-repos` | Search GitHub repositories |
| `github-discussions` | List GitHub Discussions (requires GITHUB_TOKEN) |
| `telegram-channel` | Fetch posts from a public Telegram channel, or search for channels by topic |
| `discord-channel` | Fetch messages from a Discord channel (requires DISCORD_BOT_TOKEN) |
| `reddit-search` | Best-effort Reddit search |

---

## web-search

Full web search with automatic content extraction. Each result includes cleaned main content, readability metrics, and quality signals.

**Basic usage:**
```bash
scout-it web-search --query "your search query"
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--max` / `-m` | int | `10` (30 in `--snippets` mode) | Number of results to return |
| `--workers` / `-w` | int | `5` | Parallel fetch workers |
| `--out` / `-o` | str | `.scout-it/struct_format_results.json` | Output file |
| `--markdown` | flag | — | Save results as Markdown (.md) instead of JSON |
| `--region` | str | *(none)* | Region (e.g., `us-en`, `uk-en`, `de-de`) |
| `--safesearch` | str | `moderate` | `on`, `moderate`, or `off` |
| `--timelimit` | str | *(none)* | `d` (day), `w` (week), `m` (month), `y` (year) |
| `--backend` | str | `auto` | `auto`, `html`, or `lite` |
| `--sources` | str | *(none)* | Also search source plugins (comma-separated, e.g. `openalex,arxiv,wikidata`) and merge with BM25F+vector re-ranking. Run `scout-it sources` for the list |
| `--auto-sources` | flag | — | Let the source-selection bandit pick the best sources for this query type. Overrides `--sources` |
| `--source` | str | *(none)* | Search source override — use `wikimedia` to search Wikipedia directly (falls back to DuckDuckGo on zero results) |
| `--category` | str (nargs+) | *(none)* | RSS feed categories (`ai`, `engineering`, `cloud`, `devops`, `research`, `security`, `startups`, etc.). Multiple allowed, e.g. `--category ai cloud` |
| `--snippets` | flag | — | Return ranked snippets only. Skips content extraction for ~10x faster results (~2-4s vs 20-70s) |
| `--no-retry-on-zero` | flag | — | Skip retry on zero successful extractions |
| `--retry-attempts` | int | `2` | Retry attempts when 0 successful extractions |
| `--retry-backoff` | float | `1.0` | Backoff seconds between retries |
| `--max-fetch-retries` | int | `3` | Retry attempts per fetch tier (requests → Playwright) |
| `--no-js-fallback` | flag | — | Disable Playwright fallback on blocked pages |
| `--enable-alternate-source` | flag | — | If every fetch tier fails, try AMP/mobile/print URL variants + a Wayback Machine snapshot before giving up (extra requests, opt-in) |
| `--no-dns-fallback` | flag | — | Disable the DNS-over-HTTPS retry that otherwise kicks in on DNS-looking failures (on by default) |
| `--tls-impersonate` | flag | — | Insert a browser-accurate TLS/JA3 fingerprint tier between requests and Playwright — needs `pip install scout-it[tls-impersonate]` |
| `--persistent-profile` | flag | — | Use a persistent Playwright profile (cookies/session survive across runs) instead of a throwaway context for the JS-render tier |
| `--profile-name` | str | `default` | Persistent profile name — only meaningful with `--persistent-profile` |
| `--use-bandit` | flag | — | Once a domain has enough recorded history, skip straight to whichever fetch tier has actually worked best for it instead of always starting with plain requests — see `scout-it stats` |
| `--semantic` | flag | — | Re-rank results by semantic relevance (hybrid BM25+dense-vector + cross-encoder). Needs `pip install sentence-transformers torch` |

> `web-search` writes to a file by default and has **no `--json` flag** — use `--out` / `--markdown`.

**Examples:**
```bash
# Basic search
scout-it web-search --query "Python 3.13 new features"

# Verbose, 20 results, save to JSON
scout-it web-search --query "machine learning trends" --max 20 --out results.json

# Save as Markdown
scout-it web-search --query "AI regulation" --max 15 --markdown --out ai-report.md

# Region-specific with time filter
scout-it web-search --query "climate policy" --region us-en --timelimit w

# HTML backend with aggressive retry
scout-it web-search --query "niche topic" --backend html --retry-attempts 5 --retry-backoff 2.0

# Struggling with a heavily-protected site: layer on more resilience
scout-it web-search --query "site:example.com" --tls-impersonate --enable-alternate-source

# Let the bandit route requests to whatever's actually worked before for these domains
scout-it web-search --query "recurring research topic" --use-bandit
```

---

## image-search

```bash
scout-it image-search --query "sunset landscapes" --max 10
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--max` / `-m` | int | `5` | Max images (1-50) |
| `--out` / `-o` | str | `.scout-it/image_search_results.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--sources` | str | *(none)* | Also search source plugins (comma-separated, e.g. `internet_archive,openstreetmap`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | flag | — | Bandit-picked sources for this query type. Overrides `--sources` |
| `--download` / `-d` | flag | — | Download the images |
| `--download-dir` | str | `.scout-it/downloaded_images` | Where to save downloaded images |
| `--region` | str | `us-en` | DuckDuckGo region (e.g. us-en, wt-wt) |
| `--safesearch` | str | `moderate` | `on`, `moderate`, or `off` |
| `--timelimit` | str | *(none)* | `d`/`w`/`m`/`y` |
| `--size` | str | *(none)* | `Small`, `Medium`, `Large`, `Wallpaper` |
| `--color` | str | *(none)* | Color filter |
| `--type-image` | str | *(none)* | `photo`, `clipart`, `gif`, `transparent`, `line` |
| `--layout` | str | *(none)* | `Square`, `Tall`, `Wide` |
| `--license-image` | str | *(none)* | License filter |
| `--min-width` / `--max-width` / `--min-height` / `--max-height` | int | *(none)* | Dimension filters (in pixels) |
| `--category` | str (nargs+) | *(none)* | Image RSS categories (e.g. `nature space travel`). Fetches Media RSS feeds (Flickr/NASA) alongside DuckDuckGo |
| `--rss` | flag | — | Include image RSS discovery even without `--category` (uses a Flickr tag feed from the query) |
| `--no-retry-on-zero` | flag | — | Disable retry when 0 valid images are found |
| `--retry-attempts` | int | `2` | Retry attempts |
| `--retry-backoff` | float | `1.0` | Backoff seconds between retries |

---

## news-search

```bash
scout-it news-search --query "artificial intelligence" --max 5
```

Same unified extraction engine, staged ranking, `--snippets`, `--sources` / `--auto-sources`, `--category`, retry/fallback, TLS/profile/bandit, and `--semantic` flags as `web-search`. News-specific additions:

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--max` / `-m` | int | `10` (30 in `--snippets` mode) | Number of results to return |
| `--snippets` | flag | — | Return ranked snippets only (~10x faster) |
| `--out` / `-o` | str | `.scout-it/news_search_results.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--sources` | str | *(none)* | Also search source plugins (comma-separated, e.g. `gdelt,openalex,crossref`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | flag | — | Bandit-picked sources for this query type. Overrides `--sources` |
| `--region` | str | `us-en` | DuckDuckGo region |
| `--safesearch` | str | `moderate` | `on`, `moderate`, `off` |
| `--timelimit` | str | *(none)* | `d`/`w`/`m`/`y` |
| `--workers` | int | `5` | Parallel workers for article content extraction |
| `--source` | str | *(none)* | Search source override — use `google-news` for Google News RSS (falls back to DuckDuckGo News on zero results) |
| `--category` | str (nargs+) | *(none)* | News RSS categories (`ai`, `startups`, `security`, `cloud`, `all`). Multiple allowed, e.g. `--category ai startups` |
| `--location` | str (nargs+) | *(none)* | Location(s) for localized news from Times of India RSS (e.g. `india`, `US`, `UK`, `europe`, `china`, `india-delhi`). Multiple allowed |
| `--max-chars` | int | *(none)* | Maximum characters to keep in extracted article content |
| `--max-size` | str | *(none)* | Maximum response size per article (e.g. `5mb`). Truncates raw HTML before extraction |
| `--max-fetch-retries` | int | `3` | Retry attempts per fetch tier when fetching each article |
| `--no-js-fallback` | flag | — | Disable Playwright fallback for blocked articles |
| `--enable-alternate-source` | flag | — | Try AMP/mobile/print/Wayback variants on failure (opt-in) |
| `--no-dns-fallback` | flag | — | Disable DNS-over-HTTPS retry (on by default) |
| `--tls-impersonate` | flag | — | Browser-accurate TLS/JA3 fingerprint tier (needs `scout-it[tls-impersonate]`) |
| `--persistent-profile` | flag | — | Persistent Playwright profile |
| `--profile-name` | str | `default` | Persistent profile name |
| `--use-bandit` | flag | — | Skip to best-performing tier per domain from history |
| `--semantic` | flag | — | Re-rank by semantic relevance (needs `pip install sentence-transformers torch`) |
| `--no-retry-on-zero` / `--retry-attempts` / `--retry-backoff` | — | see web-search | Zero-result retry controls |

> `news-search` writes to a file by default and has **no `--json` flag** — use `--out` / `--markdown`.

---

## video-search

```bash
scout-it video-search --query "python tutorial" --max 5
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--max` / `-m` | int | `5` | Max videos (1-50) |
| `--out` / `-o` | str | `.scout-it/video_search_results.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--sources` | str | *(none)* | Also search source plugins (comma-separated, e.g. `internet_archive,listennotes`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | flag | — | Bandit-picked sources for this query type. Overrides `--sources` |
| `--region` / `--safesearch` / `--timelimit` | — | `us-en` / `moderate` / *(none)* | Standard DuckDuckGo filters |
| `--resolution` | str | *(none)* | `high` or `standard` |
| `--duration` | str | *(none)* | `short`, `medium`, or `long` |
| `--license-videos` | str | *(none)* | License filter |
| `--category` | str (nargs+) | *(none)* | Video RSS categories (e.g. `technology science news`). Fetches YouTube channel RSS feeds alongside DuckDuckGo |
| `--rss` | flag | — | Include video RSS discovery even without `--category` (pulls a default set of YouTube channels) |
| `--no-retry-on-zero` | flag | — | Disable retries when 0 results are found |
| `--retry-attempts` | int | `2` | Retry attempts when 0 results found |
| `--retry-backoff` | float | `1.0` | Backoff seconds between retries |

Note: `video-search` only lists videos — it doesn't extract per-video content. Use `video-extract` for a single video's full metadata/subtitles.

---

## fetch-url

Fetch and extract content from **one specific URL** (not a search).

```bash
scout-it fetch-url --url "https://example.com/article"
scout-it fetch-url --url "https://spa-heavy-site.com" --js-render
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--url` / `-u` | str | *required* | URL to fetch |
| `--timeout` | int | `25` | Per-attempt timeout in seconds |
| `--max-chars` | int | *(none)* | Truncate extracted content by character count — mutually exclusive with `--max-size` |
| `--max-size` | str | *(none)* | Cap raw response size, e.g. `500kb`, `5mb` — mutually exclusive with `--max-chars` |
| `--raw-html` | flag | — | Return prettified raw HTML instead of extracted main content |
| `--js-render` | flag | — | Skip straight to Playwright instead of trying `requests` first |
| `--no-js-fallback` | flag | — | Disable the automatic Playwright fallback |
| `--enable-alternate-source` | flag | — | Try AMP/mobile/print URL variants + Wayback Machine when all tiers fail (opt-in) |
| `--max-retries` | int | `3` | Retry attempts per fetch tier |
| `--persistent-profile` | flag | — | Use a persistent Playwright profile (cookies/session survive across runs) for the JS-render tier |
| `--profile-name` | str | `default` | Persistent profile name (only with `--persistent-profile`) |
| `--out` / `-o` | str | `.scout-it/url_fetch_result.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--json` | flag | — | Output raw JSON to stdout |

Providing both `--max-chars` and `--max-size` is an error — use at most one.

---

## video-extract

Extract full metadata + subtitles from a single video URL (YouTube only for now).

```bash
scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
scout-it video-extract --url "https://youtu.be/dQw4w9WgXcQ" --subtitle-lang fr --segments
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--url` | str | *required* | YouTube video URL |
| `--subtitle-lang` | str | `en` | Preferred subtitle language code |
| `--segments` | flag | — | Include timestamped subtitle segments |
| `--max-fetch-retries` | int | `3` | Retry attempts per fetch tier |
| `--no-js-fallback` | flag | — | Disable Playwright fallback |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--json` | flag | — | Output raw JSON to stdout |
| `--out` / `-o` | str | `.scout-it/video_extract_results.json` | Output file |

Non-YouTube URLs return a clear `unsupported_platform` error rather than failing silently.

---

## multi-search

Search across multiple engines (DuckDuckGo + optional Brave/Bing/Google/SerpAPI) in parallel. DuckDuckGo works with no setup; the others need a free/paid API key each, configured via `scout-it config`.

**Basic usage:**
```bash
scout-it multi-search --query "your query" --engines duckduckgo,brave,bing
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--engines` | str | `duckduckgo` | Comma-separated: `duckduckgo,brave,bing,google,serpapi,wikimedia` |
| `--source` | str | *(none)* | Include Wikimedia as a search source. Shorthand for `--engines wikimedia` |
| `--max` / `-m` | int | `10` | Max merged results |
| `--workers` / `-w` | int | `5` | Parallel content-extraction workers |
| `--serpapi-engine` | str | `google` | Underlying engine for SerpAPI (google/bing/yahoo/baidu/yandex) |
| `--no-dedupe` | flag | — | Keep duplicate URLs across engines instead of deduping (dedupe is on by default) |
| `--max-fetch-retries` | int | `3` | Retry attempts per fetch tier |
| `--no-js-fallback` | flag | — | Disable automatic Playwright fallback |
| `--out` / `-o` | str | `.scout-it/multi_search_results.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--sources` | str | *(none)* | Also search source plugins (comma-separated, e.g. `openalex,arxiv,wikidata,huggingface`) in parallel and merge with BM25F+vector re-ranking |
| `--auto-sources` | flag | — | Bandit-picked sources for this query type. Overrides `--sources` |
| `--json` | flag | — | Output raw JSON to stdout |

`duckduckgo` works with no setup; the others each need a free/paid API key configured via `scout-it config` or an environment variable — run `scout-it list-engines` to check status. Unconfigured engines are skipped (not treated as an error).

**Examples:**
```bash
# DuckDuckGo + Brave + Bing
scout-it multi-search --query "quantum computing" --engines duckduckgo,brave,bing

# All configured engines
scout-it multi-search --query "climate science" --engines duckduckgo,brave,bing,google --max 15
```

---

---

## wikipedia-search

Search any Wikimedia project via the MediaWiki Action API — all 12 projects: wikipedia, commons, wikivoyage, wiktionary, wikibooks, wikidata, wikiversity, wikiquote, mediawiki, wikisource, wikispecies, wikifunctions.

```bash
scout-it wikipedia-search --query "machine learning"
scout-it wikipedia-search --query "Albert Einstein" --project wikipedia --extract
scout-it wikipedia-search --query "quantum physics" --bundle
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query or page title |
| `--max` / `-m` | int | `10` | Max results (1-50) |
| `--project` | str | `wikipedia` | Wikimedia project (any of the 12 in `SITE_MAP`) |
| `--language` / `-l` | str | `en` | Project language for language-scoped wikis |
| `--timeout` | int | `25` | HTTP timeout in seconds |
| `--workers` / `-w` | int | `5` | Parallel workers |
| `--out` / `-o` | str | `.scout-it/wikimedia_results.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--json` | flag | — | Output raw JSON to stdout |
| `--summary` | flag | — | Fetch a Wikipedia REST summary for the title |
| `--extract` | flag | — | Fetch cleaned full-page extract via the Action API |
| `--sections` | flag | — | Export section-by-section cleaned text |
| `--crawl` | flag | — | Recursive crawl from search results (with `--crawl-depth`) |
| `--crawl-depth` | int | `2` | Crawl depth for `--crawl` mode |
| `--bundle` | flag | — | Broad multi-project topic bundle (all 12 projects) |
| `--robots` | flag | — | Check robots.txt allowance before searching |
| `--no-clean` | flag | — | Disable text cleaning |
| `--rss` | flag | — | Include MediaWiki RecentChanges RSS feeds in discovery |
| `--category` / `-c` | str | *(none)* | Wikimedia project RSS category to include (repeatable) |

---

## sources

List all source plugins available via the `--sources` flag on `web-search`, `news-search`, `image-search`, `video-search`, and `multi-search`. All free or free-tier (30+ plugins: `openalex`, `arxiv`, `crossref`, `semantic_scholar`, `huggingface`, `zenodo`, `wikidata`, `gdelt`, `internet_archive`, `openstreetmap`, `hackernews`, `stackexchange`, etc.).

```bash
scout-it sources          # formatted table
scout-it sources --json   # JSON
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--json` | flag | — | Output as JSON instead of a formatted table |

---

## index

Fetch, extract, chunk, and embed `web-search` or `news-search` results into the persistent LanceDB store at `~/.scout-it/semantic/lancedb/`. The corpus then powers `semantic-search`. Needs: `pip install sentence-transformers torch lancedb`.

```bash
scout-it index --query "transformer architecture" --max 20
scout-it index --query "AI news" --source news
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Query to fetch and index |
| `--max` / `-m` | int | `20` | Max results to fetch and index |
| `--source` | str | `web` | Source to fetch from: `web` or `news` |

---

## semantic-search

Search a persistent corpus of previously-indexed documents using hybrid BM25 + dense-vector retrieval. Use `scout-it index` to build the corpus first. Storage: `~/.scout-it/semantic/lancedb/`. Model configurable via `SCOUT_SEMANTIC_MODEL` (default: `BAAI/bge-m3`). Needs: `pip install sentence-transformers torch lancedb`.

```bash
scout-it index --query "transformer architecture" --max 20    # build corpus
scout-it semantic-search --query "attention mechanisms" --max 5  # query it
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--max` / `-m` | int | `10` | Max results |
| `--out` / `-o` | str | `.scout-it/semantic_results.json` | Output file |
| `--markdown` | flag | — | Save as Markdown instead of JSON |
| `--json` | flag | — | Output raw JSON to stdout |

---

## config

Set up API keys/tokens for GitHub, Brave, Bing, Google, SerpAPI, Discord, Reddit. Stored at `~/.scout-it/credentials.json` (owner-only file permissions).

```bash
scout-it config              # interactive wizard -- Enter to skip any key you don't have
scout-it config --show       # check what's configured (no secrets printed)
scout-it config --clear GITHUB_TOKEN
scout-it config --clear-all
```

A real environment variable (e.g. `GITHUB_TOKEN`) always takes precedence over a stored value. Use `scout-it list-engines` to see which search engines are configured specifically.

---

## stats

Shows what scout-it has learned about each domain it's fetched from — which `{tier, proxy, fingerprint}` combination has worked best, overall success rate, and attempt counts. Backed by a local SQLite file at `~/.scout-it/strategy_cache.db` — pure local bookkeeping, no network calls. This is what `--use-bandit` (on `web-search`) reads from to decide whether to skip a doomed fetch tier.

```bash
scout-it stats                          # summary across all known domains
scout-it stats --domain example.com     # stats for one domain only
scout-it stats --export stats.json      # full dump to a JSON file
scout-it stats --reset example.com      # forget learned history for one domain
scout-it stats --reset-all              # forget everything
scout-it stats --sources               # source-selection bandit stats
```

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--domain` | str | *(none)* | Show stats for one domain only |
| `--export` | str | *(none)* | Write the full stats dump to this JSON path instead of printing a summary |
| `--reset` | str | *(none)* | Forget all recorded strategy history for one domain |
| `--reset-all` | flag | — | Forget all recorded strategy history for every domain |
| `--sources` | flag | — | Show source-selection bandit stats (which sources work best per query type) |

---

## doctor

Runs a battery of lightweight, local-first checks (no destructive actions) to diagnose "why does this always fall back to tier 3" type questions: whether Playwright/Chromium is actually installed (not just the pip package), whether `PROXY_LIST` is configured and reachable, response-cache and strategy-cache size, which credentials are configured, and basic internet connectivity.

```bash
scout-it doctor
```

No flags — always runs the full check. Every check is independent, so one failing (e.g. Playwright not installed) doesn't stop the others from reporting.

---

## GitHub subcommands

Repo-scoped commands (`github-repo`, `github-commits`, `github-commit`, `github-pr`, `github-prs`, `github-issues`, `github-issue`, `github-file`, `github-folder`, `github-discussions`) all accept `--repo` as one of:
- `owner/repo` format
- Full GitHub URL: `https://github.com/owner/repo`

`github-search-code` and `github-search-repos` take `--query` instead (they search across GitHub, not within one repo).

Auth is **not** a per-command flag — set `GITHUB_TOKEN` as an environment variable, or run `scout-it config` to store it once. Unauthenticated requests are capped at 60/hour; a token raises that to 5,000/hour and is **required** for `github-discussions` and `github-search-code`.

**Examples:**
```bash
# Repo metadata (full overview by default: branches, contributors, releases, languages)
scout-it github-repo --repo gajjalaashok75-UI/scout-it

# List recent PRs
scout-it github-prs --repo gajjalaashok75-UI/scout-it --state open

# Get a PR with full diff (patch_lines includes old/new file line numbers)
scout-it github-pr --repo gajjalaashok75-UI/scout-it --number 1

# Search code (requires GITHUB_TOKEN)
scout-it github-search-code --query "class EnterpriseSearch language:python"

# List commits
scout-it github-commits --repo gajjalaashok75-UI/scout-it --max 20

# Full commit details with line-numbered diff
scout-it github-commit --repo gajjalaashok75-UI/scout-it --sha <commit-sha>
```

---

## Social platform subcommands

### Telegram
```bash
# Fetch recent posts from a known public channel
scout-it telegram-channel --channel "channel_name" --max 10

# Search for public channels matching a topic (via a site:t.me web search --
# there's no official Telegram-wide search API for anonymous use)
scout-it telegram-channel --query "Python programming" --max 5

# Save to Markdown
scout-it telegram-channel --channel "channel_name" --markdown --out channel.md
```

### Discord (requires DISCORD_BOT_TOKEN set via `scout-it config`)

### Discord (requires DISCORD_BOT_TOKEN set via `scout-it config`)
```bash
# Fetch recent messages from a channel
scout-it discord-channel --channel-id "123456789"
```

### Reddit
```bash
# Best-effort search (unreliable as of 2026)
scout-it reddit-search --query "Python" --subreddit "learnprogramming"
```

---

## Output format

Every command writes a JSON **object** (not a bare array) to `.scout-it/<command>_results.json` by default — typically containing the query/repo/etc., a `parameters` or similar echo of the options used, a `stats` block, and the actual results under a key like `structured_results`, `commits`, `posts`, etc. (the exact key varies by command). Long string fields (extracted article text, diff patches, raw HTML) are automatically chunked into arrays of <=500-character pieces so no single line in the file is unreasonably long — this never affects the actual content, just how it's laid out in the file.

For web-search/news-search/fetch-url specifically, each result also contains:
- `title` / `url` — search result title and URL
- `main_content` — cleaned, extracted content
- `extraction_method` — which extraction layer succeeded, and which fetch tier got the page (e.g. `"trafilatura (playwright)"`)
- `confidence_score` — content quality score (0.0–1.0)
- `extraction_status` — `"success"` or `"failed"`
- `content_word_count` — word count of cleaned content

**`--markdown` works on every command that writes output** (all 30 of them, not just web-search) — renders the same data as a Markdown document (tables, fenced code blocks, headers) instead of JSON. `--out somefile.md` does the same thing without needing the flag explicitly.

## Content-extraction fallback chain

Once a page's HTML is fetched, extracting the *main content* tries these in order, keeping whichever result scores highest (confidence x word count) rather than just the first one that returns something:

```
1. Trafilatura   — usually best for news/articles
2. Justext       — good general-purpose extractor
3. BoilerPy3     — robust fallback
4. Readability   — alternative extractor
5. Heuristic (BeautifulSoup-based) — ultimate fallback, always produces *something*
```

This is separate from the **fetch** fallback chain (getting the raw HTML in the first place) — see below.

## Fetch resilience chain (the "layers")

Getting a page's raw HTML tries these layers in order, all inside a single `fetch_resilient()` call shared by every command that fetches a URL:

```
Tier 1    requests                     — cheap, fast; full consistent browser-header-profile
                                          rotation; honors Retry-After/rate-limit headers instead
                                          of guessing backoff; routed through PROXY_LIST if set
                                          (transparently direct if not)
   ↳ on a DNS-looking failure: one DNS-over-HTTPS retry against the resolved IP (on by default)
Tier 1.5  TLS/JA3 impersonation        — opt-in (--tls-impersonate), needs curl_cffi installed
Tier 2    Playwright (headless)        — only when Tier 1/1.5 fail or look blocked; optionally a
                                          persistent profile (--persistent-profile) instead of a
                                          throwaway context
Tier 3    Basic last-resort request    — minimal, non-fingerprinted headers
Tier 4    Alternate-source ladder      — opt-in (--enable-alternate-source): AMP/mobile/print URL
                                          variants, then a Wayback Machine snapshot
```

With `--use-bandit`, once a domain has enough recorded history (see `scout-it stats`) showing Playwright reliably outperforms plain requests for it, Tier 1 is skipped entirely instead of wasting an attempt on it — this only changes behavior for domains with real accumulated history; everything else follows the tiers above unchanged.

Every attempt (success or failure) is recorded to the local strategy cache regardless of whether `--use-bandit` is on — `scout-it stats` reads that history any time, and `--use-bandit` just chooses to *act* on it during the fetch itself.

## Config / cache directories

- Credentials: `~/.scout-it/credentials.json` (owner-only file permissions; see `scout-it config`)
- Strategy cache (per-domain fetch history): `~/.scout-it/strategy_cache.db` (see `scout-it stats`)
- Response cache: `~/.scout-it/cache/`
- Persistent browser profiles: `~/.scout-it/browser-profiles/<name>/` (only created with `--persistent-profile`)
- Output files default to `.scout-it/` in the current working directory (created automatically)

## Rate limiting

DuckDuckGo may rate-limit aggressive usage. Recommendations:
- Keep `--max` under 30 for routine use
- Use `--retry-attempts 5 --retry-backoff 2.0` for important queries
- If you see zero results, try `--backend html` or `--no-js-fallback`
- For high-volume needs, use `multi-search` with additional engines
- For a single heavily-protected domain, layer on `--tls-impersonate` and/or `--enable-alternate-source`; run `scout-it doctor` first to confirm Playwright/curl_cffi are actually available before relying on them
