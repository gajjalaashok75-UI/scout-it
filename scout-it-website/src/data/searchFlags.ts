// Seeded from scout_it/cli.py argparse definitions (build_parser). Single source of truth for flags.

export interface CliFlag {
  flag: string
  arg?: string
  description: string
}

export interface FlagGroup {
  id: string
  label: string
  usage: string
  intro?: string
  flags: CliFlag[]
  example: string
}

export const webSearchFlags: FlagGroup = {
  id: 'web-search',
  label: 'web-search',
  usage: 'scout-it web-search --query "<text>" [options]',
  intro: 'DuckDuckGo text search plus full content extraction and cleaning for every result. Pipeline: collect snippets from all sources → rank by relevance → extract full content for the top N.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Number of results to return. Default: 10 (full extraction), 30 (--snippets mode).' },
    { flag: '--snippets', description: 'Return ranked snippets only. Skips content extraction for ~10x faster results (~2-4s vs 20-70s). Default limit: 30 snippets.' },
    { flag: '--workers, -w', arg: '<n>', description: 'Parallel workers (default: 5).' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/struct_format_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--sources', arg: '<list>', description: 'Also search source plugins (comma-separated, e.g. openalex,arxiv,wikidata) and merge results with BM25F+vector re-ranking. Run `scout-it sources` for available sources.' },
    { flag: '--auto-sources', description: 'Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off (default: moderate).' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d (day), w (week), m (month), y (year).' },
    { flag: '--backend', arg: '<backend>', description: 'DDGS backend: auto, html, lite (default: auto).' },
    { flag: '--source', arg: '<wikimedia>', description: 'Search source override (default: DuckDuckGo). Use "wikimedia" to search Wikipedia directly. Falls back to the other source on zero results.' },
    { flag: '--category', arg: '<categories...>', description: 'Category-specific RSS feeds to include (ai, engineering, cloud, devops, research, security, startups, etc.). Multiple allowed, e.g. --category ai cloud. Merged with DuckDuckGo results.' },
    { flag: '--no-retry-on-zero', description: 'Disable retries when 0 successful extractions (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts when 0 successful extractions (default: 2).' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries (default: 1.0).' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier (requests, then Playwright) when fetching each result page (default: 3).' },
    { flag: '--enable-alternate-source', description: 'If every fetch tier fails, try AMP/mobile/print URL variants and a Wayback Machine snapshot before giving up (extra requests, opt-in).' },
    { flag: '--no-dns-fallback', description: 'Disable the DNS-over-HTTPS retry on DNS-looking errors (on by default).' },
    { flag: '--tls-impersonate', description: 'Insert a browser-accurate TLS/JA3 fingerprint tier between requests and Playwright (needs: pip install scout-it[tls-impersonate]).' },
    { flag: '--persistent-profile', description: 'Use a persistent Playwright profile (cookies/session survive across runs) instead of a throwaway context for the JS-render tier.' },
    { flag: '--profile-name', arg: '<name>', description: 'Persistent profile name (only with --persistent-profile, default: default).' },
    { flag: '--use-bandit', description: 'Once a domain has enough recorded history, skip straight to whichever fetch tier has worked best for it instead of always starting with plain requests (see scout-it stats).' },
    { flag: '--no-js-fallback', description: 'Disable the automatic Playwright fallback for blocked/failed page fetches.' },
    { flag: '--semantic', description: 'Re-rank results by semantic relevance (hybrid BM25+dense-vector + cross-encoder). Needs: pip install sentence-transformers torch.' },
  ],
  example: 'scout-it web-search --query "machine learning" --max 5\nscout-it web-search --query "kubernetes" --category devops --snippets\nscout-it web-search --query "transformer architecture" --sources openalex,arxiv --semantic -m 5',
}

