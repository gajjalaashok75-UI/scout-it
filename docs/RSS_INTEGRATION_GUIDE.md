# TechCrunch RSS Integration Guide

## Overview

The TechCrunch RSS module has been successfully integrated into the `news-search` command as a category-aware provider. This integration adds rich, topic-specific RSS feeds to the existing news aggregation pipeline without modifying `web-search` or creating a separate command.

---

## Architecture

### Integration Flow

```
User Command
    ↓
scout-it news-search --query "openai" --category ai
    ↓
news-search Pipeline
    ├─→ DuckDuckGo News (always)
    ├─→ Google News RSS (if --source google-news)
    ├─→ Times of India RSS (if --location)
    └─→ Category RSS Providers (if --category) ← NEW
         └─→ TechCrunch RSS Provider
              ├─ Fetch feeds for category
              ├─ Search & rank entries
              ├─ Normalize to news format
              └─ Return results
    ↓
Merge & Deduplicate (by URL)
    ↓
Extract Full Article Content (existing extraction pipeline)
    ↓
Clean & Structure (process_results)
    ↓
Return Unified Results
```

### Provider Architecture

```
category_providers.py (NEW)
    ├─ CATEGORY_PROVIDERS registry
    │   ├─ "ai" → [techcrunch_ai_provider]
    │   ├─ "startups" → [techcrunch_startups_provider]
    │   ├─ "security" → [techcrunch_security_provider]
    │   └─ "cloud" → [techcrunch_cloud_provider]
    │
    └─ fetch_category_news()
         ├─ Resolves categories to providers
         ├─ Runs providers in parallel
         ├─ Deduplicates by URL
         └─ Returns normalized entries
```

---

## CLI Changes

### New Argument

```bash
--category CATEGORY [CATEGORY ...]
```

**Supported Categories:**
- `ai` - Artificial intelligence and machine learning news
- `startups` - Startup funding, launches, and venture capital
- `security` - Cybersecurity and data protection
- `cloud` - Cloud computing and enterprise technology

**Usage:**
```bash
# Single category
scout-it news-search -q "openai" --category ai

# Multiple categories
scout-it news-search -q "funding" --category ai startups

# Combined with other sources
scout-it news-search -q "kubernetes" --category cloud --source google-news
```

### Complete news-search Syntax

```bash
scout-it news-search \
  --query "search terms" \
  --max 20 \
  --category ai startups \
  --source google-news \
  --location india US \
  --region us-en \
  --timelimit w \
  --workers 8 \
  --out results.json
```

---

## Modified Files

### 1. `scout_it/category_providers.py` (NEW)

**Purpose:** Category-aware RSS provider registry

**Key Components:**
- `CATEGORY_PROVIDERS` - Registry mapping categories to provider functions
- `techcrunch_*_provider()` - Provider functions for each category
- `fetch_category_news()` - Parallel execution and deduplication
- `get_available_categories()` - List supported categories

**Provider Function Signature:**
```python
def provider(query: str, max_results: int = 50, **kwargs) -> List[Dict[str, Any]]:
    """Returns normalized news entries."""
```

**Normalized Entry Format:**
```python
{
    "title": "Article title",
    "url": "https://...",
    "href": "https://...",
    "body": "Summary text",
    "source": "techcrunch:ai",
    "publish_date": "2026-08-02T...",
    "score": 95.5,
    "author": "Author Name",
    "rss_metadata": {
        "matched_terms": ["openai", "agents"],
        "confidence": 0.95,
        "feed_name": "techcrunch.com",
        "category": "ai",
    }
}
```

### 2. `scout_it/cli.py` (MODIFIED)

**Changes:**

#### a. `news_search()` function
- Added `categories` parameter
- Added Stream 4: Category RSS providers
- Parallel execution with existing sources
- URL-level deduplication
- Stats tracking for category results

**Lines Changed:** ~369-550

#### b. Argument Parser
- Added `--category` argument with `nargs='+'`
- Help text explaining supported categories
- Example usage in help

**Lines Changed:** ~1779-1820

#### c. Command Dispatch
- Pass `categories=args.category` to `news_search()`

**Lines Changed:** ~2345-2380

---

## Sample Commands

### Basic Category Search

```bash
# AI news
scout-it news-search -q "openai agents" --category ai

# Startup news
scout-it news-search -q "series A funding" --category startups

# Security news
scout-it news-search -q "data breach" --category security

# Cloud news
scout-it news-search -q "kubernetes" --category cloud
```

