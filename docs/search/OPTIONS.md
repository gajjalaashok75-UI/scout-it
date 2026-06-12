# Extended Options Reference

Complete reference of all supported options for each search type, including advanced filtering and customization parameters.

## Web Search - Full Options

### Command
```bash
gakr-ddgs web-search [OPTIONS]
```

### All Options

#### Required
| Option | Alias | Type | Description |
|--------|-------|------|-------------|
| `--query` | `-q` | STRING | Search query (required) |

#### Extraction & Performance
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | INT | Maximum results to fetch and extract |
| `--timeout` | - | `5` | INT | Extraction timeout in seconds per URL |
| `--workers` | `-w` | `4` | INT | Parallel extraction workers (1-16) |

#### Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--out` | `-o` | `web_search_results.json` | PATH | Output file path |
| `--json` | - | `false` | BOOL | Output to stdout as JSON |

#### Retry & Fallback (Optional)
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--no-retry-on-zero` | - | `false` | BOOL | Disable retry on zero successful extractions |
| `--retry-attempts` | - | `2` | INT | Number of retry attempts (1-5) |
| `--retry-backoff` | - | `1.0` | FLOAT | Backoff multiplier between retries |

#### Search Parameters (DuckDuckGo)
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | STRING | Region/locale (e.g., `us-en`, `uk-en`, `wt-wt` for worldwide) |
| `--safesearch` | - | `moderate` | ENUM | Safe search level: `on`, `moderate`, `off` |
| `--timelimit` | - | - | ENUM | Time filter: `d` (day), `w` (week), `m` (month), `y` (year) |
| `--backend` | - | `auto` | ENUM | Search backend: `auto`, `html`, `lite` |

#### Examples

**Basic Search:**
```bash
gakr-ddgs web-search --query "machine learning"
```

**With Custom Workers & Timeout:**
```bash
gakr-ddgs web-search --query "Python" --max-results 20 --workers 8 --timeout 10
```

**UK Region, Safe Search Off:**
```bash
gakr-ddgs web-search --query "technology" --region uk-en --safesearch off
```

**Last Week's Articles:**
```bash
gakr-ddgs web-search --query "news" --timelimit w --max-results 20
```

**With Retry Configuration:**
```bash
gakr-ddgs web-search --query "research" --retry-attempts 3 --retry-backoff 1.5
```

**Custom Output Location:**
```bash
gakr-ddgs web-search --query "data" --out ./results/my_results.json
```

---

## Image Search - Full Options

### Command
```bash
gakr-ddgs image-search [OPTIONS]
```

### All Options

#### Required
| Option | Alias | Type | Description |
|--------|-------|------|-------------|
| `--query` | `-q` | STRING | Image search query (required) |

#### Filtering - Dimensions
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--min-width` | - | `0` | INT | Minimum image width in pixels |
| `--max-width` | - | `0` | INT | Maximum image width in pixels |
| `--min-height` | - | `0` | INT | Minimum image height in pixels |
| `--max-height` | - | `0` | INT | Maximum image height in pixels |

#### Filtering - Visual Characteristics
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--size` | - | - | ENUM | Image size: `Small`, `Medium`, `Large`, `Wallpaper`, `Custom` |
| `--color` | - | - | ENUM | Color type: `Red`, `Orange`, `Yellow`, `Green`, `Blue`, `Purple`, `Pink`, `Brown`, `Black`, `Gray`, `White`, `Transparent` |
| `--type-image` | - | - | ENUM | Image type: `photo`, `clipart`, `gif`, `transparent`, `line`, `other` |
| `--layout` | - | - | ENUM | Image layout: `Square`, `Tall`, `Wide`, `Panoramic` |
| `--license-image` | - | - | ENUM | License type: `public`, `commercial`, `creative_commons`, `any` |

#### Search Parameters
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | STRING | Region/locale |
| `--safesearch` | - | `moderate` | ENUM | Safe search: `on`, `moderate`, `off` |
| `--timelimit` | - | - | ENUM | Time filter: `d`, `w`, `m`, `y` |

#### Download Options
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--download` | `-d` | `false` | BOOL | Download matched images |
| `--download-dir` | - | `downloaded_images` | PATH | Directory for downloads |

