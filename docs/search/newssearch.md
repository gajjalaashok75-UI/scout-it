# news-search

News search is documented together with web-search in [websearch.md](./websearch.md), since both use the identical `EnterpriseSearchEngine` and share most flags.

## Quick reference

```bash
scout-it news-search --query "<text>" [options]
```

`news-search` shares the same resilient fetch chain, `--snippets`, `--sources` / `--auto-sources`, `--category`, retry/fallback, TLS/profile/bandit, and `--semantic` flags as `web-search`. The differences are:

| News-specific flag | Description |
|------|-------------|
| `--source` `<google-news>` | Search source override (default: DuckDuckGo News). Use `google-news` for Google News RSS. Falls back to the other source on zero results |
| `--category` `<categories...>` | News RSS categories: `ai`, `startups`, `security`, `cloud`, `all`. Multiple allowed, e.g. `--category ai startups` |
| `--location` `<places...>` | Location(s) for localized news from Times of India RSS (e.g. `india`, `US`, `UK`, `europe`, `china`, `india-delhi`, `india-bangalore`). Multiple allowed |
| `--max-chars` `<n>` | Maximum characters to keep in extracted article content |
| `--max-size` `<size>` | Maximum response size per article (e.g. `5mb`). Truncates raw HTML before extraction |

Default output: `.scout-it/news_search_results.json`. Default `--max`: 10 (full extraction), 30 (`--snippets` mode). Default `--region`: `us-en`.

See [websearch.md](./websearch.md) for the full flag table and pipeline description.

## Examples

```bash
scout-it news-search --query "artificial intelligence" --max 5
scout-it news-search --query "AI updates" --category ai --snippets
scout-it news-search --query "India economy" --source google-news --location india
scout-it news-search --query "zero-day vulnerabilities" --category security --timelimit d
scout-it news-search --query "cloud computing" --category ai cloud devops
```

## Related documentation

- [web-search & news-search](./websearch.md)
- [README.md](../README.md)
