# Web Search Toolkit

A production-style Python search toolkit that combines DuckDuckGo search, web content extraction, content cleaning, and structured JSON output.

This project supports multiple query types:

1. Web search with content extraction and cleaning
2. Image search with optional dimension filtering and download
3. News search
4. Video search
5. Single URL fetch and extraction

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Query Types](#query-types)
- [Key Features](#key-features)
- [Project Structure](#project-structure)
- [Architecture and Data Flow](#architecture-and-data-flow)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
  - [Global Help](#global-help)
  - [web-search](#web-search)
  - [image-search](#image-search)
  - [news-search](#news-search)
  - [video-search](#video-search)
  - [fetch-url](#fetch-url)
- [Programmatic API](#programmatic-api)
- [Output Files and JSON Shapes](#output-files-and-json-shapes)
- [Retry and Fallback Behavior](#retry-and-fallback-behavior)
- [Image Dimension Filtering Rules](#image-dimension-filtering-rules)
- [Examples](#examples)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Performance Notes](#performance-notes)
- [Limitations](#limitations)

## What This Project Does

The toolkit gives you an end-to-end search pipeline:

- Search DuckDuckGo
- Fetch page HTML
- Extract main content using multi-strategy extraction
- Clean and structure extracted text
- Save structured outputs as JSON

It is designed for data collection and analysis workflows where you need more than just links.

## Query Types

There are 5 query/search modes available through `search.py`:

1. `web-search`: DuckDuckGo text search plus content extraction and cleaning
2. `image-search`: DuckDuckGo image search with rich filters and optional download
3. `news-search`: DuckDuckGo news search
4. `video-search`: DuckDuckGo video search
5. `fetch-url`: Direct extraction from a single URL

## Key Features

- Multi-mode CLI with subcommands
- Automatic compatibility fallback for DDGS call signatures
- Retry-on-zero-success logic for web and image search
- Advanced DuckDuckGo options (region, safesearch, timelimit, backend)
- Image metadata filtering by `min/max width` and `min/max height`
- Multi-engine HTML content extraction (`trafilatura`, `justext`, `boilerpy3`, heuristic fallbacks)
- Structured content cleaning and quality scoring
- JSON-first outputs for downstream data science workflows
- Test suite with mocked integration behavior

## Project Structure

```text
scout-it/
  scout_it/
    __init__.py               # Package initialization + public API
    cli.py                    # CLI entry point (scout-it command)
    extraction.py             # Search engines + extraction engines
    cleaner.py                # Content cleaning + structuring
  tests/
    test_cli.py               # Pytest suite (38+ test cases)
  docs/                       # User documentation
  references/                 # Legacy code archive
  pyproject.toml              # PEP 517/518 build config
  setup.py                    # Legacy setup script
  README.md                   # Main documentation
  AGENTS.md                   # AI agent instructions
  LICENSE                     # MIT License
```

## Architecture and Data Flow

### Web Search Pipeline

1. `search.py web-search` starts request
2. `EnterpriseSearchEngine` queries DDGS text
3. URLs are fetched in parallel
4. `ExtractionEngine` extracts main content using layered methods
5. `main_content_cleaner.process_results` filters failed extraction records and structures text
6. Output is written as JSON

### Image Search Pipeline

1. `search.py image-search` runs DDGS image query
2. Results are normalized into `ImageSearchResult`
3. Optional dimension filters are applied
4. Optional retry occurs when 0 valid images
5. Optional download saves files locally
6. Output JSON is written

### News and Video Pipelines

1. `search.py news-search` or `video-search`
2. Generic DDGS wrapper executes compatible method calls
3. Raw result list and stats are returned as JSON

### Fetch URL Pipeline

1. `search.py fetch-url --url ...`
2. URL is validated (`http`/`https`)
3. HTML is fetched
4. Content extraction + cleaner processing runs
5. Single structured record is written

## Requirements

- Python 3.11+ (tested in this workspace with Python 3.13)
- Internet access for live search/fetch

Python packages used by the project:

- `ddgs` (falls back to `duckduckgo_search` automatically if unavailable)
- `trafilatura`
- `requests`
- `beautifulsoup4`
- `justext`
- `boilerpy3`
- `rich`
- `youtube-transcript-api` (for `video-extract` subtitles)
- `playwright` — *optional*, only needed for the Tier-2 JS-render fallback. Install with `pip install scout-it[js-render]` then `playwright install chromium`.
- `pytest` (for tests)

## Installation

### Option 1: Install from Repository (Development Mode)

```bash
# Clone repository
git clone https://github.com/Ashok-gakr/data-scout.git
cd data-scout

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

### Option 2: Install from PyPI

```bash
pip install scout-it
```

### Verify Installation

```bash
scout-it --help
```

## Quick Start

### 1) Web Search (3 results)

```bash
scout-it web-search --query "dog" --max-results 3
```

### 2) Image Search (3 results)

```bash
scout-it image-search --query "dog" --max-results 3
```

### 3) News Search

```bash
scout-it news-search --query "dog" --max-results 5
```

### 4) Video Search

```bash
scout-it video-search --query "dog" --max-results 5
```

### 5) Fetch and Extract a Single URL

```bash
scout-it fetch-url --url "https://en.wikipedia.org/wiki/Dog"
```

### 6) Web Search with JSON Output

```bash
scout-it web-search --query "machine learning" --max-results 10 --json
```

## CLI Reference

### Global Help

```bash
scout-it --help
```

Subcommands:

- `web-search` - Search the web with content extraction
- `image-search` - Search for images
- `news-search` - Search for news articles
- `video-search` - Search for videos
- `fetch-url` - Extract content from a single URL

### web-search

```bash
scout-it web-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max, -m` (default: `10`): number of results to fetch
- `--workers` (default: `8`): parallel content-extraction workers
- `--region`, `--safesearch`, `--timelimit`, `--backend`: DDGS search parameters
- `--retry-on-zero` / `--no-retry-on-zero` (default: on): retry the DDGS search itself if it comes back with 0 results
- `--retry-attempts` (default: `2`), `--retry-backoff` (default: `1.0`): tuning for the above
- `--max-fetch-retries` (default: `3`): retry attempts *per tier* (requests, then Playwright) when fetching each result's page content
- `--no-js-fallback`: disable the automatic Playwright fallback for blocked/failed page fetches
- `--json`: output as JSON to stdout

**Example:**
```bash
scout-it web-search --query "machine learning" --max 5
scout-it web-search --query "site behind cloudflare" --max-fetch-retries 4
```

### image-search

```bash
scout-it image-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max, -m` (default: `10`): number of images
- `--min-width`, `--min-height`, `--max-width`, `--max-height`: dimension filters
- `--color`, `--type-image`, `--layout`, `--license-images`: DDGS image filters
- `--retry-on-zero` / `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`: zero-result retry tuning
- `--json`: output as JSON to stdout

**Example:**
```bash
scout-it image-search --query "landscape" --max 10 --min-width 1024 --min-height 768
```

### news-search

```bash
scout-it news-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max, -m` (default: `10`): number of articles
- `--region`, `--safesearch`, `--timelimit`: DDGS search parameters
- `--retry-on-zero` / `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`: zero-result retry tuning (previously news-search made only a single DDGS attempt; it now has the same retry parity as web-search/image-search)
- `--max-fetch-retries` (default: `3`), `--no-js-fallback`: same resilient-fetch controls as web-search, applied to fetching each article's full text
- `--json`: output as JSON to stdout

**Example:**
```bash
scout-it news-search --query "artificial intelligence" --max 5
```

### video-search

```bash
scout-it video-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max, -m` (default: `10`): number of videos
- `--region`, `--safesearch`, `--timelimit`, `--resolution`, `--duration`, `--license-videos`: DDGS video filters
- `--retry-on-zero` / `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`: zero-result retry tuning (previously video-search had no retry logic at all)
- `--json`: output as JSON to stdout

**Example:**
```bash
scout-it video-search --query "python tutorial" --max 5
```

### video-extract

```bash
scout-it video-extract --url "<youtube-url>" [options]
```

Extracts full metadata (title, channel, view/like counts, description, upload date) and, where available, subtitles/transcript for a YouTube video.

Options:

- `--url` (required): YouTube video URL (`youtube.com/watch?v=...` or `youtu.be/...`)
- `--subtitle-lang` (default: `en`): preferred subtitle language code
- `--segments`: include timestamped subtitle segments in the output
- `--max-fetch-retries` (default: `3`), `--no-js-fallback`: resilient-fetch controls for the underlying YouTube page fetch
- `--json`: output as JSON to stdout

**Example:**
```bash
scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments
```

Only YouTube is currently supported; other platforms return a clear `unsupported_platform` error rather than failing silently.

### fetch-url

```bash
scout-it fetch-url --url "https://example.com" [options]
```

Options:

- `--url, -u` (required): URL to fetch and extract
- `--timeout` (default: `25`): fetch timeout in seconds, applied per attempt/tier
- `--max-chars`: truncate extracted content to N characters (mutually exclusive with `--max-size`)
- `--max-size`: cap the raw response size, e.g. `5mb`, `500kb` (mutually exclusive with `--max-chars`)
- `--raw-html`: return prettified raw HTML instead of extracted main content
- `--js-render`: skip straight to Playwright rendering instead of trying `requests` first
- `--no-js-fallback`: disable the automatic Playwright fallback that normally kicks in when `requests` fails or looks blocked
- `--max-retries` (default: `3`): retry attempts per tier (requests, then Playwright)
- `--json`: output as JSON to stdout

**Example:**
```bash
scout-it fetch-url --url "https://example.com/article"
scout-it fetch-url --url "https://spa-heavy-site.com" --js-render
```

### multi-search — search across multiple engines

```bash
scout-it multi-search --query "<text>" --engines duckduckgo,brave,google [options]
```

Queries several search engines **in parallel**, merges/dedupes by URL, then runs the same
content-extraction pipeline as `web-search`. `duckduckgo` needs no setup; the others need a
free/paid API key set as an environment variable — run `scout-it list-engines` to see what's
configured and what each one needs.

Options: `--query/-q`, `--engines` (comma-separated), `--max/-m`, `--workers/-w`,
`--serpapi-engine` (google/bing/yahoo/baidu/yandex/... when `serpapi` is in `--engines`),
`--no-dedupe`, `--max-fetch-retries`, `--no-js-fallback`, `--json`.

```bash
scout-it multi-search --query "rust vs go performance" --engines duckduckgo,brave --max 15
BRAVE_API_KEY=xxx scout-it list-engines   # check what's configured
```

### Credential setup — `scout-it config`

Several commands need an API key or token (multi-engine search, GitHub Discussions/code search,
Discord). Instead of exporting environment variables every session, run:

```bash
scout-it config              # interactive wizard -- Enter to skip any key you don't have
scout-it config --show       # check what's configured (no secrets printed)
scout-it config --clear GITHUB_TOKEN   # remove one stored key
scout-it config --clear-all            # remove everything
```

Values are stored at `~/.data-scout/credentials.json` (owner-only file permissions on POSIX) and
loaded automatically on every future run. A real environment variable always takes precedence
over a stored value, so CI/scripting setups that export env vars directly are unaffected. Every
command that needs a key tells you exactly which one and how to get it if it isn't configured yet.

### GitHub extraction

Uses GitHub's official REST + GraphQL APIs (no scraping). Works unauthenticated at 60
requests/hour; set `GITHUB_TOKEN` (a personal access token, no special scopes needed for public
repos) for 5,000/hour. GitHub Discussions specifically **requires** `GITHUB_TOKEN` — GraphQL has
no anonymous access at all, even for public repos, which is a GitHub platform rule. Run
`scout-it config` to store `GITHUB_TOKEN` once instead of exporting it every session.

| Command | What it does |
|---|---|
| `github-repo --repo owner/repo` | **Full repo overview by default**: metadata, branches, ~commit count, accurately-split open issue/PR counts, top contributors, latest release, language breakdown. Pass `--quick` for just the fast single-call metadata. Pass `--file-tree` for the full, untruncated file tree (capped by `--max-chars`/`--max-size` if the repo is huge — mutually exclusive, error if both given). |
| `github-commits --repo owner/repo [--branch][--path][--author][--since][--until][--max]` | List commits (full, untruncated commit messages) |
| `github-commit --repo owner/repo --sha SHA` | **Full diff**: every changed file, +/- counts, raw unified `patch` text AND a structured `patch_lines` array (each line tagged `added`/`removed`/`context`/`hunk_header`) |
| `github-pr --repo owner/repo --number N` | PR metadata + full diff/changed files (same `patch_lines` structuring) |
| `github-prs --repo owner/repo [--state][--sort][--max]` | List pull requests (draft status, base/head branch — PR-specific fields `github-issues` doesn't carry) |
| `github-issues --repo owner/repo [--state][--labels][--max]` | List issues |
| `github-issue --repo owner/repo --number N` | Full issue body + all comments |
| `github-file --repo owner/repo --path PATH [--ref REF]` | Fetch & decode one file's contents |
| `github-folder --repo owner/repo --path src/ [--no-recursive][--include-content][--max-files][--max-chars/--max-size][--save-path-dir]` | List (and optionally fetch) every file under a folder. `--max-files` requires `--include-content` (error otherwise); without `--max-files`, `--include-content` fetches ALL files found. `--save-path-dir` (requires `--include-content`) also writes fetched files to disk, preserving the repo-relative tree. Each fetched file gets a `detected_type` (python/markdown/json/yaml/etc.) |
| `github-search-code --query "..."` | Code search (needs `GITHUB_TOKEN`, 10 req/min) |
| `github-search-repos --query "language:python stars:>1000"` | Repo search — each hit carries the same full metadata as `github-repo` |
| `github-discussions --repo owner/repo` | List discussions (**requires** `GITHUB_TOKEN`) |

```bash
scout-it github-repo --repo pytorch/pytorch              # full overview: branches, contributors, releases, etc.
scout-it github-commit --repo psf/requests --sha <sha>   # full diff for one commit, line-by-line +/- structure
scout-it github-folder --repo psf/requests --path src/ --include-content --max-files 10
GITHUB_TOKEN=ghp_xxx scout-it github-discussions --repo pytorch/pytorch
```

### Social / platform commands

| Command | Tier | Needs |
|---|---|---|
| `telegram-channel --channel NAME [--max]` | 0 — works now | nothing (public `t.me/s/` preview; retries 3x then falls back to a richer parser if 0 posts found) |
| `telegram-channel --query "..." [--max][--posts-per-channel]` | 0 — works now | nothing (finds public channels via a `site:t.me` search) |
| `discord-channel --channel-id ID [--max]` | 1 — needs a key | `DISCORD_BOT_TOKEN` (bot must be in the server) |
| `reddit-search --query "..." [--subreddit][--max]` | 2 — best-effort | Reddit blocks most anonymous requests as of 2026; optionally set `REDDIT_COOKIE` |

```bash
scout-it telegram-channel --channel durov --max 10
scout-it telegram-channel --query "machine learning" --max 10   # find & preview matching public channels
DISCORD_BOT_TOKEN=xxx scout-it discord-channel --channel-id 123456789012345678
scout-it reddit-search --query "python" --subreddit programming   # best-effort, see --help
```

Discord intentionally has no `--query` topic-search mode: unlike Telegram's public preview pages,
Discord has no anonymous read API of any kind — you always need a bot already invited into the
specific server, so there's no cross-server search this library could legitimately offer.

Twitter/X, Instagram, TikTok, and similar platforms are **not implemented** — none of them
currently offer a working zero-config or affordable-API path (all require either a paid official
API or a logged-in browser session with cookie management, which is out of scope for this
library). Adding one for real would mean either paying for API access or building an
authenticated Playwright session manager — happy to scope that separately if you need it.

## Detailed Search Documentation

For comprehensive documentation on each search type with all available options, examples, and advanced usage, see the detailed guides in `docs/search/`:

| Document | Coverage |
|----------|----------|
| **[Extended Options Reference](./docs/search/OPTIONS.md)** | ⭐ START HERE - Complete reference of ALL supported parameters for all search types |
| [Web Search Guide](./docs/search/websearch.md) | Full web search documentation with extraction strategy, 6+ examples, Python API |
| [Image Search Guide](./docs/search/imagesearch.md) | Complete image filtering (dimensions, colors, layouts, licenses), 7+ examples |
| [News Search Guide](./docs/search/newssearch.md) | News aggregation with date filtering, monitoring, analysis examples |
| [Video Search Guide](./docs/search/videosearch.md) | Video search with duration/resolution filtering, playlist creation |
| [URL Fetch Guide](./docs/search/fetch.md) | Single URL extraction with content cleaning, batch processing |

### All Supported Options by Search Type

Quick reference of common options:
- **Query** (`--query, -q`): Search term (required)
- **Results** (`--max-results, -m`): Limit results (default: 10)
- **Output** (`--out, -o`): Save to file (defaults provided per type)
- **JSON** (`--json`): Output raw JSON to stdout
- **Timeout** (`--timeout`): Extraction timeout in seconds (default: 5)
- **Region** (`--region`): Geographic region (default: `us-en`)
- **Safe Search** (`--safesearch`): Filter level: `on|moderate|off` (default: `moderate`)
- **Time Filter** (`--timelimit`): Time range: `d|w|m|y`
- **Image Dimensions** (`--min-width`, `--max-width`, `--min-height`, `--max-height`): Image search only
- **Workers** (`--workers, -w`): Parallel extraction workers for web search
- **Retry** (`--retry-attempts`, `--retry-backoff`): Automatic retry configuration

See [Extended Options Reference](./docs/search/OPTIONS.md) for complete parameter listings with all enums and examples.

## Programmatic API

You can import and use the search engines and extraction functions directly from the package.

### Web Search with Content Extraction

```python
from scout_it.extraction import EnterpriseSearchEngine
from scout_it.cleaner import process_results

engine = EnterpriseSearchEngine()
results = engine.search(
    query="machine learning",
    max_results=5,
    extraction_timeout=10
)

# Clean and structure results
cleaned_results = process_results(results)

for result in cleaned_results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Quality Score: {result['quality_score']}")
    print()
```

### Image Search

```python
from scout_it.extraction import ImageSearchEngine

engine = ImageSearchEngine()
results = engine.search(
    query="mountain landscape",
    max_results=10,
    min_width=1024,
    min_height=768
)

for result in results:
    print(f"Title: {result.title}")
    print(f"Size: {result.dimensions}")
    print(f"Image URL: {result.image_url}")
    print()
```

### Direct Content Extraction from URL

```python
from scout_it.extraction import ExtractionEngine

engine = ExtractionEngine()
content, method, confidence = engine.extract(
    url="https://example.com/article",
    timeout=5
)

print(f"Extraction Method: {method}")
print(f"Confidence Score: {confidence:.2%}")
print(f"Content:\n{content[:500]}...")
```

### Text Cleaning and Processing

```python
from scout_it.cleaner import advanced_clean_text

raw_text = "   Hello   world   with   extra    spaces   "
cleaned = advanced_clean_text(raw_text)
print(cleaned)  # Output: "Hello world with extra spaces"
```

## Output Files and JSON Shapes

### Where output goes, and in what format

Every command's default `--out` path lives under `.data-scout/` (created automatically next to
wherever you run the command), e.g. `.data-scout/web_search_results.json` — an explicit
`--out some/path.json` is always honored exactly as given instead.

**Line-length-safe JSON**: any string field over 500 characters (a long article body, extracted
page content, etc.) is broken into an array of <=500-char chunks at word boundaries instead of
one giant single-line value — still fully standard, valid JSON (an array just serializes one
element per line). Diff `patch` text is left as-is since it already has a structured `patch_lines`
breakdown for readability instead.

**Markdown export**: add `--markdown` to any command to save a readable `.md` file instead of
JSON (tables for lists of uniform records, fenced code blocks for file/diff content). `--out
file.md` also works without `--markdown`. Combining `--markdown` with an explicit `--out
....json` is rejected with a clear error.

```bash
scout-it github-repo --repo psf/requests --markdown          # .data-scout/github_repo_results.md
scout-it web-search --query "rust vs go" --out report.md     # markdown, no --markdown flag needed
scout-it web-search --query "x" --markdown --out result.json # ERROR: conflicting formats
```

### Web Search Output (`results.json`)

Top-level structure:

- `query`
- `search_type` = `web`
- `parameters`
- `stats`
- `structured_results` (list)

Each item in `structured_results` contains cleaned and structured text fields from `main_content_cleaner.py`, including:

- `title`, `url`, `final_url`
- `cleaned_content`
- `paragraphs`, `content_sections`
- `top_keywords`
- `readability_metrics`
- `quality_signals`
- `content_quality_score`

### Image Search Output (`image_search_results.json`)

Top-level structure:

- `query`
- `search_type` = `image`
- `parameters`
- `stats`
- `image_results`

Each image item includes:

- `title`
- `image_url`
- `source_url`
- `thumbnail_url`
- `width`, `height`
- `image_size`

### News/Video Output

`news_results.json` and `video_results.json` include:

- `query`
- `search_type` (`news` or `video`)
- `parameters`
- `stats`
- result array (`news_results` or `video_results`)

### Fetch URL Output

`url_fetch_result.json` includes:

- `url`
- `search_type` = `fetch`
- `result` object containing extracted/cleaned fields and fetch stats

## Retry and Fallback Behavior

scout-it retries and falls back at **two independent layers**, and it's worth understanding the difference:

1. **Search/discovery layer** — did DDGS return any results at all?
2. **Content-fetch layer** — for each individual result URL, can we actually download and extract its page content?

### 1. Search-layer retry (zero-results retry)

`web-search`, `image-search`, `news-search`, and `video-search` all share the same retry-on-zero-results behavior (via `_ddgs_list_search_with_retry`):

- Attempt 1 uses your configured options (`region`, `safesearch`, `timelimit`, etc.)
- If DDGS returns 0 results, later attempts progressively relax filters (drop `timelimit`, then relax `safesearch`) to maximize the chance of a non-empty result set
- Stops as soon as an attempt returns results
- Controlled by `--retry-on-zero/--no-retry-on-zero`, `--retry-attempts` (default `2`), `--retry-backoff` (default `1.0`s)
- **Previously**, only `web-search`/`image-search` had this. `news-search` made exactly one DDGS attempt and `video-search` had no retry logic or flags at all — both now have full parity.

### 2. Content-fetch layer: the `fetch_resilient()` fallback chain

Every individual page fetch — web-search result extraction, news-search article extraction, `fetch-url`, and the YouTube page fetch behind `video-extract` — goes through a shared **three-tier fallback chain**:

```
Tier 1: requests            (up to --max-fetch-retries attempts, UA rotation, backoff)
   │  fails / looks bot-blocked (403/429/503, captcha, "enable JS", tiny body, etc.)
   ▼
Tier 2: Playwright (headless Chromium)   (up to --max-fetch-retries attempts)
   │  fails, or Playwright isn't installed, or the failure was a pure
   │  connection/DNS-level error where a browser can't do any better
   ▼
Tier 3: last-resort basic request        (one attempt, minimal non-fingerprinted headers)
```

Notes on the design:

- **Tier 2 is skipped automatically** when every Tier 1 attempt failed at the connection level (DNS failure, connection refused, timeout) rather than getting an actual HTTP response — a browser hitting the same broken network path won't succeed either, so this avoids wasting 3× browser launches (~tens of seconds) on an unreachable host. It's still tried whenever at least one Tier 1 attempt *did* get a response (e.g. a 403 or a bot-check page), since that's exactly the case Playwright is good at getting past.
- Every result records which tier actually succeeded, e.g. `extraction_method: "trafilatura (playwright)"`, so you can see in the output how much the fallback chain is being used.
- `--no-js-fallback` disables Tier 2 entirely (useful if Playwright/Chromium isn't installed in your environment, or you want fast-fail behavior).
- Playwright is optional: `pip install scout-it[js-render] && playwright install chromium`. If it isn't installed, Tier 2 is skipped with a note in the diagnostics and the chain still falls through to Tier 3.
- `fetch-url --js-render` skips straight to Tier 2 instead of trying `requests` first (useful when you already know a page needs JS).

### DDGS Signature Compatibility

The project prefers the `ddgs` package and falls back to the older `duckduckgo_search` package name automatically, and attempts multiple call signatures for DDGS methods to support version differences between them.

## Image Dimension Filtering Rules

When any dimension filter is enabled:

- Images missing width/height are excluded
- Range checks are inclusive
- Invalid negative/unknown numeric dimensions are treated as missing

If no dimension filters are enabled:

- Missing dimensions are allowed

## Examples

### Example A: Web Search for Articles

```bash
scout-it web-search --query "artificial intelligence" --max-results 5
```

**Output:**
```
Title: AI Article 1
URL: https://example.com/ai-1
Confidence: 95%
Content: [extracted article text...]
📂 Results saved to: /path/to/results.json
```

### Example B: High-Resolution Image Search

```bash
scout-it image-search --query "mountain scenery" --max-results 10 --min-width 1920 --min-height 1080
```

### Example C: News Search

```bash
scout-it news-search --query "technology breakthroughs" --max-results 5
```

### Example D: Video Search

```bash
scout-it video-search --query "python programming tutorial" --max-results 5
```

### Example E: Extract Content from Specific URL

```bash
scout-it fetch-url --url "https://en.wikipedia.org/wiki/Artificial_intelligence"
```

### Example F: Programmatic Web Search (Python)

```python
from scout_it.extraction import EnterpriseSearchEngine

engine = EnterpriseSearchEngine()
results = engine.search(
    query="Python web frameworks",
    max_results=5,
    extraction_timeout=10
)

for result in results:
    print(f"{result.title} ({result.confidence_score:.0%})")
    print(f"{result.url}")
```

## Testing

Run all tests:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=scout_it --cov-report=html
```

Current test suite includes:

- 38+ comprehensive test cases
- Web search functionality
- Image search with dimension filtering
- News and video search
- URL extraction and content cleaning
- Confidence scoring
- Error handling and timeouts
- Mock API responses (no external API calls)

**Minimum Coverage Requirement:** 80%

## Troubleshooting

### 1) No search results returned

**Check:**
- Verify internet connection
- Try a different, simpler query
- Check DuckDuckGo is accessible

### 2) Low confidence scores

**Possible causes:**
- Website uses heavy JavaScript
- Poor HTML structure
- Extraction method not suitable for site

**Solutions:**
- Increase extraction timeout: `--timeout 15`
- Check if content is accessible in browser

### 3) Slow extraction times

**Solutions:**
- Reduce `--max-results` to fewer articles
- Decrease `--timeout` for faster (but less complete) results
- Check your internet speed

### 4) Package installation issues

**If getting import errors:**
```bash
# Reinstall in development mode
pip install -e ".[dev]"

# Or verify installation
python -c "from scout_it import EnterpriseSearchEngine; print('OK')"
```

### 5) Python version mismatch

**Check installed Python:**
```bash
python --version
```

**Required:** Python 3.8+

## Performance Notes

- Web extraction uses parallel workers (`--workers`)
- Higher `--max` increases runtime and network load
- Content extraction quality favors richer pages and can vary by domain
- Retry increases resilience but can increase total runtime

## Limitations

- Actual DuckDuckGo support depends on installed package versions (`ddgs`, `duckduckgo_search`)
- Some DDGS capabilities (for example maps/answers/suggestions) are not guaranteed in all installed versions
- `fetch-url` returns sanitized errors by design (`fetch_url failed`) to avoid leaking internals
- Search output quality depends on network, source pages, and extractor heuristics

---

If you extend the CLI with additional DDGS methods (for example maps), update this README by adding:

1. New query type in the Query Types section
2. Full CLI option reference
3. Example commands
4. JSON output shape