#### Output & Retry
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | INT | Maximum images to return |
| `--out` | `-o` | `image_search_results.json` | PATH | Output file path |
| `--json` | - | `false` | BOOL | Output to stdout as JSON |
| `--no-retry-on-zero` | - | `false` | BOOL | Disable retry on zero results |
| `--retry-attempts` | - | `2` | INT | Number of retry attempts |
| `--retry-backoff` | - | `1.0` | FLOAT | Backoff multiplier |

#### Examples

**Basic Image Search:**
```bash
gakr-ddgs image-search --query "dog"
```

**HD Images Only (1920×1080+):**
```bash
gakr-ddgs image-search --query "wallpaper" --min-width 1920 --min-height 1080 --max-results 20
```

**Specific Visual Characteristics:**
```bash
gakr-ddgs image-search --query "logo" --type-image "clipart" --color "Blue" --layout "Square"
```

**Size + Layout:**
```bash
gakr-ddgs image-search --query "landscape" --size "Wallpaper" --layout "Wide" --max-results 10
```

**License Filtered:**
```bash
gakr-ddgs image-search --query "photo" --license-image "creative_commons" --max-results 15
```

**Download Images:**
```bash
gakr-ddgs image-search \
  --query "nature" \
  --max-results 20 \
  --min-width 1024 \
  --download \
  --download-dir "./my_images"
```

**Aspect Ratio (Panoramic):**
```bash
gakr-ddgs image-search --query "mountain" --layout "Panoramic" --size "Wallpaper"
```

**Last Week's Images:**
```bash
gakr-ddgs image-search --query "news" --timelimit w --max-results 30
```

---

## News Search - Full Options

### Command
```bash
gakr-ddgs news-search [OPTIONS]
```

### All Options

#### Required
| Option | Alias | Type | Description |
|--------|-------|------|-------------|
| `--query` | `-q` | STRING | News search query (required) |

#### Results & Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | INT | Maximum articles to return |
| `--out` | `-o` | `news_search_results.json` | PATH | Output file path |
| `--json` | - | `false` | BOOL | Output to stdout as JSON |

#### Search Parameters
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | STRING | Region/locale for news sources |
| `--safesearch` | - | `moderate` | ENUM | Safe search: `on`, `moderate`, `off` |
| `--timelimit` | - | - | ENUM | Time filter: `d` (today), `w` (week), `m` (month), `y` (year) |

#### Retry Options
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--no-retry-on-zero` | - | `false` | BOOL | Disable retry on zero results |
| `--retry-attempts` | - | `2` | INT | Number of retry attempts |
| `--retry-backoff` | - | `1.0` | FLOAT | Backoff multiplier |

#### Examples

**Breaking News:**
```bash
gakr-ddgs news-search --query "AI breakthrough"
```

**Regional News (UK):**
```bash
gakr-ddgs news-search --query "technology" --region uk-en
```

**Last 24 Hours:**
```bash
gakr-ddgs news-search --query "politics" --timelimit d --max-results 20
```

**Last Week's News:**
```bash
gakr-ddgs news-search --query "finance" --timelimit w --max-results 30
```

**Safe Search Enabled:**
```bash
gakr-ddgs news-search --query "general interest" --safesearch on
```

**Custom Output:**
```bash
gakr-ddgs news-search --query "technology" --out ./news/tech_news.json --max-results 50
```

---

## Video Search - Full Options

### Command
```bash
gakr-ddgs video-search [OPTIONS]
```

### All Options

#### Required
| Option | Alias | Type | Description |
|--------|-------|------|-------------|
| `--query` | `-q` | STRING | Video search query (required) |

#### Results & Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | INT | Maximum videos to return |
| `--out` | `-o` | `video_search_results.json` | PATH | Output file path |
| `--json` | - | `false` | BOOL | Output to stdout as JSON |

#### Search Parameters
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | STRING | Region/locale |
| `--safesearch` | - | `moderate` | ENUM | Safe search: `on`, `moderate`, `off` |
| `--timelimit` | - | - | ENUM | Time filter: `d`, `w`, `m`, `y` |
| `--duration` | - | - | ENUM | Video duration: `short` (< 5 min), `medium` (5-30 min), `long` (> 30 min) |
| `--resolution` | - | - | ENUM | Resolution: `high`, `standard`, `any` |

#### Retry Options
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--no-retry-on-zero` | - | `false` | BOOL | Disable retry on zero results |
| `--retry-attempts` | - | `2` | INT | Number of retry attempts |
| `--retry-backoff` | - | `1.0` | FLOAT | Backoff multiplier |

