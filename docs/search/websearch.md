# Web Search Documentation

## Overview

Web search combines DuckDuckGo search functionality with multi-strategy content extraction and cleaning. It retrieves search results and extracts the main article content from each result using a 5-layer fallback strategy.

## Command Syntax

```bash
data-scout web-search [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--query` | `-q` | Search query string | `STRING` |

## Optional Options

### Extraction & Performance
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max` | `-m` | `100` | `INT` | Maximum results to fetch and extract (1-100) |
| `--timeout` | - | `5` | `INT` | Extraction timeout in seconds per URL (1-60) |
| `--workers` | `-w` | `4` | `INT` | Parallel extraction workers (1-16) |

### Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--out` | `-o` | `web_search_results.json` | `PATH` | Output file path |
| `--json` | - | `false` | `BOOL` | Output raw JSON to stdout instead of saving to file |

### Retry & Fallback (Optional)
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--no-retry-on-zero` | - | `false` | `BOOL` | Disable retry on zero successful extractions |
| `--retry-attempts` | - | `2` | `INT` | Number of retry attempts (1-5) |
| `--retry-backoff` | - | `1.0` | `FLOAT` | Backoff multiplier between retries |

### Search Parameters (DuckDuckGo)
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | `STRING` | Region/locale (e.g., `us-en`, `uk-en`, `wt-wt` for worldwide) |
| `--safesearch` | - | `moderate` | `ENUM` | Safe search level: `on`, `moderate`, `off` |
| `--timelimit` | - | - | `ENUM` | Time filter: `d` (day), `w` (week), `m` (month), `y` (year) |
| `--backend` | - | `auto` | `ENUM` | Search backend: `auto`, `html`, `lite` |

## Output File

By default, results are saved to:

```
web_search_results.json
```

Location: Full path is displayed in console with 📂 emoji

### Output Format

```json
{
  "query": "machine learning",
  "search_type": "web",
  "timestamp": "2026-06-12T10:30:00Z",
  "total_results": 3,
  "results": [
    {
      "position": 1,
      "title": "Article Title",
      "url": "https://example.com/article",
      "snippet": "Brief description...",
      "main_content": "Full extracted article content...",
      "extraction_method": "trafilatura",
      "confidence_score": 0.95,
      "metrics": {
        "word_count": 1250,
        "sentence_count": 42,
        "paragraph_count": 8
      }
    }
  ],
  "metadata": {
    "extraction_timeout": 5,
    "successful_extractions": 3,
    "failed_extractions": 0
  }
}
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `position` | INT | Result position (1-indexed) |
| `title` | STRING | Page title |
| `url` | STRING | Full URL |
| `snippet` | STRING | Search result snippet |
| `main_content` | STRING | Extracted article body |
| `extraction_method` | STRING | Which extractor succeeded (trafilatura, justext, boilerpy3, readability, beautifulsoup) |
| `confidence_score` | FLOAT | 0.0-1.0 confidence in extraction quality |
| `metrics` | OBJECT | Text metrics (word_count, sentence_count, paragraph_count) |

## Content Extraction Strategy

Web search uses a 5-layer fallback approach:

1. **Trafilatura** (confidence: 1.0) - Best for news/articles
2. **Justext** (confidence: 0.95) - Good for general content
3. **BoilerPy3** (confidence: 0.90) - Robust fallback
4. **Readability** (confidence: 0.85) - Alternative extractor
5. **BeautifulSoup** (confidence: 0.70) - Ultimate HTML parser fallback

If layer 1 succeeds, layers 2-5 are skipped. This ensures fast extraction with best quality.

## Usage Examples

### Basic Web Search

Search for articles about Python:

```bash
data-scout web-search --query "Python programming"
```

### With Custom Workers & Timeout

Increase extraction parallelism:

```bash
data-scout web-search --query "Python" --max 20 --workers 8 --timeout 10
```

### UK Region, Safe Search Off

Search in UK region without filtering:

```bash
data-scout web-search --query "technology" --region uk-en --safesearch off
```

### Last Week's Articles

Get recent articles:

```bash
data-scout web-search --query "news" --timelimit w --max 20
```

### With Retry Configuration

Retry on failures:

```bash
data-scout web-search --query "research" --retry-attempts 3 --retry-backoff 1.5
```

### Custom Output Location

Save to specific file:

```bash
data-scout web-search --query "data" --out ./results/my_results.json
```

### JSON Output to Console

Output raw JSON to stdout for piping:

```bash
data-scout web-search --query "machine learning" --json > results.json
```

### Combined Options

Comprehensive search with multiple parameters:

```bash
data-scout web-search \
  --query "renewable energy" \
  --max 20 \
  --workers 8 \
  --timeout 15 \
  --region "us-en" \
  --safesearch "on" \
  --json
```

## Programmatic API

### Python Example

```python
from gakr_ddgs.extraction import EnterpriseSearchEngine
from gakr_ddgs.cleaner import process_results

# Create search engine
engine = EnterpriseSearchEngine()

# Perform search
results = engine.search(
    query="machine learning applications",
    max_results=10,
    extraction_timeout=5
)

# Clean and process results
cleaned_results = process_results(results)

# Access results
for result in cleaned_results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Quality: {result['quality_score']:.0%}")
    print(f"Sentiment: {result['sentiment']}")
    print()
```

