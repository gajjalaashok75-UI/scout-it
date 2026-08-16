# scout-it

[![PyPI version](https://img.shields.io/badge/version-2.0.0-blue)](https://pypi.org/project/scout-it/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Enterprise-grade web search, content extraction, and data collection toolkit for AI pipelines and research.**

scout-it searches the web via DuckDuckGo (and Brave/Bing/Google/SerpAPI), fetches and extracts page content through a multi-tier resilience chain, cleans and structures the results, and outputs JSON or Markdown — all from a single CLI command.

---

## Table of Contents

- [What is scout-it?](#what-is-scout-it)
- [Architecture](#architecture)
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

### Latest Features (August 2026)

- **🔥 Unified extraction engine**: web-search and news-search now use identical `EnterpriseSearchEngine` with all resilience features
- **⚡ Browser pool optimization**: 3-5x faster extraction by reusing browser instances (3-8s → 0.5s per page)
- **🚀 Staged ranking**: Discovery-first pipeline for 70-85% faster searches (10s vs 30-60s)
- **📊 Snippets mode**: `--snippets` flag returns ranked snippets only (~10x faster than full extraction)
- **🌐 Category support**: `--category` flag with 65 web RSS feeds and 50+ news sources across 13 categories
- **🎯 Quality escalation**: Auto-retries with Playwright when low-quality extraction detected
- **🧠 Domain learning**: Per-domain strategy memory with Thompson sampling for optimal tier selection
- **🎥 Video search YouTube fallback**: when DuckDuckGo Videos returns nothing (its endpoint is intermittently unreliable), `video-search` automatically falls back to YouTube search so the command reliably returns ranked results
- **🛡️ Thread-safe extraction**: the native C-extension parsers (trafilatura/justext/boilerpy3 via lxml) are now serialized in parallel-extraction paths, eliminating the intermittent `double free`/SIGSEGV crash in `multi-search`

---

## Architecture

```mermaid
graph TB
    subgraph CLI["CLI Layer"]
        CLI_Entry["scout-it &lt;command&gt; [options]"]
        Parser["Argparse<br/>28 subcommands"]
    end

    subgraph SEARCH["Search Engines"]
        DDG["DuckDuckGo<br/>web / news / images / videos"]
        BRAVE["Brave Search API"]
        BING["Bing Search API"]
        GOOGLE["Google Custom Search"]
        SERP["SerpAPI<br/>(proxied engines)"]
        MULTI["multi-search<br/>parallel + dedupe"]
    end

    subgraph FETCH["Resilience Fetch Chain<br/>(5 tiers)"]
        T1["Tier 1: requests<br/>stdlib HTTP"]
        T2["Tier 2: TLS Impersonation<br/>curl_cffi JA3 fingerprint"]
        T3["Tier 3: Playwright<br/>Full browser JS render"]
        T4["Tier 4: Bandit<br/>domain history pick"]
        T5["Tier 5: Alternate Sources<br/>AMP / mobile / print / Wayback"]
        DNS["DNS-over-HTTPS<br/>fallback on error"]
        PROXY["Proxy Pool<br/>auto-rotate"]
    end

    subgraph EXTRACT["Content Extraction<br/>(5 strategies)"]
        S1["Trafilatura<br/>confidence: 1.0"]
        S2["Justext<br/>confidence: 0.95"]
        S3["BoilerPy3<br/>confidence: 0.90"]
        S4["Readability<br/>confidence: 0.85"]
        S5["BeautifulSoup<br/>confidence: 0.70"]
    end

    subgraph SOCIAL["Social Platforms"]
        TG["Telegram Channel<br/>public t.me/s/"]
        DC["Discord Channel<br/>bot + DDGS"]
        RD["Reddit Search<br/>best-effort"]
        IG["Instagram<br/>DDGS + profile scrape"]
    end

    subgraph GITHUB["GitHub Extractors"]
        GH_REPO["Repo overview"]
        GH_COMMITS["Commits"]
        GH_COMMIT["Single commit + diff"]
        GH_PR["Pull request + diff"]
        GH_PRS["PR list"]
        GH_ISSUES["Issue list"]
        GH_ISSUE["Single issue + comments"]
        GH_FILE["File contents"]
        GH_FOLDER["Folder tree + contents"]
        GH_CODE["Code search"]
        GH_REPOS["Repo search"]
        GH_DISC["Discussions"]
    end

    subgraph OUTPUT["Output Layer"]
        JSON_OUT["JSON files<br/>.scout-it/*.json"]
        MD_OUT["Markdown files<br/>.scout-it/*.md"]
        STDOUT["stdout<br/>--json flag"]
        CLEANER["Cleaner<br/>process_results()"]
    end

    CLI_Entry --> Parser
    Parser --> SEARCH
    Parser --> FETCH
    Parser --> SOCIAL
    Parser --> GITHUB
    SEARCH --> FETCH
    FETCH --> EXTRACT
    EXTRACT --> CLEANER
    CLEANER --> OUTPUT

    style CLI_Entry fill:#4a90d9,color:#fff
    style CLEANER fill:#e6a23c,color:#fff
    style T1 fill:#67c23a,color:#fff
    style T2 fill:#67c23a,color:#fff
    style T3 fill:#67c23a,color:#fff
    style T4 fill:#e6a23c,color:#fff
    style T5 fill:#e6a23c,color:#fff
    style DNS fill:#909399,color:#fff
    style PROXY fill:#909399,color:#fff
```

### Core data flow

| Step | Component | What happens |
|------|-----------|-------------|
| 1. **Search** | DuckDuckGo / multi-search API | Query dispatched to selected engine(s); raw results returned |
| 2. **Fetch** | Resilience chain (5 tiers) | Each URL fetched through tiers until one succeeds; DoH fallback and proxy pool active throughout |
| 3. **Extract** | 5-strategy extraction pipeline | Page HTML processed by each strategy in priority order; first with sufficient confidence wins |
| 4. **Clean** | `process_results()` (cleaner.py) | Extracted text scored, structured, and formatted; confidence, quality, and sentiment metrics computed |
| 5. **Output** | JSON / Markdown writer | Results written to file under `.scout-it/` or to stdout with `--json` |

The entire pipeline supports **parallel extraction** via `ThreadPoolExecutor` (configurable with `--workers`, default 4) and **extraction-only mode** where pre-fetched URLs can be re-extracted without re-fetching.

---

## Features

### Core Capabilities

- **Search modes**: web, news, images, videos, YouTube, single-URL fetch, multi-engine search, Wikimedia search, semantic index/search, source plugins — 28 subcommands total
- **12 GitHub extractors**: repos, commits, PRs, issues, discussions, code search, repo search, files, folders
- **4 social platform extractors** (unified under `social-search`): Telegram channels (public), Discord channels (bot + DDGS), Reddit (RSS-first: subreddit / user / search feeds), Instagram (DDGS query + profile scraping)
- **30+ source plugins**: openalex, arxiv, crossref, semantic_scholar, huggingface, zenodo, wikidata, gdelt, internet_archive, and more (all free or free-tier)
- **5-tier content extraction**: Trafilatura → justext → BoilerPy3 → Readability → BeautifulSoup, with confidence scoring

### Search Enhancements (NEW)

- **🔥 Unified extraction engine**: Both web-search and news-search use identical `EnterpriseSearchEngine`
  - Eliminated 300 lines of duplicate code
  - Google News /articles/ automatic detection and Playwright rendering
  - Error page detection prevents returning 404 content
  
- **⚡ Browser pool optimization**: 3-5x faster extraction
  - Launches browser ONCE (not per-URL)
  - Reuses context across all URLs
  - Reduces overhead from 3-8s to 0.5s per page
  
- **🚀 Staged ranking**: Discovery-first pipeline (70-85% faster)
  - Collect candidates (~40) → Initial ranking → Extract top 15 → Final ranking
  - 10s total vs 30-60s before
  - 92.5% fewer extractions
  
- **📊 Snippets mode**: `--snippets` flag (~10x faster)
  - Returns ranked snippets without content extraction
  - Default: 30 snippets in snippets mode, 10 full extractions in normal mode
  - Perfect for quick browsing and candidate discovery

### RSS Feed Integration (NEW)

- **Web search RSS**: 65 RSS feeds across 13 categories
  - Categories: ai, engineering, cloud, devops, research, security, startups, all, etc.
  - Parallel stream architecture with DuckDuckGo results
  - Example: `--category ai cloud` for combined feeds
  
- **Expanded news RSS**: 50+ sources (expanded from 1-2)
  - **cloud** category: 6 feeds (AWS Blog, Google Cloud, Azure, Red Hat, etc.)
  - **ai** category: 8 feeds (MIT Tech Review, TLDR AI, Import AI, etc.)
  - **startups** category: 6 feeds (VentureBeat, Product Hunt, a16z, Y Combinator, etc.)
  - **security** category: 6 feeds (BleepingComputer, Krebs on Security, etc.)
  - **all** category: 9 feeds (The Verge, Ars Technica, WIRED, etc.)
  
- **Dedicated news sources**: Google News RSS (`news-search --source google-news`) and Times of India RSS (`news-search --location <country/city>`), merged additively with DuckDuckGo News
- **Wikimedia search**: `wikipedia-search` and `--source wikimedia` query any of the 12 Wikimedia projects via the MediaWiki Action API

### Resilience & Performance

- **5-tier resilience chain**: plain requests → TLS impersonation → Playwright JS render → bandit-strategy cache → alternate source fallback (AMP/mobile/Wayback)
- **Quality escalation (NEW)**: Auto-retries with Playwright when requests tier yields < 30 chars
- **Domain learning (NEW)**: Per-domain strategy memory with Thompson sampling
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
scout-it --version          # Shows scout-it 2.0.0
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

# Web search with category RSS feeds (NEW)
scout-it web-search --query "AI tools" --category ai --max 10

# Fast snippets mode - 10x faster (NEW)
scout-it web-search --query "kubernetes" --category devops --snippets

# Web search with Markdown output
scout-it web-search --query "Python async programming" --markdown

# News search with staged ranking (70-85% faster) (NEW)
scout-it news-search --query "AI updates" --category ai --max 10

# News search snippets only (NEW)
scout-it news-search --query "tech news" --category startups --snippets

# Multi-category news search (NEW)
scout-it news-search --query "cloud computing" --category ai cloud devops

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

**NEW**: Unified extraction engine with browser pool optimization (3-5x faster), staged ranking, snippets mode, and category RSS feeds (65 feeds across 13 categories).

```bash
scout-it web-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Number of results to return. Default: 10 (full extraction), 30 (`--snippets` mode) |
| `--snippets` | Return ranked snippets only (~10x faster; default 30 snippets) |
| `--workers, -w` `<n>` | Parallel workers (default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/struct_format_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `openalex,arxiv,wikidata`) and merge with BM25F+vector re-ranking. Run `scout-it sources` for the list |
| `--auto-sources` | Let the source-selection bandit pick the best sources for this query type. Overrides `--sources` |
| `--region` `<region>` | DuckDuckGo region (example: `us-en`, `wt-wt`) |
| `--safesearch` `<level>` | Safe search: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | Time limit: `d`, `w`, `m`, `y` |
| `--backend` `<backend>` | DDGS backend: `auto`, `html`, `lite` (default: `auto`) |
| `--source` `<wikimedia>` | Search source override (default: DuckDuckGo). Use `wikimedia` to search Wikipedia directly. Falls back to the other source on zero results |
| `--category` `<categories...>` | RSS feed categories (ai, engineering, cloud, devops, research, security, startups, etc.). Multiple allowed, e.g. `--category ai cloud`. Merged with DuckDuckGo results |
| `--no-retry-on-zero` | Disable retries on 0 results (retries on by default) |
| `--retry-attempts` `<n>` | Retry attempts when 0 successful extractions (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier (default: 3) |
| `--no-js-fallback` | Disable Playwright fallback |
| `--enable-alternate-source` | Try AMP/mobile/print/Wayback variants on failure |
| `--no-dns-fallback` | Disable DNS-over-HTTPS retry (on by default) |
| `--tls-impersonate` | Browser-accurate TLS/JA3 fingerprint tier (needs `scout-it[tls-impersonate]`) |
| `--persistent-profile` | Persistent Playwright profile (cookies survive runs) |
| `--profile-name` `<name>` | Persistent profile name (with `--persistent-profile`) |
| `--use-bandit` | Skip to best-performing tier per domain from history |
| `--semantic` | Re-rank results by semantic relevance (needs `pip install sentence-transformers torch`) |

> `web-search` writes to a file by default and has **no `--json` flag** — use `--out` / `--markdown`.

#### `wikipedia-search`

Search any Wikimedia project via the MediaWiki Action API (Wikipedia, Wikidata, Commons, Wiktionary, Wikivoyage, Wikisource, and more).

```bash
scout-it wikipedia-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query or page title (required) |
| `--max, -m` `<n>` | Max results (1-50, default: 10) |
| `--project` `<project>` | Wikimedia project (default: `wikipedia`; any of the 12 entries in `wikimedia_source.SITE_MAP`) |
| `--language, -l` `<code>` | Project language for language-scoped wikis (default: `en`) |
| `--timeout` `<seconds>` | HTTP timeout (default: 25) |
| `--workers, -w` `<n>` | Parallel workers (default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/wikimedia_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--json` | Output raw JSON to stdout |
| `--summary` | Fetch the Wikipedia REST summary for the title |
| `--extract` | Fetch the cleaned full-page extract via the Action API |
| `--sections` | Export section-by-section cleaned text |
| `--crawl` | Recursive crawl from search results (with `--crawl-depth`, default 2) |
| `--crawl-depth` `<n>` | Crawl depth for `--crawl` mode (default: 2) |
| `--bundle` | Broad multi-project topic bundle across all 12 projects |
| `--robots` | Check robots.txt allowance before searching |
| `--no-clean` | Disable text cleaning |
| `--rss` | Include MediaWiki RecentChanges RSS feeds in discovery (uses `--project` as default category) |
| `--category, -c` `<project>` | Wikimedia project RSS category to include (repeatable): wikipedia, commons, wiktionary, wikivoyage, etc. Adds recently-changed pages to the candidate pool before ranking |

#### `news-search`

DuckDuckGo news search with regional/temporal filtering and full article content extraction. Same unified extraction engine, staged ranking, snippets mode, and resilient fetch chain as `web-search`.

```bash
scout-it news-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Number of results. Default: 10 (full extraction), 30 (`--snippets` mode) |
| `--snippets` | Return ranked snippets only (~10x faster; 2-4s vs 20-70s) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/news_search_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `gdelt,openalex,crossref`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | Bandit-picked sources for this query type. Overrides `--sources` |
| `--region` `<region>` | DuckDuckGo region (default: `us-en`) |
| `--safesearch` `<level>` | Safe search: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | Time limit: `d`, `w`, `m`, `y` |
| `--workers` `<n>` | Parallel workers for content extraction (default: 5) |
| `--source` `<google-news>` | Search source override (default: DuckDuckGo News). Use `google-news` for Google News RSS. Falls back to the other source on zero results |
| `--category` `<categories...>` | News RSS categories (ai, startups, security, cloud, all). Multiple allowed, e.g. `--category ai startups` |
| `--location` `<places...>` | Localized news from Times of India RSS (e.g. `india`, `US`, `UK`, `europe`, `china`, `india-delhi`). Multiple allowed |
| `--max-chars` `<n>` | Maximum characters to keep in extracted article content |
| `--max-size` `<size>` | Maximum response size per article (e.g. `5mb`) |
| `--no-retry-on-zero` | Disable retries on 0 results |
| `--retry-attempts` `<n>` | Retry attempts on zero results (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier (default: 3) |
| `--no-js-fallback` | Disable Playwright fallback |
| `--enable-alternate-source` | Try AMP/mobile/print/Wayback variants on failure |
| `--no-dns-fallback` | Disable DNS-over-HTTPS retry (on by default) |
| `--tls-impersonate` | Browser-accurate TLS/JA3 fingerprint tier (needs `scout-it[tls-impersonate]`) |
| `--persistent-profile` | Persistent Playwright profile |
| `--profile-name` `<name>` | Persistent profile name (default: `default`) |
| `--use-bandit` | Skip to best-performing tier per domain from history |
| `--semantic` | Re-rank by semantic relevance (needs `pip install sentence-transformers torch`) |

> `news-search` writes to a file by default and has **no `--json` flag** — use `--out` / `--markdown`.

#### `image-search`

DuckDuckGo image search with dimension, color, and license filters.

```bash
scout-it image-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max images (1-50, default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/image_search_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `internet_archive,openstreetmap`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | Bandit-picked sources for this query type. Overrides `--sources` |
| `--download, -d` | Download images to disk |
| `--download-dir` `<path>` | Download directory (default: `.scout-it/downloaded_images`) |
| `--region` `<region>` | DuckDuckGo region (default: `us-en`) |
| `--safesearch` `<level>` | Safe search: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | Time limit: `d`, `w`, `m`, `y` |
| `--size` `<size>` | Image size: Small, Medium, Large, Wallpaper |
| `--color` `<color>` | Color filter |
| `--type-image` `<type>` | Image type: photo, clipart, gif, transparent, line |
| `--layout` `<layout>` | Layout: Square, Tall, Wide |
| `--license-image` `<license>` | License filter |
| `--min-width` `<px>` | Minimum width |
| `--max-width` `<px>` | Maximum width |
| `--min-height` `<px>` | Minimum height |
| `--max-height` `<px>` | Maximum height |
| `--category` `<categories...>` | Image RSS categories (e.g. `nature space travel`). Fetches Media RSS feeds (Flickr/NASA) alongside DuckDuckGo and ranks them together |
| `--rss` | Include image RSS discovery even without `--category` (uses a Flickr tag feed from the query) |
| `--no-retry-on-zero` | Disable retries on 0 results |
| `--retry-attempts` `<n>` | Retry attempts when 0 valid images found (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |

#### `video-search`

Video search with duration and resolution filters. DuckDuckGo Videos is the
primary source; when it returns nothing (its endpoint intermittently raises
"No results found" for most queries), the pipeline automatically falls back to
**YouTube search**, so the command reliably returns ranked results.

```bash
scout-it video-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max videos (1-50, default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/video_search_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `internet_archive,listennotes`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | Bandit-picked sources for this query type. Overrides `--sources` |
| `--region` `<region>` | DuckDuckGo region (default: `us-en`) |
| `--safesearch` `<level>` | Safe search: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | Time limit: `d`, `w`, `m`, `y` |
| `--resolution` `<res>` | Resolution: high, standard |
| `--duration` `<duration>` | Duration: short, medium, long |
| `--license-videos` `<license>` | License filter |
| `--category` `<categories...>` | Video RSS categories (e.g. `technology science news`). Fetches YouTube channel RSS feeds alongside DuckDuckGo and ranks them together |
| `--rss` | Include video RSS discovery even without `--category` (pulls a default set of YouTube channels) |
| `--no-retry-on-zero` | Disable retries on 0 results |
| `--retry-attempts` `<n>` | Retry attempts when 0 results found (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |

> **Source fallback:** Results' `source` field shows `DuckDuckGo` or
> `YouTube`. When DDG returns nothing, YouTube search provides 14-20
> candidates that get ranked down to your `--max`. Stats include
> `youtube_candidates`/`youtube_count` to track fallback usage. Only public
> search metadata is used (title, channel, views, duration, published) — no
> video downloading.

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
| `--timeout` `<seconds>` | Extraction timeout (increase for JS-rendered SPAs, default: 25) |
| `--max-chars` `<n>` | Max characters to extract (e.g. 10000). Mutually exclusive with `--max-size` |
| `--max-size` `<size>` | Max response size (e.g. 100kb, 1mb, 500mb). Mutually exclusive with `--max-chars` |
| `--raw-html` | Return raw HTML instead of extracted content |
| `--js-render` | Skip straight to Playwright rendering |
| `--no-js-fallback` | Disable Playwright fallback |
| `--enable-alternate-source` | Try AMP/mobile/print/Wayback variants on failure |
| `--max-retries` `<n>` | Retry attempts per fetch tier (default: 3) |
| `--persistent-profile` | Persistent Playwright profile (cookies survive runs) |
| `--profile-name` `<name>` | Persistent profile name (default: `default`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--out, -o` `<path>` | Output file (default: `.scout-it/url_fetch_result.json`) |
| `--json` | Output raw JSON to stdout |

#### `multi-search`

Queries several search engines in parallel, merges and dedupes by URL, then runs content extraction. DuckDuckGo works with no setup; Brave/Bing/Google/SerpAPI need an API key (run `scout-it list-engines`). Unconfigured engines are skipped, not errors.

```bash
scout-it multi-search --query "<text>" --engines duckduckgo,brave [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--engines` `<list>` | Comma-separated engines: `duckduckgo, brave, bing, google, serpapi, wikimedia` (default: `duckduckgo`) |
| `--source` `<wikimedia>` | Include Wikimedia as a search source. Shorthand for `--engines wikimedia` |
| `--max, -m` `<n>` | Max merged results (default: 10) |
| `--workers, -w` `<n>` | Parallel content-extraction workers (default: 5) |
| `--serpapi-engine` `<engine>` | Underlying engine for SerpAPI (google/bing/yahoo/baidu/yandex, default: google) |
| `--no-dedupe` | Keep duplicate URLs across engines (dedupe on by default) |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier (default: 3) |
| `--no-js-fallback` | Disable Playwright fallback |
| `--out, -o` `<path>` | Output file (default: `.scout-it/multi_search_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `openalex,arxiv,wikidata,huggingface`) in parallel and merge with BM25F+vector re-ranking |
| `--auto-sources` | Bandit-picked sources for this query type. Overrides `--sources` |
| `--json` | Output raw JSON to stdout |

#### `list-engines`

Show which search engines are configured and available.

```bash
scout-it list-engines
```

No flags.

#### `sources`

List all source plugins available via the `--sources` flag on `web-search`, `news-search`, `image-search`, `video-search`, and `multi-search`. All sources are free or have free tiers — 30+ plugins including `openalex`, `arxiv`, `crossref`, `semantic_scholar`, `huggingface`, `zenodo`, `wikidata`, `gdelt`, `internet_archive`, `openstreetmap`, `hackernews`, `stackexchange`, and more.

```bash
scout-it sources          # formatted table
scout-it sources --json   # JSON
```

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON instead of a formatted table |

#### `index`

Fetch, extract, chunk, and embed `web-search` or `news-search` results into the persistent LanceDB store at `~/.scout-it/semantic/lancedb/`. The corpus then powers `semantic-search` and survives across runs. Needs: `pip install sentence-transformers torch lancedb`.

```bash
scout-it index --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Query to fetch and index (required) |
| `--max, -m` `<n>` | Max results to fetch and index (default: 20) |
| `--source` `<web\|news>` | Source to fetch from: `web` or `news` (default: `web`) |

#### `semantic-search`

Search a persistent corpus of previously-indexed documents using hybrid BM25 + dense-vector retrieval. Use `scout-it index` to build the corpus first. Storage: `~/.scout-it/semantic/lancedb/`. Model configurable via the `SCOUT_SEMANTIC_MODEL` env var (default: `BAAI/bge-m3`). Needs: `pip install sentence-transformers torch lancedb`.

```bash
scout-it semantic-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max results (default: 10) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/semantic_results.json`) |
| `--markdown` | Save as Markdown instead of JSON |
| `--json` | Output raw JSON to stdout |

Typical workflow:
```bash
scout-it index --query "transformer architecture" --max 20   # build corpus
scout-it semantic-search --query "attention mechanisms" --max 5  # query it
```

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

A single unified command, `social-search`, covers all social platforms.
Each platform is a *provider* that declares the capabilities it supports,
and the CLI does **not** restrict platform-specific arguments — each
provider decides whether it can serve `--channel`, `--channel-id`,
`--subreddit`, or `--profile`, and falls back to public query-based
discovery when a requested argument is unsupported.

```bash
# Search all enabled social providers (Telegram, Reddit, Discord, Instagram)
scout-it social-search --query "AI agents"

# Single platform
scout-it social-search --platform telegram --query "AI agents"

# Multiple platforms (comma-separated) — providers run in parallel
scout-it social-search --platform telegram,reddit,discord,instagram --query "AI agents"

# Platform-specific source arguments
scout-it social-search --platform telegram --channel durov
scout-it social-search --platform reddit --subreddit python --query "best practices"
scout-it social-search --platform reddit --user spez
scout-it social-search --platform reddit --subreddit python+programming --sort new
scout-it social-search --platform discord --channel-id 123456789
scout-it social-search --platform discord --query "python programming"  # no token needed (DDGS)
scout-it social-search --platform instagram --profile natgeo           # scrapes public profile (3-tier fallback)
scout-it social-search --platform instagram --query "travel photography"  # no login needed (DDGS)

# Reddit: full-page extraction of each top post's permalink (slower, richer)
scout-it social-search --platform reddit --subreddit python --extract-full

# Common options
scout-it social-search --platform telegram --query "..." [--max] [--out] [--markdown] [--json]
```

#### Capability-based fallback

If you pass a platform-specific argument that a selected platform does not
support, that platform falls back to query search instead of being skipped:

```bash
scout-it social-search --platform telegram,reddit,discord,instagram --channel durov --query "AI"
```

| Platform | Supported capabilities | Behavior for `--channel durov` |
|----------|------------------------|--------------------------------|
| Telegram | `query`, `channel` | Executes channel search |
| Reddit | `query`, `subreddit`, `user` | `--channel` unsupported → falls back to `--query` search |
| Discord | `channel-id`, `query` | `--channel` unsupported → falls back to `--query` (DDGS web search of Discord content; + bot guild search if `DISCORD_BOT_TOKEN` is set) |
| Instagram | `profile`, `query` | `--channel` unsupported → falls back to `--query` (DDGS web search of Instagram content; set `INSTAGRAM_SESSION_ID` for direct profile scraping) |

General rule per provider:
- Requested feature supported → execute it.
- Requested feature unsupported → fall back to provider query search.
- Provider unavailable (no fallback) → report provider failure; other providers continue.

#### Unified result format

All providers normalize results into a common schema, so multi-platform
results can be aggregated, ranked, filtered, and exported uniformly:

```json
{
  "platform": "telegram",
  "author": "...",
  "content": "...",
  "url": "...",
  "timestamp": "...",
  "metadata": { ... }
}
```

| Platform | Capabilities | Auth / notes |
|----------|--------------|--------------|
| `telegram` | `query`, `channel` | Public `t.me/s/` previews — no login needed. Paginates `?before=` for larger `--max`; detects non-existent/private channels and falls back to query search when `--channel` is wrong/empty. |
| `reddit` | `query`, `subreddit`, `user` | **RSS-first** — fetches public `.rss` feeds (subreddit, user activity, site-wide search), ranked by query relevance; falls back to anonymous `.json` only if RSS is blocked. `--extract-full` extracts full permalink pages. No login needed. |
| `discord` | `channel-id`, `query` | **No token needed for `--query`**: DDGS web search of public Discord content (servers, invites, message pages). With `DISCORD_BOT_TOKEN`: full message search across the bot's guilds + `--channel-id` message history (paginated). No self-bot/user-token usage (TOS-compliant). |

Unsupported platforms (return clear errors): Twitter/X, Instagram, TikTok.

#### Adding a future platform

No CLI redesign is required. A new platform needs only:
1. A provider implementation (subclass of `SocialProvider`).
2. A capability declaration (`SUPPORTED_CAPABILITIES`).
3. Registration in the provider registry (`scout_it/social/registry.py`).

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
scout-it stats --sources         # Source-selection bandit stats (which sources work best per query type)
```

#### `doctor`

Self-check for Playwright availability, proxy config, cache health, credentials, DNS/connectivity.

```bash
scout-it doctor
```

---

## Credentials & Configuration

scout-it reads credentials from environment variables. Use `scout-it config` to set them interactively (stored in `~/.scout-it/credentials.json`, permissioned 0600 on POSIX; the pre-rename `~/.data-scout/credentials.json` is still read as a fallback). Environment variables take precedence.

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
2. `~/.scout-it/credentials.json` (set via `scout-it config`)
3. Built-in default (if any)

---

## Resilience Layer

scout-it uses a multi-tier fetch strategy to extract content from even the most difficult sites. Each tier is tried in order; if all tiers fail, the command returns a clear error.

**NEW**: Browser pool optimization reduces overhead from 3-8s to 0.5s per page. Quality escalation automatically retries with Playwright when low-quality extraction detected.

| # | Tier | What it does | When it activates |
|---|------|-------------|-------------------|
| 1 | **requests** | Standard HTTP request with rotating User-Agent | Always tried first |
| 2 | **TLS impersonation** | Browser-accurate TLS/JA3 fingerprint via `curl_cffi` | `--tls-impersonate` |
| 3 | **Playwright** | Full browser rendering (JS, SPAs, Cloudflare) | Automatic on requests failure, or `--js-render` |
| 4 | **Bandit** | Skips to best-performing tier per domain | `--use-bandit` |
| 5 | **Alternate sources** | AMP/mobile/print URL variants + Wayback Machine | `--enable-alternate-source` |

### Performance Enhancements (NEW)

- **Browser pool**: Launches browser ONCE and reuses context across all URLs
  - 3-8s overhead per URL → 0.5s per page
  - Automatic cleanup after extraction complete
  - Thread-local pool for concurrent extraction

- **Quality escalation**: Auto-retries with Playwright when requests tier yields:
  - < 30 characters of extracted content
  - Error pages or 404 content
  - Low-quality extractions

- **Domain learning**: Tracks per-domain strategy performance
  - Thompson sampling for optimal tier selection
  - Persistent SQLite cache at `~/.scout-it/strategy_cache.db`
  - Skips permanently-failing domains

- **Wrapper resolution**: Resolves MSN/Yahoo/AOL URLs before extraction
  - URL-based resolution first
  - HTML-based fallback after fetch
  - Prevents wasted extraction cycles

### Additional Protections

- **DNS-over-HTTPS fallback**: Automatically retries failed fetches via DoH when the error looks DNS-related (on by default; disable with `--no-dns-fallback`)
- **Zero-result retry**: When a search returns 0 results, retries with progressively relaxed filters (on by default; disable with `--no-retry-on-zero`)
- **Proxy pool**: Auto-rotates through proxies from `PROXY_LIST` env var
- **Politeness governor**: Per-domain concurrency caps + robots.txt checks to avoid tripping rate limits
- **Response cache**: Disk cache under `.scout-it/cache/` with stale-if-error fallback
- **Canary probe**: Cheap pre-fetch block-page check before burning full tier attempts

---

## Programmatic API

scout-it can be used as a Python library:

```python
from scout_it import (
    web_search,
    fetch_url,
    multi_engine_search,
    wikimedia_search,
)

# Search with full content extraction -> (results, stats) tuple
results, stats = web_search("machine learning transformers", max_results=3)

# Each result dict has: title, url, source, publish_date, confidence_score,
# extraction_method, cleaned_content, first_paragraph, top_keywords, ...
for r in results:
    print(f"{r['title']} (confidence: {r['confidence_score']:.2f})")
    print(r["cleaned_content"][:200])
    print("---")

# Multi-engine search (tier-1 engines without API keys are skipped, not errors)
result = multi_engine_search("rust vs go", engines=["duckduckgo", "brave"])
for r in result["merged_results"]:
    print(r["title"])

# Direct URL extraction through the full resilience chain
fetch_result = fetch_url("https://example.com/article", max_fetch_retries=3)

# Wikimedia search (returns DDGS-compatible result dicts)
wiki_results, _ = wikimedia_search("machine learning", project="wikipedia")
```

### Key Functions

| Function | Purpose |
|----------|---------|
| `web_search()` | DuckDuckGo web search + parallel content extraction |
| `news_search()` | DuckDuckGo news search (Google News via `--source`, ToI via `--location`) |
| `image_search()` | Image search with dimension/color/license filters |
| `video_search()` | Video search with duration/resolution filters (YouTube fallback) |
| `video_extract()` | Full metadata + subtitles from a YouTube URL |
| `fetch_url()` | Single-URL fetch through the full resilience chain |
| `multi_search()` | Multi-engine search (parallel merge + dedupe) |
| `multi_engine_search()` | Lower-level parallel Brave/Bing/Google/SerpAPI search with dedupe |
| `wikipedia_search()` | Search any Wikimedia project via the Action API |
| `fetch_resilient()` | Low-level tiered fetch (requests → Playwright → bandit → alternate) |
| `process_results()` | Structure + clean a raw result list into scored records |
| `advanced_clean_text()` | Noise-only text cleaning that preserves content |

> Note: `ExtractionEngine.extract_content(url, html_content, timeout)` expects the HTML to already be fetched — pass the page HTML you obtained yourself. The end-to-end fetch+extract path is `fetch_url()` / `web_search()`. The semantic index/store (`SemanticIndex` in `scout_it.semantic`) is CLI-only (`scout-it index` / `scout-it semantic-search`).

---

## Usage Examples

### Basic Searches

```bash
# Quick web search with 3 results
scout-it web-search -q "Python best practices" -m 3

# News search with time filter
scout-it news-search -q "AI breakthrough" --timelimit d -m 5

# Image search with filters
scout-it image-search -q "sunset" --min-width 1920 --size Large -d
```

### Category-Based Searches (NEW)

```bash
# AI news from 8 RSS sources
scout-it news-search -q "large language models" --category ai -m 10

# Cloud computing from web RSS feeds
scout-it web-search -q "kubernetes best practices" --category cloud devops

# Multi-category news
scout-it news-search -q "startup funding" --category startups ai -m 15

# Security news from 6 sources
scout-it news-search -q "zero-day vulnerabilities" --category security
```

### Fast Snippets Mode (NEW)

```bash
# Quick browse: 30 snippets in ~3 seconds
scout-it web-search -q "react hooks" --category engineering --snippets

# News snippets for rapid scanning
scout-it news-search -q "tech news" --category all --snippets -m 50

# Research phase: collect candidates fast
scout-it web-search -q "machine learning papers" --snippets -m 100
```

### Advanced Resilience

```bash
# Difficult site with JS rendering
scout-it fetch-url --url "https://spa-site.com" --js-render

# With TLS impersonation
scout-it fetch-url --url "https://protected-site.com" --tls-impersonate

# Full resilience stack
scout-it web-search -q "news" --enable-alternate-source --use-bandit

# Persistent browser profile for login-required sites
scout-it fetch-url --url "https://members-only.com" --persistent-profile
```

### Multi-Source Searches

```bash
# Combine DuckDuckGo + Google News + Location RSS
scout-it news-search -q "India economy" --source google-news --location india

# Web search with Wikimedia
scout-it web-search -q "quantum computing" --source wikimedia -m 5

# Multi-engine search (requires API keys)
scout-it multi-search -q "rust vs go performance" --engines duckduckgo,brave,bing
```

### GitHub & Social

```bash
# Full repo analysis
scout-it github-repo --repo microsoft/vscode --file-tree

# Recent commits with filters
scout-it github-commits --repo facebook/react --since "2024-01-01" -m 10

# Public Telegram channel
scout-it social-search --platform telegram --channel technews --max 20

# Reddit subreddit listing (RSS feed) — no query needed
scout-it social-search --platform reddit --subreddit learnpython --max 20

# Reddit user activity (posts + comments) via RSS feed
scout-it social-search --platform reddit --user spez

# Reddit site-wide search (falls back to .json if RSS is blocked)
scout-it social-search --platform reddit --query "python best practices"

# Discord search — no token needed (DDGS web discovery of public Discord content)
scout-it social-search --platform discord --query "python programming"

# Discord channel history (needs DISCORD_BOT_TOKEN; paginates beyond 100)
scout-it social-search --platform discord --channel-id 123456789 --max 200
```

---

## Performance

```
scout-it/
├── scout_it/                    # Main package
│   ├── __init__.py              # Public API + exports
│   ├── cli.py                   # Argparse CLI (28 subcommands)
│   ├── extraction.py            # Search engines, ExtractionEngine, fetch_resilient
│   ├── cleaner.py               # process_results / advanced_clean_text / scoring
│   ├── engines.py               # Brave, Bing, Google, SerpAPI engine wrappers
│   ├── config.py                # Credential management (~/.scout-it/credentials.json)
│   ├── output.py                # Output path routing + markdown rendering
│   ├── github_extract.py        # All 12 GitHub extractors
│   ├── social/                  # Unified social-search (Telegram, Reddit, Discord)
│   │   ├── base.py              # SocialProvider base + unified result schema
│   │   ├── registry.py          # Provider registry (capability-based dispatch)
│   │   ├── telegram.py          # TelegramProvider (query, channel)
│   │   ├── reddit.py            # RedditProvider (query, subreddit)
│   │   └── discord.py           # DiscordProvider (channel-id)
│   ├── google_news_source.py    # Google News RSS (news-search --source google-news)
│   ├── toi_rss_source.py        # Times of India RSS (news-search --location)
│   ├── wikimedia_source.py      # Wikimedia search (wikipedia-search / --source wikimedia)
│   ├── tech_crunch_rss.py       # TechCrunch RSS aggregation (NEW: 50+ sources across categories)
│   ├── web_search_rss.py        # Web search RSS provider (NEW: 65 feeds, 13 categories)
│   ├── category_providers.py    # Category-aware RSS provider registry (NEW)
│   ├── web_category_providers.py # Web search category provider functions (NEW)
│   ├── heuristic_extract.py     # DOM-based heuristic content scoring
│   ├── selector_cache.py        # Per-domain CSS selector memory
│   ├── alternate_source.py      # AMP/mobile/print/Wayback variants
│   ├── browser_pool.py          # Thread-local Playwright browser pool (NEW: 3-5x faster)
│   ├── browser_profile.py       # Persistent Playwright profile + stealth
│   ├── tls_fingerprint.py       # curl_cffi TLS/JA3 impersonation
│   ├── dns_resilience.py        # DNS-over-HTTPS fallback
│   ├── proxy_pool.py            # Auto-rotating proxy pool
│   ├── retry_classifier.py      # Transient vs permanent failure classifier
│   ├── politeness_governor.py   # Per-domain concurrency caps + robots.txt
│   ├── strategy_cache.py        # Per-domain strategy memory (SQLite)
│   ├── strategy_bandit.py       # Thompson-sampling tier selection
│   ├── response_cache.py        # Disk response cache (.scout-it/cache/)
│   ├── canary_probe.py          # Cheap block-page pre-check
│   ├── header_profiles.py       # Browser-consistent header bundles
│   ├── domain_routing.py        # Per-domain strategy learning (NEW)
│   ├── extraction_quality.py    # Content quality scoring + escalation (NEW)
│   ├── source_resolvers.py      # Wrapper URL resolution (MSN/Yahoo/AOL) (NEW)
│   ├── staged_ranker.py         # Two-stage ranking pipeline (NEW)
│   └── _utils.py                # Shared helpers
├── tests/                       # Test suite (~790 tests, 40 test files)
│   ├── test_cli.py
│   ├── test_cleaner.py
│   ├── test_new_sources.py
│   ├── test_resilience.py
│   ├── test_output.py
│   ├── test_strategy.py
│   ├── test_advanced_evasion.py
│   ├── test_browser_pool.py            # Browser pool tests (NEW)
│   ├── test_browser_pool_integration.py # Browser pool integration (NEW)
│   ├── test_domain_routing.py          # Domain routing tests (NEW)
│   ├── test_source_resolvers.py        # Wrapper resolution tests (NEW)
│   ├── test_staged_ranking.py          # Staged ranking tests (NEW)
│   ├── test_extraction_quality.py      # Quality escalation tests (NEW)
│   ├── test_extraction_concurrency.py  # Concurrency tests (NEW)
│   ├── test_complete_workflow.py       # Full pipeline tests (NEW)
│   ├── test_expanded_rss_feeds.py      # RSS expansion tests (NEW)
│   ├── test_web_search_rss_integration.py # Web RSS integration (NEW)
│   └── ...
├── docs/                        # Search-specific documentation
│   ├── NETWORK_RESILIENCE_FEATURE.md      # Network resilience guide (NEW)
│   ├── PRODUCTION_HARDENING_GUIDE.md      # Production features (NEW)
│   ├── RSS_INTEGRATION_GUIDE.md           # RSS integration guide (NEW)
│   ├── RSS_FEEDS_EXPANSION.md             # RSS expansion docs (NEW)
│   ├── STAGED_RANKING_IMPLEMENTATION.md   # Staged ranking design (NEW)
│   ├── QUICK_START_STAGED_RANKING.md      # Quick start guide (NEW)
│   └── search/                            # Command-specific docs
├── scout-it-website/            # React TypeScript landing page & docs site
├── pyproject.toml
├── setup.py
├── CHANGELOG.md
├── README.md
├── GAKRCLI.md                   # Agent instructions (replaces AGENTS.md)
└── LICENSE
```

---

## Performance

### Speed Improvements (August 2026)

| Feature | Before | After | Improvement |
|---------|--------|-------|-------------|
| **News search** | 30-60s | 7-10s | **70-85% faster** |
| **Browser launch overhead** | 3-8s per URL | 0.5s per page | **85-94% faster** |
| **Snippets mode** | 15-20s full extraction | 2-5s snippets only | **~10x faster** |
| **Extraction efficiency** | 200 extractions | 15 extractions | **92.5% fewer** |

### Staged Ranking Pipeline

```
Old: Collect 200 articles → Extract ALL → Rank → Return 10
     Time: 30-60 seconds

New: Collect 40 candidates → Rank → Extract top 15 → Rank → Return 10
     Time: 7-10 seconds ⚡
```

### Performance Targets

| Phase | Target | Typical | Status |
|-------|--------|---------|--------|
| Collection | < 3s | 2.5s | ✅ |
| Initial Rank | < 1s | 45ms | ✅ |
| Extraction | < 5s | 4.2s | ✅ |
| Final Rank | < 1s | 12ms | ✅ |
| **Total** | **< 10s** | **7.2s** | ✅ |

---

## Testing

```bash
# Run the full suite (fast unit + mocked-integration tests; ~40s)
pytest

# Run a single file
pytest tests/test_resilience.py -v

# Run a single test
pytest tests/test_output.py::TestChunkText::test_long_text_chunked_under_limit -v

# Run with coverage
pytest tests/test_cleaner.py --cov=scout_it --cov-report=term-missing
```

The suite collects **~790 tests** across 40 `test_*.py` files. By default it runs in
**~41s with 747 passing and ~40 skipped** — no hangs, no network required.

### Live-network (integration) tests

A subset of tests fetch live RSS feeds / search results. These are **skipped by
default** so the suite runs reliably in CI and offline sandboxes. Enable them with:

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/test_enhanced_rss.py tests/test_provider_updates.py
```

Files guarded by this flag include `test_enhanced_rss.py`, `test_provider_updates.py`,
`test_news_integration.py`, `test_expanded_rss_feeds.py` (live fetches), and several
tests in `test_production_hardening.py`. The heavy semantic-retrieval tests
(`test_semantic.py`, `test_phase3_ranking.py`) additionally require
`sentence-transformers`/`torch`; without them they degrade gracefully and skip.

Minimum coverage target: 80%. For end-to-end behavior verification, exercise the real
`scout-it` CLI directly (see `real-tests.md`).

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
