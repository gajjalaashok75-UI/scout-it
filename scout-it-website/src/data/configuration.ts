// Seeded from scout_it/config.py and the README's config/credentials sections.

export interface EnvVar {
  name: string
  description: string
}

export const envVars: EnvVar[] = [
  { name: 'GITHUB_TOKEN', description: 'Personal access token for GitHub extraction. Unauthenticated works at 60 req/hour; with a token, 5,000/hour. Required (no exceptions) for github-discussions and github-search-code.' },
  { name: 'BRAVE_API_KEY', description: 'Enables the brave engine in multi-search.' },
  { name: 'BING_API_KEY', description: 'Enables the bing engine in multi-search via Azure Bing Search API.' },
  { name: 'GOOGLE_API_KEY', description: 'Google API key for Custom Search JSON API — paired with GOOGLE_CSE_ID for the google engine in multi-search.' },
  { name: 'GOOGLE_CSE_ID', description: 'Google Programmable Search Engine ID — paired with GOOGLE_API_KEY.' },
  { name: 'SERPAPI_KEY', description: 'Enables the serpapi engine in multi-search, which proxies real Google/Bing/Yahoo/Baidu/Yandex results.' },
  { name: 'TAVILY_API_KEY', description: 'Enables the tavily API search provider on web/news/image/multi-search via --source tavily. AI-optimized search with answer + content chunks.' },
  { name: 'EXA_API_KEY', description: 'Enables the exa API search provider on web/news/multi-search via --source exa. Neural web/news search with highlights (no image-search support).' },
  { name: 'FIRECRAWL_API_KEY', description: 'Enables the firecrawl API search provider on web/news/image/multi-search via --source firecrawl. Web/news/image search with built-in page scraping.' },
  { name: 'DISCORD_BOT_TOKEN', description: 'Bot token for discord-channel via social-search --platform discord. The bot must already be a member of the target server.' },
  { name: 'REDDIT_COOKIE', description: 'Optional session cookie that improves reddit reliability in social-search --platform reddit against anonymous-request blocking.' },
  { name: 'INSTAGRAM_SESSION_ID', description: 'Enables direct profile scraping for social-search --platform instagram --profile NAME. Without it, instagram falls back to a DDGS query search.' },

  { name: 'PROXY_LIST', description: 'Comma-separated proxy URLs (e.g. http://user:pass@host:port) for the auto-rotating proxy pool.' },
]

export interface ConfigCommand {
  usage: string
  description: string
}

export const configCommands: ConfigCommand[] = [
  { usage: 'scout-it config', description: 'Interactive wizard \u2014 press Enter to skip any key you don\u2019t have.' },
  { usage: 'scout-it config --show', description: 'Check what\u2019s configured. No secret values are ever printed.' },
  { usage: 'scout-it config --clear GITHUB_TOKEN', description: 'Remove one stored key.' },
  { usage: 'scout-it config --clear-all', description: 'Remove every stored credential.' },
]

export interface OutputSetting {
  key: string
  description: string
}

export const outputSettings: OutputSetting[] = [
  { key: '--out, -o <path>', description: 'Explicit output path, always honored exactly as given \u2014 overrides the per-command default under .scout-it/.' },
  { key: '--json', description: 'Print raw JSON straight to stdout instead of writing a file.' },
  { key: '--markdown', description: 'Save a readable .md file instead of JSON (tables for uniform records, fenced code blocks for file/diff content). Rejected if combined with an explicit --out ....json.' },
]
