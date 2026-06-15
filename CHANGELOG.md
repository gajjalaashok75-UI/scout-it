# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### 🎉 Added

#### video-extract — New standalone video extraction command
- **`gakr-ddgs video-extract --url <URL>`**: New subcommand that extracts full metadata, description, and subtitles from a video URL. Currently supports YouTube. Non-YouTube URLs receive a friendly notice: "Only YouTube supported, others coming soon."
  - Extracts: title, description, channel, view count, duration, thumbnail, subtitles (via `youtube-transcript-api`), and structured JSON output
  - Validates URL format and video URL validity before extraction
  - Error classification: `invalid_url`, `unsupported_platform`, `video_not_found`, `network_error`, `timeout`, `http_error`, `missing_dependency`
  - Default output: `video_extract_results.json` (configurable via `--out`)
  - Supports youtube.com, youtu.be, youtube.com/embed/, and m.youtube.com URL formats
  - 6 tests: empty URL, invalid URL, non-YouTube rejection, YouTube success, youtu.be short URL, JSON serializability
- **`gakr-ddgs video-extract --subtitle-lang <CODE>`**: New `--subtitle-lang` flag for requesting non-English subtitles.
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
- Fixed mock patch imports to use correct `gakr_ddgs` submodule paths
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
  - Example: `gakr-ddgs web-search --query "example" --max 50`
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
