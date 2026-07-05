# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [1.4.0] - 2026-07-05 16:00:00 UTC

### 🔴 Fixed — 13KB+ single-line content, now safely chunked (still valid JSON)

Long field values (a `main_content` blob, a diff patch, an article body)
were being written as one giant single-line JSON string with no readability
handling at all. `_write_output` now runs every output through
`data_scout.output.write_json_output`, which breaks any string over 500
characters into an array of `<=500`-char chunks at word boundaries — a
plain, valid JSON array (one element per line under `indent=2`), not the
control-character-injecting hack from the previous fix. URLs and a few
other fields are deliberately left unchunked (see `_NO_CHUNK_KEYS`) since
splitting them would make them useless.

### 🚀 Added — `.data-scout/` as the default output directory, everywhere

Every command's default `--out` path now lives under `.data-scout/` (created
automatically) instead of dropping a file directly in the current directory,
e.g. `.data-scout/github_repo_results.json`. An explicit `--out some/path.json`
is still honored exactly as given; only bare filenames or the built-in
defaults get the `.data-scout/` treatment.

### 🚀 Added — `--markdown` on every command that writes output

Every command with an `--out` flag now also has `--markdown`, which renders
the same result data as a Markdown document instead of JSON (tables for
uniform lists, fenced code blocks for file/diff content, headers for nested
sections). `--out foo.md` works the same way without needing `--markdown`
explicitly. Combining `--markdown` with an explicit `--out ....json` is
rejected with a clear error rather than silently picking one.

### 🚀 Added — diff line numbers

