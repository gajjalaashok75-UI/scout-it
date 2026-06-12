# Video Search Documentation

## Overview

Video search retrieves videos from DuckDuckGo matching your query. Results include video titles, URLs, descriptions, thumbnails, and metadata.

## Command Syntax

```bash
gakr-ddgs video-search [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--query` | `-q` | Video search query string | `STRING` |

## Optional Options

| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | `INT` | Maximum number of videos to return |
| `--json` | - | `false` | `BOOL` | Output raw JSON to stdout instead of saving to file |

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

### Programming Tutorial

Search for coding tutorials:

```bash
gakr-ddgs video-search --query "Python tutorial"
```

**Output:**
```
1. Python For Beginners - Corey Schafer
   Duration: 4:26:25
   Views: 2.3M views
   https://www.youtube.com/watch?v=...
   
2. Complete Python Course - Udemy
   Duration: 22:15:00
   ...

📂 Results saved to: C:\path\to\video_search_results.json
```

### How-To Video

Search for instructional videos:

```bash
gakr-ddgs video-search --query "how to make sourdough bread"
```

### Music Video

Search for music:

```bash
gakr-ddgs video-search --query "Imagine John Lennon"
```

### Lecture/Educational

Search for lectures:

```bash
gakr-ddgs video-search --query "MIT OpenCourseWare machine learning"
```

### Limited Results

Get top 5 videos only:

```bash
gakr-ddgs video-search --query "JavaScript basics" --max-results 5
```

### More Results

Get 30 videos:

```bash
gakr-ddgs video-search --query "yoga exercises" --max-results 30
```

### JSON Output

Get raw JSON for processing:

```bash
gakr-ddgs video-search --query "photography tips" --json > video_results.json
```

### Different Topics

```bash
# Educational
gakr-ddgs video-search --query "quantum physics explained"

# Entertainment
gakr-ddgs video-search --query "funny cat videos"

# Gaming
gakr-ddgs video-search --query "Minecraft building tutorial"

# Music
gakr-ddgs video-search --query "guitar lesson for beginners"

# Fitness
gakr-ddgs video-search --query "30 minute workout"
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
gakr-ddgs video-search \
  --query "web development bootcamp" \
  --max-results 15
```

### Research

Find educational videos:

```bash
gakr-ddgs video-search \
  --query "climate change science" \
  --max-results 10
```

### Entertainment

Find music or movies:

```bash
gakr-ddgs video-search \
  --query "trailer science fiction movie 2026" \
  --max-results 5
```

### Software Development

Find code walkthroughs:

```bash
gakr-ddgs video-search \
  --query "React hooks tutorial" \
  --max-results 20 \
  --json > react_videos.json
```

### Entertainment Collection

Create a list of videos for later:

```bash
gakr-ddgs video-search \
  --query "stand-up comedy special" \
  --max-results 30 \
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
| `--max-results` | Low | Video search is fast (no extraction) |
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
- Increase `--max-results` to allow for more results
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
  gakr-ddgs video-search \
    --query "${lang} tutorial" \
    --max-results 10 \
    --json > "videos_${lang}.json"
done
```

### Extract Video URLs

Get just the URLs for batch downloading:

```bash
gakr-ddgs video-search --query "course" --json | \
  jq -r '.results[] | .url' > urls.txt

# Download with youtube-dl
youtube-dl -a urls.txt
```

### Create Playlist File

Extract video URLs in playlist format:

```bash
gakr-ddgs video-search --query "music" --json | \
  jq -r '.results[] | .url' > my_playlist.m3u
```

### Analyze Video Sources

Find which platforms have most content:

```bash
gakr-ddgs video-search --query "tutorial" --max-results 50 --json | \
  jq '.results[] | .source' | sort | uniq -c | sort -rn
```

### Search Multiple Related Topics

```bash
# Create a research collection
for query in "machine learning" "deep learning" "neural networks"; do
  gakr-ddgs video-search \
    --query "$query" \
    --max-results 20 \
    --json > "research_${query// /_}.json"
done
```

## Related Documentation

- [Web Search](./websearch.md)
- [Image Search](./imagesearch.md)
- [News Search](./newssearch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
