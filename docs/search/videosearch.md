# Video Search Documentation

## Overview

Video search retrieves videos from DuckDuckGo matching your query. Results include video titles, URLs, descriptions, thumbnails, and metadata.

## Command Syntax

```bash
data-scout video-search [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--query` | `-q` | Video search query string | `STRING` |

## Optional Options

### Results & Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max` | `-m` | `50` | `INT` | Maximum videos to return |
| `--out` | `-o` | `video_search_results.json` | `PATH` | Output file path |
| `--json` | - | `false` | `BOOL` | Output to stdout as JSON |

### Search Parameters
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | `STRING` | Region/locale |
| `--safesearch` | - | `moderate` | `ENUM` | Safe search: `on`, `moderate`, `off` |
| `--timelimit` | - | - | `ENUM` | Time filter: `d` (day), `w` (week), `m` (month), `y` (year) |
| `--duration` | - | - | `ENUM` | Video duration: `short` (< 5 min), `medium` (5-30 min), `long` (> 30 min) |
| `--resolution` | - | - | `ENUM` | Resolution: `high`, `standard`, `any` |

### Retry Options
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--no-retry-on-zero` | - | `false` | `BOOL` | Disable retry on zero results |
| `--retry-attempts` | - | `2` | `INT` | Number of retry attempts |
| `--retry-backoff` | - | `1.0` | `FLOAT` | Backoff multiplier |

## Output File

By default, results are saved to:

```
video_search_results.json
```

Location: Full path is displayed in console with 📂 emoji

### Output Format

```json
{
  "query": "python tutorial",
  "search_type": "video",
  "timestamp": "2026-06-12T10:30:00Z",
  "total_results": 5,
  "results": [
    {
      "position": 1,
      "title": "Python For Beginners - Full Tutorial",
      "url": "https://www.youtube.com/watch?v=video123",
      "description": "Learn Python from scratch with this comprehensive tutorial...",
      "thumbnail": "https://img.youtube.com/vi/video123/default.jpg",
      "duration": "3:45:20",
      "views": "1.2M views",
      "source": "YouTube"
    }
  ],
  "metadata": {
    "search_datetime": "2026-06-12T10:30:00Z",
    "total_found": 5
  }
}
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `position` | INT | Result position (1-indexed) |
| `title` | STRING | Video title |
| `url` | STRING | Direct URL to the video |
| `description` | STRING | Video description/summary |
| `thumbnail` | STRING | Thumbnail image URL |
| `duration` | STRING | Video length (HH:MM:SS format) |
| `views` | STRING | View count (if available) |
| `source` | STRING | Video platform (YouTube, Vimeo, etc.) |

## Usage Examples

### Basic Video Search

Search for Python tutorials:

```bash
data-scout video-search --query "Python tutorial"
```

### Short Videos Only

Find short-form content (< 5 minutes):

```bash
data-scout video-search --query "motivation" --duration short --max 20
```

### Long-form Content (Courses)

Find full courses and lectures:

```bash
data-scout video-search --query "web development" --duration long --max 10
```

### High Resolution Videos

Find HD videos:

```bash
data-scout video-search --query "music" --resolution high --max 15
```

### Recent Videos

Get videos from the past day:

```bash
data-scout video-search --query "breaking news" --timelimit d --max 10
```

### Weekly Videos

Get trending videos:

```bash
data-scout video-search --query "trending" --timelimit w --max 30
```

### Custom Output

Save to specific file:

```bash
data-scout video-search --query "Python" --out ./results/python_videos.json
```

### JSON Output

Output to stdout:

```bash
data-scout video-search --query "tutorial" --json
```

### Comprehensive Video Research

Get detailed video results:

```bash
data-scout video-search \
  --query "machine learning course" \
  --duration "long" \
  --resolution "high" \
  --max 30 \
  --safesearch on \
  --json > ml_courses.json
```

## Video Duration Options

| Duration | Description |
|----------|-------------|
| `short` | Less than 5 minutes |
| `medium` | 5 to 30 minutes |
| `long` | More than 30 minutes |

