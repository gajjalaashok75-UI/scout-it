# wikipedia-search, sources, index, semantic-search

## wikipedia-search

Search any Wikimedia project via the MediaWiki Action API — all **12 projects**: wikipedia, commons, wikivoyage, wiktionary, wikibooks, wikidata, wikiversity, wikiquote, mediawiki, wikisource, wikispecies, wikifunctions.

```bash
scout-it wikipedia-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query or page title (required) |
| `--max, -m` `<n>` | Max results (1-50, default: 10) |
| `--project` `<project>` | Wikimedia project to search (default: `wikipedia`; any of the 12 projects in `SITE_MAP`) |
| `--language, -l` `<code>` | Project language for language-scoped wikis (default: `en`) |
| `--timeout` `<seconds>` | HTTP timeout in seconds (default: 25) |
| `--workers, -w` `<n>` | Parallel workers (default: 5) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/wikimedia_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--json` | Output raw JSON to stdout |
| `--summary` | Fetch a Wikipedia REST summary for the given title |
| `--extract` | Fetch cleaned full-page extract via the Action API |
| `--sections` | Export section-by-section cleaned text |
| `--crawl` | Enable recursive crawl from the search results (with `--crawl-depth`) |
| `--crawl-depth` `<n>` | Crawl depth for `--crawl` mode (default: 2) |
| `--bundle` | Run a broad multi-project topic bundle (searches all 12 projects) |
| `--robots` | Check robots.txt allowance before searching |
| `--no-clean` | Disable text cleaning |
| `--rss` | Include MediaWiki RecentChanges RSS feeds in discovery (uses `--project` as default category) |
| `--category, -c` `<project>` | Wikimedia project RSS category to include (repeatable): `wikipedia`, `commons`, `wiktionary`, `wikivoyage`, `wikibooks`, `wikidata`, `wikiversity`, `wikiquote`, `mediawiki`, `wikisource`, `wikispecies`, `wikifunctions`. Adds recently-changed pages to the candidate pool before ranking |

### Examples

```bash
scout-it wikipedia-search --query "machine learning"
scout-it wikipedia-search --query "Albert Einstein" --project wikipedia --extract
scout-it wikipedia-search --query "quantum physics" --bundle
scout-it wikipedia-search --query "dogs" --project wiktionary --summary
scout-it wikipedia-search --query "API" --project mediawiki --sections
```

## sources

List all source plugins available via the `--sources` flag on `web-search`, `news-search`, `image-search`, `video-search`, and `multi-search`. All sources are free or have free tiers — 30+ plugins including `openalex`, `arxiv`, `crossref`, `semantic_scholar`, `huggingface`, `zenodo`, `wikidata`, `gdelt`, `internet_archive`, `openstreetmap`, `hackernews`, `stackexchange`, and more.

```bash
scout-it sources [--json]
```

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON instead of a formatted table |

Sources needing a key (e.g. `semantic_scholar`, `core`) show ❌ until configured via `scout-it config`; free sources are ready immediately. Use `--sources openalex,arxiv` on any search command to merge those results with BM25F+vector re-ranking, or `--auto-sources` to let the bandit pick.

## index

Fetch, extract, chunk, and embed `web-search` or `news-search` results into the persistent LanceDB store at `~/.scout-it/semantic/lancedb/`. The corpus then powers `semantic-search` and survives across runs. Needs: `pip install sentence-transformers torch lancedb`.

```bash
scout-it index --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Query to fetch and index (required) |
| `--max, -m` `<n>` | Max results to fetch and index (default: 20) |
| `--source` `<web\|news>` | Source to fetch from: `web` or `news` (default: `web`) |

### Examples

```bash
scout-it index --query "transformer architecture" --max 20
scout-it index --query "AI news" --source news
```

## semantic-search

Search a persistent corpus of previously-indexed documents using hybrid BM25 + dense-vector retrieval. Use `scout-it index` to build the corpus first. Storage: `~/.scout-it/semantic/lancedb/`. Model configurable via the `SCOUT_SEMANTIC_MODEL` env var (default: `BAAI/bge-m3`). Needs: `pip install sentence-transformers torch lancedb`.

```bash
scout-it semantic-search --query "<text>" [options]
```

| Flag | Description |
|------|-------------|
| `--query, -q` `<text>` | Search query (required) |
| `--max, -m` `<n>` | Max results (default: 10) |
| `--out, -o` `<path>` | Output file (default: `.scout-it/semantic_results.json`) |
| `--markdown` | Save results as Markdown (.md) instead of JSON |
| `--json` | Output raw JSON to stdout |

### Typical workflow

```bash
# 1. Build the corpus once (or refresh it periodically)
scout-it index --query "transformer architecture" --max 20

# 2. Query it any time
scout-it semantic-search --query "attention mechanisms" --max 5
```

## Programmatic API

```python
from scout_it import wikimedia_search

results, _ = wikimedia_search("machine learning", project="wikipedia")
```

The semantic index/store is currently CLI-only (`SemanticIndex` lives in `scout_it.semantic`).

## Related documentation

- [web-search & news-search](./websearch.md)
- [README.md](../README.md)
