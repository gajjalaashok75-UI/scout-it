# web-search & news-search

## Overview

`web-search` and `news-search` both use the unified `EnterpriseSearchEngine` to run DuckDuckGo queries and extract full article content from every result through the multi-tier resilient fetch chain. The pipeline is discovery-first: collect snippets from all sources → rank by relevance → extract full content for the top N (or return snippets only with `--snippets`).

Both commands can also pull in category RSS feeds, dedicated source plugins, and a search-source override, all merged and re-ranked together.

## web-search

```bash
scout-it web-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Number of results to return. Default: 10 (full extraction), 30 (`--snippets` mode) |
| `--snippets` | Return ranked snippets only. Skips content extraction for ~10x faster results (~2-4s vs 20-70s). Default limit: 30 snippets |
| `--workers, -w` `<n>` | Parallel workers (default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/struct_format_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `openalex,arxiv,wikidata`) and merge with BM25F+vector re-ranking. Run `scout-it sources` for the list |
| `--auto-sources` | Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides `--sources` |
| `--region` `<region>` | DuckDuckGo region (example: `us-en`, `wt-wt`) |
| `--safesearch` `<level>` | Safe search mode: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | DuckDuckGo time limit: `d`, `w`, `m`, `y` |
| `--backend` `<backend>` | DDGS backend: `auto`, `html`, `lite` (default: `auto`) |
| `--source` `<wikimedia>` | Search source override (default: DuckDuckGo). Use `wikimedia` to search Wikipedia directly. Falls back to the other source on zero results |
| `--category` `<categories...>` | Category RSS feeds to include (`ai`, `engineering`, `cloud`, `devops`, `research`, `security`, `startups`, etc.). Multiple allowed, e.g. `--category ai cloud`. Merged with DuckDuckGo results |
| `--no-retry-on-zero` | Disable retries when 0 successful extractions (retries on by default) |
| `--retry-attempts` `<n>` | Retry attempts when 0 successful extractions (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier (requests → Playwright) when fetching each result page (default: 3) |
| `--enable-alternate-source` | If every fetch tier fails, try AMP/mobile/print URL variants + a Wayback Machine snapshot before giving up (opt-in) |
| `--no-dns-fallback` | Disable the DNS-over-HTTPS retry on DNS-looking errors (on by default) |
| `--tls-impersonate` | Browser-accurate TLS/JA3 fingerprint tier between requests and Playwright (needs: `pip install scout-it[tls-impersonate]`) |
| `--persistent-profile` | Persistent Playwright profile (cookies/session survive across runs) |
| `--profile-name` `<name>` | Persistent profile name (only with `--persistent-profile`, default: `default`) |
| `--use-bandit` | Once a domain has enough recorded history, skip straight to the best-performing fetch tier for it (see `scout-it stats`) |
| `--no-js-fallback` | Disable the automatic Playwright fallback |
| `--semantic` | Re-rank results by semantic relevance (hybrid BM25+dense-vector + cross-encoder). Needs: `pip install sentence-transformers torch` |

**Examples:**
```bash
scout-it web-search --query "machine learning transformers" --max 5
scout-it web-search --query "kubernetes" --category devops --snippets
scout-it web-search --query "quantum computing" --source wikimedia -m 5
scout-it web-search --query "site behind cloudflare" --max-fetch-retries 4 --tls-impersonate
scout-it web-search --query "news" --enable-alternate-source --use-bandit
scout-it web-search --query "AI regulation" --max 15 --markdown --out ai-report.md
```

## news-search

```bash
scout-it news-search --query "<text>" [options]
```

Same core flags and resilient fetch chain as `web-search`, plus news-specific options:

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Number of results to return. Default: 10 (full extraction), 30 (`--snippets` mode) |
| `--snippets` | Return ranked news snippets only (~10x faster). Default limit: 30 snippets |
| `--out, -o` `<path>` | Output file (default: `.scout-it/news_search_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `gdelt,openalex,crossref`) and merge with BM25F+vector re-ranking |
| `--auto-sources` | Bandit-picked sources for this query type. Overrides `--sources` |
| `--region` `<region>` | DuckDuckGo region (default: `us-en`) |
| `--safesearch` `<level>` | `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | `d`, `w`, `m`, `y` |
| `--workers` `<n>` | Parallel workers for content extraction (default: 5) |
| `--source` `<google-news>` | Search source override (default: DuckDuckGo News). Use `google-news` for Google News RSS. Falls back to the other source on zero results |
| `--category` `<categories...>` | News RSS categories (`ai`, `startups`, `security`, `cloud`, `all`). Multiple allowed, e.g. `--category ai startups` |
| `--location` `<places...>` | Location(s) for localized news from Times of India RSS (e.g. `india`, `US`, `UK`, `europe`, `china`, `india-delhi`, `india-bangalore`). Multiple allowed |
| `--max-chars` `<n>` | Maximum characters to keep in extracted article content |
| `--max-size` `<size>` | Maximum response size per article (e.g. `5mb`). Truncates raw HTML before extraction |
| `--no-retry-on-zero` | Disable retries on zero results (retries on by default) |
| `--retry-attempts` `<n>` | Retry attempts on zero results (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier (default: 3) |
| `--no-js-fallback` | Disable Playwright fallback |
| `--enable-alternate-source` | Try AMP/mobile/print/Wayback variants on failure (opt-in) |
| `--no-dns-fallback` | Disable DNS-over-HTTPS retry (on by default) |
| `--tls-impersonate` | Browser-accurate TLS/JA3 fingerprint tier (needs: `pip install scout-it[tls-impersonate]`) |
| `--persistent-profile` | Persistent Playwright profile |
| `--profile-name` `<name>` | Persistent profile name (default: `default`) |
| `--use-bandit` | Skip to best-performing tier per domain from history |
| `--semantic` | Re-rank by semantic relevance (needs: `pip install sentence-transformers torch`) |

**Examples:**
```bash
scout-it news-search --query "artificial intelligence" --max 5
scout-it news-search --query "AI updates" --category ai --snippets
scout-it news-search --query "India economy" --source google-news --location india
scout-it news-search --query "zero-day vulnerabilities" --category security --timelimit d
```

## Pipeline

1. `EnterpriseSearchEngine` queries DuckDuckGo (text or news), plus any `--sources` plugins, `--category` RSS feeds, and the `--source` override, in parallel.
2. Candidates are ranked by relevance (metadata-only scoring first).
3. Top N result URLs are fetched in parallel (`--workers` controls concurrency) through the resilient fetch chain.
4. `ExtractionEngine` extracts main content (trafilatura → justext → boilerpy3 → readability → heuristic).
5. `process_results()` filters failed extractions and structures the surviving text.
6. Output is written as JSON (or Markdown with `--markdown`).

Every individual page fetch goes through the shared resilient fetch chain — see [fetch.md](fetch.md) for the tier breakdown.

> Note: `web-search` and `news-search` write to a file by default and have **no `--json` flag** — use `--out` / `--markdown` to control output. (`--json` exists on the GitHub, social, video-extract, fetch-url, multi-search, and semantic-search commands.)
