# URL Fetch Documentation

## Overview

URL fetch extracts main content from a single URL and cleans it for analysis. It uses the same 5-layer content extraction strategy as web search, automatically detecting and extracting article content, removing boilerplate, and providing structured output.

## Command Syntax

```bash
gakr-ddgs fetch-url [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--url` | `-u` | URL to fetch and extract | `STRING` |

## Optional Options

| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--timeout` | - | `5` | `INT` | Request timeout in seconds (e.g., 10, 30) |
| `--max-chars` | - | - | `INT` | Maximum characters to extract (e.g., 10000, 50000) - truncates content if exceeded |
| `--max-size` | - | - | `STRING` | Maximum response size to accept (e.g., `100kb`, `1mb`, `500mb`) - truncates if exceeded |
| `--json` | - | `false` | `BOOL` | Output raw JSON to stdout instead of saving to file |
| `--out` | `-o` | `url_fetch_result.json` | `PATH` | Custom output file path |

**⚠️ Important:** Only one of `--max-chars` OR `--max-size` can be used at a time. Using both together will return an error. Choose one parameter based on your constraint type:
- Use `--max-chars` to limit by character count in extracted content
- Use `--max-size` to limit by response file size (total HTML downloaded)

## Output File

By default, results are saved to:

```
url_fetch_result.json
```

Location: Full path is displayed in console with 📂 emoji

### Output Format

```json
{
  "url": "https://example.com/article",
  "search_type": "fetch",
  "status": "success",
  "timestamp": "2026-06-12T10:30:00Z",
  "result": {
    "title": "Article Title",
    "main_content": "Full extracted article text...",
    "extraction_method": "trafilatura",
    "confidence_score": 0.95,
    "html_title": "Page Title from HTML",
    "meta_description": "Meta description from page",
    "metrics": {
      "word_count": 2150,
      "sentence_count": 68,
      "paragraph_count": 12
    },
    "cleaned_content": {
      "cleaned_text": "Cleaned and normalized text...",
      "sections": ["Section 1", "Section 2"],
      "sentiment": {
        "positive": 0.45,
        "negative": 0.15,
        "neutral": 0.40
      },
      "quality_score": 0.87,
      "top_keywords": ["keyword1", "keyword2", "keyword3"]
    }
  },
  "metadata": {
    "status_code": 200,
    "response_time_ms": 1250,
    "content_length": 45678
  }
}
```

## Field Descriptions

### Top Level

| Field | Type | Description |
|-------|------|-------------|
| `url` | STRING | The URL that was fetched |
| `search_type` | STRING | Always "fetch" |
| `status` | STRING | "success" or "error" |
| `timestamp` | STRING | When fetch was performed |
| `result` | OBJECT | Extraction results (see below) |
| `metadata` | OBJECT | Response metadata |

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | STRING | Extracted article title |
| `main_content` | STRING | Full extracted article body |
| `extraction_method` | STRING | Which layer succeeded (trafilatura, justext, boilerpy3, readability, beautifulsoup) |
| `confidence_score` | FLOAT | 0.0-1.0 confidence in extraction |
| `html_title` | STRING | HTML `<title>` tag content |
| `meta_description` | STRING | Meta description from `<meta>` tag |
| `metrics` | OBJECT | Text statistics (word_count, sentence_count, paragraph_count) |
| `cleaned_content` | OBJECT | Cleaned and processed content |

### Cleaned Content Fields

| Field | Type | Description |
|-------|------|-------------|
| `cleaned_text` | STRING | Text with normalized whitespace and formatting |
| `sections` | ARRAY | Extracted sections/paragraphs |
| `sentiment` | OBJECT | Sentiment analysis (positive, negative, neutral scores) |
| `quality_score` | FLOAT | 0.0-1.0 content quality estimate |
| `top_keywords` | ARRAY | Most relevant keywords extracted |

## Content Extraction Strategy

URL fetch uses the same 5-layer fallback approach as web search:

1. **Trafilatura** (confidence: 1.0) - Best for news/articles
2. **Justext** (confidence: 0.95) - Good for general content
3. **BoilerPy3** (confidence: 0.90) - Robust fallback
4. **Readability** (confidence: 0.85) - Alternative extractor
5. **BeautifulSoup** (confidence: 0.70) - Ultimate HTML parser fallback

## Usage Examples

### Extract Article

Fetch and extract an article:

```bash
gakr-ddgs fetch-url --url "https://en.wikipedia.org/wiki/Machine_learning"
```

**Output:**
```
Title: Machine Learning - Wikipedia
Confidence: 98%
Method: trafilatura
Words: 3245
...
📂 Results saved to: C:\path\to\url_fetch_result.json
```

### News Article

Extract from a news site:

```bash
gakr-ddgs fetch-url --url "https://technews.com/ai-breakthrough"
```

### Blog Post

Extract from a blog:

```bash
gakr-ddgs fetch-url --url "https://medium.com/@author/how-to-learn-python"
```

### With Max Characters Limit

Extract but limit to first 5000 characters:

```bash
gakr-ddgs fetch-url --url "https://example.com/article" --max-chars 5000
```

### With Max Size Constraint

Fetch only if response is under 2 MB:

```bash
gakr-ddgs fetch-url --url "https://example.com/document" --max-size 2mb
```

### With Custom Timeout

Increase timeout for slow-loading pages:

```bash
gakr-ddgs fetch-url --url "https://example.com" --timeout 30
```

### With Custom Output Location

Save to custom file:

```bash
gakr-ddgs fetch-url --url "https://example.com" --out ./results/my_fetch.json
```

### With JSON Output to Console

Output JSON to stdout instead of file:

```bash
gakr-ddgs fetch-url --url "https://example.com" --json
```

### ❌ INVALID: Both constraints together

```bash
# This will ERROR - only use ONE constraint parameter
gakr-ddgs fetch-url --url "https://example.com" --max-chars 10000 --max-size 5mb
# ERROR: Cannot use both --max-chars and --max-size together. Use only ONE parameter at a time
```

### Technical Documentation

Extract from documentation:

```bash
gakr-ddgs fetch-url --url "https://docs.python.org/3/tutorial/"
```

### Longer Timeout

For slow or complex pages:

```bash
gakr-ddgs fetch-url \
  --url "https://example.com/heavy-page" \
  --timeout 15
