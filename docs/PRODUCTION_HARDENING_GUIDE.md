# Production Hardening Guide

## Overview

This document covers the production-ready features, operational excellence improvements, and best practices for the TechCrunch RSS module.

---

## Table of Contents

1. [Configuration System](#configuration-system)
2. [Exception Hierarchy](#exception-hierarchy)
3. [Observability & Logging](#observability--logging)
4. [Performance Metrics](#performance-metrics)
5. [Data Quality](#data-quality)
6. [Reliability Features](#reliability-features)
7. [Operational Best Practices](#operational-best-practices)
8. [Monitoring & Alerts](#monitoring--alerts)
9. [Troubleshooting](#troubleshooting)

---

## Configuration System

### RSSConfig Class

All magic numbers have been moved into a centralized configuration class:

```python
from scout_it.tech_crunch_rss import RSSConfig, DEFAULT_CONFIG

# Use default configuration
print(DEFAULT_CONFIG.timeout)  # 15.0
print(DEFAULT_CONFIG.retries)  # 3
print(DEFAULT_CONFIG.cache_ttl_seconds)  # 600
```

### Configuration from Environment Variables

All settings can be overridden via environment variables:

```bash
export TECHCRUNCH_RSS_TIMEOUT=20.0
export TECHCRUNCH_RSS_RETRIES=5
export TECHCRUNCH_RSS_BACKOFF_FACTOR=1.0
export TECHCRUNCH_RSS_CACHE_TTL=900
export TECHCRUNCH_RSS_ARTICLE_CACHE_TTL=3600
export TECHCRUNCH_RSS_MAX_WORKERS=12
export TECHCRUNCH_RSS_USER_AGENT="MyApp/1.0"
export TECHCRUNCH_RSS_DEBUG=true
```

```python
# Load configuration from environment
config = RSSConfig.from_environment()
config.validate()

print(config.timeout)  # 20.0 (from environment)
print(config.debug)    # True
```

### Configuration Validation

```python
config = RSSConfig(
    timeout=15.0,
    retries=3,
    max_workers=8
)

# Validate all constraints
try:
    config.validate()
    print("Configuration valid")
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

### Ranking Weights Configuration

```python
from scout_it.tech_crunch_rss import RankingWeights

weights = RankingWeights(
    title=12.0,           # Increased title importance
    summary=6.0,
    content=10.0,
    recency_base=70.0,    # More recency weight
    recency_decay_rate=1.5
)

config = RSSConfig(ranking_weights=weights)
```

---

## Exception Hierarchy

### Custom Exceptions

All operations use predictable, typed exceptions:

```python
from scout_it.tech_crunch_rss import (
    RSSProviderError,      # Base exception
    FeedValidationError,   # Feed validation failed
    FeedFetchError,        # Network/HTTP errors
    FeedParseError,        # XML/RSS parsing errors
    SearchError,           # Search operation failed
    ExportError,           # Export operation failed
)
```

### Graceful Error Handling

All public APIs handle errors gracefully:

```python
from scout_it.tech_crunch_rss import search_feeds, SearchError

try:
    results = search_feeds("openai", domains=["ai"], limit=20)
except SearchError as e:
    logger.error(f"Search failed: {e}")
    results = []
```

### Error Context

Exceptions include context for debugging:

```python
try:
    export_json(entries, "/invalid/path/file.json")
except ExportError as e:
    print(f"Export failed: {e}")
    # Output: "Export failed: JSON export failed: [Errno 2] No such file or directory..."
```

---

## Observability & Logging

### Structured Logging

All operations emit structured log events:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug mode for detailed logs
import os
os.environ["TECHCRUNCH_RSS_DEBUG"] = "true"

from scout_it.tech_crunch_rss import get_latest_entries

entries = get_latest_entries("ai", limit=5)
```

**Log Output:**
```
[cache_miss] {"key": "https://techcrunch.com/category/artificial-intelligence/feed/"}
[feed_fetch_started] {"url": "https://techcrunch.com/..."}
[feed_fetch_completed] {"url": "...", "duration_ms": 1234.56, "size_bytes": 102400}
[feed_parse_started] {"domain": "ai", "size_bytes": 102400}
[feed_parsed] {"parser": "feedparser", "entry_count": 20, "duration_ms": 45.12}
```

### Log Events

| Event | Description | Level |
|-------|-------------|-------|
| `cache_hit` | Cache entry found | DEBUG |
| `cache_miss` | Cache entry not found | DEBUG |
| `cache_expired` | Cache entry expired | DEBUG |
| `feed_fetch_started` | Feed fetch initiated | DEBUG |
| `feed_fetch_completed` | Feed fetch succeeded | DEBUG |
| `feed_fetch_failed` | Feed fetch failed | WARNING |
| `feed_parse_started` | Feed parsing initiated | DEBUG |
| `feed_parsed` | Feed parsed successfully | DEBUG |
| `feed_parse_failed` | Feed parsing failed | ERROR |
| `search_started` | Search operation initiated | DEBUG |
| `search_completed` | Search completed | DEBUG |
| `search_error` | Search failed | ERROR |
| `export_completed` | Export succeeded | DEBUG |
| `export_error` | Export failed | ERROR |
| `circuit_breaker_open` | Circuit breaker opened | WARNING |

---

## Performance Metrics

### Runtime Statistics

Track aggregate performance metrics:

```python
from scout_it.tech_crunch_rss import get_runtime_statistics

# Perform operations
entries = get_latest_entries(limit=100)
results = search_feeds("openai", limit=20)

# Get metrics
stats = get_runtime_statistics()

print(f"Fetch operations: {stats['fetch_count']}")
print(f"Fetch success rate: {stats['fetch_success'] / stats['fetch_count'] * 100:.1f}%")
print(f"Average fetch time: {stats['avg_fetch_ms']:.2f}ms")
print(f"Average parse time: {stats['avg_parse_ms']:.2f}ms")
print(f"Average search time: {stats['avg_search_ms']:.2f}ms")
print(f"Cache hit rate: {stats['cache_hit_rate'] * 100:.1f}%")
```

### Metric Types

| Metric | Description | Unit |
|--------|-------------|------|
| `fetch_count` | Total feed fetches | count |
| `fetch_success` | Successful fetches | count |
| `fetch_failure` | Failed fetches | count |
| `fetch_total_ms` | Total fetch time | milliseconds |
| `avg_fetch_ms` | Average fetch time | milliseconds |
| `parse_count` | Total parse operations | count |
| `parse_success` | Successful parses | count |
| `parse_failure` | Failed parses | count |
| `avg_parse_ms` | Average parse time | milliseconds |
| `search_count` | Total searches | count |
| `avg_search_ms` | Average search time | milliseconds |
| `ranking_count` | Total ranking operations | count |
| `avg_ranking_ms` | Average ranking time | milliseconds |
| `cache_hits` | Cache hits | count |
| `cache_misses` | Cache misses | count |
| `cache_hit_rate` | Hit rate (0-1) | ratio |
| `export_count` | Total exports | count |
| `avg_export_ms` | Average export time | milliseconds |

### Performance Monitoring

```python
import time

# Baseline metrics
baseline = get_runtime_statistics()

# Perform operations
start = time.time()
results = search_feeds("AI agents", limit=100)
duration = time.time() - start

# Check metrics
current = get_runtime_statistics()

print(f"Operation took: {duration:.2f}s")
print(f"New fetches: {current['fetch_count'] - baseline['fetch_count']}")
print(f"New searches: {current['search_count'] - baseline['search_count']}")
print(f"Cache efficiency: {current['cache_hit_rate'] * 100:.1f}%")
```

---

## Data Quality

### URL Normalization

URLs are automatically normalized to remove tracking parameters:

```python
# Before normalization:
# https://techcrunch.com/article?utm_source=twitter&fbclid=xyz#section

# After normalization:
# https://techcrunch.com/article
```

**Removed Parameters:**
- `utm_*` (Google Analytics)
- `fbclid` (Facebook)
- `gclid` (Google Ads)
- `mc_cid`, `mc_eid` (Mailchimp)
- `_ga` (Google Analytics)
- `ref`, `source` (Referral tracking)

### Date Normalization

Comprehensive date parsing with timezone conversion to UTC:

```python
# Supported formats:
# - RFC 822/2822: "Mon, 01 Jan 2024 12:00:00 +0000"
# - ISO 8601: "2024-01-01T12:00:00+00:00"
# - ISO 8601 Zulu: "2024-01-01T12:00:00Z"
# - Timezone names: "Mon, 01 Jan 2024 12:00:00 EST"

# All normalized to: "2024-01-01T12:00:00+00:00"
```

### Content Sanitization

Content is automatically sanitized:

- **HTML Removal:** Strip HTML tags from summaries
- **Whitespace Normalization:** Collapse multiple spaces
- **Control Characters:** Remove invalid characters
- **HTML Entities:** Decode entities (`&amp;` → `&`)
- **Length Limits:** Truncate extremely long summaries (5000 chars)

### Duplicate Detection

Enhanced deduplication using:

1. **URL + GUID + Title fingerprinting**
2. **Normalized title similarity (90% threshold)**
3. **Common word overlap detection**

```python
from scout_it.tech_crunch_rss import deduplicate_entries

# Automatically removes:
# - Same URL with different tracking params
# - Same story from different feeds
# - Title variations ("AI Startup Raises $10M" vs "AI Startup Raises $10 Million")

unique_entries = deduplicate_entries(entries)
```

---

## Reliability Features

### Circuit Breaker

Automatically stops fetching repeatedly failing feeds:

```python
# Circuit breaker states:
# - CLOSED: Feed is healthy, requests proceed normally
# - OPEN: Feed has failed 5 times, requests blocked
# - HALF_OPEN: Testing if feed has recovered

# Configuration:
# - Threshold: 5 consecutive failures
# - Timeout: 300 seconds (5 minutes)
# - Auto-recovery: Attempts after timeout
```

Check circuit breaker status:

```python
from scout_it.tech_crunch_rss import get_feed_health, _CIRCUIT_BREAKERS

health = get_feed_health()

for url, h in health.items():
    if h['success_rate'] < 0.5:
        print(f"Unhealthy feed: {url}")
        print(f"  Success rate: {h['success_rate'] * 100:.1f}%")
        print(f"  Last error: {h['last_error']}")

# Check circuit breakers
for url, breaker in _CIRCUIT_BREAKERS.items():
    if breaker['state'] == 'open':
        print(f"Circuit open for: {url}")
```

### Retry with Jitter

Exponential backoff with random jitter prevents thundering herd:

```
Attempt 1: Wait 0.75s + random(0-0.075s)
Attempt 2: Wait 1.50s + random(0-0.150s)
Attempt 3: Wait 3.00s + random(0-0.300s)
```

### Feed Health Tracking

Comprehensive health metrics per feed:

```python
health = get_feed_health("https://techcrunch.com/feed/")

print(f"Success rate: {health['success_rate'] * 100:.1f}%")
print(f"Uptime: {health['uptime_percentage']:.1f}%")
print(f"Avg response time: {health['average_response_time']:.2f}s")
print(f"Total attempts: {health['successes'] + health['failures']}")
print(f"Last success: {health['last_success']}")
```

### Safeguards

- **Max Feed Size:** 10MB limit (prevents memory exhaustion)
- **Max Entries Per Feed:** 1000 entries (configurable)
- **Request Timeout:** 15 seconds default (configurable)
- **Connection Pooling:** 20 connections max
- **Circuit Breaker:** Auto-disable failing feeds

---

## Operational Best Practices

### Production Configuration

```python
# production_config.py
import os
from scout_it.tech_crunch_rss import RSSConfig, RankingWeights

# Load from environment with production defaults
config = RSSConfig(
    timeout=20.0,              # Higher timeout for slow networks
    retries=5,                 # More retries for reliability
    cache_ttl_seconds=1800,    # 30-minute cache for production
    max_workers=16,            # More parallelism
    debug=False,               # Disable debug logging
    ranking_weights=RankingWeights(
        recency_base=80.0,     # Strong recency preference
        recency_decay_rate=2.0 # Faster decay for news
    )
)

config.validate()
```

### Logging Configuration

```python
import logging
import sys

# Production logging setup
logging.basicConfig(
    level=logging.INFO,  # INFO in production, DEBUG for troubleshooting
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/var/log/rss_provider.log')
    ]
)

# Separate logger for metrics
metrics_logger = logging.getLogger('metrics')
metrics_logger.setLevel(logging.INFO)
metrics_handler = logging.FileHandler('/var/log/rss_metrics.log')
metrics_logger.addHandler(metrics_handler)
```

### Health Check Endpoint

```python
from flask import Flask, jsonify
from scout_it.tech_crunch_rss import get_runtime_statistics, get_feed_health

app = Flask(__name__)

@app.route('/health')
def health():
    """Health check endpoint for load balancers."""
    stats = get_runtime_statistics()
    
    # Check if service is healthy
    fetch_success_rate = (
        stats['fetch_success'] / max(stats['fetch_count'], 1)
    )
    
    healthy = fetch_success_rate > 0.7  # 70% success threshold
    
    return jsonify({
        "status": "healthy" if healthy else "degraded",
        "fetch_success_rate": fetch_success_rate,
        "cache_hit_rate": stats['cache_hit_rate'],
        "avg_response_time_ms": stats['avg_fetch_ms']
    }), 200 if healthy else 503

@app.route('/metrics')
def metrics():
    """Prometheus-style metrics endpoint."""
    stats = get_runtime_statistics()
    
    return jsonify({
        "fetch_count": stats['fetch_count'],
        "fetch_success": stats['fetch_success'],
        "fetch_failure": stats['fetch_failure'],
        "avg_fetch_ms": stats['avg_fetch_ms'],
        "cache_hit_rate": stats['cache_hit_rate'],
        "avg_search_ms": stats['avg_search_ms'],
    })
```

### Monitoring Queries

```python
# Check for degraded performance
stats = get_runtime_statistics()

if stats['avg_fetch_ms'] > 3000:
    alert("High fetch latency: {stats['avg_fetch_ms']:.0f}ms")

if stats['cache_hit_rate'] < 0.3:
    alert(f"Low cache hit rate: {stats['cache_hit_rate'] * 100:.1f}%")

if stats['fetch_failure'] / max(stats['fetch_count'], 1) > 0.3:
    alert(f"High failure rate: {stats['fetch_failure']} / {stats['fetch_count']}")

# Check feed health
health = get_feed_health()
unhealthy = [url for url, h in health.items() if h['success_rate'] < 0.5]

if unhealthy:
    alert(f"{len(unhealthy)} feeds unhealthy: {unhealthy[:5]}")
```

---

## Monitoring & Alerts

### Key Metrics to Monitor

#### Availability Metrics
- Feed fetch success rate (target: > 95%)
- Circuit breaker status (alert if > 20% open)
- Parse success rate (target: > 99%)

#### Performance Metrics
- Average fetch time (alert if > 3s)
- Average search time (alert if > 500ms)
- Cache hit rate (alert if < 30%)

#### Capacity Metrics
- Cache size (feed + article)
- Active circuit breakers
- Concurrent workers

### Alert Thresholds

```yaml
# alerts.yaml
alerts:
  - name: high_fetch_latency
    condition: avg_fetch_ms > 3000
    severity: warning
    
  - name: low_success_rate
    condition: fetch_success_rate < 0.80
    severity: critical
    
  - name: low_cache_hit_rate
    condition: cache_hit_rate < 0.30
    severity: warning
    
  - name: many_circuit_breakers
    condition: circuit_breakers_open > 5
    severity: warning
    
  - name: parse_failures
    condition: parse_failure_rate > 0.05
    severity: critical
```

---

## Troubleshooting

### High Fetch Latency

**Symptoms:** `avg_fetch_ms > 3000`

**Diagnosis:**
```python
stats = get_runtime_statistics()
print(f"Avg fetch: {stats['avg_fetch_ms']}ms")

health = get_feed_health()
slow_feeds = {
    url: h for url, h in health.items()
    if h['average_response_time'] > 3.0
}

for url, h in sorted(slow_feeds.items(), key=lambda x: -x[1]['average_response_time'])[:5]:
    print(f"{url}: {h['average_response_time']:.2f}s")
```

**Solutions:**
- Increase timeout: `TECHCRUNCH_RSS_TIMEOUT=30`
- Reduce max workers to avoid overwhelming network
- Enable circuit breakers (automatic)
- Remove chronically slow feeds from registry

### Low Cache Hit Rate

**Symptoms:** `cache_hit_rate < 0.30`

**Diagnosis:**
```python
stats = get_runtime_statistics()
print(f"Cache hits: {stats['cache_hits']}")
print(f"Cache misses: {stats['cache_misses']}")
print(f"Hit rate: {stats['cache_hit_rate'] * 100:.1f}%")
```

**Solutions:**
- Increase cache TTL: `TECHCRUNCH_RSS_CACHE_TTL=1800`
- Ensure cache isn't being cleared too frequently
- Check that same feeds are being requested repeatedly

### Circuit Breakers Triggering

**Symptoms:** Many feeds showing as unhealthy

**Diagnosis:**
```python
from scout_it.tech_crunch_rss import _CIRCUIT_BREAKERS

open_breakers = {
    url: b for url, b in _CIRCUIT_BREAKERS.items()
    if b['state'] == 'open'
}

for url, breaker in open_breakers.items():
    print(f"Open: {url}")
    print(f"  Failures: {breaker['failure_count']}")
    print(f"  Last failure: {breaker['last_failure_time']}")
```

**Solutions:**
- Check network connectivity
- Verify feed URLs are still valid
- Increase retry count: `TECHCRUNCH_RSS_RETRIES=5`
- Manually validate feeds: `validate_all_feeds()`

### Memory Growth

**Symptoms:** Increasing memory usage over time

**Diagnosis:**
```python
from scout_it.tech_crunch_rss import _FEED_CACHE, _ARTICLE_CACHE

print(f"Feed cache entries: {len(_FEED_CACHE)}")
print(f"Article cache entries: {len(_ARTICLE_CACHE)}")

# Estimate memory usage
import sys
feed_cache_size = sum(sys.getsizeof(v[1]) for v in _FEED_CACHE.values())
article_cache_size = sum(sys.getsizeof(v[1]) for v in _ARTICLE_CACHE.values())

print(f"Feed cache size: {feed_cache_size / 1024 / 1024:.2f} MB")
print(f"Article cache size: {article_cache_size / 1024 / 1024:.2f} MB")
```

**Solutions:**
- Reduce cache TTL
- Clear cache periodically: `clear_cache()`
- Reduce `max_entries_per_feed` config
- Limit article content fetching

### Search Performance Degradation

**Symptoms:** `avg_search_ms > 500`

**Diagnosis:**
```python
stats = get_runtime_statistics()
print(f"Avg search: {stats['avg_search_ms']}ms")
print(f"Avg ranking: {stats['avg_ranking_ms']}ms")
print(f"Search count: {stats['search_count']}")
```

**Solutions:**
- Reduce entries before search (filter by date/domain first)
- Disable article content fetching if not needed
- Use simpler queries (avoid complex operators)
- Consider pagination for large result sets

---

## Summary

The production-hardened RSS module includes:

✅ **Configuration Management** - Centralized config with environment variable support  
✅ **Exception Hierarchy** - Typed, predictable error handling  
✅ **Structured Logging** - Comprehensive event tracking  
✅ **Performance Metrics** - Real-time statistics and monitoring  
✅ **Data Quality** - Normalization, sanitization, deduplication  
✅ **Reliability** - Circuit breakers, retry logic, health tracking  
✅ **Observability** - Detailed logs, metrics, and health checks  
✅ **Operational Excellence** - Best practices and troubleshooting guides  

The module is now production-ready for enterprise deployments! 🚀
