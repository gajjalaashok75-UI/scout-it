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
web-search/
  search.py                 # Main CLI entrypoint
  quick_scrape.py           # Search engines + extraction engines
  main_content_cleaner.py   # Content cleaning + structuring
  test_search.py            # Pytest suite
  results.json              # Example web-search output
  image_search_results.json # Example image-search output
  news_results.json         # Example news-search output
  video_results.json        # Example video-search output
  my_images/                # Downloaded images
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

From the project root:

```bash
pip install ddgs duckduckgo_search trafilatura requests beautifulsoup4 justext boilerpy3 rich pytest
```

On Windows, if you have multiple Python versions, prefer this style:

```bash
C:/Users/<you>/AppData/Local/Programs/Python/Python313/python.exe -m pip install ddgs duckduckgo_search trafilatura requests beautifulsoup4 justext boilerpy3 rich pytest
```

## Quick Start

### 1) Web Search (3 results)

```bash
python search.py web-search --query "dog" --max 3 --workers 2 --out results.json
```

### 2) Image Search (3 results)

```bash
python search.py image-search --query "dog" --max 3 --out image_search_results.json
```

### 3) Image Search + Download + Dimension Filter

```bash
python search.py image-search --query "dog" --max 10 --min-width 800 --min-height 600 --download --download-dir ./my_images --out image_filtered_results.json
```

### 4) News Search

```bash
python search.py news-search --query "dog" --max 5 --out news_results.json
```

### 5) Video Search

```bash
python search.py video-search --query "dog" --max 5 --duration short --out video_results.json
```

### 6) Fetch and Extract a Single URL

```bash
python search.py fetch-url --url "https://en.wikipedia.org/wiki/Dog" --out url_fetch_result.json
```

## CLI Reference

### Global Help

```bash
python search.py --help
```

Subcommands:

- `web-search`
- `image-search`
- `news-search`
- `video-search`
- `fetch-url`

### web-search

```bash
python search.py web-search --query "<text>" [options]
```

Options:

- `--query, -q` (required): search query
- `--max, -m` (default: `100`): max candidate results
- `--workers, -w` (default: `8`): parallel extraction workers
- `--out, -o` (default: `struct_format_results.json`): output path
- `--region` (example: `us-en`, `wt-wt`)
- `--safesearch` (`on|moderate|off`, default: `moderate`)
- `--timelimit` (`d|w|m|y`)
- `--backend` (`auto|html|lite`, default: `auto`)
- `--no-retry-on-zero`: disable retries when successful extraction count is 0
- `--retry-attempts` (default: `2`)
- `--retry-backoff` (default: `1.0` seconds)

### image-search

```bash
python search.py image-search --query "<text>" [options]
```

Options:

- `--query, -q` (required)
- `--max, -m` (default: `50`)
- `--out, -o` (default: `image_search_results.json`)
- `--download, -d`: download matched images
- `--download-dir` (default: `downloaded_images`)
- `--region` (default: `us-en`)
- `--safesearch` (`on|moderate|off`, default: `moderate`)
- `--timelimit` (`d|w|m|y`)
- `--size` (for example: `Small`, `Medium`, `Large`, `Wallpaper`)
- `--color`
- `--type-image` (for example: `photo`, `clipart`, `gif`, `transparent`, `line`)
- `--layout` (for example: `Square`, `Tall`, `Wide`)
- `--license-image`
- `--min-width`
- `--max-width`
- `--min-height`
- `--max-height`
- `--no-retry-on-zero`
- `--retry-attempts`
- `--retry-backoff`

Validation rule:

- `min-width <= max-width`
- `min-height <= max-height`

### news-search

```bash
python search.py news-search --query "<text>" [options]
```

Options:

- `--query, -q` (required)
- `--max, -m` (default: `50`)
- `--out, -o` (default: `news_search_results.json`)
- `--region` (default: `us-en`)
- `--safesearch` (`on|moderate|off`)
- `--timelimit` (`d|w|m|y`)

### video-search

```bash
python search.py video-search --query "<text>" [options]
```

Options:

- `--query, -q` (required)
- `--max, -m` (default: `50`)
- `--out, -o` (default: `video_search_results.json`)
- `--region` (default: `us-en`)
- `--safesearch` (`on|moderate|off`)
- `--timelimit` (`d|w|m|y`)
- `--resolution` (`high|standard` depending on backend support)
- `--duration` (`short|medium|long`)
- `--license-videos`

### fetch-url

```bash
python search.py fetch-url --url "https://example.com" [options]
```

Options:

- `--url, -u` (required)
- `--out, -o` (default: `url_fetch_result.json`)

## Programmatic API

You can import and use the functions directly from `search.py`.

```python
from search import web_search, image_search, news_search, video_search, fetch_url

web_results, web_stats = web_search(
    "dog",
    max_results=10,
    workers=4,
    retry_attempts=2,
    backend="auto",
)

img_results, img_stats = image_search(
    "dog",
    max_results=20,
    min_width=800,
    min_height=600,
    retry_attempts=2,
)

news_results, news_stats = news_search("dog", max_results=10)
video_results, video_stats = video_search("dog", max_results=10, duration="short")
url_result = fetch_url("https://en.wikipedia.org/wiki/Dog")
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

### Example A: Strict Safe Search Web Query

```bash
python search.py web-search --query "machine learning" --max 25 --safesearch on --timelimit m --backend auto --workers 6 --out ml_web.json
```

### Example B: Global Region Image Query

```bash
python search.py image-search --query "sunset" --max 30 --region wt-wt --size Large --layout Wide --out sunset_images.json
```

### Example C: Creative Commons-like Image Search + Download

```bash
python search.py image-search --query "city skyline" --max 20 --license-image "public" --download --download-dir ./my_images --out skyline_images.json
```

### Example D: News by Time Window

```bash
python search.py news-search --query "AI regulation" --max 20 --timelimit w --out ai_news_week.json
```

### Example E: Short Videos Only

```bash
python search.py video-search --query "python tutorial" --max 10 --duration short --resolution high --out py_videos_short.json
```

### Example F: Direct URL Content Extraction

```bash
python search.py fetch-url --url "https://docs.python.org/3/tutorial/" --out python_tutorial_page.json
```

## Testing

Run all tests:

```bash
python -m pytest -q
```

Current suite covers:

- Search function availability
- Web/image function behavior
- Retry and filtering logic
- URL validation and fetch behavior
- Backward compatibility for `fatchurl`

## Troubleshooting

### 1) `pip3 show` and runtime versions do not match

On Windows, `pip3` can point to a different Python than your runtime.

Check runtime interpreter:

```bash
python -c "import sys; print(sys.executable)"
```

Install dependencies into the exact interpreter you run:

```bash
C:/Users/<you>/AppData/Local/Programs/Python/Python313/python.exe -m pip install ddgs duckduckgo_search
```

### 2) No search results returned

Try:

- Increase `--max`
- Disable strict filters
- Set `--safesearch off`
- Remove `--timelimit`
- Keep retries enabled

### 3) Image download errors (403/404)

This can happen due to remote host restrictions. The downloader continues with remaining images.

### 4) Dependency import error in `quick_scrape.py`

Install missing packages:

```bash
pip install ddgs duckduckgo_search rich trafilatura requests beautifulsoup4 justext boilerpy3
```

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