```

### JSON Output

Get raw JSON for processing:

```bash
gakr-ddgs fetch-url \
  --url "https://example.com/article" \
  --json > article.json
```

### Wikipedia Entry

Extract knowledge base article:

```bash
gakr-ddgs fetch-url --url "https://en.wikipedia.org/wiki/Artificial_intelligence"
```

## Programmatic API

### Python Example - Basic Extraction

```python
from gakr_ddgs.extraction import ExtractionEngine

engine = ExtractionEngine()
content, method, confidence = engine.extract(
    url="https://example.com/article",
    timeout=5
)

print(f"Extraction Method: {method}")
print(f"Confidence: {confidence:.0%}")
print(f"Content Length: {len(content)} characters")
print(f"\nFirst 500 characters:\n{content[:500]}")
```

### Python Example - Cleaned Content

```python
from gakr_ddgs.cli import fetch_url

# Use CLI function directly
result = fetch_url(url="https://en.wikipedia.org/wiki/Dogs")

# Access structured result
if result and "result" in result:
    content_info = result["result"]["cleaned_content"]
    print(f"Quality Score: {content_info['quality_score']:.0%}")
    print(f"Sentiment: {content_info['sentiment']}")
    print(f"Keywords: {content_info['top_keywords']}")
```

### Python Example - Error Handling

```python
from gakr_ddgs.extraction import ExtractionEngine

engine = ExtractionEngine()

try:
    content, method, confidence = engine.extract(
        url="https://invalid-url-example.test",
        timeout=5
    )
    
    if confidence < 0.5:
        print("Warning: Low confidence extraction")
    
    print(f"Successfully extracted via {method}")
    
except Exception as e:
    print(f"Extraction failed: {e}")
```

### Python Example - Batch URL Processing

```python
from gakr_ddgs.extraction import ExtractionEngine

engine = ExtractionEngine()

urls = [
    "https://example.com/article1",
    "https://example.com/article2",
    "https://example.com/article3",
]

results = []
for url in urls:
    try:
        content, method, confidence = engine.extract(url, timeout=10)
        results.append({
            "url": url,
            "length": len(content),
            "method": method,
            "confidence": confidence
        })
        print(f"✓ {url}: {len(content)} chars ({confidence:.0%})")
    except Exception as e:
        print(f"✗ {url}: {e}")

print(f"\nProcessed {len(results)}/{len(urls)} URLs successfully")
```

## Common Use Cases

### Single Article Analysis

Extract a specific article for analysis:

```bash
gakr-ddgs fetch-url \
  --url "https://example.com/tech-article" \
  --json > analysis.json
```

### Research Data Collection

Extract research papers or documentation:

```bash
gakr-ddgs fetch-url \
  --url "https://arxiv.org/pdf/2306.12345" \
  --timeout 15
```

### Content Backup

Create a local copy of web content:

```bash
gakr-ddgs fetch-url \
  --url "https://important-blog.com/article" \
  --json > backup.json
```

### Monitoring

Check if a page is still accessible and extractable:

```bash
# Run periodically
gakr-ddgs fetch-url \
  --url "https://critical-page.com" \
  --json > status.json
```

### Data Extraction Pipeline

Extract multiple URLs in batch:

```bash
# Read URLs from file
while IFS= read -r url; do
  echo "Fetching: $url"
  gakr-ddgs fetch-url --url "$url" --json > "result_${counter}.json"
  ((counter++))