export const newsSearchFlags: FlagGroup = {
  id: 'news-search',
  label: 'news-search',
  usage: 'scout-it news-search --query "<text>" [options]',
  intro: 'DuckDuckGo news search with regional/temporal filtering and full article content extraction. Same staged ranking, snippets mode, and resilient fetch chain as web-search.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Number of results to return. Default: 10 (full extraction), 30 (--snippets mode).' },
    { flag: '--snippets', description: 'Return ranked news snippets only. Skips article extraction for ~10x faster results (~2-4s vs 20-70s). Default limit: 30 snippets.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/news_search_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--sources', arg: '<list>', description: 'Also search source plugins (comma-separated, e.g. gdelt,openalex,crossref) and merge with BM25F+vector re-ranking.' },
    { flag: '--auto-sources', description: 'Let the source-selection bandit pick the best sources for this query type (learned from past outcomes). Overrides --sources.' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (default: us-en; example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off (default: moderate).' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d, w, m, y.' },
    { flag: '--workers', arg: '<n>', description: 'Parallel workers for content extraction (default: 5).' },
    { flag: '--source', arg: '<google-news>', description: 'Search source override (default: DuckDuckGo News). Use "google-news" to search Google News RSS directly. Falls back to the other source on zero results.' },
    { flag: '--category', arg: '<categories...>', description: 'News RSS categories (ai, startups, security, cloud, all). Multiple allowed, e.g. --category ai startups. Merged with DuckDuckGo News.' },
    { flag: '--no-retry-on-zero', description: 'Disable retries on zero results (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts on zero results (default: 2).' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries (default: 1.0).' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier (requests, then Playwright) when fetching each article page (default: 3).' },
    { flag: '--no-js-fallback', description: 'Disable automatic Playwright fallback when an article fetch fails or looks blocked.' },
    { flag: '--enable-alternate-source', description: 'If every fetch tier fails, try AMP/mobile/print URL variants + a Wayback Machine snapshot before giving up (opt-in).' },
    { flag: '--no-dns-fallback', description: 'Disable the DNS-over-HTTPS retry on DNS-looking errors (on by default).' },
    { flag: '--tls-impersonate', description: 'Browser-accurate TLS/JA3 fingerprint tier (needs: pip install scout-it[tls-impersonate]).' },
    { flag: '--persistent-profile', description: 'Persistent Playwright profile (cookies/session survive across runs).' },
    { flag: '--profile-name', arg: '<name>', description: 'Persistent profile name (only with --persistent-profile, default: default).' },
    { flag: '--use-bandit', description: 'Skip to best-performing tier per domain from history.' },
    { flag: '--location', arg: '<places...>', description: 'Location(s) for localized news from Times of India RSS (e.g. india, US, UK, europe, china, india-delhi, india-bangalore). Multiple allowed.' },
    { flag: '--max-chars', arg: '<n>', description: 'Maximum characters to keep in extracted article content.' },
    { flag: '--max-size', arg: '<size>', description: 'Maximum response size per article (e.g. 5mb). Truncates the raw HTML before extraction.' },
    { flag: '--semantic', description: 'Re-rank results by semantic relevance (hybrid BM25+dense-vector + cross-encoder). Needs: pip install sentence-transformers torch.' },
  ],
  example: 'scout-it news-search --query "artificial intelligence" --max 5\nscout-it news-search --query "AI updates" --category ai --snippets\nscout-it news-search --query "India economy" --source google-news --location india',
}