### Multi-Category Search

```bash
# AI + Startups
scout-it news-search -q "AI startup" --category ai startups

# All tech categories
scout-it news-search -q "tech news" --category ai startups security cloud
```

### Combined Sources

```bash
# Category + Google News
scout-it news-search -q "openai" --category ai --source google-news

# Category + Location
scout-it news-search -q "startup" --category startups --location india

# Category + Google News + Location
scout-it news-search -q "AI" --category ai --source google-news --location US
```

### Advanced Options

```bash
# With time filtering
scout-it news-search -q "AI funding" --category ai startups --timelimit w

# With more workers
scout-it news-search -q "cloud" --category cloud --workers 10 --max 50

# Export to markdown
scout-it news-search -q "security" --category security --markdown --out security_news.md
```

---

## Example Output

### Command
```bash
scout-it news-search -q "openai agents" --category ai --max 5
```

### Console Output
```
📰 Starting news search: 'openai agents'

[blue]Category RSS providers enabled:[/blue] ai
[dim]Available categories: ai, cloud, security, startups[/dim]

Fetching TechCrunch AI news for query: openai agents
TechCrunch AI provider returned 5 results
[green]Category RSS providers returned 5 unique results[/green]

Phase 1: Discovery (4 sources)
  ✓ DDGS news: 3 results
  ✓ Category RSS: 5 results
  • Total after dedup: 7 results

Phase 2: Content Extraction
  ⚙️  Extracting 7 articles with 5 workers...
  ✓ Extracted 7/7 (100%)

Phase 3: Cleaning & Structuring
  ✓ Processed 7 results

📊 Final Statistics:
  • Total Results: 7
  • Category RSS: 5
  • DDGS News: 3
  • Success Rate: 100%

💾 Saved to: .scout-it/news_search_results.json
```

### JSON Output Structure
```json
{
  "query": "openai agents",
  "search_type": "news",
  "parameters": {
    "max_results": 5,
    "categories": ["ai"]
  },
  "stats": {
    "search_engine": {
      "total": 7,
      "category_providers": ["ai"],
      "category_rss_count": 5,
      "execution_time": 2.456
    },
    "cleaner": {
      "total_input": 7,
      "successful": 7,
      "processed": 7
    }
  },
  "results": [
    {
      "title": "OpenAI reportedly finds evidence that more of its agents ran...",
      "url": "https://techcrunch.com/...",
      "source": "techcrunch:ai",
      "publish_date": "2026-08-01T20:26:04+00:00",
      "score": 100.98,
      "author": "Kyle Wiggers",
      "cleaned_content": "Full article text...",
      "main_content": "Cleaned content...",
      "word_count": 850,
      "reading_time_minutes": 4,
      "extraction_status": "success",
      "quality_signals": {
        "has_title": true,
        "has_content": true,
        "content_length": 4250,
        "is_suspicious": false
      }
    }
  ]
}
```

---

## Test Results

Run integration tests:
```bash
python test_news_integration.py
```

**Expected Output:**
```
============================================================
TECHCRUNCH RSS INTEGRATION TEST SUITE
============================================================
============================================================
TEST 1: Category Provider Registry
============================================================
✓ Available categories: ['ai', 'cloud', 'security', 'startups']
  • ai
  • cloud
  • security
  • startups

============================================================
TEST 2: TechCrunch Provider Direct Test
============================================================
✓ Fetched 5 results from AI category

  Sample result:
    Title: OpenAI reportedly finds evidence that more of its agents ran...
    Source: techcrunch:ai
    Score: 100.98
    URL: https://techcrunch.com/2026/08/01/openai-reportedly-finds...

============================================================
TEST 3: news_search with --category
============================================================
✓ news_search completed
  Total results: 10
  Category RSS contributed: 7 results

  Source distribution:
    techcrunch:ai: 5
    techcrunch:cloud: 2
    duckduckgo: 3

============================================================
RESULTS: 6 passed, 0 failed
============================================================
✅ ALL INTEGRATION TESTS PASSED
```

---

## Adding New Providers

### Step 1: Create Provider Function

