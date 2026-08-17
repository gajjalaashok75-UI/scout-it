# image-search

## Overview

DuckDuckGo image search with dimension, color, type, layout, and license filters, plus optional image download and Media RSS feed discovery (Flickr/NASA/DeviantArt) via `--category` / `--rss`.

## Command

```bash
scout-it image-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max images (1-50, default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/image_search_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--sources` `<list>` | Also search source plugins (comma-separated, e.g. `internet_archive,openstreetmap`) and merge with BM25F+vector re-ranking. Run `scout-it sources` for the list |
| `--auto-sources` | Let the source-selection bandit pick the best sources for this query type. Overrides `--sources` |
| `--download, -d` | Download images to disk |
| `--download-dir` `<path>` | Download directory (default: `.scout-it/downloaded_images`) |
| `--region` `<region>` | DuckDuckGo region (default: `us-en`; example: `us-en`, `wt-wt`) |
| `--safesearch` `<level>` | Safe search mode: `on`, `moderate`, `off` (default: `moderate`) |
| `--timelimit` `<range>` | DuckDuckGo time limit: `d`, `w`, `m`, `y` |
| `--size` `<size>` | Image size filter: `Small`, `Medium`, `Large`, `Wallpaper` |
| `--color` `<color>` | Image color filter |
| `--type-image` `<type>` | Image type filter: `photo`, `clipart`, `gif`, `transparent`, `line` |
| `--layout` `<layout>` | Image layout filter: `Square`, `Tall`, `Wide` |
| `--license-image` `<license>` | Image license filter |
| `--min-width` `<px>` | Minimum image width in pixels |
| `--max-width` `<px>` | Maximum image width in pixels |
| `--min-height` `<px>` | Minimum image height in pixels |
| `--max-height` `<px>` | Maximum image height in pixels |
| `--category` `<categories...>` | Image RSS categories to include (e.g. `nature space travel anime_art fantasy_art`). Fetches Media RSS feeds (Flickr/NASA/DeviantArt) alongside DuckDuckGo and ranks them together |
| `--rss` | Include image RSS discovery even without `--category` — fetches a Flickr tag feed **and** keyword-matched DeviantArt tag feeds from the query in parallel |
| `--no-retry-on-zero` | Disable retries when 0 valid images are found (retries on by default) |
| `--retry-attempts` `<n>` | Retry attempts when 0 valid images are found (default: 2) |
| `--retry-backoff` `<seconds>` | Backoff seconds between retries (default: 1.0) |

## Dimension filtering rules

When any of `--min-width` / `--max-width` / `--min-height` / `--max-height` is set:

- Images missing width/height are excluded.
- Range checks are inclusive.
- Invalid/negative dimensions are treated as missing.

With no dimension filters enabled, images missing dimensions are allowed through.

## Examples

```bash
scout-it image-search --query "sunset" --max 10 --min-width 1920 --min-height 1080
scout-it image-search --query "landscape" --size Large --license-image public
scout-it image-search --query "space" --category nature space --download
scout-it image-search --query "icons" --type-image transparent --color blue
scout-it image-search --query "wallpapers" --layout Wide --download-dir ./walls

# DeviantArt art discovery — keyword-matched tag feeds fetched in parallel with Flickr
scout-it image-search --query "anime girls sword" --rss --max 20
scout-it image-search --query "dnd elves fantasy" --category fantasy_art --max 15
scout-it image-search --query "digital art concept" --category concept_art digital_art --max 20
```

## DeviantArt RSS integration

When `--rss` is used (or an art-related `--category`), image-search fetches DeviantArt Media RSS feeds from `backend.deviantart.com/rss.xml?q=<tag>&type=deviation` alongside Flickr/NASA feeds. The query is matched against a keyword map (97 keywords → DeviantArt tags) so the right tag feeds are selected automatically:

| Query keywords | DeviantArt tags fetched |
|----------------|------------------------|
| `anime girls sword` | `animegirls`, `anime`, `animemanga`, `swords` |
| `dnd elves` | `elves`, `dnd`, `rpg` |
| `digital art concept` | `digitalart`, `conceptart`, `traditional`, `painting` |
| `fantasy dragons` | `fantasy`, `magicrealms`, `dnd` |
| `cute kawaii` | `kawaii`, `cute` |

Queries with no keyword match still get a DeviantArt feed (the raw query becomes the tag). DeviantArt-enriched categories: `digital_art`, `fantasy_art`, `anime_art`, `concept_art`, `fan_art`, `photography`.

## Output

Writes a JSON object (or Markdown with `--markdown`) to `.scout-it/image_search_results.json` by default. Each result includes the image URL, dimensions, thumbnail, source, and (if `--download`) the local download path.

## Programmatic API

```python
from scout_it import image_search

images, stats = image_search("mountain landscape", max_results=10, min_width=1024)
for img in images:
    print(img.get("image"), img.get("dimensions"))
```

## Related documentation

- [web-search & news-search](./websearch.md)
- [video-search](./videosearch.md)
- [README.md](../README.md)