#### Examples

**Basic Video Search:**
```bash
gakr-ddgs video-search --query "Python tutorial"
```

**Short Videos Only:**
```bash
gakr-ddgs video-search --query "motivation" --duration short --max-results 20
```

**Long-form Content (Courses):**
```bash
gakr-ddgs video-search --query "web development" --duration long --max-results 10
```

**High Resolution Videos:**
```bash
gakr-ddgs video-search --query "music" --resolution high --max-results 15
```

**Recent Videos:**
```bash
gakr-ddgs video-search --query "breaking news" --timelimit d --max-results 10
```

**Weekly Videos:**
```bash
gakr-ddgs video-search --query "trending" --timelimit w --max-results 30
```

---

## URL Fetch - Full Options

### Command
```bash
gakr-ddgs fetch-url [OPTIONS]
```

### All Options

#### Required
| Option | Alias | Type | Description |
|--------|-------|------|-------------|
| `--url` | `-u` | STRING | URL to fetch and extract (required) |

#### Extraction
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--timeout` | - | `5` | INT | Extraction timeout in seconds |

#### Output
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--out` | `-o` | `url_fetch_result.json` | PATH | Output file path |
| `--json` | - | `false` | BOOL | Output to stdout as JSON |

#### Examples

**Basic URL Fetch:**
```bash
gakr-ddgs fetch-url --url "https://example.com/article"
```

**Longer Timeout:**
```bash
gakr-ddgs fetch-url --url "https://heavy-site.com" --timeout 15
```

**JSON Output:**
```bash
gakr-ddgs fetch-url --url "https://example.com" --json > article.json
```

**Custom Output Location:**
```bash
gakr-ddgs fetch-url --url "https://wikipedia.org/wiki/AI" --out ./results/ai_article.json
```

---

## Region Codes

Common region codes for `--region` parameter:

| Code | Region |
|------|--------|
| `us-en` | United States (English) |
| `uk-en` | United Kingdom (English) |
| `ca-en` | Canada (English) |
| `au-en` | Australia (English) |
| `de-de` | Germany (German) |
| `fr-fr` | France (French) |
| `it-it` | Italy (Italian) |
| `es-es` | Spain (Spanish) |
| `jp-ja` | Japan (Japanese) |
| `cn-zh` | China (Chinese) |
| `br-pt` | Brazil (Portuguese) |
| `in-en` | India (English) |
| `wt-wt` | Worldwide |

---

## Safe Search Levels

| Level | Description |
|-------|-------------|
| `on` | Strict filtering - excludes adult content |
| `moderate` | Balanced filtering - default |
| `off` | No filtering - all results shown |

---

## Time Filters

| Code | Description |
|------|-------------|
| `d` | Last 24 hours (Day) |
| `w` | Last 7 days (Week) |
| `m` | Last 30 days (Month) |
| `y` | Last 365 days (Year) |

---

## Image Size Options

| Size | Typical Resolution |
|------|-------------------|
| `Small` | < 800px width |
| `Medium` | 800-1200px width |
| `Large` | 1200-1920px width |
| `Wallpaper` | > 1920px width |
| `Custom` | User-defined (use min/max width/height) |

---

## Image Colors

Available colors for `--color` filter:
- `Red`
- `Orange`
- `Yellow`
- `Green`
- `Blue`
- `Purple`
- `Pink`
- `Brown`
- `Black`
- `Gray`
- `White`
- `Transparent`

---

## Image Types

Available types for `--type-image` filter:
- `photo` - Photographs
- `clipart` - Vector graphics
- `gif` - Animated GIFs
- `transparent` - PNG with transparency
- `line` - Line drawings
- `other` - Other types

---

## Image Layouts

Available layouts for `--layout` filter:
- `Square` - 1:1 aspect ratio
- `Tall` - Portrait orientation (height > width)
- `Wide` - Landscape orientation (width > height)
- `Panoramic` - Ultra-wide (width >> height)

