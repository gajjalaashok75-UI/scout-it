// Seeded from scout_it/engines.py and the README's multi-search / list-engines section.

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
    notes: 'Free tier available. Add to multi-search with --engines brave.',
  },
  {
    id: 'google',
    name: 'Google (via SerpApi)',
    setup: 'SERPAPI_API_KEY',
    notes: 'Routed through SerpApi. Use --serpapi-engine google with --engines serpapi.',
  },
  {
    id: 'bing',
    name: 'Bing (via SerpApi)',
    setup: 'SERPAPI_API_KEY',
    notes: '--serpapi-engine bing with --engines serpapi.',
  },
  {
    id: 'yahoo',
    name: 'Yahoo (via SerpApi)',
    setup: 'SERPAPI_API_KEY',
    notes: '--serpapi-engine yahoo with --engines serpapi.',
  },
  {
    id: 'baidu',
    name: 'Baidu (via SerpApi)',
    setup: 'SERPAPI_API_KEY',
    notes: '--serpapi-engine baidu with --engines serpapi.',
  },
  {
    id: 'yandex',
    name: 'Yandex (via SerpApi)',
    setup: 'SERPAPI_API_KEY',
    notes: '--serpapi-engine yandex with --engines serpapi.',
  },
]