done < urls.txt
```

## Performance Considerations

| Factor | Impact | Notes |
|--------|--------|-------|
| Page complexity | High | Complex pages take longer to extract |
| `--timeout` | Medium | Higher timeout = more wait time for results |
| Network speed | High | Internet speed significantly impacts fetch time |
| Server response | High | Slow servers = slower extraction |

**Typical Execution Times:**
- Simple article: 2-5 seconds
- Complex page: 5-15 seconds
- Very heavy page: 15-30 seconds

## Timeout Recommendations

| Scenario | Recommended Timeout |
|----------|-------------------|
| Simple text article | 3-5 seconds |
| Blog post with images | 5-8 seconds |
| Heavy news site | 10-15 seconds |
| Academic papers | 15-20 seconds |
| Very heavy pages | 20-30 seconds |

## Troubleshooting

### Low Confidence Score

**Problem:** Result shows `confidence_score` < 0.5

**Causes:**
- Website uses heavy JavaScript rendering
- Poor HTML structure
- Content not suitable for extraction

**Solutions:**
- Increase `--timeout` to 15
- Try `--timeout 20` for very complex pages
- Check if URL is accessible in browser manually
- Some websites may not be extractable

### Timeout Error

**Problem:** Gets timeout exception

**Solutions:**
- Increase `--timeout` value
- Check your internet speed
- Try again later (server may be slow)
- Verify URL is correct and accessible

### Empty Content

**Problem:** `main_content` is empty or very short

**Causes:**
- Website design not suitable for extraction
- Content loaded via JavaScript (not in initial HTML)
- Page may be a gallery or mostly images

**Solutions:**
- Try increasing timeout
- Check page manually in browser
- Some page types can't be extracted
- Use `--json` to see all available fields

### Connection Refused

**Problem:** Can't connect to URL

**Causes:**
- URL is incorrect or offline
- Website is blocking automated requests
- Network issue

**Solutions:**
- Verify URL is correct
- Try in browser to confirm accessibility
- Check for `robots.txt` restrictions
- Some sites block automated access

### Slow Extraction

**Problem:** Takes very long to extract

**Solutions:**
- Reduce `--timeout` to 5 (faster but less complete)
- Check your internet speed
- Try at different time
- Website may be slow

## Advanced Usage

### Extract and Parse Content

```bash
# Get JSON output
gakr-ddgs fetch-url --url "https://example.com/article" --json | \
  jq '.result | {title, confidence_score, word_count: .metrics.word_count}'
```

### Monitor Website Changes

```bash
# Store current version
gakr-ddgs fetch-url --url "https://example.com" --json > version_1.json

# Later, check again
gakr-ddgs fetch-url --url "https://example.com" --json > version_2.json

# Compare
diff version_1.json version_2.json
```

### Extract Links from Content

```bash
# Extract HTML and parse links
gakr-ddgs fetch-url --url "https://example.com" --json | \
  jq '.result.main_content' | \
  grep -oP 'https?://[^\s)]+' | sort -u
```

### Quality Assessment

```bash
# Check multiple URLs and compare quality
for url in "https://site1.com/article" "https://site2.com/article"; do
  gakr-ddgs fetch-url --url "$url" --json | \
    jq "{url: .url, quality: .result.cleaned_content.quality_score}"
done
```

### Sentiment Analysis

```bash
# Extract sentiment from fetched content
gakr-ddgs fetch-url --url "https://example.com" --json | \
  jq '.result.cleaned_content.sentiment'
```

## ⚠️ Extraction & Rate Limiting Notes

### Content Extraction Challenges

Extraction may fail or return limited content for:

1. **JavaScript-heavy sites** - Content loaded dynamically after page load
   - Solution: Try with `--max-chars` to get partial content

2. **Paywalled content** - Articles behind login or subscription walls
   - Solution: These typically won't be extractable; check access first

3. **Dynamic content** - Content that changes after JavaScript execution
   - Solution: May get limited content; use `--timeout` parameter if needed

4. **Rate limiting** - Target website may rate-limit your requests
   - Solution: Space out requests, respect robots.txt, add delays

5. **Authentication required** - Protected pages needing login
   - Solution: Not available via fetch-url; requires browser-based access

### Extraction Success Tips

```bash
# For pages with strict size limits
gakr-ddgs fetch-url --url "https://example.com" --max-chars 5000

# For problematic sites, increase timeout
gakr-ddgs fetch-url --url "https://example.com" --timeout 30

# Check extraction result metadata
gakr-ddgs fetch-url --url "https://example.com" --json | \
  jq '.result.extraction_metadata'
```

### Best Practices

- **Verify URL works** - Test URL in browser first
- **Check robots.txt** - Respect the site's robots.txt
- **Space requests** - Don't hammer sites with rapid requests
- **Reasonable timeouts** - 5-30 seconds is typical
- **Monitor success rate** - Track which sites extract well

## Related Documentation

- [Web Search](./websearch.md)
- [Image Search](./imagesearch.md)
- [News Search](./newssearch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