## Video Resolution Options

| Resolution | Description |
|-----------|-------------|
| `high` | 720p or higher |
| `standard` | 480p to 720p |
| `any` | Any resolution |

Get 30 videos:

```bash
data-scout video-search --query "yoga exercises" --max 30
```

### JSON Output

Get raw JSON for processing:

```bash
data-scout video-search --query "photography tips" --json > video_results.json
```

### Different Topics

```bash
# Educational
data-scout video-search --query "quantum physics explained"

# Entertainment
data-scout video-search --query "funny cat videos"

# Gaming
data-scout video-search --query "Minecraft building tutorial"

# Music
data-scout video-search --query "guitar lesson for beginners"

# Fitness
data-scout video-search --query "30 minute workout"
```

## Programmatic API

### Python Example - Basic Search

```python
from gakr_ddgs.extraction import DDGS

ddgs = DDGS()
results = ddgs.videos(query="python programming", max_results=10)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Source: {result['source']}")
    print(f"Duration: {result['duration']}")
    print(f"Views: {result['views']}")
    print(f"URL: {result['url']}")
    print()
```

### Python Example - Filter by Duration

```python
from gakr_ddgs.extraction import DDGS

ddgs = DDGS()
results = ddgs.videos(query="tutorial", max_results=20)

def parse_duration(duration_str):
    """Convert HH:MM:SS to seconds"""
    parts = duration_str.split(':')
    hours = int(parts[0]) if len(parts) > 2 else 0
    minutes = int(parts[1]) if len(parts) > 1 else 0
    seconds = int(parts[2] if len(parts) > 2 else parts[0])
    return hours * 3600 + minutes * 60 + seconds

# Find videos between 10-30 minutes
for video in results:
    duration_sec = parse_duration(video['duration'])
    if 600 <= duration_sec <= 1800:  # 10-30 minutes
        print(f"{video['title']} - {video['duration']}")
```

### Python Example - Download Playlist

```python
import subprocess
from gakr_ddgs.extraction import DDGS

ddgs = DDGS()
results = ddgs.videos(query="web development crash course", max_results=5)

# Create playlist file for youtube-dl
with open('playlist.txt', 'w') as f:
    for result in results:
        f.write(result['url'] + '\n')
        print(f"Added: {result['title']}")

# Uncomment to download (requires youtube-dl)
# subprocess.run(['youtube-dl', '-a', 'playlist.txt'])
```

### Python Example - Analyze Video Results

```python
from gakr_ddgs.extraction import DDGS
import re

ddgs = DDGS()
results = ddgs.videos(query="productivity", max_results=20)

sources = {}
for video in results:
    source = video['source']
    if source not in sources:
        sources[source] = []
    sources[source].append(video)

print("Videos by Platform:")
for platform, videos in sorted(sources.items(), key=lambda x: -len(x[1])):
    print(f"\n{platform}: {len(videos)} videos")
    for v in videos[:3]:
        print(f"  - {v['title']}")
```

## Common Use Cases

### Learning New Skills

Search for tutorial series:

```bash
data-scout video-search \
  --query "web development bootcamp" \
  --max 15
```

### Research

Find educational videos:

```bash
data-scout video-search \
  --query "climate change science" \
  --max 10
```

### Entertainment

Find music or movies:

```bash
data-scout video-search \
  --query "trailer science fiction movie 2026" \
  --max 5
```

### Software Development

Find code walkthroughs:

```bash
data-scout video-search \
  --query "React hooks tutorial" \
  --max 20 \
  --json > react_videos.json
```

### Entertainment Collection

Create a list of videos for later:

```bash
data-scout video-search \
  --query "stand-up comedy special" \
  --max 30 \
  --json > comedy_videos.json
```

## Duration Classification

Videos often fall into these categories:

