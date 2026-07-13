# News Search Documentation

## Overview

News search retrieves recent news articles related to your query from DuckDuckGo's news index. Results include article headlines, snippets, and URLs to full articles.

## Command Syntax

```bash
scout-it news-search [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--query` | `-q` | News search query string | `STRING` |

## Optional Options

### Results & Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max` | `-m` | `50` | `INT` | Maximum articles to return |
| `--out` | `-o` | `.scout-it/news_search_results.json` | `PATH` | Output file path |
| `--json` | - | `false` | `BOOL` | Output to stdout as JSON |
| `--markdown` | - | `false` | `BOOL` | Format output as Markdown |

### Search Parameters
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | `STRING` | Region/locale for news sources |
| `--safesearch` | - | `moderate` | `ENUM` | Safe search: `on`, `moderate`, `off` |
| `--timelimit` | - | - | `ENUM` | Time filter: `d` (today), `w` (week), `m` (month), `y` (year) |

### Performance & Resilience
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--workers` | - | `4` | `INT` | Number of parallel workers |
| `--max-fetch-retries` | - | `2` | `INT` | Max retries per URL on fetch failure |
| `--no-js-fallback` | - | `false` | `BOOL` | Disable JavaScript rendering fallback |

### Retry Options
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--no-retry-on-zero` | - | `false` | `BOOL` | Disable retry on zero results |
| `--retry-attempts` | - | `2` | `INT` | Number of retry attempts |
| `--retry-backoff` | - | `1.0` | `FLOAT` | Backoff multiplier |

## Output File

By default, results are saved to:

```
.scout-it/news_search_results.json
```

Location: Full path is displayed in console with 📂 emoji

### Output Format

```json
{
  "query": "artificial intelligence",
  "search_type": "news",
  "timestamp": "2026-06-12T10:30:00Z",
  "total_results": 5,
  "results": [
    {
      "position": 1,
      "title": "New AI Model Achieves Breakthrough",
      "url": "https://technews.com/ai-breakthrough",
      "source": "Tech News Daily",
      "date": "2026-06-12T08:15:00Z",
      "snippet": "Researchers announce a new AI model that outperforms previous benchmarks...",
      "image": "https://technews.com/images/ai-breakthrough.jpg"
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
| `title` | STRING | Article headline |
| `url` | STRING | Full URL to the article |
| `source` | STRING | News organization/publication name |
| `date` | STRING | Publication date (ISO 8601 format) |
| `snippet` | STRING | Article preview/summary |
| `image` | STRING | Thumbnail image URL (if available) |

## Usage Examples

### Breaking News

Get the latest news on a topic:

```bash
scout-it news-search --query "AI breakthrough"
```

### Regional News (UK)

Search for news from UK region:

```bash
scout-it news-search --query "technology" --region uk-en
```

### Last 24 Hours

Get today's news:

```bash
scout-it news-search --query "politics" --timelimit d --max 20
```

### Last Week's News

Get news from the past week:

```bash
scout-it news-search --query "finance" --timelimit w --max 30
```

### Safe Search Enabled

Filter adult content:

```bash
scout-it news-search --query "general interest" --safesearch on
```

### Custom Output

Save to specific file:

```bash
scout-it news-search --query "technology" --out ./news/tech_news.json --max 50
```

### JSON Output

Output to stdout:

```bash
scout-it news-search --query "AI breakthrough" --json
```

### With Retry Configuration

Retry on failures:

```bash
scout-it news-search --query "research" --retry-attempts 3 --retry-backoff 1.5
```

## Programmatic API

### Python Example - Basic Search

```python
from scout_it.extraction import DDGS

ddgs = DDGS()
results = ddgs.news(query="artificial intelligence", max_results=10)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Source: {result['source']}")
    print(f"Date: {result['date']}")
    print(f"URL: {result['url']}")
    print()
```

### Python Example - Recent News Only

```python
from scout_it.extraction import DDGS
from datetime import datetime, timedelta

ddgs = DDGS()
results = ddgs.news(query="technology", max_results=20)

# Filter for today's news only
today = datetime.now().date()
today_news = [
    r for r in results 
    if datetime.fromisoformat(r['date']).date() == today
]

print(f"Found {len(today_news)} articles from today")
for article in today_news:
    print(f"  {article['title']}")
```

### Python Example - News by Source

```python
from scout_it.extraction import DDGS

ddgs = DDGS()
results = ddgs.news(query="finance", max_results=30)

# Group by source
by_source = {}
for article in results:
    source = article['source']
    if source not in by_source:
        by_source[source] = []
    by_source[source].append(article)

for source, articles in by_source.items():
    print(f"\n{source} ({len(articles)} articles):")
    for article in articles[:3]:  # Show first 3
        print(f"  - {article['title']}")
```

## Common Use Cases

### News Aggregation

Get latest news on a specific topic:

```bash
scout-it news-search \
  --query "electric vehicles" \
  --max 20 \
  --json > ev_news.json
