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
| `web-search` | Web search with full content extraction (5-layer pipeline) |
| `news-search` | News search with full article content extraction |
| `image-search` | Image search (with optional download) |
| `video-search` | Video search with duration/resolution filters |
| `fetch-url` | Extract readable content from a single URL |
| `video-extract` | Extract video transcripts/subtitles (YouTube) |
| `multi-search` | Search across DuckDuckGo + Brave/Bing/Google/SerpAPI in parallel |
| `list-engines` | List available engines and their config status |
| `config` | Set up API keys/tokens for all platforms |
| `github-repo` | Get comprehensive GitHub repo details |
| `github-commits` | List commits in a GitHub repo |
| `github-commit` | Full details for one commit with unified diff |
| `github-pr` | Get PR with full diff and changed files |
| `github-prs` | List PRs in a repo |
| `github-folder` | List/fetch every file under a repo folder |
| `github-issues` | List issues in a repo |
| `github-issue` | Get one issue with body and comments |
| `github-file` | Fetch a single file's contents from a repo |
| `github-search-code` | Search code across GitHub (requires GITHUB_TOKEN) |
| `github-search-repos` | Search GitHub repositories |
| `github-discussions` | List GitHub Discussions (requires GITHUB_TOKEN) |
| `telegram-channel` | Fetch posts from a public Telegram channel |
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
| `--max` / `-m` | int | `10` | Max results (1-100) |
| `--workers` / `-w` | int | `3` | Parallel fetch workers |
| `--out` / `-o` | str | `.data-scout/struct_format_results.json` | Output file |
| `--markdown` | flag | — | Save results as Markdown (.md) instead of JSON |
| `--region` | str | `wt-wt` | Region (e.g., `us-en`, `uk-en`, `de-de`) |
| `--safesearch` | str | `moderate` | `on`, `moderate`, or `off` |
| `--timelimit` | str | — | `d` (day), `w` (week), `m` (month), `y` (year) |
| `--backend` | str | `auto` | `auto`, `html`, or `lite` |
| `--no-retry-on-zero` | flag | — | Skip retry on zero results |
| `--retry-attempts` | int | `3` | Max retry attempts |
| `--retry-backoff` | float | `1.0` | Backoff seconds between retries |
| `--max-fetch-retries` | int | — | Retry attempts per fetch tier (requests → Playwright) |
| `--no-js-fallback` | flag | — | Disable Playwright fallback on blocked pages |

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
```

---

## multi-search

Search across multiple engines (DuckDuckGo + optional Brave/Bing/Google/SerpAPI) in parallel. Requires API keys set via `scout-it config`.

**Basic usage:**
```bash
scout-it multi-search --query "your query" --engines ddg,brave,bing
```

**Flags:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` / `-q` | str | *required* | Search query |
| `--engines` | str | `ddg` | Comma-separated: `ddg,brave,bing,google,serpapi` |
| `--max` / `-m` | int | `10` | Max results per engine |
| `--out` / `-o` | str | *(stdout)* | Output file |

**Examples:**
```bash
# DuckDuckGo + Brave + Bing
scout-it multi-search --query "quantum computing" --engines ddg,brave,bing

# All configured engines
scout-it multi-search --query "climate science" --engines ddg,brave,bing,google --max 15
```

---

## config

Set up API keys/tokens for GitHub, Brave, Bing, Google, SerpAPI, Discord, Reddit. Stored at `~/.data-scout/config.json`.

```bash
scout-it config
```

Run interactively to set tokens. Use `scout-it list-engines` to see which are configured.

---

## GitHub subcommands

All GitHub commands accept one of:
- `owner/repo` format
- Full GitHub URL: `https://github.com/owner/repo`

**Flags common to all GitHub commands:**

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--repo` | str | *required* | `owner/repo` or full URL |
| `--token` / `-t` | str | `~/.data-scout/config.json` | GitHub token override |
| `--out` / `-o` | str | *(stdout)* | Output file |

**Examples:**
```bash
# Repo metadata
scout-it github-repo --repo gajjalaashok75-UI/scout-it

# List recent PRs
scout-it github-prs --repo gajjalaashok75-UI/scout-it --state open

# Get a PR with full diff
scout-it github-pr --repo gajjalaashok75-UI/scout-it --number 1

# Search code
scout-it github-search-code --query "class EnterpriseSearch" --repo gajjalaashok75-UI/scout-it

# List commits
scout-it github-commits --repo gajjalaashok75-UI/scout-it --limit 20

# Full commit details with diff
scout-it github-commit --repo gajjalaashok75-UI/scout-it --sha <commit-sha>
```

---

## Social platform subcommands

### Telegram
```bash
# Fetch recent posts from a public channel
scout-it telegram-channel --channel "channel_name"

# Search for channels by topic
scout-it telegram-channel --search "Python programming"
```

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

All subcommands output JSON arrays by default. Each result contains:

- `title` / `body` — search result title and snippet
- `url` / `href` — the result URL
- `main_content` — cleaned, extracted content (web-search, news-search, fetch-url)
- `extraction_method` — which extraction layer succeeded (e.g., `readability`, `trafilatura`)
- `confidence_score` — content quality score (0.0–1.0)
- `extraction_status` — `"success"` or `"failed"`
- `content_word_count` — word count of cleaned content

The `--markdown` flag (on `web-search`) saves results as a Markdown file instead.

## 5-Layer Extraction Fallback

```
1. Trafilatura (confidence: 1.0)  — Best for news/articles
2. Justext (confidence: 0.95)     — Good for general content
3. BoilerPy3 (confidence: 0.90)   — Robust fallback
4. Readability (confidence: 0.85) — Alternative extractor
5. BeautifulSoup (confidence: 0.70) — Ultimate HTML fallback
```

## Config directory

All config and credentials stored at `~/.data-scout/config.json`.
Output files default to `.data-scout/` in the working directory.

## Rate limiting

DuckDuckGo may rate-limit aggressive usage. Recommendations:
- Keep `--max` under 30 for routine use
- Use `--retry-attempts 5 --retry-backoff 2.0` for important queries
- If you see zero results, try `--backend html` or `--no-js-fallback`
- For high-volume needs, use `multi-search` with additional engines