| Duration | Category | Use Case |
|----------|----------|----------|
| < 5 min | Clips/Shorts | Quick demos, highlights |
| 5-15 min | Short Videos | Quick tutorials, news |
| 15-60 min | Medium Videos | Tutorials, talks, episodes |
| 1-3 hours | Long Videos | Full courses, complete tutorials |
| 3+ hours | Full Courses | Complete training programs |

## Performance Considerations

| Factor | Impact | Notes |
|--------|--------|-------|
| `--max` | Low | Video search is fast (no extraction) |
| Query specificity | High | More specific = better results |
| Network Speed | Low | Lightweight requests |

**Typical Execution Times:**
- Any number of results: 2-5 seconds (very fast)

## Troubleshooting

### No Videos Found

**Problem:** Search returns empty results

**Solutions:**
- Try simpler, different keywords
- Topic may have limited video coverage
- Check if DuckDuckGo video search is available in your region
- Try more generic terms

### Too Few Results

**Problem:** Getting fewer videos than requested

**Solutions:**
- Increase `--max` to allow for more results
- Try different search terms
- Some queries have limited video coverage
- Use broader search terms

### Duplicate Results

**Problem:** Same video appears multiple times

**Solutions:**
- This is expected behavior (video from multiple sources/links)
- De-duplicate on client side if needed
- Use JSON output and filter by URL

### Video Not Accessible

**Problem:** Video link doesn't work

**Causes:**
- Video removed or made private
- Geographic restrictions
- Regional blocking

**Solutions:**
- Try downloading with appropriate tools (youtube-dl, etc.)
- Check if video available in your region
- Use proxy if geographic restrictions apply

## Advanced Usage

### Batch Video Search

Search multiple topics:

```bash
topics=("Python" "JavaScript" "Go" "Rust" "Kotlin")

for lang in "${topics[@]}"; do
  data-scout video-search \
    --query "${lang} tutorial" \
    --max 10 \
    --json > "videos_${lang}.json"
done
```

### Extract Video URLs

Get just the URLs for batch downloading:

```bash
data-scout video-search --query "course" --json | \
  jq -r '.results[] | .url' > urls.txt

# Download with youtube-dl
youtube-dl -a urls.txt
```

### Create Playlist File

Extract video URLs in playlist format:

```bash
data-scout video-search --query "music" --json | \
  jq -r '.results[] | .url' > my_playlist.m3u
```

### Analyze Video Sources

Find which platforms have most content:

```bash
data-scout video-search --query "tutorial" --max 50 --json | \
  jq '.results[] | .source' | sort | uniq -c | sort -rn
```

### Search Multiple Related Topics

```bash
# Create a research collection
for query in "machine learning" "deep learning" "neural networks"; do
  data-scout video-search \
    --query "$query" \
    --max 20 \
    --json > "research_${query// /_}.json"
done
```

## ⚠️ Rate Limiting & Troubleshooting

### DuckDuckGo Rate Limiting

Video search is **rate-limited** by DuckDuckGo. If you encounter zero results:

**Solutions:**
1. **Simplify query** - Use basic keywords without special characters
2. **Remove filters** - Try without `--duration` or `--resolution`
3. **Reduce results** - Lower `--max` parameter (start with 5-10)
4. **Change region** - Try different `--region` setting
5. **Broader terms** - Use more general search words
6. **Wait and retry** - Wait several minutes before trying again

### Zero Results Recovery Steps

```bash
# Wait before retrying
sleep 300

# Try basic search without filters
data-scout video-search --query "simple keywords" --max 5

# Try without duration filter
data-scout video-search --query "original query" --max 10

# Try different region
data-scout video-search --query "original query" --region "us-en" --max 10

# Try with broader query
data-scout video-search --query "broad search term" --max 20
```

### Best Practices

- **General terms** - Use common video search keywords
- **No filters initially** - Start without `--duration` or `--resolution`
- **Small batches** - Begin with `--max 5-10` results
- **Avoid rapid requests** - Space out repeated searches
- **Monitor for limits** - Watch for persistent zero results

## Related Documentation

- [Web Search](./websearch.md)
- [Image Search](./imagesearch.md)
- [News Search](./newssearch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