### Custom Extraction from Results

```python
from gakr_ddgs.extraction import EnterpriseSearchEngine

engine = EnterpriseSearchEngine()
results = engine.search(query="Python", max_results=3)

for result in results:
    print(f"{result.title}")
    print(f"  URL: {result.url}")
    print(f"  Confidence: {result.confidence_score:.0%}")
    print(f"  Method: {result.extraction_method}")
    if result.main_content:
        print(f"  Content (first 200 chars): {result.main_content[:200]}...")
    print()
```

## Region Codes

Common region codes for `--region` parameter:

| Code | Region |
|------|--------|
| `us-en` | United States (English) |
| `uk-en` | United Kingdom (English) |
| `ca-en` | Canada (English) |
| `au-en` | Australia (English) |
| `de-de` | Germany (German) |
| `fr-fr` | France (French) |
| `it-it` | Italy (Italian) |
| `es-es` | Spain (Spanish) |
| `jp-ja` | Japan (Japanese) |
| `cn-zh` | China (Chinese) |
| `br-pt` | Brazil (Portuguese) |
| `in-en` | India (English) |
| `wt-wt` | Worldwide |

## Safe Search Levels

| Level | Description |
|-------|-------------|
| `on` | Strict filtering - excludes adult content |
| `moderate` | Balanced filtering - default |
| `off` | No filtering - all results shown |

## Time Filters

| Code | Description |
|------|-------------|
| `d` | Last 24 hours (Day) |
| `w` | Last 7 days (Week) |
| `m` | Last 30 days (Month) |
| `y` | Last 365 days (Year) |

## Performance Considerations

| Factor | Impact | Notes |
|--------|--------|-------|
| `--max` | High | More results = longer execution time. Start with 5-10. |
| `--timeout` | Medium | Higher timeout allows complex pages but slows search. Default 5s is good for most sites. |
| Network Speed | High | Slow internet significantly increases total time |
| Target Websites | High | Some sites extract faster than others |

**Typical Execution Times:**
- 5 results: 5-15 seconds
- 10 results: 10-30 seconds
- 20 results: 20-60 seconds

## Troubleshooting

### No Results Returned

**Problem:** Search returns empty results

**Solutions:**
- Verify internet connection
- Try a different, simpler query
- Increase `--max` to 20
- Check if DuckDuckGo is accessible in your region

### Low Confidence Scores

**Problem:** All results show confidence < 0.5

**Causes:**
- Website uses heavy JavaScript rendering
- Poor HTML structure
- Content behind login or paywall

**Solutions:**
- Try `--timeout 15` for complex pages
- Try different search query
- Check if URL is accessible in browser manually

### Slow Extraction

**Problem:** Search takes too long

**Solutions:**
- Reduce `--max` to 5
- Decrease `--timeout` to 3 (faster but potentially incomplete)
- Check your internet speed
- Try during off-peak hours

### Extraction Failures

**Problem:** Most results show `confidence_score` = 0.0

**Causes:**
- All layers failed to extract content
- Website may require JavaScript
- Content may be dynamically loaded

**Solutions:**
- These sites may not be suitable for automated extraction
- Try with `--timeout 15` to allow more time
- Manual extraction may be necessary for such sites

## Advanced Usage

### Batch Processing Multiple Queries

```bash
for query in "Python" "JavaScript" "Go programming"; do
  data-scout web-search --query "$query" --max 5
done
```

### Processing Results with JQ

```bash
data-scout web-search --query "AI" --json | jq '.results[] | {title, confidence_score}'
```

### Extracting Only High-Confidence Results

```bash
data-scout web-search --query "news" --json | \
  jq '.results[] | select(.confidence_score > 0.8)'
```

## ⚠️ Rate Limiting & Troubleshooting

### DuckDuckGo Rate Limiting

DuckDuckGo search is **rate-limited**. If you encounter zero results after multiple retry attempts:

**Solutions:**
1. **Try different query** - Use more specific or different keywords
2. **Adjust retry parameters:**
   - Increase `--retry-attempts` (default: 2)
   - Increase `--retry-backoff` (default: 1.0 seconds)
3. **Reduce results** - Lower `--max` parameter to reduce load
4. **Change parameters** - Try different `--region`, `--timelimit`, or `--backend`
5. **Wait and retry** - Wait several minutes before trying again
6. **Check connection** - Verify internet connectivity

### Zero Results After Retries

If the search still returns zero results:

```bash
# Before retrying - wait a few minutes
sleep 300

# Try with simplified query
data-scout web-search --query "simplified query" --max 5

# Try different region
data-scout web-search --query "original query" --region "wt-wt" --max 5

# Try with fewer retries but more backoff
data-scout web-search --query "original query" \
  --retry-attempts 3 \
  --retry-backoff 2.0
```

### Best Practices for Reliability

- **Small batches** - Search for 5-10 results at a time
- **Specific queries** - More specific = faster, fewer retries
- **Reasonable timeouts** - Default 5s extraction timeout is good
- **Rate yourself** - Don't hammer with repeated requests
- **Monitor output** - Watch for consistent zero results (rate limit signal)

## Related Documentation

- [Image Search](./imagesearch.md)
- [URL Fetch](./fetch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
