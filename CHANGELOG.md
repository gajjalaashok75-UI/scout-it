# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-06-12 14:30:00 UTC

### 🎉 Added

#### CLI Features
- **Web Search Parameters**: Added complete parameter support including `--workers`, `--region`, `--safesearch`, `--timelimit`, `--backend`, `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`
- **Image Search Parameters**: Added dimension filtering (`--min-width`, `--max-width`, `--min-height`, `--max-height`), image properties (`--size`, `--color`, `--type-image`, `--layout`, `--license-image`), and retry options
- **News Search Parameters**: Added `--region`, `--safesearch`, `--timelimit`, `--no-retry-on-zero`, `--retry-attempts`, `--retry-backoff`
- **Video Search Parameters**: Added `--region`, `--safesearch`, `--timelimit`, `--resolution`, `--duration`, `--license-videos`
- **Fetch URL Parameters**: Added `--timeout` parameter with 5-second default

#### Function Signatures
- Updated `web_search()` to accept all documented parameters
- Updated `image_search()` to accept all documented parameters
- Updated `news_search()` to accept retry parameters: `retry_on_zero_success`, `retry_attempts`, `retry_backoff`
- Updated `video_search()` to accept all documented parameters
- Updated `fetch_url()` to accept `timeout` parameter

#### Documentation
- Created `docs/search/OPTIONS.md` - Comprehensive parameter reference for all search types
- Created `docs/search/websearch.md` - Web search usage guide
- Created `docs/search/imagesearch.md` - Image search usage guide
- Created `docs/search/newssearch.md` - News search usage guide
- Created `docs/search/videosearch.md` - Video search usage guide
- Created `docs/search/fetch.md` - URL fetching guide
- Created `AGENTS.md` - AI coding agent instructions

#### Test Coverage
- Added 38 comprehensive unit tests covering all search types
- Added parametric tests for web search with custom workers and options
- Added parametric tests for image search with dimension filtering
- Added parametric tests for news search with retry options
- Added parametric tests for video search
- Added integration tests for fetch URL with timeout
- All tests use correct import paths: `gakr_ddgs.cli`, `gakr_ddgs.extraction`, `gakr_ddgs.cleaner`

### ✅ Fixed

#### Parameter Passing
- Fixed `web_search()` to pass all parameters to `EnterpriseSearchEngine`
- Fixed `news_search()` to pass retry parameters through to underlying engine
- Fixed `fetch_url()` to accept and use `timeout` parameter
- Fixed `image_search()` to pass all image filtering parameters

#### Test Infrastructure
- Fixed all mock patch imports from old `search` module to correct `gakr_ddgs` submodules
- Updated 16+ mock.patch calls to use correct import paths
- Fixed test assertions to match actual function signatures
- Fixed backward compatibility test for `fatchurl` function

#### Import Paths
- Corrected `gakr_ddgs.cli.EnterpriseSearchEngine` mock patches
- Corrected `gakr_ddgs.extraction.ExtractionEngine` mock patches
- Corrected `gakr_ddgs.cleaner.process_results` mock patches

### 📝 Changed

#### CLI Arguments
- Updated `web-search` subparser with all new parameters
- Updated `image-search` subparser with dimension filtering options
- Updated `news-search` subparser with retry and region options
- Updated `video-search` subparser with resolution and duration options
- Updated `fetch-url` subparser with timeout parameter

#### Function Behavior
- `web_search()` now properly constructs `search_options` dict with all parameters
- `image_search()` now passes complete filtering options to engine
- `news_search()` now forwards retry parameters to underlying search engine
- `video_search()` now includes all parameter options in search

### 🚀 Improved

#### Code Quality
- All parameters now documented and functional end-to-end
- Complete documentation of all available search parameters
- Comprehensive test coverage for parameter passing
- Consistent parameter naming across all search types

#### User Experience
- CLI help text shows all available parameters with descriptions
- Parameters are well-organized by search type
- Consistent parameter handling across all search functions

### ⚙️ Technical Details

#### Version: 1.0.0
- Python: >=3.8
- Status: Production-ready
- Test Coverage: 38 comprehensive tests, all passing
- Package Status: Ready for PyPI publishing

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
