# Search Documentation

Comprehensive guides for all gakr-ddgs search types.

## Available Search Types

| Search Type | File | Description |
|-------------|------|-------------|
| [Web Search](./websearch.md) | `websearch.md` | Search the web with content extraction and cleaning |
| [Image Search](./imagesearch.md) | `imagesearch.md` | Search for images with dimension filtering |
| [News Search](./newssearch.md) | `newssearch.md` | Search for news articles |
| [Video Search](./videosearch.md) | `videosearch.md` | Search for videos |
| [URL Fetch](./fetch.md) | `fetch.md` | Extract and clean content from a single URL |

## Complete Reference

**[Extended Options Reference →](./OPTIONS.md)** - Complete reference of ALL supported parameters for all search types, including:
- Full parameter documentation tables
- Default values for each option
- All filter options (regions, safe search, time limits, etc.)
- Enum values and choices
- Combined usage examples

## Quick Command Reference

### Web Search
```bash
gakr-ddgs web-search --query "your query" --max-results 10 --timeout 5
```

### Image Search
```bash
gakr-ddgs image-search --query "your query" --max-results 10 --min-width 800 --min-height 600
```

### News Search
```bash
gakr-ddgs news-search --query "your query" --max-results 10
```

### Video Search
```bash
gakr-ddgs video-search --query "your query" --max-results 10
```

### URL Fetch
```bash
gakr-ddgs fetch-url --url "https://example.com" --timeout 5
```

## Common Features

All search commands support:

- **JSON Output**: Add `--json` flag to output raw JSON instead of formatted results
- **Timeout**: Control request timeout with `--timeout SECONDS` (default: 5)
- **Max Results**: Limit results with `--max-results N` (default: 10)

## Output Format

By default, results are saved to JSON files:

- `web_search_results.json` - Web search results
- `image_search_results.json` - Image search results
- `news_search_results.json` - News search results
- `video_search_results.json` - Video search results
- `url_fetch_result.json` - Single URL fetch result

Use `--json` flag to output to stdout instead.

## Configuration

### Environment Variables

```bash
# Custom User-Agent (optional)
export USER_AGENT="YourBot/1.0"

# Request timeout (optional)
export REQUEST_TIMEOUT="10"

# Max workers for parallel extraction (optional)
export MAX_WORKERS="8"
```

### Python API Configuration

When using the Python API, pass parameters directly:

```python
from gakr_ddgs.extraction import EnterpriseSearchEngine

engine = EnterpriseSearchEngine()
results = engine.search(
    query="your query",
    max_results=10,
    extraction_timeout=5
)
```

## Performance Tips

1. **Use appropriate timeout**: Increase for complex pages, decrease for speed
2. **Limit results**: Start with small `--max-results` for testing
3. **Parallel extraction**: Uses ThreadPoolExecutor with optimal worker count
4. **Content extraction**: Multi-strategy fallback ensures best extraction quality

## Error Handling

All search types handle errors gracefully:

- Network timeouts are caught and reported
- Missing dependencies are warned
- Invalid queries return empty results
- Output always contains metadata about the search

## See Also

- [AGENTS.md](../../AGENTS.md) - AI agent instructions and architecture
- [README.md](../../README.md) - Main documentation
- [../PACKAGE_CONVERSION_SUMMARY.md](../PACKAGE_CONVERSION_SUMMARY.md) - Technical details
