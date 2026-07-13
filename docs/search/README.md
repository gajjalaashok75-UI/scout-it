# Search Documentation

Comprehensive guides for all scout-it search types.

## Available Search Types

| Search Type | File | Description |
|-------------|------|-------------|
| [Web Search](./websearch.md) | `websearch.md` | Search the web with content extraction and cleaning |
| [Image Search](./imagesearch.md) | `imagesearch.md` | Search for images with dimension filtering |
| [News Search](./newssearch.md) | `newssearch.md` | Search for news articles |
| [Video Search](./videosearch.md) | `videosearch.md` | Search for videos |
| [URL Fetch](./fetch.md) | `fetch.md` | Extract and clean content from a single URL |

## Quick Command Reference

### Web Search
```bash
scout-it web-search --query "your query" --max 10
```

### Image Search
```bash
scout-it image-search --query "your query" --max 10 --min-width 800 --min-height 600
```

### News Search
```bash
scout-it news-search --query "your query" --max 10
```

### Video Search
```bash
scout-it video-search --query "your query" --max 10
```

### URL Fetch
```bash
scout-it fetch-url --url "https://example.com"
```

## Common Features

All search commands support:

- **JSON Output**: Add `--json` flag to output raw JSON instead of formatted results
- **Markdown Output**: Add `--markdown` flag to format output as Markdown
- **Max Results**: Limit results with `--max N` (default: 10)

## Output Format

By default, results are saved to JSON files in the `.scout-it/` directory:

- `.scout-it/struct_format_results.json` - Web search results
- `.scout-it/image_search_results.json` - Image search results
- `.scout-it/news_search_results.json` - News search results
- `.scout-it/video_search_results.json` - Video search results
- `.scout-it/url_fetch_result.json` - Single URL fetch result

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
from scout_it.extraction import EnterpriseSearchEngine

engine = EnterpriseSearchEngine()
results = engine.search(
    query="your query",
    max_results=10
)
```

## Performance Tips

1. **Use appropriate timeout**: Increase for complex pages (default fetch timeout: 25s)
2. **Limit results**: Start with small `--max` for testing
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
