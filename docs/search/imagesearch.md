# Image Search Documentation

## Overview

Image search retrieves images from DuckDuckGo with advanced filtering options. It supports dimension filtering to find images of specific sizes and resolutions.

## Command Syntax

```bash
gakr-ddgs image-search [OPTIONS]
```

## Required Options

| Option | Alias | Description | Type |
|--------|-------|-------------|------|
| `--query` | `-q` | Image search query string | `STRING` |

## Optional Options

| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | `INT` | Maximum number of images to return |
| `--min-width` | - | `0` | `INT` | Minimum image width in pixels (0 = no limit) |
| `--min-height` | - | `0` | `INT` | Minimum image height in pixels (0 = no limit) |
| `--json` | - | `false` | `BOOL` | Output raw JSON to stdout instead of saving to file |

## Output File

By default, results are saved to:

```
image_search_results.json
```

Location: Full path is displayed in console with 📂 emoji

### Output Format

```json
{
  "query": "mountain landscape",
  "search_type": "image",
  "timestamp": "2026-06-12T10:30:00Z",
  "total_results": 5,
  "results": [
    {
      "position": 1,
      "title": "Beautiful Mountain Vista",
      "image_url": "https://example.com/image.jpg",
      "source_url": "https://example.com/photo-gallery",
      "thumbnail_url": "https://example.com/thumb.jpg",
      "dimensions": {
        "width": 1920,
        "height": 1080
      },
      "image_size": "2.3 MB"
    }
  ],
  "metadata": {
    "search_parameters": {
      "min_width": 1024,
      "min_height": 768
    },
    "filtered_count": 5,
    "timestamp": "2026-06-12T10:30:00Z"
  }
}
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `position` | INT | Result position (1-indexed) |
| `title` | STRING | Image title/alt text |
| `image_url` | STRING | Direct URL to the image |
| `source_url` | STRING | URL of the page containing the image |
| `thumbnail_url` | STRING | Thumbnail preview URL |
| `dimensions` | OBJECT | Image width and height in pixels |
| `image_size` | STRING | Approximate file size |

## Dimension Filtering

### No Filters (Default)

Get any images:

```bash
gakr-ddgs image-search --query "cat"
```

### Minimum Width

Find images at least 1024px wide:

```bash
gakr-ddgs image-search --query "wallpaper" --min-width 1024
```

### Minimum Height

Find images at least 768px tall:

```bash
gakr-ddgs image-search --query "portrait" --min-height 768
```

### Both Width and Height

Find HD images (1920×1080 or larger):

```bash
gakr-ddgs image-search --query "landscape" --min-width 1920 --min-height 1080
```

### Filtering Behavior

- **Images without dimensions** are excluded if ANY filter is enabled
- **Filters are inclusive** (image >= min dimension passes)
- **Invalid dimensions** are treated as missing and excluded
- **Disabled filters** (0 value) allow any dimension

## Usage Examples

### Basic Image Search

Search for dog images:

```bash
gakr-ddgs image-search --query "dog"
```

### High-Resolution Images

Find images suitable for wallpaper (2560×1440+):

```bash
gakr-ddgs image-search --query "nature landscape" --min-width 2560 --min-height 1440
```

### HD Ready

Find images that work on 1080p displays:

```bash
gakr-ddgs image-search --query "architecture" --min-width 1920 --min-height 1080
```

### Limited Results

Get only 5 high-quality images:

```bash
gakr-ddgs image-search --query "sunset" --max-results 5 --min-width 1280 --min-height 720
```

### Mobile-Friendly

Get portrait-oriented images:

```bash
gakr-ddgs image-search --query "phone wallpaper" --min-width 540 --min-height 960
```

### JSON Output

Output raw JSON for processing:

```bash
gakr-ddgs image-search --query "city" --json > city_images.json
```

### Combined Options

```bash
gakr-ddgs image-search \
  --query "mountain" \
  --max-results 20 \
  --min-width 1920 \
  --min-height 1080 \
  --json
```

## Programmatic API

### Python Example - Basic Search

```python
from gakr_ddgs.extraction import ImageSearchEngine

engine = ImageSearchEngine()
results = engine.search(
    query="mountain landscape",
    max_results=10
)

for result in results:
    print(f"Title: {result.title}")
    print(f"Image URL: {result.image_url}")
    print(f"Size: {result.dimensions['width']}x{result.dimensions['height']}")
    print()
```

### Python Example - With Dimension Filtering

```python
from gakr_ddgs.extraction import ImageSearchEngine

