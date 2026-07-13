// Seeded from scout_it/cli.py argparse definitions and README.md.

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
  intro: 'DuckDuckGo text search plus full content extraction and cleaning for every result.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max results (1-100).' },
    { flag: '--workers, -w', arg: '<n>', description: 'Parallel workers for content extraction.' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off.' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d (day), w (week), m (month), y (year).' },
    { flag: '--backend', arg: '<backend>', description: 'DDGS backend: auto, html, lite.' },
    { flag: '--no-retry-on-zero', description: 'Disable retries when 0 successful extractions (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts when 0 successful extractions.' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier (requests, then Playwright) when fetching each result page.' },
    { flag: '--no-js-fallback', description: 'Disable the automatic Playwright fallback for blocked/failed page fetches.' },
    { flag: '--enable-alternate-source', description: 'If every fetch tier fails, try AMP/mobile/print URL variants and a Wayback Machine snapshot before giving up (extra requests, opt-in).' },
    { flag: '--no-dns-fallback', description: 'Disable the DNS-over-HTTPS retry on DNS-looking errors (on by default).' },
    { flag: '--tls-impersonate', description: 'Insert a browser-accurate TLS/JA3 fingerprint tier between requests and Playwright (needs: pip install scout-it[tls-impersonate]).' },
    { flag: '--persistent-profile', description: 'Use a persistent Playwright profile (cookies/session survive across runs) instead of a throwaway context for the JS-render tier.' },
    { flag: '--profile-name', arg: '<name>', description: 'Persistent profile name (only with --persistent-profile).' },
    { flag: '--use-bandit', description: 'Once a domain has enough recorded history, skip straight to whichever fetch tier has worked best for it instead of always starting with plain requests (see scout-it stats).' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/struct_format_results.json).' },
  ],
  example: 'scout-it web-search --query "machine learning" --max 5\nscout-it web-search --query "site behind cloudflare" --max-fetch-retries 4',
}

export const newsSearchFlags: FlagGroup = {
  id: 'news-search',
  label: 'news-search',
  usage: 'scout-it news-search --query "<text>" [options]',
  intro: 'DuckDuckGo news search with the same zero-result retry parity and resilient article-text fetching as web-search.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max news items (1-50).' },
    { flag: '--workers', arg: '<n>', description: 'Parallel workers for content extraction.' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off.' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d, w, m, y.' },
    { flag: '--no-retry-on-zero', description: 'Disable retries on zero results (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts on zero results.' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier (requests, then Playwright) when fetching each article page.' },
    { flag: '--no-js-fallback', description: 'Disable automatic Playwright fallback when an article fetch fails or looks blocked.' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/news_search_results.json).' },
  ],
  example: 'scout-it news-search --query "artificial intelligence" --max 5',
}

export const imageSearchFlags: FlagGroup = {
  id: 'image-search',
  label: 'image-search',
  usage: 'scout-it image-search --query "<text>" [options]',
  intro: 'DuckDuckGo image search with rich dimension, color, and license filters.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max images (1-50).' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off.' },
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
    { flag: '--download, -d', description: 'Download images to disk.' },
    { flag: '--download-dir', arg: '<path>', description: 'Download directory (default: .scout-it/downloaded_images).' },
    { flag: '--no-retry-on-zero', description: 'Disable retries when 0 valid images are found (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts when 0 valid images are found.' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries.' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/image_search_results.json).' },
  ],
  example: 'scout-it image-search --query "landscape" --max 10 --min-width 1024 --min-height 768',
}

export const videoSearchFlags: FlagGroup = {
  id: 'video-search',
  label: 'video-search',
  usage: 'scout-it video-search --query "<text>" [options]',
  intro: 'DuckDuckGo video search with duration, resolution, and license filters, and the same zero-result retry parity as every other search mode.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--max, -m', arg: '<n>', description: 'Max videos (1-50).' },
    { flag: '--region', arg: '<region>', description: 'DuckDuckGo region (example: us-en, wt-wt).' },
    { flag: '--safesearch', arg: '<level>', description: 'Safe search mode: on, moderate, off.' },
    { flag: '--timelimit', arg: '<range>', description: 'DuckDuckGo time limit: d, w, m, y.' },
    { flag: '--resolution', arg: '<res>', description: 'Video resolution filter: high, standard.' },
    { flag: '--duration', arg: '<duration>', description: 'Video duration filter: short, medium, long.' },
    { flag: '--license-videos', arg: '<license>', description: 'Video license filter.' },
    { flag: '--no-retry-on-zero', description: 'Disable retries when 0 results are found (retries are on by default).' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Retry attempts when 0 results are found.' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff seconds between retries.' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/video_search_results.json).' },
  ],
  example: 'scout-it video-search --query "python programming tutorial" --max 5',
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
  intro: 'Queries several search engines in parallel, merges and dedupes by URL, then runs the same content-extraction pipeline as web-search.',
  flags: [
    { flag: '--query, -q', arg: '<text>', description: 'Search query (required).' },
    { flag: '--engines', arg: '<list>', description: 'Comma-separated engine names: duckduckgo, brave, bing, google, serpapi.' },
    { flag: '--max, -m', arg: '<n>', description: 'Max merged results.' },
    { flag: '--workers, -w', arg: '<n>', description: 'Parallel content-extraction workers.' },
    { flag: '--serpapi-engine', arg: '<engine>', description: 'Underlying engine for SerpAPI: google, bing, yahoo, baidu, yandex, etc.' },
    { flag: '--no-dedupe', description: 'Keep duplicate URLs across engines instead of deduping.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per fetch tier when fetching each result page.' },
    { flag: '--no-js-fallback', description: 'Disable automatic Playwright fallback.' },
    { flag: '--markdown', description: 'Save results as Markdown (.md) instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output file (default: .scout-it/multi_search_results.json).' },
    { flag: '--json', description: 'Output raw JSON to stdout.' },
  ],
  example: 'scout-it multi-search --query "rust vs go performance" --engines duckduckgo,brave --max 15',
}
