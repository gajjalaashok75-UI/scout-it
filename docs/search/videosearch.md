# video-search & video-extract

## video-search

DuckDuckGo video search with duration, resolution, and license filters. When DuckDuckGo Videos returns nothing (its endpoint intermittently raises "No results found" for most queries), the pipeline automatically falls back to **YouTube search**, so the command reliably returns ranked results.

```bash
scout-it video-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max videos (1-50, default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/video_search_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `internet_archive,listennotes`) and merge with BM25F+vector re-ranking. Run `scout-it sources` for the list |
| `--auto-sources` | Let the source-selection bandit pick the best sources for this query type. Overrides `--sources` |
| `--region` `<region>` | DuckDuckGo region (default: `us-en`; example: `us-en`, `wt-wt`) |
| `--safesearch` `<level>` | Safe search mode: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | DuckDuckGo time limit: `d`, `w`, `m`, `y` |
| `--resolution` `<res>` | Video resolution filter: `high`, `standard` |
| `--duration` `<duration>` | Video duration filter: `short`, `medium`, `long` |
| `--license-videos` `<license>` | Video license filter |
| `--category` `<categories...>` | Video RSS categories to include (e.g. `technology science news`). Fetches YouTube channel RSS feeds alongside DuckDuckGo and ranks them together |
| `--rss` | Include video RSS discovery even without `--category` (pulls a default set of YouTube channels) |
| `--no-retry-on-zero` | Disable retries when 0 results are found (retries on by default) |
| `--retry-attempts` `<n>` | Retry attempts when 0 results are found (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |

### Examples

```bash
scout-it video-search --query "python tutorial" --max 5
scout-it video-search --query "tech talks" --category technology --duration long
scout-it video-search --query "breaking news" --timelimit d --resolution high
```

> `video-search` only lists videos (title, channel, views, duration, published) — it does not extract per-video content or download anything. Use `video-extract` for a single video's full metadata/subtitles.

## video-extract

Extract full metadata (title, channel, view/like counts, description, upload date) and, where available, subtitles/transcript from a single video URL. **YouTube only** today; other platforms return a clear `unsupported_platform` error.

```bash
scout-it video-extract --url "<youtube-url>" [options]
```

| Flag | Description |
|------|-------------|
| `--url` `<url>` | Video URL to extract, e.g. `https://www.youtube.com/watch?v=VIDEO_ID` or `https://youtu.be/VIDEO_ID` (required) |
| `--subtitle-lang` `<code>` | Preferred subtitle language code (default: `en`) |
| `--segments` | Include subtitle segments with timestamps (default: off) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/video_extract_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--json` | Output raw JSON to stdout |
| `--max-fetch-retries` `<n>` | Retry attempts per fetch tier (requests → Playwright) when fetching the video page (default: 3) |
| `--no-js-fallback` | Disable automatic Playwright fallback when the page fetch fails or looks blocked |

### Examples

```bash
scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
scout-it video-extract --url "https://youtu.be/dQw4w9WgXcQ" --subtitle-lang fr --segments
scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json
```

## Programmatic API

```python
from scout_it import video_search, video_extract

videos, stats = video_search("python tutorial", max_results=5)
for v in videos:
    print(v.get("title"), v.get("duration"))

result = video_extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ", subtitle_lang="en")
```

## Related documentation

- [web-search & news-search](./websearch.md)
- [image-search](./imagesearch.md)
- [README.md](../README.md)
