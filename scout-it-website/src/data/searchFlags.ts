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
    { flag: '--max, -m', arg: '<n>', description: 'Number of results to fetch. Default: 10.' },
    { flag: '--workers', arg: '<n>', description: 'Parallel content-extraction workers. Default: 8.' },
    { flag: '--region', arg: '<region>', description: 'DDGS region code, e.g. us-en. Default: us-en.' },
    { flag: '--safesearch', arg: '<level>', description: 'on | moderate | off. Default: moderate.' },
    { flag: '--timelimit', arg: '<range>', description: 'Restrict by recency: d | w | m | y.' },
    { flag: '--backend', arg: '<backend>', description: 'DDGS backend selection.' },
    { flag: '--retry-on-zero / --no-retry-on-zero', description: 'Retry the DDGS search itself on 0 results, progressively relaxing filters. On by default.' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Zero-result retry attempts. Default: 2.' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Backoff between zero-result retries. Default: 1.0.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Retry attempts per tier (requests, then Playwright) when fetching each result page. Default: 3.' },
    { flag: '--no-js-fallback', description: 'Disable the automatic Playwright fallback for blocked/failed page fetches.' },
    { flag: '--markdown', description: 'Save a readable .md file instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output path. Defaults under .scout-it/.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
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
    { flag: '--max, -m', arg: '<n>', description: 'Number of articles. Default: 10.' },
    { flag: '--region', arg: '<region>', description: 'DDGS region code.' },
    { flag: '--safesearch', arg: '<level>', description: 'on | moderate | off.' },
    { flag: '--timelimit', arg: '<range>', description: 'd | w | m | y.' },
    { flag: '--retry-on-zero / --no-retry-on-zero', description: 'Zero-result retry, same behavior as web-search. On by default.' },
    { flag: '--retry-attempts', arg: '<n>', description: 'Default: 2.' },
    { flag: '--retry-backoff', arg: '<seconds>', description: 'Default: 1.0.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Resilient-fetch retries per tier for each article\u2019s full text. Default: 3.' },
    { flag: '--no-js-fallback', description: 'Disable the Playwright fallback tier.' },
    { flag: '--markdown', description: 'Save a readable .md file instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output path.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
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
    { flag: '--max, -m', arg: '<n>', description: 'Number of images. Default: 10.' },
    { flag: '--min-width / --max-width', arg: '<px>', description: 'Width bounds. Inclusive when set.' },
    { flag: '--min-height / --max-height', arg: '<px>', description: 'Height bounds. Inclusive when set.' },
    { flag: '--color', arg: '<color>', description: 'DDGS color filter.' },
    { flag: '--type-image', arg: '<type>', description: 'photo, clipart, gif, transparent, line.' },
    { flag: '--layout', arg: '<layout>', description: 'Square, Tall, Wide.' },
    { flag: '--license-images', arg: '<license>', description: 'DDGS image license filter.' },
    { flag: '--retry-on-zero / --no-retry-on-zero', description: 'Zero-result retry tuning.' },
    { flag: '--retry-attempts / --retry-backoff', description: 'Retry tuning knobs.' },
    { flag: '--markdown', description: 'Save a readable .md file instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output path.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
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
    { flag: '--max, -m', arg: '<n>', description: 'Number of videos. Default: 10.' },
    { flag: '--region / --safesearch / --timelimit', description: 'Standard DDGS search parameters.' },
    { flag: '--resolution', arg: '<res>', description: 'DDGS resolution filter.' },
    { flag: '--duration', arg: '<duration>', description: 'DDGS duration filter.' },
    { flag: '--license-videos', arg: '<license>', description: 'DDGS video license filter.' },
    { flag: '--retry-on-zero / --no-retry-on-zero', description: 'Zero-result retry (previously video-search had none at all).' },
    { flag: '--retry-attempts / --retry-backoff', description: 'Retry tuning knobs.' },
    { flag: '--markdown', description: 'Save a readable .md file instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output path.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
  ],
  example: 'scout-it video-search --query "python programming tutorial" --max 5',
}

export const videoExtractFlags: FlagGroup = {
  id: 'video-extract',
  label: 'video-extract',
  usage: 'scout-it video-extract --url "<youtube-url>" [options]',
  intro: 'Full metadata (title, channel, view/like counts, description, upload date) and, where available, subtitles/transcript for a YouTube video. Only YouTube is supported today; other platforms return a clear unsupported_platform error.',
  flags: [
    { flag: '--url', arg: '<url>', description: 'YouTube video URL: youtube.com/watch?v=... or youtu.be/... (required).' },
    { flag: '--subtitle-lang', arg: '<code>', description: 'Preferred subtitle language code. Default: en.' },
    { flag: '--segments', description: 'Include timestamped subtitle segments in the output.' },
    { flag: '--max-fetch-retries', arg: '<n>', description: 'Resilient-fetch retries for the underlying page fetch. Default: 3.' },
    { flag: '--no-js-fallback', description: 'Disable the Playwright fallback tier.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
  ],
  example: 'scout-it video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments',
}

export const fetchUrlFlags: FlagGroup = {
  id: 'fetch-url',
  label: 'fetch-url',
  usage: 'scout-it fetch-url --url "https://example.com" [options]',
  intro: 'Direct extraction from a single URL, through the same three-tier resilient-fetch chain used everywhere else.',
  flags: [
    { flag: '--url, -u', arg: '<url>', description: 'URL to fetch and extract (required).' },
    { flag: '--timeout', arg: '<seconds>', description: 'Fetch timeout per attempt/tier. Default: 25.' },
    { flag: '--max-chars', arg: '<n>', description: 'Truncate extracted content to N characters (mutually exclusive with --max-size).' },
    { flag: '--max-size', arg: '<size>', description: 'Cap the raw response size, e.g. 5mb, 500kb (mutually exclusive with --max-chars).' },
    { flag: '--raw-html', description: 'Return prettified raw HTML instead of extracted main content.' },
    { flag: '--js-render', description: 'Skip straight to Playwright rendering instead of trying requests first.' },
    { flag: '--no-js-fallback', description: 'Disable the automatic Playwright fallback.' },
    { flag: '--max-retries', arg: '<n>', description: 'Retry attempts per tier. Default: 3.' },
    { flag: '--markdown', description: 'Save a readable .md file instead of JSON.' },
    { flag: '--out, -o', arg: '<path>', description: 'Output path.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
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
    { flag: '--engines', arg: '<list>', description: 'Comma-separated engine list, e.g. duckduckgo,brave,google.' },
    { flag: '--max, -m', arg: '<n>', description: 'Number of results.' },
    { flag: '--workers, -w', arg: '<n>', description: 'Parallel extraction workers.' },
    { flag: '--serpapi-engine', arg: '<engine>', description: 'google | bing | yahoo | baidu | yandex | ... when serpapi is in --engines.' },
    { flag: '--no-dedupe', description: 'Disable URL-based deduplication across engines.' },
    { flag: '--max-fetch-retries / --no-js-fallback', description: 'Same resilient-fetch controls as web-search.' },
    { flag: '--json', description: 'Print raw JSON to stdout.' },
  ],
  example: 'scout-it multi-search --query "rust vs go performance" --engines duckduckgo,brave --max 15',
}