export const imageSearchFlags: FlagGroup = {
  id: 'image-search',
  label: 'image-search',
  usage: 'scout-it image-search --query "<text>" [options]',
  intro: 'DuckDuckGo image search with rich dimension, color, and license filters, plus optional Media RSS feeds.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max images (1-50, default: 5).' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/image_search_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--sources', arg: '<list>', description: 'Also search source plugins (comma-separated, e.g. internet_archive,openstreetmap) and merge with BM25F+vector re-ranking.' },
    { flag: '--auto-sources', description: 'Let the source-selection bandit pick the best sources for this query type. Overrides --sources.' },
    { flag: '--download, -d', description: 'Download images to disk.' },
    { flag: '--download-dir', arg: '<path>', description: 'Download directory (default: .scout-it/downloaded_images).' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (default: us-en; example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off (default: moderate).' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d, w, m, y.' },
    { flag: '--size', arg: '<size>', description: 'Image size filter: Small, Medium, Large, Wallpaper.' },
    { flag: '--color', arg: '<color>', description: 'Image color filter.' },
    { flag: '--type-image', arg: '<type>', description: 'Image type filter: photo, clipart, gif, transparent, line.' },
    { flag: '--layout', arg: '<layout>', description: 'Image layout filter: Square, Tall, Wide.' },
    { flag: '--license-image', arg: '<license>', description: 'Image license filter.' },
    { flag: '--min-width', arg: '<px>', description: 'Minimum image width in pixels.' },
    { flag: '--max-width', arg: '<px>', description: 'Maximum image width in pixels.' },
    { flag: '--min-height', arg: '<px>', description: 'Minimum image height in pixels.' },
    { flag: '--max-height', arg: '<px>', description: 'Maximum image height in pixels.' },
    { flag: '--category', arg: '<categories...>', description: 'Image RSS categories to include (e.g. nature space travel). Fetches Media RSS feeds (Flickr/NASA) alongside DuckDuckGo and ranks them together.' },
    { flag: '--rss', description: 'Include image RSS discovery even without --category (uses a Flickr tag feed from the query).' },
    { flag: '--no-retry-on-zero', description: 'Disable retries when 0 valid images are found (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts when 0 valid images are found (default: 2).' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries (default: 1.0).' },
  ],
  example: 'scout-it image-search --query "landscape" --max 10 --min-width 1024 --min-height 768\nscout-it image-search --query "space" --category nature space --download',
}

export const videoSearchFlags: FlagGroup = {
  id: 'video-search',
  label: 'video-search',
  usage: 'scout-it video-search --query "<text>" [options]',
  intro: 'DuckDuckGo video search with duration, resolution, and license filters. When DuckDuckGo Videos returns nothing (its endpoint is intermittently unreliable), the pipeline automatically falls back to YouTube search so the command reliably returns ranked results.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max videos (1-50, default: 5).' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/video_search_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--sources', arg: '<list>', description: 'Also search source plugins (comma-separated, e.g. internet_archive,listennotes) and merge with BM25F+vector re-ranking.' },
    { flag: '--auto-sources', description: 'Let the source-selection bandit pick the best sources for this query type. Overrides --sources.' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (default: us-en; example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off (default: moderate).' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d, w, m, y.' },
    { flag: '--resolution', arg: '<res>', description: 'Video resolution filter: high, standard.' },
    { flag: '--duration', arg: '<duration>', description: 'Video duration filter: short, medium, long.' },
    { flag: '--license-videos', arg: '<license>', description: 'Video license filter.' },
    { flag: '--category', arg: '<categories...>', description: 'Video RSS categories to include (e.g. technology science news). Fetches YouTube channel RSS feeds alongside DuckDuckGo and ranks them together.' },
    { flag: '--rss', description: 'Include video RSS discovery even without --category (pulls a default set of YouTube channels).' },
    { flag: '--no-retry-on-zero', description: 'Disable retries when 0 results are found (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts when 0 results are found (default: 2).' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries (default: 1.0).' },
  ],
  example: 'scout-it video-search --query "python programming tutorial" --max 5\nscout-it video-search --query "tech talks" --category technology --duration long',
}

export const videoExtractFlags: FlagGroup = {
  id: 'video-extract',
  label: 'video-extract',
  usage: 'scout-it video-extract --url "<youtube-url>" [options]',
  intro: 'Full metadata (title, channel, view/like counts, description, upload date) and, where available, subtitles/transcript for a YouTube video. Only YouTube is supported today; other platforms return a clear unsupported_platform error.',
  flags: [
    { flag: '--url', arg: '<url>', description: 'Video URL to extract (e.g. https://www.youtube.com/watch?v=VIDEO_ID).' },
    { flag: '--subtitle-lang', arg: '<code>', description: 'Preferred subtitle language code (default: en).' },
    { flag: '--segments', description: 'Include subtitle segments with timestamps.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier (requests, then Playwright) when fetching the video page.' },
    { flag: '--no-js-fallback', description: 'Disable automatic Playwright fallback when the page fetch fails or looks blocked.' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/video_extract_results.json).' },
    { flag: '--json', description: 'Output raw JSON to stdout.' },
  ],
  example: 'scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments',
}

export const fetchUrlFlags: FlagGroup = {
  id: 'fetch-url',
  label: 'fetch-url',
  usage: 'scout-it fetch-url --url "https://example.com" [options]',
  intro: 'Direct extraction from a single URL, through the same three-tier resilient-fetch chain used everywhere else.',
  flags: [
    { flag: '--url, -u', arg: '<url>', description: 'URL to fetch.' },
    { flag: '--timeout', arg: '<seconds>', description: 'Extraction timeout in seconds (increase for JS-rendered SPAs).' },
    { flag: '--max-chars', arg: '<n>', description: 'Maximum characters to extract (e.g. 10000). Mutually exclusive with --max-size.' },
    { flag: '--max-size', arg: '<size>', description: 'Maximum response size (e.g. 100kb, 1mb, 500mb). Mutually exclusive with --max-chars.' },
    { flag: '--raw-html', description: 'Return raw HTML (prettified) instead of extracted/cleaned content.' },
    { flag: '--js-render', description: 'Skip straight to Playwright rendering instead of trying requests first.' },
    { flag: '--no-js-fallback', description: 'Disable automatic Playwright fallback when requests fails or looks blocked.' },
    { flag: '--enable-alternate-source', description: 'If every fetch tier fails, try AMP/mobile/print URL variants and a Wayback Machine snapshot before giving up (extra requests, opt-in).' },
    { flag: '--max-retries', arg: '<n>', description: 'Retry attempts per fetch tier (requests, then Playwright).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/url_fetch_result.json).' },
    { flag: '--json', description: 'Output raw JSON to stdout.' },
  ],
  example: 'scout-it fetch-url --url "https://example.com/article"\nscout-it fetch-url --url "https://spa-heavy-site.com" --js-render',
}

export const multiSearchFlags: FlagGroup = {
  id: 'multi-search',
  label: 'multi-search',
  usage: 'scout-it multi-search --query "<text>" --engines duckduckgo,brave,google [options]',
  intro: 'Queries several search engines in parallel, merges and dedupes by URL, then runs the same content-extraction pipeline as web-search. DuckDuckGo works with no setup; Brave/Bing/Google/SerpAPI each need an API key (run `scout-it list-engines`). Unconfigured engines are skipped, not treated as errors.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--engines', arg: '<list>', description: 'Comma-separated engine names: duckduckgo, brave, bing, google, serpapi, wikimedia (default: duckduckgo).' },
    { flag: '--source', arg: '<wikimedia>', description: 'Include Wikimedia as a search source. Shorthand for --engines wikimedia.' },
    { flag: '--max, -m', arg: '<n>', description: 'Max merged results (default: 10).' },
    { flag: '--workers, -w', arg: '<n>', description: 'Parallel content-extraction workers (default: 5).' },
    { flag: '--serpapi-engine', arg: '<engine>', description: 'Underlying engine for SerpAPI: google, bing, yahoo, baidu, yandex, etc. (default: google).' },
    { flag: '--no-dedupe', description: 'Keep duplicate URLs across engines instead of deduping (dedupe is on by default).' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier when fetching each result page (default: 3).' },
    { flag: '--no-js-fallback', description: 'Disable automatic Playwright fallback.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/multi_search_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--sources', arg: '<list>', description: 'Also search source plugins (comma-separated, e.g. openalex,arxiv,wikidata,huggingface) in parallel and merge with BM25F+vector re-ranking.' },
    { flag: '--auto-sources', description: 'Let the source-selection bandit pick the best sources for this query type. Overrides --sources.' },
    { flag: '--json', description: 'Output raw JSON to stdout.' },
  ],
  example: 'scout-it multi-search --query "rust vs go performance" --engines duckduckgo,brave --max 15\nscout-it multi-search --query "climate science" --engines duckduckgo,wikimedia --sources openalex,arxiv',
}

export const wikipediaSearchFlags: FlagGroup = {
  id: 'wikipedia-search',
  label: 'wikipedia-search',
  usage: 'scout-it wikipedia-search --query "<text>" [options]',
  intro: 'Search any Wikimedia project via the MediaWiki Action API — all 12 projects: wikipedia, commons, wikivoyage, wiktionary, wikibooks, wikidata, wikiversity, wikiquote, mediawiki, wikisource, wikispecies, wikifunctions. Use --summary / --extract / --sections / --crawl for different data modes.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query or page title (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max results (1-50, default: 10).' },
    { flag: '--project', arg: '<project>', description: 'Wikimedia project to search (default: wikipedia; any of the 12 projects in SITE_MAP).' },
    { flag: '--language, -l', arg: '<code>', description: 'Project language for language-scoped wikis (default: en).' },
    { flag: '--timeout', arg: '<seconds>', description: 'HTTP timeout in seconds (default: 25).' },
    { flag: '--workers, -w', arg: '<n>', description: 'Parallel workers (default: 5).' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/wikimedia_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--json', description: 'Output raw JSON to stdout.' },
    { flag: '--summary', description: 'Fetch a Wikipedia REST summary for the given title.' },
    { flag: '--extract', description: 'Fetch cleaned full-page extract via the Action API.' },
    { flag: '--sections', description: 'Export section-by-section cleaned text.' },
    { flag: '--crawl', description: 'Enable recursive crawl from the search results (with --crawl-depth).' },
    { flag: '--crawl-depth', arg: '<n>', description: 'Crawl depth for --crawl mode (default: 2).' },
    { flag: '--bundle', description: 'Run a broad multi-project topic bundle (searches all 12 projects).' },
    { flag: '--robots', description: 'Check robots.txt allowance before searching.' },
    { flag: '--no-clean', description: 'Disable text cleaning.' },
    { flag: '--rss', description: 'Include MediaWiki RecentChanges RSS feeds in discovery (uses --project as default category).' },
    { flag: '--category, -c', arg: '<project>', description: 'Wikimedia project RSS category to include (repeatable): wikipedia, commons, wiktionary, wikivoyage, etc. Adds recently-changed pages to the candidate pool before ranking.' },
  ],
  example: 'scout-it wikipedia-search --query "machine learning"\nscout-it wikipedia-search --query "Albert Einstein" --project wikipedia --extract\nscout-it wikipedia-search --query "quantum physics" --bundle',
}