---

## Image Licenses

Available licenses for `--license-image` filter:
- `public` - Public domain
- `commercial` - Commercial use allowed
- `creative_commons` - Creative Commons licensed
- `any` - Any license

---

## Video Duration Options

| Duration | Description |
|----------|-------------|
| `short` | Less than 5 minutes |
| `medium` | 5 to 30 minutes |
| `long` | More than 30 minutes |

---

## Video Resolution Options

| Resolution | Description |
|-----------|-------------|
| `high` | 720p or higher |
| `standard` | 480p to 720p |
| `any` | Any resolution |

---

## Combine Options Examples

### Example 1: Professional Photo Database
```bash
gakr-ddgs image-search \
  --query "business professional" \
  --type-image "photo" \
  --license-image "commercial" \
  --min-width 1280 \
  --max-results 50 \
  --safesearch on
```

### Example 2: High-Res Wallpaper Collection
```bash
gakr-ddgs image-search \
  --query "nature landscape" \
  --size "Wallpaper" \
  --layout "Wide" \
  --min-width 2560 \
  --min-height 1440 \
  --max-results 20 \
  --download \
  --download-dir "./wallpapers"
```

### Example 3: Tech News with Multiple Regions
```bash
for region in "us-en" "uk-en" "de-de"; do
  gakr-ddgs web-search \
    --query "artificial intelligence" \
    --region "$region" \
    --timelimit w \
    --max-results 20 \
    --out "ai_news_${region}.json"
done
```

### Example 4: Comprehensive Video Research
```bash
gakr-ddgs video-search \
  --query "machine learning course" \
  --duration "long" \
  --resolution "high" \
  --max-results 30 \
  --safesearch on \
  --json > ml_courses.json
```

### Example 5: Quality-First Web Search
```bash
gakr-ddgs web-search \
  --query "research paper" \
  --max-results 50 \
  --workers 8 \
  --timeout 15 \
  --retry-attempts 3 \
  --region "us-en" \
  --safesearch on \
  --out "./research/papers.json"
```

---

## Implementation Status

| Feature | Status | Notes |
|---------|--------|-------|
| `--query` | ✅ Implemented | All search types |
| `--max-results` | ✅ Implemented | All search types |
| `--json` | ✅ Implemented | All search types |
| `--timeout` | ✅ Implemented | Web search, URL fetch |
| `--out` | ✅ Implemented | All search types |
| `--min/max-width/height` | ✅ Implemented | Image search only |
| `--download` | ✅ Available | Image search (optional feature) |
| `--region` | ⚠️ Partial | Supported by DuckDuckGo backend |
| `--safesearch` | ⚠️ Partial | Supported by DuckDuckGo backend |
| `--timelimit` | ⚠️ Partial | Supported by DuckDuckGo backend |
| `--workers` | ✅ Implemented | Web search extraction parallelism |
| `--retry-*` | ✅ Implemented | Web & image search |
| `--backend` | ⚠️ Partial | Auto-selected by DuckDuckGo |
| `--size`, `--color`, `--type-image`, `--layout`, `--license-image` | ⚠️ Partial | DuckDuckGo backend dependent |
| `--duration`, `--resolution` | ⚠️ Partial | Video search backend dependent |

---

## Notes

1. **DuckDuckGo Backend**: Some advanced options depend on DuckDuckGo API support, which varies by region and search type
2. **Parallelism**: `--workers` controls extraction parallelism (not API calls) for better performance
3. **Retry Logic**: Automatic retry helps overcome transient failures and zero-result scenarios
4. **Output Paths**: Absolute or relative paths can be used for `--out` parameter
5. **JSON Mode**: Use `--json` for piping to other tools (jq, Python, etc.)
6. **Timeouts**: Adjust `--timeout` based on page complexity (simple=5s, complex=15s, heavy=30s)

---

## Related Documentation

- [WebSearch.md](./websearch.md)
- [ImageSearch.md](./imagesearch.md)
- [NewsSearch.md](./newssearch.md)
- [VideoSearch.md](./videosearch.md)
- [Fetch.md](./fetch.md)
- [README.md](../../README.md)