```

### Monitoring Breaking News

Check for updates on an ongoing story:

```bash
# Run periodically (e.g., in a cron job)
scout-it news-search \
  --query "natural disaster" \
  --max 10 \
  --json > breaking_news.json
```

### Industry Intelligence

Track news in your industry:

```bash
scout-it news-search \
  --query "software development trends" \
  --max 15
```

### Competitive Analysis

Monitor competitor news:

```bash
scout-it news-search \
  --query "major_competitor_name" \
  --max 25
```

### News by Category

Search different news categories:

```bash
# Technology
scout-it news-search --query "technology innovation" --max 10

# Health
scout-it news-search --query "medical breakthrough" --max 10

# Finance
scout-it news-search --query "stock market" --max 10

# Politics
scout-it news-search --query "government policy" --max 10
```

## Performance Considerations

| Factor | Impact | Notes |
|--------|--------|-------|
| `--max` | Low | News search is fast (no content extraction) |
| Query specificity | High | More specific queries = better results |
| Network Speed | Low | News search uses lightweight requests |

**Typical Execution Times:**
- Any number of results: 2-5 seconds (very fast)

## Date Handling

News results are ordered by relevance and recency. The `date` field indicates publication time:

```json
"date": "2026-06-12T14:30:00Z"  // ISO 8601 format
```

To parse in Python:

```python
from datetime import datetime

date_str = "2026-06-12T14:30:00Z"
date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
print(date_obj.strftime("%B %d, %Y"))  # June 12, 2026
```

## Troubleshooting

### No News Results

**Problem:** Search returns empty results

**Solutions:**
- Try a simpler, more specific query
- Use different keywords
- Topic may not have recent coverage
- Check if DuckDuckGo news is available in your region

### Too Many Irrelevant Results

**Problem:** Results don't match your query well

**Solutions:**
- Try more specific search terms
- Use quotes for exact phrases: `"AI safety"`
- Add context terms: `"AI safety regulations" vs "AI safety"`
- Reduce `--max` to see top matches only

### Missing Specific Publication

**Problem:** Don't see articles from your preferred news source

**Solutions:**
- DuckDuckGo indexes many but not all sources
- Try including the publication name in query
- Check if publication has different article name
- RSS feeds may be an alternative

### Slow Results

**Problem:** News search seems slow

**Solutions:**
- News search is normally very fast (2-5 seconds)
- If slow, check your internet connection
- DuckDuckGo may be rate-limiting; try again later

## Advanced Usage

### Batch News Monitoring

Monitor multiple topics:

```bash
topics=("AI" "Climate" "Space" "Medicine")

for topic in "${topics[@]}"; do
  scout-it news-search \
    --query "$topic" \
    --max 10 \
    --json > "news_${topic}.json"
  echo "Collected news for: $topic"
done
```

### Parsing News with JQ

Extract headlines and sources:

```bash
scout-it news-search --query "technology" --json | \
  jq '.results[] | {title, source, date}'
```

### Filtering by Date Range

Find news from the last 24 hours:

```bash
scout-it news-search --query "urgent" --json | \
  jq '.results[] | 
      select(
        (now - (.date | fromdateiso8601)) < 86400
      ) | 
      {title, date}'
```

### News Analysis Pipeline

```bash
# Collect news
scout-it news-search --query "AI" --max 30 --json > ai_news.json

# Extract unique sources
jq '.results[] | .source' ai_news.json | sort -u

# Count articles per source
jq '.results[] | .source' ai_news.json | sort | uniq -c | sort -rn
```

## ⚠️ Rate Limiting & Troubleshooting

### DuckDuckGo Rate Limiting

News search is **rate-limited** by DuckDuckGo. If you get zero results:

**Solutions:**
1. **Broaden query** - Use more general terms ("AI" instead of "artificial intelligence machine learning deep learning")
2. **Remove time filter** - Drop `--timelimit` to search all news
3. **Change region** - Try different `--region` (default: us-en)
4. **Reduce results** - Lower `--max` parameter (try 5-10 first)
5. **Different keywords** - Try alternative search terms
6. **Wait and retry** - Wait several minutes before trying again

### Zero Results Recovery

```bash
# Wait before retrying
sleep 300

# Try with basic query
scout-it news-search --query "simple keywords" --max 5

# Try without time filter
scout-it news-search --query "original query" --max 5

# Try different region
scout-it news-search --query "original query" --region "wt-wt" --max 10
```

### Best Practices

- **Specific topics** - News search works better with specific topics
- **Recent news** - Use `--timelimit d` or `w` for better results
- **Small batches** - Start with `--max 5` or `--max 10`
- **Avoid duplication** - Don't run same query repeatedly
- **Rate yourself** - Space out requests by a few minutes

## Related Documentation

- [Web Search](./websearch.md)
- [Video Search](./videosearch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