export const indexFlags: FlagGroup = {
  id: 'index',
  label: 'index',
  usage: 'scout-it index --query "<text>" [options]',
  intro: 'Fetch, extract, chunk, and embed web-search or news-search results into the persistent LanceDB store at ~/.scout-it/semantic/lancedb/. The corpus then powers `scout-it semantic-search` and survives across runs. Needs: pip install sentence-transformers torch lancedb.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Query to fetch and index (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max results to fetch and index (default: 20).' },
    { flag: '--source', arg: '<web|news>', description: 'Source to fetch from: web or news (default: web).' },
  ],
  example: 'scout-it index --query "transformer architecture" --max 20\nscout-it index --query "AI news" --source news',
}

export const semanticSearchFlags: FlagGroup = {
  id: 'semantic-search',
  label: 'semantic-search',
  usage: 'scout-it semantic-search --query "<text>" [options]',
  intro: 'Search a persistent corpus of previously-indexed documents using hybrid BM25 + dense-vector retrieval. Use `scout-it index` to build the corpus first. Storage: ~/.scout-it/semantic/lancedb/. Model configurable via SCOUT_SEMANTIC_MODEL env var (default: BAAI/bge-m3).',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max results (default: 10).' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/semantic_results.json).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--json', description: 'Output raw JSON to stdout.' },
  ],
  example: 'scout-it semantic-search --query "attention mechanisms" --max 5',
}

export const sourcesFlags: FlagGroup = {
  id: 'sources',
  label: 'sources',
  usage: 'scout-it sources [--json]',
  intro: 'List all source plugins available via the --sources flag on web-search, news-search, image-search, video-search, and multi-search. All sources are free or have free tiers (30+ plugins: openalex, arxiv, crossref, semantic_scholar, huggingface, zenodo, wikidata, gdelt, internet_archive, and more).',
  flags: [
    { flag: '--json', description: 'Output as JSON instead of a formatted table.' },
  ],
  example: 'scout-it sources\nscout-it sources --json',
}
