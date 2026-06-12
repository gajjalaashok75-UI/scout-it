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

### Filtering - Dimensions
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--min-width` | - | `0` | `INT` | Minimum image width in pixels |
| `--max-width` | - | `0` | `INT` | Maximum image width in pixels |
| `--min-height` | - | `0` | `INT` | Minimum image height in pixels |
| `--max-height` | - | `0` | `INT` | Maximum image height in pixels |

### Filtering - Visual Characteristics
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--size` | - | - | `ENUM` | Image size: `Small`, `Medium`, `Large`, `Wallpaper`, `Custom` |
| `--color` | - | - | `ENUM` | Color type: `Red`, `Orange`, `Yellow`, `Green`, `Blue`, `Purple`, `Pink`, `Brown`, `Black`, `Gray`, `White`, `Transparent` |
| `--type-image` | - | - | `ENUM` | Image type: `photo`, `clipart`, `gif`, `transparent`, `line`, `other` |
| `--layout` | - | - | `ENUM` | Image layout: `Square`, `Tall`, `Wide`, `Panoramic` |
| `--license-image` | - | - | `ENUM` | License type: `public`, `commercial`, `creative_commons`, `any` |

### Search Parameters
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--region` | - | `us-en` | `STRING` | Region/locale (e.g., `us-en`, `uk-en`, `wt-wt`) |
| `--safesearch` | - | `moderate` | `ENUM` | Safe search: `on`, `moderate`, `off` |
| `--timelimit` | - | - | `ENUM` | Time filter: `d` (day), `w` (week), `m` (month), `y` (year) |

### Download Options
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--download` | `-d` | `false` | `BOOL` | Download matched images |
| `--download-dir` | - | `downloaded_images` | `PATH` | Directory for downloads |

### Output & Retry
| Option | Alias | Default | Type | Description |
|--------|-------|---------|------|-------------|
| `--max-results` | `-m` | `10` | `INT` | Maximum images to return |
| `--out` | `-o` | `image_search_results.json` | `PATH` | Output file path |
| `--json` | - | `false` | `BOOL` | Output to stdout as JSON |
| `--no-retry-on-zero` | - | `false` | `BOOL` | Disable retry on zero results |
| `--retry-attempts` | - | `2` | `INT` | Number of retry attempts |
| `--retry-backoff` | - | `1.0` | `FLOAT` | Backoff multiplier |

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

### HD Images Only (1920×1080+)

Find high-resolution wallpapers:

```bash
gakr-ddgs image-search --query "wallpaper" --min-width 1920 --min-height 1080 --max-results 20
```

### Specific Visual Characteristics

Find blue clipart logos:

```bash
gakr-ddgs image-search --query "logo" --type-image "clipart" --color "Blue" --layout "Square"
```

### Size + Layout

Find panoramic landscape images:

```bash
gakr-ddgs image-search --query "landscape" --size "Wallpaper" --layout "Wide" --max-results 10
```

### License Filtered

Find Creative Commons images:

```bash
gakr-ddgs image-search --query "photo" --license-image "creative_commons" --max-results 15
```

### Download Images

Download matching images:

```bash
gakr-ddgs image-search \
  --query "nature" \
  --max-results 20 \
  --min-width 1024 \
  --download \
  --download-dir "./my_images"
```

### Aspect Ratio (Panoramic)

Find ultra-wide images:

```bash
gakr-ddgs image-search --query "mountain" --layout "Panoramic" --size "Wallpaper"
```

### Last Week's Images

Find recently added images:

```bash
gakr-ddgs image-search --query "news" --timelimit w --max-results 30
```

### JSON Output

Output raw JSON for processing:

```bash
gakr-ddgs image-search --query "city" --json > city_images.json
```

### Professional Photo Database

Find high-quality commercial images:

```bash
gakr-ddgs image-search \
  --query "business professional" \
  --type-image "photo" \
  --license-image "commercial" \
  --min-width 1280 \
  --max-results 50 \
  --safesearch on
```

### High-Res Wallpaper Collection

Create a wallpaper collection:

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

## Image Size Options

| Size | Typical Resolution |
|------|-------------------|
| `Small` | < 800px width |
| `Medium` | 800-1200px width |
| `Large` | 1200-1920px width |
| `Wallpaper` | > 1920px width |
| `Custom` | User-defined (use min/max width/height) |

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

## Image Types

Available types for `--type-image` filter:
- `photo` - Photographs
- `clipart` - Vector graphics
- `gif` - Animated GIFs
- `transparent` - PNG with transparency
- `line` - Line drawings
- `other` - Other types

## Image Layouts

Available layouts for `--layout` filter:
- `Square` - 1:1 aspect ratio
- `Tall` - Portrait orientation (height > width)
- `Wide` - Landscape orientation (width > height)
- `Panoramic` - Ultra-wide (width >> height)

## Image Licenses

Available licenses for `--license-image` filter:
- `public` - Public domain
- `commercial` - Commercial use allowed
- `creative_commons` - Creative Commons licensed
- `any` - Any license

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
