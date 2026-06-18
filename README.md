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
data-scout/
  data_scout/
    __init__.py               # Package initialization + public API
    cli.py                    # CLI entry point (data-scout command)
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

- `ddgs`
- `duckduckgo_search`
- `trafilatura`
- `requests`
- `beautifulsoup4`
- `justext`
- `boilerpy3`
- `rich`
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

### Option 2: Install from PyPI (When Published)

```bash
pip install data-scout
```

### Verify Installation

```bash
data-scout --help
```

## Quick Start

### 1) Web Search (3 results)

```bash
data-scout web-search --query "dog" --max-results 3
```

### 2) Image Search (3 results)

```bash
data-scout image-search --query "dog" --max-results 3
```

### 3) News Search

```bash
data-scout news-search --query "dog" --max-results 5
```

### 4) Video Search

```bash
data-scout video-search --query "dog" --max-results 5
```

### 5) Fetch and Extract a Single URL

```bash
data-scout fetch-url --url "https://en.wikipedia.org/wiki/Dog"
```

### 6) Web Search with JSON Output

```bash
data-scout web-search --query "machine learning" --max-results 10 --json
```

## CLI Reference

### Global Help

```bash
data-scout --help
```

Subcommands:

- `web-search` - Search the web with content extraction
- `image-search` - Search for images
- `news-search` - Search for news articles
- `video-search` - Search for videos
- `fetch-url` - Extract content from a single URL

### web-search

```bash
data-scout web-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max-results, -m` (default: `10`): number of results to fetch
- `--json`: output as JSON to stdout
- `--timeout` (default: `5`): extraction timeout in seconds

**Example:**
```bash
data-scout web-search --query "machine learning" --max-results 5
```

### image-search

```bash
data-scout image-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max-results, -m` (default: `10`): number of images
- `--json`: output as JSON to stdout
- `--min-width` (default: `0`): minimum image width
- `--min-height` (default: `0`): minimum image height

**Example:**
```bash
data-scout image-search --query "landscape" --max-results 10 --min-width 1024 --min-height 768
```

### news-search

```bash
data-scout news-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max-results, -m` (default: `10`): number of articles
- `--json`: output as JSON to stdout

**Example:**
```bash
data-scout news-search --query "artificial intelligence" --max-results 5
```

### video-search

```bash
data-scout video-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max-results, -m` (default: `10`): number of videos
- `--json`: output as JSON to stdout

**Example:**
```bash
data-scout video-search --query "python tutorial" --max-results 5
```

### fetch-url

```bash
data-scout fetch-url --url "https://example.com" [options]
```

Options:

- `--url, -u` (required): URL to fetch and extract
- `--json`: output as JSON to stdout
- `--timeout` (default: `5`): request timeout in seconds

**Example:**
```bash
data-scout fetch-url --url "https://example.com/article"
```

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
from data_scout.extraction import EnterpriseSearchEngine
from data_scout.cleaner import process_results

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
from data_scout.extraction import ImageSearchEngine

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
from data_scout.extraction import ExtractionEngine

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
from data_scout.cleaner import advanced_clean_text

raw_text = "   Hello   world   with   extra    spaces   "
cleaned = advanced_clean_text(raw_text)
print(cleaned)  # Output: "Hello world with extra spaces"
```

## Output Files and JSON Shapes

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

### Web Search Retry

Web search retries when extraction success count is 0:

- Attempt 1 uses your configured options
- Later attempts relax restrictive options (for higher chance of results)
- Stops early after first successful extraction set

### Image Search Retry

Image search retries when valid image count is 0:

- Applies filters and counts valid images
- Retries up to configured attempts
- Stops early on first non-zero valid set

### DDGS Signature Compatibility

The project attempts multiple call signatures for DDGS methods to support version differences between `ddgs` and `duckduckgo_search` implementations.

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
data-scout web-search --query "artificial intelligence" --max-results 5
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
data-scout image-search --query "mountain scenery" --max-results 10 --min-width 1920 --min-height 1080
```

### Example C: News Search

```bash
data-scout news-search --query "technology breakthroughs" --max-results 5
```

### Example D: Video Search

```bash
data-scout video-search --query "python programming tutorial" --max-results 5
```

### Example E: Extract Content from Specific URL

```bash
data-scout fetch-url --url "https://en.wikipedia.org/wiki/Artificial_intelligence"
```

### Example F: Programmatic Web Search (Python)

```python
from data_scout.extraction import EnterpriseSearchEngine

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
pytest tests/ --cov=data_scout --cov-report=html
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
python -c "from data_scout import EnterpriseSearchEngine; print('OK')"
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
