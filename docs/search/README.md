# Search Documentation

Reference guides for every scout-it search command. The authoritative source for flags is the CLI itself — run `scout-it <command> --help`.

## Available guides

| Guide | Commands covered |
|-------|-------------------|
| [websearch.md](./websearch.md) | `web-search`, `news-search` |
| [fetch.md](./fetch.md) | `fetch-url` |
| [imagesearch.md](./imagesearch.md) | `image-search` |
| [videosearch.md](./videosearch.md) | `video-search`, `video-extract` |
| [wikipedia.md](./wikipedia.md) | `wikipedia-search`, `sources`, `index`, `semantic-search` |

## Quick command reference

```bash
scout-it web-search --query "your query" --max 5
scout-it news-search --query "your query" --category ai --snippets
scout-it image-search --query "your query" --max 10 --min-width 800
scout-it video-search --query "your query" --max 5
scout-it fetch-url --url "https://example.com"
scout-it multi-search --query "your query" --engines duckduckgo,brave
scout-it wikipedia-search --query "machine learning"
scout-it sources                       # list 30+ source plugins
scout-it index --query "topic" --max 20
scout-it semantic-search --query "topic"
```

## Output

By default, every command writes a JSON object to `.scout-it/<command>_results.json`. `--markdown` saves a readable `.md` file instead. The GitHub, social, `video-extract`, `fetch-url`, `multi-search`, `wikipedia-search`, and `semantic-search` commands also accept `--json` to print raw JSON to stdout.

> `web-search`, `news-search`, `image-search`, and `video-search` do **not** have a `--json` flag — use `--out` / `--markdown` to control their output.

## Programmatic API

```python
from scout_it import web_search, news_search, image_search, video_search, fetch_url

results, stats = web_search("your query", max_results=10)
```

Each CLI subcommand has a same-named Python function mirroring its flags as keyword arguments.

## See also

- [../README.md](../../README.md) — full CLI reference (all 30 subcommands)
- [../INSTALL.md](../INSTALL.md) — installation & setup
