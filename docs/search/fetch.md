# fetch-url

## Overview

Direct extraction of main content from a single URL through the full resilient fetch chain — the same tiers used by every search command. Useful when you already have a URL and want its cleaned, structured text.

## Command

```bash
scout-it fetch-url --url "https://example.com" [options]
```

| Flag | Description |
|------|-------------|
| `--url, -u` `<url>` | URL to fetch (required) |
| `--timeout` `<seconds>` | Extraction timeout in seconds (default: 25; increase for JS-rendered SPAs) |
| `--max-chars` `<n>` | Maximum characters to extract (e.g. `10000`). Mutually exclusive with `--max-size` |
| `--max-size` `<size>` | Maximum response size (e.g. `100kb`, `1mb`, `500mb`). Mutually exclusive with `--max-chars` |
| `--out, -o` `<path>` | Output file (default: `.scout-it/url_fetch_result.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--json` | Output raw JSON to stdout |
| `--raw-html` | Return raw HTML (prettified) instead of extracted/cleaned content |
| `--js-render` | Skip straight to Playwright rendering instead of trying requests first |
| `--no-js-fallback` | Disable the automatic Playwright fallback when requests fails or looks blocked |
| `--max-retries` `<n>` | Retry attempts per fetch tier (requests → Playwright) (default: 3) |
| `--enable-alternate-source` | If every fetch tier fails, try AMP/mobile/print URL variants + a Wayback Machine snapshot before giving up (opt-in) |
| `--persistent-profile` | Use a persistent Playwright profile (cookies/session survive across runs) for the JS-render tier |
| `--profile-name` `<name>` | Persistent profile name (only with `--persistent-profile`, default: `default`) |

> `--max-chars` and `--max-size` are mutually exclusive — use at most one.

## Fetch tiers

Every `fetch-url` runs through `fetch_resilient()`, trying tiers in order until one succeeds:

1. **requests** — standard HTTP with rotating browser-accurate headers (always first)
2. **TLS impersonation** — opt-in (`--tls-impersonate`); needs `pip install scout-it[tls-impersonate]`
3. **Playwright** — full browser JS render; automatic on failure, or `--js-render` to skip straight here
4. **Bandit pick** — `--use-bandit`; skip to the best-performing tier per domain from history
5. **Alternate sources** — `--enable-alternate-source`; AMP/mobile/print URL variants + Wayback Machine

DNS-over-HTTPS retry is on by default (`--no-dns-fallback` to disable); the proxy pool rotates through `PROXY_LIST` if set.

## Examples

```bash
# Basic extraction
scout-it fetch-url --url "https://example.com/article"

# JS-heavy SPA — go straight to Playwright
scout-it fetch-url --url "https://spa-heavy-site.com" --js-render

# Protected site — TLS impersonation + alternate sources
scout-it fetch-url --url "https://protected-site.com" --enable-alternate-source

# Persistent profile for login-required sites
scout-it fetch-url --url "https://members-only.com" --persistent-profile

# Cap output size
scout-it fetch-url --url "https://example.com" --max-chars 10000

# Raw HTML instead of extracted content
scout-it fetch-url --url "https://example.com" --raw-html --json
```

## Output

Writes a JSON object (or Markdown with `--markdown`) to `.scout-it/url_fetch_result.json` by default. Each result includes `title`, `url`, `main_content` / `cleaned_content`, `extraction_method` (which layer + fetch tier succeeded), `confidence_score`, and `extraction_status`. Long string fields are chunked into ≤500-char arrays for line-length safety.

## Programmatic API

```python
from scout_it import fetch_url

result = fetch_url("https://example.com/article", max_fetch_retries=3)
print(result.get("cleaned_content", "")[:500])
```

For lower-level control, `ExtractionEngine.extract_content(url, html_content, timeout)` expects already-fetched HTML and returns `(content, method, confidence)`.