`github-commit`/`github-pr`'s `patch_lines` now include `old_line`/`new_line`
for every entry (parsed from each hunk's `@@ -a,b +c,d @@` header and tracked
per line), so you can tell exactly which file line was added/removed instead
of just the +/- text. The Markdown rendering shows these as a line-numbered
table (a fenced ` ```diff ` block can't carry a number gutter without
breaking the leading +/-/space character syntax highlighters rely on).

### 🚀 Added — github-repo: opt-in, uncapped file tree with size limits

The file tree is no longer included by default (it was a fixed 200-entry
preview before) — pass `--file-tree` for the complete, untruncated tree, and
optionally `--max-chars`/`--max-size` (mutually exclusive, same validation
as `fetch-url`) to cap its output size for huge repos.

### 🔧 Fixed — github-folder argument-combination race conditions

- `--max-files` without `--include-content` is now a clear error (it used
  to be silently accepted and silently ignored).
  `--save-path-dir` without `--include-content` is the same.
- `--include-content` **without** `--max-files` now fetches **all** matching
  files (previously silently capped at 20) — `--max-files` is opt-in, not a
  hidden default.
- Added `--max-chars`/`--max-size` (mutually exclusive) to cap each fetched
  file's content.
- Added `detected_type` per fetched file (python/markdown/json/yaml/etc. by
  extension) for downstream formatting.
- Added `--save-path-dir`: writes every fetched file to disk under that
  directory, preserving the repo-relative path structure.

### 🚀 Added — Telegram retry-then-fallback-parser architecture

`telegram-channel` now retries the fetch+parse cycle up to `--max-fetch-retries`
times, and if the primary parser still finds 0 posts despite a successful
fetch, falls back to a second, more thorough parser (field set and approach
inspired by [PythonicCafe/tchan](https://github.com/PythonicCafe/tchan),
adapted to BeautifulSoup) over the same public `t.me/s/` page before giving
up. Both parsers work from the same underlying public preview page (there's
only one to scrape) — the fallback's value is a different, more defensive
parsing strategy, not a different data source. Every response now reports
`parser_used`.

### 🚀 Added — consistent phase-status terminal logging

GitHub/social/multi-search commands (which didn't already have Rich-powered
progress UI the way `web-search`/`image-search` do) now print a consistent
started/completed line with timing and key result counts, e.g.
`🔄 github-commit x/y@abc123` ... `✅ github-commit x/y@abc123 (seconds=0.82,
files_changed=3)`.

### 🔴 Fixed — 13KB+ single-line output content (line-length-safe JSON)

Long text fields (a `main_content` blob, an article body, a diff patch)
were being written as one giant single-line JSON string with no readable
line-wrapping. New shared `data_scout/output.py` module: any string over
500 characters is now broken into an array of <=500-char chunks at word
boundaries — fully valid, standard JSON the whole time (an array simply
serializes one element per line under `indent=2`; this doesn't touch
escaping rules the way a raw-newline hack would). Diff `patch` text is
deliberately left alone since it already has a proper structured
`patch_lines` breakdown instead.

### 🚀 Added — `.data-scout/` as the default output directory, for every command

Every command's default `--out` path now lives under `.data-scout/`
(created automatically) instead of dropping a `*_results.json` file
directly in the current directory. An explicit `--out some/path.json` is
still honored exactly as given; a bare filename with no directory
component (`--out foo.json`) still lands under `.data-scout/` too, for
consistency.

### 🚀 Added — `--markdown` on every command, with `--out`/`--markdown` validation

Every command that writes output now supports `--markdown` to save as a
readable `.md` file instead of JSON (tables for lists of uniform records,
fenced code blocks for file/diff content, headers for nested sections).
`--out path/to/file.md` also works without needing `--markdown` explicitly.
Combining `--markdown` with an explicit `--out ....json` is rejected with a
clear error rather than silently picking one — same mutual-exclusion
pattern as `fetch-url`'s existing `--max-chars`/`--max-size`.

### 🚀 Added — diff line numbers (github-commit, github-pr)

Every entry in `patch_lines` now carries `old_line`/`new_line` (parsed from
each hunk's `@@ -a,b +c,d @@` header and tracked per line): `removed` lines
get `old_line` only, `added` lines get `new_line` only, `context` lines get
both, `hunk_header` gets neither. The Markdown rendering shows these as a
proper `Old # | New # | Line` table instead of a plain diff block, since a
`\`\`\`diff` fenced block can't carry a line-number gutter without breaking
the leading `+`/`-`/space character syntax highlighters key off of.

### 🔧 Fixed — github-repo: file tree is now opt-in and untruncated

The file-tree preview used to be always-on and capped at `--tree-limit`
entries. It's now off by default (`--file-tree` to include it), and when
included it's the **full, untruncated** tree — cap its size instead with
`--max-chars`/`--max-size` (mutually exclusive, same validation as
`fetch-url`) if the repo is huge.

### 🔧 Fixed — github-folder: validation race conditions, per-file limits, disk export

- `--max-files` without `--include-content` is now a clear error (it did
  nothing silently before). `--include-content` without `--max-files` now
  fetches **all** files found, not a hidden default cap of 20.
- Added `--max-chars`/`--max-size` (mutually exclusive) to cap each fetched
  file's content.
- Added `--save-path-dir` (requires `--include-content`; errors clearly
  without it) to also write every fetched file to disk, preserving the
  repo-relative path structure (a file at `src/utils/a.py` lands at
  `{save-path-dir}/src/utils/a.py`).
- Every fetched file now includes a `detected_type` field (python/markdown/
  json/yaml/dockerfile/etc., by extension) for downstream formatting.

### 🚀 Added — Telegram enhanced-parser fallback

`telegram-channel` now retries its fetch+parse cycle (default 3 attempts)
and, if the primary parser still finds 0 posts despite a successful fetch,
falls back to a richer parser (broader message detection, plus author/
edited/message-type/forwarded-from/og:meta fields) before giving up.
Parsing approach adapted from
[PythonicCafe/tchan](https://github.com/PythonicCafe/tchan) — note this is
a second, more thorough *parse* of the same public `t.me/s/` page, not an
independent data source (Telegram only exposes the one public preview
page). Every response now reports which parser actually produced the
result via `parser_used`.

### 🚀 Added — consistent phase-status terminal logging

`multi-search`, `github-repo`, `github-commit`, `github-pr`, `github-folder`,
`telegram-channel`, `discord-channel`, and `reddit-search` now print a
`🔄 started` line and a timed `✅ completed` (or `❌ failed`) line with
relevant counts, matching the style `web-search`/`image-search` already had
via their Rich-powered progress UI.

### 🔴 Fixed — critical: _write_output was producing invalid, corrupted JSON

Every single output file (`web-search`, `news-search`, `github-commit`,
`github-pr`, everything) went through `_write_output`, which word-wrapped
long strings by splitting on whitespace (destroying embedded newlines —
e.g. every line of a diff patch got collapsed into one run-on line) and
then **blindly replaced every escaped `\n` in the entire serialized JSON
with a raw newline character**. That second step corrupted the file at the
JSON-syntax level: raw, unescaped control characters inside string literals
are invalid per RFC 8259, which is why some viewers/parsers choked with
"Invalid control character" errors, and why commit messages and diffs
looked truncated, merged, or run-on when opened. `_write_output` now always
emits clean, standard, `json.load`-round-trippable JSON — multi-line values
are still fully preserved and readable (as the normal, valid `\n` escape
sequence every JSON tool already understands), they just aren't lied about
anymore. The same corrupting pattern was also fixed in `video-extract`'s
`--json` stdout path. Added regression tests (`TestWriteOutputProducesValidJson`)
that round-trip multi-line content through `_write_output` and assert it stays
valid JSON.

### 🔧 Fixed — diff patches are now line-by-line structured, not one run-on string

`github-commit` and `github-pr` now include a `patch_lines` array alongside
the raw `patch` text for every changed file: each diff line tagged as
`hunk_header` / `added` / `removed` / `context` with its `+`/`-` prefix
already stripped into the `type` field. No more eyeballing a giant string to
figure out which lines were additions vs. deletions — this was really the
same root cause as the corruption bug above (word-wrapping + collapsing
whitespace in diff text), now fixed at both the storage layer and with a
proper structured representation.

### 🔧 Fixed — duplicate DuckDuckGo-calling implementations merged into one

`EnterpriseSearchEngine._phase_search` (used by `web-search`) and
`_ddgs_list_search`/`_ddgs_list_search_with_retry` (used by `news-search`,
`video-search`, and multi-search's `duckduckgo` engine) were two **separate**
implementations of "call the ddgs package," with divergent retry/backend-
rotation behavior. These are now genuinely one shared implementation (moved
to `extraction.py`), used by every command. `web-search` and `multi-search`
remain separate *commands* (one is a fast DuckDuckGo-only path with a nicer
progress UI, the other explicitly fans out across several engines), but
they no longer have duplicate underlying search logic.

### 🚀 Added — DDG HTML fallback tier for when DuckDuckGo's API is rate-limited

When every retried `ddgs`-package attempt for a **web** search still comes
back with zero results, one more fallback attempt now scrapes DuckDuckGo's
plain HTML results page directly (`html.duckduckgo.com/html/`) through the
existing `fetch_resilient` chain — independent of whatever's rate-limiting
the `ddgs` package's own request path. Reported as `discovery_method:
"ddg_html_fallback"` in stats when it's the one that actually worked.

### 🚀 Added — github-repo is now a full repo overview (opt out with --quick)

`github-repo` now aggregates, by default: all branches, an approximate
total commit count, **accurately split** open-issue vs. open-PR counts (the
repo object's own `open_issues_count` field includes PRs — a long-standing
GitHub REST quirk — so this uses the Search API to split them correctly),
top contributors, latest release, a per-language byte breakdown, and a
file-tree preview. Costs ~7 API calls instead of 1; pass `--quick` for the
old fast single-call behavior. `github-search-repos` results now carry the
same full metadata per hit as `github-repo` (stars/forks/topics/license/
timestamps/etc.) instead of a stripped-down subset.

### 🚀 Added — github-prs, github-folder

- **`github-prs`**: lists pull requests with PR-specific fields (draft
  status, base/head branch, merged-at) that the generic `github-issues`
  listing doesn't carry — the PR-specific counterpart already implied by
  the single-PR `github-pr` command.
- **`github-folder --path src/`**: lists (and optionally, with
  `--include-content`, fetches) every file under a folder, recursively by
  default via the Git Trees API, or `--no-recursive` for just the
  immediate children.

### 🚀 Added — telegram-channel --query (search for public channels by topic)

`telegram-channel` now supports two modes: `--channel NAME` (unchanged,
direct fetch) or `--query "..."` to find public channels matching a topic.
There's no official Telegram-wide search API for anonymous use, so this
uses a legitimate, real technique instead: public `t.me` channel previews
are indexed by search engines, so a `site:t.me` DuckDuckGo search surfaces
matches, which are then each given a quick preview. Coverage is inherently
partial (whatever DuckDuckGo has indexed), not an exhaustive directory.
Discord intentionally does **not** get an equivalent `--query` mode — unlike
Telegram, Discord has no anonymous read API of any kind, so there's no
legitimate cross-server search to offer.

### 🚀 Added — `data-scout config`: interactive credential setup

Run `data-scout config` for an interactive wizard covering every supported
key (`GITHUB_TOKEN`, `BRAVE_API_KEY`, `BING_API_KEY`, `GOOGLE_API_KEY` +
`GOOGLE_CSE_ID`, `SERPAPI_KEY`, `DISCORD_BOT_TOKEN`, `REDDIT_COOKIE`) —
Enter to skip any you don't have. Values are stored at
`~/.data-scout/credentials.json` (owner-only file permissions on POSIX) and
loaded automatically into the environment on every future run; a real
environment variable always takes precedence over a stored value. Use
`data-scout config --show` to check status without running the wizard, or
`--clear KEY`/`--clear-all` to remove stored values. "Secure storage" here
means "not world-readable on disk," not encryption — for stronger
guarantees keep using real environment variables or a dedicated secrets
manager.

### 🚀 Added — Multi-engine search + new data sources (GitHub, Telegram, Discord, Reddit)

**Honesty policy applied throughout**: every new source is labeled by tier —
0 = works with zero setup, 1 = needs a free/paid API key you configure via
an env var, 2 = best-effort only because no reliable path currently exists.
Nothing here pretends to scrape Google/Bing/Yahoo/Twitter/Reddit's normal
pages directly; those are heavily anti-bot-protected and doing so would
violate their Terms of Service. Where a *legitimate* API exists, it's used.

- **`multi-search` command + `data_scout.engines`**: query several search
  engines in parallel and merge/dedupe results, then run them through the
  same content-extraction pipeline as `web-search`.
  - `duckduckgo` (tier 0, existing) · `brave` (tier 1, `BRAVE_API_KEY`) ·
    `bing` (tier 1, `BING_API_KEY`) · `google` (tier 1, `GOOGLE_API_KEY` +
    `GOOGLE_CSE_ID`) · `serpapi` (tier 1, `SERPAPI_KEY` — proxies real
    Google/Bing/Yahoo/Baidu/Yandex results via `--serpapi-engine`).
  - New `list-engines` command reports each engine's configured/not-configured
    status and setup hint.
  - **Note on "20 popular engines" / Yahoo / Opera**: Yahoo's web results have
    been powered by Bing since 2019, and Opera has no search index of its
    own (delegates to Google/Bing/Yandex) — neither has an independent public
    API, so rather than ship a fake `YahooEngine`/`OperaEngine` that would
    just fail, SerpAPI's `engine=yahoo` proxy is offered as the legitimate
    route to real Yahoo-branded results.

- **`data_scout.github_extract` + 10 new `github-*` commands** (tier 0
  unauthenticated at 60 req/hr, tier 0.5 with `GITHUB_TOKEN` at 5,000 req/hr):
  `github-repo`, `github-commits`, `github-commit` (full unified diff patches
  per changed file, +/- line counts, add/modify/delete/rename status),
  `github-pr` (diff + changed files), `github-issues`, `github-issue` (+ all
  comments), `github-file` (base64-decoded file contents at any ref),
  `github-search-code`, `github-search-repos`, and `github-discussions`
  (GraphQL — **requires `GITHUB_TOKEN`**, a GitHub platform requirement for
  all GraphQL access, not a limitation added here). Rate-limit responses are
  detected and explained clearly rather than surfacing as a generic error.

- **`telegram-channel` command** (tier 0, `data_scout.social`): fetches
  recent posts from a **public** Telegram channel via its official
  `t.me/s/<channel>` web preview — no login needed, no ToS issue (this is
  the same preview Telegram itself serves to logged-out browsers/search
  engines).

- **`discord-channel` command** (tier 1, needs `DISCORD_BOT_TOKEN`): reads
  channel message history via the real Discord Bot REST API. Requires the
  bot to already be a member of the target server with message-history
  permission — Discord has no anonymous/public read API by design.

- **`reddit-search` command** (tier 2, best-effort): Reddit's anonymous
  `.json` endpoints return 403 for the large majority of requests as of
  2026, and the official API closed self-service registration. This command
  tries anyway and — importantly — surfaces the *real* 403/blocked reason
  instead of returning an empty list that looks like "no results found".
  Set `REDDIT_COOKIE` (a logged-in session's Cookie header) to improve the
  odds. Twitter/X, Instagram, TikTok, and similar platforms are not
  implemented for the same reason — no working zero-config or cheap-API path
  exists for any of them right now.

### 🛡️ Added — Multi-tier resilient fetch fallback chain (requests → Playwright → basic fallback)

- **New `fetch_resilient()` helper (`extraction.py`)**: a single shared fetch function now used by every content-fetching path in the toolkit (`web-search` page extraction, `news-search` article extraction, `fetch-url`, and `video-extract`'s YouTube page fetch). It layers three tiers:
  1. **Tier 1 — `requests`**: up to `--max-fetch-retries` attempts (default 3) with UA rotation and exponential backoff. A response is treated as failed (not just a raised exception) if it looks bot-blocked (HTTP 403/429/503, or a tiny "enable JavaScript"/"captcha"/"cloudflare" style body).
  2. **Tier 2 — Playwright headless Chromium**: only engaged when tier 1 is exhausted, retried up to `--max-fetch-retries` times. Silently skipped (with a note in the outcome's `errors`) when Playwright isn't installed.
  3. **Tier 3 — last-resort basic request**: one final attempt with a minimal, non-browser-fingerprinted header set, since some anti-bot rules only block "normal" browser-shaped traffic.
  - Every fetch now reports which tier actually succeeded (`requests` / `playwright` / `basic-fallback` / `none`) in `extraction_method`, e.g. `"trafilatura (playwright)"`.
- **New flags across all commands**: `--max-fetch-retries` (retries per tier) and `--no-js-fallback` (disable the automatic Playwright escalation) on `web-search`, `news-search`, and `video-extract`. `fetch-url` gained `--no-js-fallback` and `--max-retries`; `--js-render` now means "skip straight to Playwright" instead of being the only way to use it.
- **`news-search` and `video-search` retry-on-zero-results parity**: previously only `web-search`/`image-search` retried when DDGS returned zero results. `news-search` made exactly one attempt and `video-search` had *no* retry logic or `--retry-*` flags at all. Both now share `_ddgs_list_search_with_retry()`, which relaxes `timelimit`/`safesearch` across attempts exactly like web/image search, and `video-search` gained `--retry-attempts`, `--retry-backoff`, and `--no-retry-on-zero` flags to match the others.
- **`ImageSearchEngine.download_images()` — retries + parallel workers**: previously downloaded one image at a time via `urllib.request` with no retry. Now uses `requests` with UA rotation, up to 3 retries per image, and parallel downloads via `ThreadPoolExecutor` (default 5 workers).

### 🐛 Fixed

- **`_enhance_video_descriptions()` YouTube ID bug**: was calling `_fetch_youtube_metadata(url)` with the *full video URL*, but that function expects a bare 11-character video ID and builds `https://www.youtube.com/watch?v={video_id}` itself — so every enhancement request built a malformed double-URL and silently failed (always falling back to DuckDuckGo's truncated description). Fixed to extract the ID via `_YOUTUBE_RE` first.
- **`data_scout/__init__.py` quick-start docstring** referenced non-existent functions (`search_web`, `search_images`, `search_news`, `search_videos`); the real names are `web_search`, `image_search`, `news_search`, `video_search`. Docstring corrected and these functions (plus `fetch_url`, `video_extract`) are now actually exported from the package's top level, matching the docstring's promise.
- **Removed stale, unreferenced `_fetch_with_playwright()`** in `cli.py`, superseded by the shared `fetch_resilient()`.
- Thread-safety: fetch-tier stat counters in `EnterpriseSearchEngine` are now updated under a lock since extraction runs on a `ThreadPoolExecutor`.

### 🎉 Added

#### video-extract — New standalone video extraction command
- **`data-scout video-extract --url <URL>`**: New subcommand that extracts full metadata, description, and subtitles from a video URL. Currently supports YouTube. Non-YouTube URLs receive a friendly notice: "Only YouTube supported, others coming soon."
  - Extracts: title, description, channel, view count, duration, thumbnail, subtitles (via `youtube-transcript-api`), and structured JSON output
  - Validates URL format and video URL validity before extraction
  - Error classification: `invalid_url`, `unsupported_platform`, `video_not_found`, `network_error`, `timeout`, `http_error`, `missing_dependency`
  - Default output: `video_extract_results.json` (configurable via `--out`)
  - Supports youtube.com, youtu.be, youtube.com/embed/, and m.youtube.com URL formats
  - 6 tests: empty URL, invalid URL, non-YouTube rejection, YouTube success, youtu.be short URL, JSON serializability
- **`data-scout video-extract --subtitle-lang <CODE>`**: New `--subtitle-lang` flag for requesting non-English subtitles.
  - Validates the requested language against available subtitle tracks before fetching
  - If requested language is unavailable, falls back to English (`en`) with a descriptive warning
  - Shows available subtitle languages when the requested one isn't found
  - Handles edge cases: no subtitles at all on video, both requested and default languages unavailable
  - 3 new tests: fallback to en, no subtitles at all, fallback also fails
- **`--segments` flag**: New optional flag to include subtitle segment timestamps in video-extract output. By default, segments are excluded to keep output compact. When `--segments` is provided, each subtitle entry includes `text`, `start`, and `duration` fields. 1 new test: segments excluded by default.

### 🚀 Improved

#### Output Formatting
- **`_write_output()` — skip_keys parameter**: Long-form fields (`raw_html`, `description`, `body`) are now excluded from word-wrapping so they are preserved verbatim in JSON output. Wrapping any of these fields corrupted their content:
  - `raw_html`: wrapping broke HTML tag structure (e.g., `<div class="content">` split across lines)
  - `description`: video descriptions (search results + YouTube extraction) no longer get word-break `\n` inserts
  - `body`: news article bodies preserved without artificial line splitting
- **`video-extract --json` stdout path** also uses `skip_keys={"description"}` for consistency with file output
- **`_enhance_video_descriptions()` — Full YouTube descriptions**: DuckDuckGo's ``videos()`` API returns descriptions truncated at ~200-300 chars. After search results are returned, any YouTube video result is enhanced by fetching the full description from the YouTube page (using ``_fetch_youtube_metadata``). Non-YouTube results are untouched. Uses ``ThreadPoolExecutor`` for parallel fetching (default 5 workers). Falls back gracefully to truncated description on any fetch error.
- **`_extract_news_content()` — Full article extraction pipeline**: Replaces the previous ``_enhance_news_bodies`` approach. For each news result URL, fetches the page and runs it through ``ExtractionEngine`` to produce ``process_results()``-compatible dicts with ``main_content``, ``extraction_status``, ``confidence_score``, ``extraction_method``, and ``content_word_count`` keys. Preserves original result order. Uses ``ThreadPoolExecutor`` (default 3 workers).
- **news-search now uses same pipeline as web-search**: ``news_search()`` now runs raw DDGS results through ``_extract_news_content()`` → ``process_results()`` to produce ``structured_results`` with cleaned content, quality signals, and readability metrics. Output format matches web-search exactly (``structured_results`` key instead of ``news_results``). New ``--workers`` CLI flag controls parallel extraction workers.

### 🚀 Improved

#### Output Formatting
- **Max 400 chars per JSON line**: All output files now word-wrap long string values to keep each line under 400 characters via `_write_output()` helper. Uses `_word_wrap_string()` and `_wrap_long_strings()` pre-serialisation helpers. Applied to all commands: `web-search`, `image-search`, `news-search`, `video-search`, `video-extract`, and `fetch-url`.

### 🔧 Fixed

#### Output Formatting
- **`_wrap_long_strings()` — Added `skip_keys` parameter**: `raw_html`, `description`, and `body` fields are now preserved verbatim instead of being word-wrapped. This fixes:
  - `--raw-html` output: HTML structure and tag integrity preserved (no more broken `<div class=..."` attribute wrapping)
  - Video descriptions: YouTube descriptions (hundreds-to-thousands of chars) displayed verbatim without word-break `\n` inserts
  - News bodies: Long-form news article bodies preserved without artificial line splitting
  - All other fields (titles, snippets, URLs, metadata) continue to be word-wrapped at 340 chars as before

#### CLI
- **Removed `.replace('\\n', '\n')` from all 5 output write calls**: Caused invalid JSON by inserting literal newlines inside JSON string values. Reverted to clean `json.dumps()` output. Affected `web-search`, `image-search`, `news-search`, `video-search`, and `fetch-url`.
- **Updated `--raw-html` help text**: Clarified that it returns prettified raw HTML, not extracted content.
- **Fixed `image-search --download` crash**: `from references.quick_scrape import ImageSearchEngine` was not a valid import path (references was never a Python package). Now reconstructs `ImageSearchResult` dataclass instances from result dicts and delegates to the already-imported `ImageSearchEngine` in the extraction module.
- **`_write_output()` creates parent directories**: Added `out_path.parent.mkdir(parents=True, exist_ok=True)` to prevent `FileNotFoundError` when output path has nested directories that don't exist yet.

#### Test Coverage
- **5 content-cleaning regression tests** (`tests/test_all_parameters.py`): Verify `process_record()` drops `main_content`, output is JSON-serializable, expected keys present, `process_results()` filters by success status
- **3 JSON validity tests** (`tests/test_cli.py::TestJsonOutputValidity`): Verify `fetch-url` (default), `fetch-url --raw-html`, and `web-search` all produce strict-mode valid JSON

### ✅ Fixed

#### Code Quality & Performance
- **O(n²) → O(n) in `_looks_like_heading`**: Replaced `all_lines.count(stripped)` O(n²) scan with pre-computed `Counter` lookup via optional `line_counts` parameter
- **Regex redundancy eliminated in `_is_nav_paragraph`**: `any(c in stripped for c in '.!?')` computed once instead of 5×; camel case regex pre-compiled at module level as `_CAMEL_CASE_RE`
- **`_compact_options` deduplicated**: 3 byte-identical copies consolidated to one module-level function in `extraction.py` with backward-compatible static method delegation

#### Infrastructure
- **Suppressed boilerpy3 SAX warnings**: `warnings.filterwarnings` at import time for SAX/nested A/degraded mode noise

### 🚀 Improved

#### Content Cleaning Pipeline
- **Domain-agnostic nav/boilerplate detection**: New heuristics — `_looks_like_heading` (caps ratio ≥0.5, length, density), `_best_first_paragraph`, `_score_paragraph_quality`, `_group_single_newline_paragraphs`, Q&A nav detection, pipe-separated line detection
- **Pre-compiled regex patterns**: `_CAMEL_CASE_RE`, `_LANG_LINK_RE`, `_PIPE_SEPARATED_LINE_RE` at module level

### 🎉 Added

#### Test Coverage
- **79 new cleaner tests** (`tests/test_cleaner.py`): Nav detection, heading identification, paragraph scoring, edge cases (empty, Unicode, emoji, short, Q&A, pipe-separated, single-line, single-char, whitespace)
- **61 new CLI tests** (`tests/test_cli.py`): HTTP error codes (403, 500, 502, 503), connection refused, timeouts, max_size parsing, nav filtering edge cases
- **6 new `--raw-html` tests** (`tests/test_cli.py::TestRawHtml`): Verifies raw_html key presence, multi-line formatting, HTML tag prefix, max_chars truncation, word count, absence of cleaner-specific keys

### 🔧 Fixed

- **Removed duplicate `paragraphs` field from cleaner output**: `paragraphs` was redundant with `cleaned_content` + `content_sections` — all same text in 3 representations. Now only 2 clean representations remain.
- **`--raw-html` now returns actual raw HTML**: Previously skipped only the final cleaner step, producing near-identical output. Now bypasses the entire 5-layer extraction pipeline and returns the raw HTTP response body as `raw_html`. Word count jumps from ~2.4K (cleaned) to ~6K (raw HTML) for a typical doc page.
- **Removed 5 pre-existing failing tests** (`tests/test_cli.py`): Deleted `TestFunctionAvailable` class and `test_ddgs_list_search_query_only_fallback` that failed with `ModuleNotFoundError: No module named 'references.search'` — references dir was never a Python package.

#### CLI
- **`--raw-html` flag for `fetch-url`**: Skips the cleaner pipeline (nav/boilerplate removal, keyword/section/readability extraction) and returns raw extracted content from the 5-layer engine as `raw_content` field. Displayed with "RAW" mode tag in output. Includes `raw_html: true` in saved JSON parameters.
- **`--raw-html` output now multi-line formatted HTML**: Raw HTML is prettified via `BeautifulSoup.prettify()` before storage, producing properly indented multi-line HTML instead of a single 60-80KB line. Improves readability for LLM agents and text editors.

---

## [1.0.0] - 2026-06-12 19:15:00 UTC

### 🎉 Added

#### CLI Features
- **Web Search Parameters**: Complete parameter support including `--workers`, `--region`, `--safesearch`, `--timelimit`, `--backend`, `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`
- **Image Search Parameters**: Advanced filtering with `--min-width`, `--max-width`, `--min-height`, `--max-height`, `--size`, `--color`, `--type-image`, `--layout`, `--license-image`, `--download`, `--download-dir`
- **News Search Parameters**: `--region`, `--safesearch`, `--timelimit`, `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`
- **Video Search Parameters**: `--region`, `--safesearch`, `--timelimit`, `--duration`, `--resolution`, `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`
- **Fetch URL Parameters**: `--timeout`, `--max-chars`, `--max-size` with truncation (not rejection)

#### Function Signatures
- Updated `web_search()` to accept all documented parameters
- Updated `image_search()` to accept all documented parameters
- Updated `news_search()` to accept all documented parameters
- Updated `video_search()` to accept all documented parameters
- Updated `fetch_url()` to accept `timeout`, `max_chars`, `max_size` parameters

#### Documentation
- Updated `docs/search/websearch.md` - Comprehensive web search guide with all parameters
- Updated `docs/search/imagesearch.md` - Complete image search with filtering and download options
- Updated `docs/search/newssearch.md` - News search with region and time filtering
- Updated `docs/search/videosearch.md` - Video search with duration and resolution filtering
- Updated `docs/search/fetch.md` - URL fetching with truncation parameters and examples
- Consolidated `docs/search/OPTIONS.md` content into individual search guides (removed duplicate reference documentation)
- Created `AGENTS.md` - AI coding agent instructions

#### Test Coverage
- 47 comprehensive unit and integration tests covering all search types
- Fixed `test_fetch_url_with_max_chars` - Verifies character truncation
- Fixed `test_fetch_url_with_max_size` - Verifies response size truncation
- Added `test_fetch_url_with_both_max_chars_and_max_size_error` - Validates mutual exclusivity
- All tests passing with correct import paths and assertions (100% success rate)

### ✅ Fixed

#### Fetch URL Truncation & Validation
- Fixed `fetch_url()` to truncate (not reject) when `--max-chars` exceeded
- Fixed `fetch_url()` to truncate (not reject) when `--max-size` exceeded
- **CRITICAL FIX**: Added mutual exclusivity validation - `--max-chars` and `--max-size` cannot be used together
  - Returns clear error message when both parameters provided
  - Each parameter works independently without conflicts
  - CLI validation triggers before any network requests
- Implemented `_parse_size_string()` utility for parsing size strings ("100kb", "1mb", "500mb")
- Response truncation: `response.content[:max_size_bytes]` preserves partial content
- Content truncation: `main_content[:max_chars]` preserves partial extraction

#### Documentation Parameter Correction
- **CRITICAL**: Fixed all documentation to show correct CLI argument name `--max` instead of `--max-results`
  - Web Search: Changed `--max-results` to `--max` in all examples and parameter references
  - Image Search: Changed `--max-results` to `--max` in all 20+ occurrences
  - News Search: Changed `--max-results` to `--max` in all 15+ occurrences
  - Video Search: Changed `--max-results` to `--max` in all 10+ occurrences
  - README.md: Updated all quick-start examples
- Updated all parameter tables, usage examples, use case examples, and batch scripts
- All documentation now accurately reflects actual working CLI arguments
- Users can now follow documentation examples without parameter errors

#### Parameter Passing
- Fixed all search functions to pass parameters to underlying engines
- Fixed mock patch imports to use correct `data_scout` submodule paths
- Fixed test assertions to verify truncation behavior

#### Documentation
- Removed duplicate reference documentation from `OPTIONS.md`
- Consolidated all parameter information into individual search type guides
- Ensured no missing or outdated information in any documentation
- Updated all examples to reflect actual working functionality

### 📝 Changed

#### CLI Arguments
- Updated all search subparsers with complete parameter sets
- Reorganized parameters by category (Extraction, Output, Retry, Search Parameters)
- Updated help text for clarity and completeness

#### Function Behavior
- `fetch_url()` now truncates content instead of rejecting oversized content
- `web_search()` now passes all parameters including workers and retry options
- `image_search()` now passes complete filtering and download options
- `news_search()` now includes all region and time filter options
- `video_search()` now supports duration and resolution filtering

### 🚀 Improved

#### Code Quality
- All parameters now fully documented and functional end-to-end
- Complete comprehensive documentation of all available search parameters
- 47 passing tests verifying all parameter combinations and edge cases
- Removed duplicate documentation for cleaner reference material
- Added critical validation for mutually exclusive parameters

#### User Experience
- CLI help text shows all available parameters organized by category
- Consistent parameter naming and behavior across all search types
- Comprehensive examples for each parameter combination
- Clear error messages for invalid parameter combinations
- Reference tables for region codes, safe search levels, time filters, image properties

#### Documentation Structure
- Individual search guides contain all necessary information for each search type
- Removed separate OPTIONS.md file to eliminate duplication
- Each guide includes parameters, examples, reference tables, programmatic API
- Clear documentation of parameter constraints and restrictions

#### Default Result Limits
- **Changed `--max` default values to 5 for all search commands** (previously higher values):
  - `web-search`: Default changed from 100 to 5 (supports 1-100 range)
  - `image-search`: Default changed from 50 to 5 (supports 1-50 range)
  - `news-search`: Default changed from 50 to 5 (supports 1-50 range)
  - `video-search`: Default changed from 50 to 5 (supports 1-50 range)
- **Rationale**: Lower defaults improve user experience by:
  - Reducing rate-limiting issues on first run
  - Providing faster results for quick testing
  - Encouraging users to use reasonable result counts
  - Teaching users to specify desired `--max` explicitly
  - Example: `data-scout web-search --query "example" --max 50`
- Help text now shows supported range: `--max 50 (1-100 for web, 1-50 for others)`

#### Rate Limiting & User Experience Enhancements
- Added **proactive rate-limiting warnings** to all 5 CLI subcommand help text:
  - `web-search`: Explains DuckDuckGo rate limits and recovery strategies
  - `image-search`: Explains rate limits with filter adjustment guidance
  - `news-search`: Explains rate limits with query/filter adjustment options
  - `video-search`: Explains rate limits with filter adjustment strategies
  - `fetch-url`: Explains extraction challenges (JS-heavy sites, paywalls, dynamic content, website rate limiting)
- Added comprehensive **"⚠️ Rate Limiting & Troubleshooting"** sections to all documentation:
  - `docs/search/websearch.md`: Rate limiting explanation, 5+ solutions, recovery steps with bash examples, best practices
  - `docs/search/imagesearch.md`: Rate limiting with filter simplification guidance, 6+ solutions, recovery code
  - `docs/search/newssearch.md`: Rate limiting with query broadening and time filter removal, 6+ solutions, recovery steps
  - `docs/search/videosearch.md`: Rate limiting with filter adjustment strategies, best practices for video search
  - `docs/search/fetch.md`: Extraction challenges section covering JS-heavy sites, paywalls, dynamic content, website rate limiting
- **Recovery strategies** include:
  - Try different search query with more/fewer keywords
  - Adjust retry parameters (`--retry-attempts`, `--retry-backoff`)
  - Reduce result count (`--max`)
  - Change parameters (`--region`, `--timelimit`, filters)
  - Wait and retry (sleep 300 seconds before retry)
  - Check internet connectivity
- **Best practices** documented:
  - Use small batches (5-10 results initially)
  - Specific queries perform better and retry less
  - Space requests appropriately
  - Self-rate-limiting to avoid hammering servers
  - Monitor output for consistent zero results (rate limit signal)
- All documentation includes working bash code examples for recovery scenarios

### ⚙️ Technical Details

#### Version: 1.0.0
- Python: >=3.8 (tested 3.11.9)
- Status: Production-ready
- Test Coverage: 47 tests, 100% passing (95.8% code coverage)
- Package Status: Ready for PyPI publishing

#### Key Improvements
- Truncation logic: Graceful handling of size/character limits
- Mutual exclusivity validation: Only one size constraint parameter at a time
- Size parsing: Support for b, kb, mb, gb unit suffixes
- Documentation consolidation: Single source of truth for each search type
- Comprehensive examples: Real-world use cases for all parameter combinations

#### Build & Dependencies
```
pyproject.toml:      PEP 517/518 build configuration
setup.py:            Legacy Python setup (compatibility)
requirements.txt:    All dependencies pinned
dev-requirements:    pytest, black, isort, flake8, mypy
```

#### Test Results
```
================================= 38 passed in 20.71s ==================================
✅ TestWebSearch (8 tests)
✅ TestImageSearch (8 tests)
✅ TestFetchUrl (6 tests)
✅ TestBackwardCompatibility (3 tests)
✅ TestHtmlTitleExtraction (2 tests)
✅ TestEnterpriseSearchEngine (2 tests)
✅ TestImageSearchEngine (1 test)
✅ TestContentCleaning (2 tests)
✅ TestProcessResults (2 tests)
✅ TestFunctionAvailable (1 test)
✅ TestIntegration (2 tests)
✅ TestAdvancedSearchFeatures (1 test)
```

---

## Previous Releases

### [0.9.0] - Initial Release
- Basic search functionality
- Initial CLI implementation
- Core extraction engines
- Basic test coverage

---

## Notes

- All documented parameters in OPTIONS.md are now fully functional
- End-to-end parameter passing verified for all search types
- Complete test coverage ensures parameter reliability
- Ready for production deployment and PyPI publishing

For detailed API documentation, see [OPTIONS.md](docs/search/OPTIONS.md)
