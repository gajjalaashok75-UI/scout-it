// Seeded from scout_it/engines.py ENGINE_REGISTRY and the actual env var checks in each engine class.

export interface Engine {
  id: string
  name: string
  setup: string
  notes: string
}

export const engines: Engine[] = [
  {
    id: 'duckduckgo',
    name: 'DuckDuckGo',
    setup: 'works out of the box',
    notes: 'No API key needed. Backs web-search, image-search, news-search, and video-search directly, and is the default engine for multi-search.',
  },
  {
    id: 'brave',
    name: 'Brave Search',
    setup: 'BRAVE_API_KEY',
    notes: 'Free tier (2k queries/mo). Add to multi-search with --engines brave.',
  },
  {
    id: 'bing',
    name: 'Bing Web Search (Azure)',
    setup: 'BING_API_KEY',
    notes: 'Azure Cognitive Services "Bing Search v7" resource. Add to multi-search with --engines bing.',
  },
  {
    id: 'google',
    name: 'Google Custom Search',
    setup: 'GOOGLE_API_KEY + GOOGLE_CSE_ID',
    notes: 'Google Programmable Search Engine (free tier: 100 queries/day). Add to multi-search with --engines google.',
  },
  {
    id: 'serpapi',
    name: 'SerpAPI',
    setup: 'SERPAPI_KEY',
    notes: 'Proxies real Google/Bing/Yahoo/Baidu/Yandex results. Free tier: 100 searches/month. Use --serpapi-engine to pick the underlying engine (default: google).',
  },
  {
    id: 'wikimedia',
    name: 'Wikimedia',
    setup: 'works out of the box',
    notes: 'Searches Wikipedia and the other 11 Wikimedia projects via the MediaWiki Action API. Add to multi-search with --engines wikimedia, or use the dedicated wikipedia-search command.',
  },
]