engine = ImageSearchEngine()
results = engine.search(
    query="wallpaper",
    max_results=10,
    min_width=1920,
    min_height=1080
)

for result in results:
    w = result.dimensions['width']
    h = result.dimensions['height']
    print(f"{result.title} - {w}x{h}")
    print(f"View at: {result.source_url}")
```

### Python Example - Filtering Results

```python
from gakr_ddgs.extraction import ImageSearchEngine

engine = ImageSearchEngine()
results = engine.search(query="nature", max_results=20)

# Filter for landscape images (width > height)
landscape_images = [
    r for r in results 
    if r.dimensions['width'] > r.dimensions['height']
]

print(f"Found {len(landscape_images)} landscape images")
for img in landscape_images:
    print(f"  {img.title}: {img.dimensions['width']}x{img.dimensions['height']}")
```

## Common Use Cases

### Collection Use Case: Building an Image Dataset

```bash
# Collect 50 high-quality cat images
gakr-ddgs image-search \
  --query "cat" \
  --max-results 50 \
  --min-width 800 \
  --min-height 600 \
  --json > cat_dataset.json
```

### Design Use Case: Finding Inspiration

```bash
# Find professional design images
gakr-ddgs image-search \
  --query "modern interior design" \
  --max-results 20 \
  --min-width 1280 \
  --min-height 720
```

### Wallpaper Use Case: Finding Desktop Backgrounds

```bash
# Find 4K wallpapers
gakr-ddgs image-search \
  --query "space universe" \
  --max-results 10 \
  --min-width 3840 \
  --min-height 2160
```

### Thumbnail Use Case: Getting Small Images

```bash
# Get images that will work as thumbnails
gakr-ddgs image-search \
  --query "logo" \
  --max-results 30 \
  --min-width 128 \
  --min-height 128
```

## Performance Considerations

| Factor | Impact | Notes |
|--------|--------|-------|
| `--max-results` | Medium | More results = longer search. Start with 10-20. |
| `--min-width` / `--min-height` | Low | Filtering is fast (done locally after fetching) |
| Network Speed | High | Each image URL needs to be fetched |

**Typical Execution Times:**
- 10 results (no filters): 3-8 seconds
- 20 results (no filters): 5-15 seconds
- Same with filters: +1-2 seconds (filtering is local)

## Troubleshooting

### No Images Returned

**Problem:** Search returns empty or very few results

**Solutions:**
- Try a simpler query term
- Remove or loosen dimension filters
- Try increasing `--max-results` to 30
- Different search terms may have better coverage

### Not Enough High-Resolution Images

**Problem:** Very few results meet dimension requirements

**Solutions:**
- Lower the `--min-width` or `--min-height`
- Increase `--max-results` to search more
- Try more specific search terms (e.g., "4K wallpaper" vs "image")
- Some image types naturally have low resolution

### Missing Image Dimensions

**Problem:** Many results skipped due to missing dimensions

**Causes:**
- Some image hosting sites don't report dimensions
- Images from certain platforms may lack metadata

**Solutions:**
- Use `--min-width 0 --min-height 0` to include unknown dimensions (default)
- Try different search terms that may have better metadata
- This is expected behavior for some sources

### Slow Search

**Problem:** Image search takes too long

**Solutions:**
- Reduce `--max-results`
- Try simpler search terms
- Check your internet speed
- DuckDuckGo may be rate-limiting; try again later

## Advanced Usage

### Batch Image Collection

```bash
# Collect images for multiple queries
for topic in "dog" "cat" "bird"; do
  gakr-ddgs image-search \
    --query "$topic" \
    --max-results 20 \
    --min-width 1280 \
    --min-height 720 \
    --json > "${topic}_images.json"
done
```

### Processing Results with JQ

Find all landscape images:

```bash
gakr-ddgs image-search --query "nature" --json | \
  jq '.results[] | 
      select(.dimensions.width > .dimensions.height) | 
      {title, dimensions, image_url}'
```

### Finding Specific Aspect Ratios

Get images with 16:9 aspect ratio (1920×1080 is 16:9):

```bash
gakr-ddgs image-search --query "landscape" --json | \
  jq '.results[] | 
      select((.dimensions.width / .dimensions.height) > 1.7 and 
             (.dimensions.width / .dimensions.height) < 1.8)'
```

## Related Documentation

- [Web Search](./websearch.md)
- [Video Search](./videosearch.md)
- [README.md](../../README.md)
- [AGENTS.md](../../AGENTS.md)
