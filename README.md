# scout-it

[![PyPI version](https://img.shields.io/badge/version-1.5.0-blue)](https://pypi.org/project/scout-it/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Enterprise-grade web search, content extraction, and data collection toolkit for AI pipelines and research.**

scout-it searches the web via DuckDuckGo (and Brave/Bing/Google/SerpAPI), fetches and extracts page content through a multi-tier resilience chain, cleans and structures the results, and outputs JSON or Markdown — all from a single CLI command.

---

## Table of Contents

- [What is scout-it?](#what-is-scout-it)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
  - [Global Help & Version](#global-help--version)
  - [Search Commands](#search-commands)
  - [GitHub Commands](#github-commands)
  - [Social Commands](#social-commands)
  - [Utility Commands](#utility-commands)
- [Credentials & Configuration](#credentials--configuration)
- [Resilience Layer](#resilience-layer)
- [Programmatic API](#programmatic-api)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

---

## What is scout-it?

scout-it is a Python CLI toolkit that provides a complete search-to-structured-data pipeline:

1. **Search** — DuckDuckGo (web, news, images, videos) plus Brave, Bing, Google Custom Search, and SerpAPI via multi-search
2. **Fetch** — Resilient page fetching through a 5-tier fallback chain (requests → TLS impersonation → Playwright → bandit-picked tier → alternate sources)
3. **Extract** — Multi-strategy content extraction (Trafilatura, justext, BoilerPy3, Readability, BeautifulSoup)
4. **Clean** — Confidence-scored, structured text output
5. **Output** — JSON or Markdown files, or stdout

It is designed for data collection, AI training pipelines, research, and any workflow where you need clean web content at scale.

---

## Features

- **8 search modes**: web, news, images, videos, YouTube metadata, single URL fetch, multi-engine search, engine listing
- **12 GitHub extractors**: repos, commits, PRs, issues, discussions, code search, repo search, files, folders
- **3 social platform extractors**: Telegram channels (public), Discord channels (bot), Reddit search
- **5-tier content extraction**: Trafilatura → justext → BoilerPy3 → Readability → BeautifulSoup, with confidence scoring
- **5-tier resilience chain**: plain requests → TLS impersonation → Playwright JS render → bandit-strategy cache → alternate source fallback (AMP/mobile/Wayback)
- **Auto-rotating proxy pool** via `PROXY_LIST` env var
- **DNS-over-HTTPS fallback** on DNS-looking errors
- **Strategy bandit**: per-domain tier selection based on past success history
- **Zero-result retry**: progressively relaxes filters when a search returns nothing
- **Parallel extraction**: ThreadPoolExecutor for concurrent page fetching
- **Markdown and JSON output** with configurable paths under `.scout-it/`
- **Output path routing**: all output files default to `.scout-it/`; `--out` with a bare filename routes there too

---

## Installation

### From PyPI (recommended)

```bash
pip install scout-it

# Optional: TLS impersonation support
pip install scout-it[tls-impersonate]
```

### From source

```bash
git clone https://github.com/gajjalaashok75-UI/scout-it.git
cd scout-it
pip install -e ".[dev]"
```

### Verify installation

```bash
scout-it --version          # Shows scout-it 1.5.0
scout-it -v                 # Short flag
scout-it --help             # Full command list
```

### Playwright (required for JS-render fallback)

```bash
playwright install chromium
```

---

## Quick Start

```bash
# Web search with content extraction
scout-it web-search --query "machine learning transformers" --max 3

# Web search with Markdown output
scout-it web-search --query "Python async programming" --markdown

# Image search with dimension filters
scout-it image-search --query "mountain landscape" --min-width 1920 --min-height 1080

# Single URL fetch with full extraction
scout-it fetch-url --url "https://example.com/article"

# Multi-engine search (requires API keys)
scout-it multi-search --query "rust vs go" --engines duckduckgo,brave

# YouTube metadata and transcript
scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments

# Use resilience features for difficult sites
scout-it fetch-url --url "https://heavy-js-site.com" --js-render --tls-impersonate

# Check what's configured
scout-it doctor
```

---

## CLI Reference

### Global Help & Version

```bash
scout-it --help              # List all subcommands
scout-it <command> --help    # Flags for one command
scout-it --version           # Show version
```

### Search Commands

#### `web-search`

DuckDuckGo text search plus full content extraction and cleaning for every result.

```bash
scout-it web-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max results (1-100) |
| `--workers, -w` `<n>` | Parallel workers for content extraction |
| `--region` `<region>` | DuckDuckGo region (e.g. us-en, wt-wt) |
| `--safesearch` `<level>` | Safe search: on, moderate, off |
| `--timelimit` `<range>` | Time limit: d, w, m, y |
| `--backend` `<backend>` | DDGS backend: auto, html, lite |
| `--no-retry-on-zero` | Disable retries on 0 results (retries on by default) |
| `--retry-attempts` `<n>` | Retry attempts when 0 successful extractions |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier |
| `--no-js-fallback` | Disable Playwright fallback |
| `--enable-alternate-source` | Try AMP/mobile/print/Wayback variants on failure |
| `--no-dns-fallback` | Disable DNS-over-HTTPS retry (on by default) |
| `--tls-impersonate` | Browser-accurate TLS/JA3 fingerprint tier (needs `scout-it[tls-impersonate]`) |
| `--persistent-profile` | Persistent Playwright profile (cookies survive runs) |
| `--profile-name` `<name>` | Persistent profile name (with `--persistent-profile`) |
| `--use-bandit` | Skip to best-performing tier per domain from history |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/struct_format_results.json`) |

#### `news-search`

DuckDuckGo news search with article text extraction.

```bash
scout-it news-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max news items (1-50) |
| `--workers` `<n>` | Parallel workers for content extraction |
| `--region` `<region>` | DuckDuckGo region |
| `--safesearch` `<level>` | Safe search: on, moderate, off |
| `--timelimit` `<range>` | Time limit: d, w, m, y |
| `--no-retry-on-zero` | Disable retries on 0 results |
| `--retry-attempts` `<n>` | Retry attempts on zero results |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier |
| `--no-js-fallback` | Disable Playwright fallback |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/news_search_results.json`) |

#### `image-search`

DuckDuckGo image search with dimension, color, and license filters.

```bash
scout-it image-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max images (1-50) |
| `--region` `<region>` | DuckDuckGo region |
| `--safesearch` `<level>` | Safe search: on, moderate, off |
| `--timelimit` `<range>` | Time limit: d, w, m, y |
| `--size` `<size>` | Image size: Small, Medium, Large, Wallpaper |
| `--color` `<color>` | Color filter |
| `--type-image` `<type>` | Image type: photo, clipart, gif, transparent, line |
| `--layout` `<layout>` | Layout: Square, Tall, Wide |
| `--license-image` `<license>` | License filter |
| `--min-width` `<px>` | Minimum width |
| `--max-width` `<px>` | Maximum width |
| `--min-height` `<px>` | Minimum height |
| `--max-height` `<px>` | Maximum height |
| `--download, -d` | Download images to disk |
| `--download-dir` `<path>` | Download directory (default: `.scout-it/downloaded_images`) |
| `--no-retry-on-zero` | Disable retries on 0 results |
| `--retry-attempts` `<n>` | Retry attempts when 0 valid images found |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/image_search_results.json`) |

#### `video-search`

DuckDuckGo video search with duration and resolution filters.

```bash
scout-it video-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max videos (1-50) |
| `--region` `<region>` | DuckDuckGo region |
| `--safesearch` `<level>` | Safe search: on, moderate, off |
| `--timelimit` `<range>` | Time limit: d, w, m, y |
| `--resolution` `<res>` | Resolution: high, standard |
| `--duration` `<duration>` | Duration: short, medium, long |
| `--license-videos` `<license>` | License filter |
| `--no-retry-on-zero` | Disable retries on 0 results |
| `--retry-attempts` `<n>` | Retry attempts when 0 results found |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/video_search_results.json`) |

#### `video-extract`

YouTube metadata and subtitles/transcript extraction.

```bash
scout-it video-extract --url "<youtube-url>" [options]
```

| Flag | Description |
|------|-------------|
| `--url` `<url>` | Video URL to extract (e.g. `https://www.youtube.com/watch?v=VIDEO_ID`) |
| `--subtitle-lang` `<code>` | Subtitle language code (default: en) |
| `--segments` | Include subtitle segments with timestamps |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier |
| `--no-js-fallback` | Disable Playwright fallback |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/video_extract_results.json`) |
| `--json` | Output raw JSON to stdout |

#### `fetch-url`

Direct extraction from a single URL through the full resilience chain.

```bash
scout-it fetch-url --url "https://example.com" [options]
```

| Flag | Description |
|------|-------------|
| `--url, -u` `<url>` | URL to fetch |
| `--timeout` `<seconds>` | Extraction timeout (increase for JS-rendered SPAs) |
| `--max-chars` `<n>` | Max characters to extract (e.g. 10000) |
| `--max-size` `<size>` | Max response size (e.g. 100kb, 1mb, 500mb) |
| `--raw-html` | Return raw HTML instead of extracted content |
| `--js-render` | Skip straight to Playwright rendering |
| `--no-js-fallback` | Disable Playwright fallback |
| `--enable-alternate-source` | Try AMP/mobile/print/Wayback variants on failure |
| `--max-retries` `<n>` | Retry attempts per fetch tier |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/url_fetch_result.json`) |
| `--json` | Output raw JSON to stdout |

#### `multi-search`

Queries several search engines in parallel, merges and dedupes by URL, then runs content extraction.

```bash
scout-it multi-search --query "<text>" --engines duckduckgo,brave [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--engines` `<list>` | Comma-separated engines: duckduckgo, brave, bing, google, serpapi |
| `--max, -m` `<n>` | Max merged results |
| `--workers, -w` `<n>` | Parallel content-extraction workers |
| `--serpapi-engine` `<engine>` | Underlying engine for SerpAPI (google/bing/yahoo/baidu/yandex) |
| `--no-dedupe` | Keep duplicate URLs across engines |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier |
| `--no-js-fallback` | Disable Playwright fallback |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/multi_search_results.json`) |
| `--json` | Output raw JSON to stdout |

#### `list-engines`

Show which search engines are configured and available.

```bash
scout-it list-engines
```

No flags.

---

### GitHub Commands

All GitHub commands require `GITHUB_TOKEN` for high rate limits (5,000 req/hour). Without a token, unauthenticated access works at 60 req/hour. `github-discussions` and `github-search-code` require a token — they have no anonymous access.

```bash
scout-it github-repo --repo owner/repo [options]
scout-it github-commits --repo owner/repo [options]
scout-it github-commit --repo owner/repo --sha SHA [options]
scout-it github-pr --repo owner/repo --number N [options]
scout-it github-prs --repo owner/repo [options]
scout-it github-folder --repo owner/repo --path src/ [options]
scout-it github-issues --repo owner/repo [options]
scout-it github-issue --repo owner/repo --number N [options]
scout-it github-file --repo owner/repo --path PATH [options]
scout-it github-search-code --query "..." [options]
scout-it github-search-repos --query "..." [options]
scout-it github-discussions --repo owner/repo [options]
```

| Command | Description |
|---------|-------------|
| `github-repo` | Full repo overview: metadata, branches, commit count, issue/PR counts, contributors, releases, languages, file tree. `--quick` for fast single-call metadata; `--file-tree` for the full tree. |
| `github-commits` | List commits with full untruncated messages. Filter by `--branch`, `--path`, `--author`, `--since`, `--until`. |
| `github-commit` | Full details for one commit: stats, changed files, unified diff. `--no-patch` to skip diff text. |
| `github-pr` | Pull request with full diff and changed files. `--no-diff` to skip diff. |
| `github-prs` | List PRs with PR-specific fields. Filter by `--state`, `--sort`. |
| `github-folder` | List (and optionally fetch) every file under a folder. `--include-content` fetches file bodies; `--save-path-dir` writes them to disk. |
| `github-issues` | List issues. Filter by `--state`, `--labels`. `--include-prs` also returns pull requests. |
| `github-issue` | One issue with full body and comments. `--no-comments` to skip comments. |
| `github-file` | Fetch a single file's contents. `--ref` to specify a branch/tag. |
| `github-search-code` | Code search across GitHub. Requires token. |
| `github-search-repos` | Repository search with full metadata on each hit. | 
| `github-discussions` | List GitHub Discussions. Requires token — GraphQL has no anonymous access. |

All GitHub commands support `--out`, `--markdown`, and `--json`.

---

### Social Commands

```bash
# Telegram public channel — tier 0 (works now, needs nothing)
scout-it telegram-channel --channel NAME [--max] [--max-fetch-retries] [--out] [--markdown] [--json]
scout-it telegram-channel --query "..." [--max] [--posts-per-channel] [--out] [--markdown] [--json]

# Discord channel — tier 1 (needs DISCORD_BOT_TOKEN)
scout-it discord-channel --channel-id ID [--max] [--before] [--out] [--markdown] [--json]

# Reddit search — tier 2 (best-effort, optional REDDIT_COOKIE)
scout-it reddit-search --query "..." [--subreddit] [--sort] [--max] [--out] [--markdown] [--json]
```

Unsupported platforms (return clear errors): Twitter/X, Instagram, TikTok.

---

### Utility Commands

#### `config`

Interactive credential management wizard.

```bash
scout-it config                  # Interactive wizard
scout-it config --show           # Check what's configured (never prints secrets)
scout-it config --clear KEY      # Remove one stored key
scout-it config --clear-all      # Remove all stored credentials
```

#### `stats`

Per-domain fetch-strategy statistics from the bandit cache.

```bash
scout-it stats                   # Summary for all domains
scout-it stats --domain DOMAIN   # Stats for one domain
scout-it stats --export PATH     # Full stats dump as JSON
scout-it stats --reset DOMAIN    # Forget history for one domain
scout-it stats --reset-all       # Forget all history
```

#### `doctor`

Self-check for Playwright availability, proxy config, cache health, credentials, DNS/connectivity.

```bash
scout-it doctor
```

---

## Credentials & Configuration

scout-it reads credentials from environment variables. Use `scout-it config` to set them interactively (stored in `~/.scout-it/config.ini`). Environment variables take precedence.

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub API access (5,000 req/hour with token; required for discussions & code search) |
| `BRAVE_API_KEY` | Brave Search API for multi-search |
| `BING_API_KEY` | Azure Bing Search API for multi-search |
| `GOOGLE_API_KEY` | Google Custom Search JSON API (paired with `GOOGLE_CSE_ID`) |
| `GOOGLE_CSE_ID` | Google Programmable Search Engine ID |
| `SERPAPI_KEY` | SerpAPI for proxied Google/Bing/Yahoo/Baidu/Yandex results |
| `DISCORD_BOT_TOKEN` | Bot token for Discord channel extraction |
| `REDDIT_COOKIE` | Optional cookie to improve Reddit search reliability |
| `PROXY_LIST` | Comma-separated proxy URLs for auto-rotating proxy pool |

### Credential Precedence

1. Environment variable (highest)
2. `~/.scout-it/config.ini` (set via `scout-it config`)
3. Built-in default (if any)

---

## Resilience Layer

scout-it uses a multi-tier fetch strategy to extract content from even the most difficult sites. Each tier is tried in order; if all tiers fail, the command returns a clear error.

| # | Tier | What it does | When it activates |
|---|------|-------------|-------------------|
| 1 | **requests** | Standard HTTP request with rotating User-Agent | Always tried first |
| 2 | **TLS impersonation** | Browser-accurate TLS/JA3 fingerprint via `curl_cffi` | `--tls-impersonate` |
| 3 | **Playwright** | Full browser rendering (JS, SPAs, Cloudflare) | Automatic on requests failure, or `--js-render` |
| 4 | **Bandit** | Skips to best-performing tier per domain | `--use-bandit` |
| 5 | **Alternate sources** | AMP/mobile/print URL variants + Wayback Machine | `--enable-alternate-source` |

Additional protections:

- **DNS-over-HTTPS fallback**: Automatically retries failed fetches via DoH when the error looks DNS-related (on by default; disable with `--no-dns-fallback`)
- **Zero-result retry**: When a search returns 0 results, retries with progressively relaxed filters (on by default; disable with `--no-retry-on-zero`)
- **Proxy pool**: Auto-rotates through proxies from `PROXY_LIST` env var

---

## Programmatic API

scout-it can be used as a Python library:

```python
from scout_it import (
    EnterpriseSearchEngine,
    ImageSearchEngine,
    ExtractionEngine,
    ContentCleaner,
)

# Search and extract
engine = EnterpriseSearchEngine()
results = engine.search_and_extract(
    query="machine learning transformers",
    max_results=3,
)

# Each result has: title, url, content, confidence, score, sentiment
for r in results:
    print(f"{r.title} (confidence: {r.confidence:.2f})")
    print(r.content[:200])
    print("---")

# Image search
img_engine = ImageSearchEngine()
images = img_engine.search(
    query="mountain landscape",
    max_results=5,
    min_width=1920,
    min_height=1080,
)

# Direct URL extraction
extractor = ExtractionEngine()
content = extractor.extract_content(
    url="https://example.com/article",
    max_fetch_retries=3,
)
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `EnterpriseSearchEngine` | Web/news search + parallel content extraction |
| `ImageSearchEngine` | Image search with dimension/color/license filters |
| `ExtractionEngine` | Multi-strategy URL content extraction |
| `ContentCleaner` | Text cleaning, structuring, and confidence scoring |

---

## Project Structure

```
scout-it/
├── scout_it/                    # Main package
│   ├── __init__.py              # Public API + exports
│   ├── cli.py                   # Argeparse CLI (26 subcommands)
│   ├── extraction.py            # Search engines + extraction
│   ├── cleaner.py               # Content cleaning
│   ├── config.py                # Credential management
│   ├── output.py                # Output path routing + markdown rendering
│   ├── proxy_pool.py            # Auto-rotating proxy pool
│   ├── social.py                # Telegram, Discord, Reddit extraction
│   ├── github_extract.py        # All 12 GitHub extractors
│   ├── video_utils.py           # YouTube metadata extraction
│   ├── engines.py               # Brave, Bing, Google, SerpAPI engine wrappers
│   └── domain_stats.py          # Strategy bandit cache persistence
├── tests/                       # Test suite (151+ tests)
│   ├── test_cli.py
│   ├── test_output.py
│   ├── test_social.py
│   ├── test_github_extract.py
│   ├── test_advanced_evasion.py
│   └── ...
├── docs/                        # Search-specific documentation
├── scout-it-website/            # React TypeScript landing page & docs site
├── pyproject.toml
├── setup.py
├── CHANGELOG.md
├── README.md
├── AGENTS.md
└── LICENSE
```

---

## Testing

```bash
# Run full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=scout_it --cov-report=term-missing

# Run specific test file
pytest tests/test_output.py -v
```

Minimum coverage target: 80%. The test suite includes unit tests, integration tests with mocked APIs, and real tests for live CLI commands.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError: playwright` | Playwright not installed | `pip install playwright && playwright install chromium` |
| Empty results / 0 returned | Site blocks requests | Try `--tls-impersonate` or `--js-render` |
| `github-discussions` returns error | No token | Set `GITHUB_TOKEN` — GraphQL requires authentication |
| DNS-looking error on fetch | DNS resolution failed | Retries automatically via DoH; disable with `--no-dns-fallback` |
| `PROXY_LIST` not working | Bad proxy format | Use `http://user:pass@host:port` format, comma-separated |
| Content extraction too short | JS-rendered page | Add `--js-render` to enable Playwright |

---

## Limitations

- **YouTube only** for `video-extract` — other platforms return `unsupported_platform` error
- **Telegram**: public channels only (via `t.me/s/` preview); no private channel access
- **Discord**: requires a bot token; no cross-server topic search
- **Reddit**: reliability varies as of 2026 — Reddit blocks most anonymous requests
- **GitHub Discussions**: requires a token (GraphQL-only, no anonymous access)
- **GitHub code search**: 10 requests/minute rate limit even with a token
- **Multi-search**: requires API keys for Brave, Bing, Google, and/or SerpAPI engines
- **No Twitter/Instagram/TikTok**: these platforms are not supported and return clear errors
- **scout-it must be installed** (`pip install`) — standalone script use is not supported