```python
# In scout_it/category_providers.py

def venturebeat_ai_provider(query: str, max_results: int = 50, **kwargs) -> List[Dict[str, Any]]:
    """VentureBeat AI news provider."""
    try:
        # Import your RSS module
        from .venturebeat_rss import search_feeds
        
        results = search_feeds(query=query, domains=["ai"], limit=max_results)
        
        # Normalize to news-search format
        normalized = []
        for entry in results:
            normalized.append({
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "href": entry.get("url", ""),
                "body": entry.get("summary", ""),
                "source": f"venturebeat:{entry.get('domain', 'ai')}",
                "publish_date": entry.get("published", ""),
            })
        
        return normalized
        
    except Exception as e:
        logger.error(f"VentureBeat provider failed: {e}")
        return []
```

### Step 2: Register Provider

```python
# Update CATEGORY_PROVIDERS registry
CATEGORY_PROVIDERS: Dict[str, List[Any]] = {
    "ai": [
        techcrunch_ai_provider,
        venturebeat_ai_provider,  # NEW
    ],
    # ... other categories
}
```

### Step 3: Test

```bash
# Provider automatically runs when category is requested
scout-it news-search -q "AI" --category ai
```

**That's it!** No changes to the news-search pipeline needed.

---

## Future Provider Examples

Here are examples of additional providers that can be added:

### Linux News
```python
def phoronix_provider(query: str, max_results: int = 50, **kwargs):
    """Phoronix Linux hardware news."""
    # Implementation...

CATEGORY_PROVIDERS["linux"] = [phoronix_provider]
```

### Open Source News
```python
def github_blog_provider(query: str, max_results: int = 50, **kwargs):
    """GitHub blog and changelog."""
    # Implementation...

CATEGORY_PROVIDERS["opensource"] = [github_blog_provider]
```

### Programming News
```python
def hacker_news_provider(query: str, max_results: int = 50, **kwargs):
    """Hacker News top stories."""
    # Implementation using Algolia API...

CATEGORY_PROVIDERS["programming"] = [hacker_news_provider]
```

---

## Benefits

### ✅ Clean Integration
- No new commands
- No modifications to `web-search`
- Fits existing news-search pattern
- Consistent output format

### ✅ Extensibility
- Easy to add new providers
- Easy to add new categories
- Providers run in parallel
- No pipeline changes needed

### ✅ Deduplication
- URL-level deduplication across all sources
- Prevents duplicate articles
- Preserves highest-scored version

### ✅ Full Content Extraction
- RSS entries go through existing extraction pipeline
- Same content quality as DDGS/Google News
- Consistent structure and cleaning

### ✅ Unified Ranking
- All results merged and ranked together
- No special-case handling
- Source-agnostic final results

---

## Performance

### Metrics (example)
- **Category Provider Execution:** ~1.5s (parallel)
- **Feed Fetching:** ~850ms average
- **RSS Parsing:** ~4ms average
- **Search & Ranking:** ~24ms for 100 entries
- **Total Impact:** +1.5s to news-search (acceptable)

### Optimization
- Providers run in parallel (ThreadPoolExecutor)
- RSS module has 10-minute feed cache
- Article content uses 30-minute cache
- Circuit breakers prevent slow providers

---

## Troubleshooting

### No Results from Category

**Problem:** `--category ai` returns 0 results

**Solutions:**
1. Check query is relevant to category
2. Verify TechCrunch RSS module is installed
3. Check network connectivity
4. Review logs for provider errors

### Duplicate Results

**Problem:** Same article appears multiple times

**Solutions:**
1. Check URL normalization (tracking params removed)
2. Verify deduplication logic in `news_search()`
3. Ensure providers use canonical URLs

### Slow Performance

**Problem:** Category search takes too long

**Solutions:**
1. Reduce `--max` parameter
2. Reduce `--workers` if network-bound
3. Check for slow RSS feeds (circuit breaker)
4. Use cache (repeat searches are fast)

---

## Summary

### What Was Added
✅ `scout_it/category_providers.py` - Provider registry (300 lines)  
✅ `--category` argument to news-search  
✅ Category RSS stream in news-search pipeline  
✅ TechCrunch RSS as first provider (4 categories)  
✅ Parallel execution with existing sources  
✅ URL-level deduplication  
✅ Integration tests  
✅ Complete documentation  

### What Was NOT Changed
✅ `web-search` command (unchanged)  
✅ Existing news sources (DDGS, Google News, ToI)  
✅ Content extraction pipeline  
✅ Output format  
✅ Cleaning logic  

### Command Responsibilities
- `web-search` → websites, docs, blogs, web pages
- `news-search` → news sources, RSS feeds, news aggregators ← **Enhanced**
- `multi-search` → combines everything

**The integration is complete, tested, and ready for production use!** 🚀
