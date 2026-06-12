# Web Search Documentation

## Overview

Web search combines DuckDuckGo search functionality with multi-strategy content extraction and cleaning. It retrieves search results and extracts the main article content from each result using a 5-layer fallback strategy.

## Command Syntax

```bash
gakr-ddgs web-search [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--query` | `-q` | Search query string | `STRING` |

## Optional Options

| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | `INT` | Maximum number of search results to fetch and extract |
| `--timeout` | - | `5` | `INT` | Extraction timeout in seconds per URL |
| `--json` | - | `false` | `BOOL` | Output raw JSON to stdout instead of saving to file |

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
gakr-ddgs web-search --query "Python programming"
```

**Output:**
```
Title: Python Programming Guide
URL: https://example.com/python-guide
Confidence: 95%
Content: [extracted article text...]
📂 Results saved to: C:\path\to\web_search_results.json
```

### Search with Custom Timeout

For pages that load slowly, increase timeout:

```bash
gakr-ddgs web-search --query "climate change research" --timeout 15
```

### Limit Results

Search but only extract from top 5 results:

```bash
gakr-ddgs web-search --query "artificial intelligence" --max-results 5
```

### JSON Output to Console

Output raw JSON to stdout for piping:

```bash
gakr-ddgs web-search --query "machine learning" --json > results.json
```

### Combined Options

```bash
gakr-ddgs web-search \
  --query "renewable energy" \
  --max-results 20 \
  --timeout 10 \
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

## Performance Considerations

| Factor | Impact | Notes |
|--------|--------|-------|
| `--max-results` | High | More results = longer execution time. Start with 5-10. |
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
- Increase `--max-results` to 20
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
- Reduce `--max-results` to 5
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
  gakr-ddgs web-search --query "$query" --max-results 5
done
```

### Processing Results with JQ

```bash
gakr-ddgs web-search --query "AI" --json | jq '.results[] | {title, confidence_score}'
```

### Extracting Only High-Confidence Results

```bash
gakr-ddgs web-search --query "news" --json | \
  jq '.results[] | select(.confidence_score > 0.8)'
```

## Related Documentation

- [Image Search](./imagesearch.md)
- [URL Fetch](./fetch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
