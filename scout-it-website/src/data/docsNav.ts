export interface DocsNavItem {
  title: string
  href: string
}

export interface DocsNavGroup {
  group: string
  items: DocsNavItem[]
}

export const docsNav: DocsNavGroup[] = [
  {
    group: 'getting started',
    items: [
      { title: 'Overview', href: '/docs/' },
      { title: 'Installation', href: '/docs/installation/' },
      { title: 'Quickstart', href: '/docs/quickstart/' },
    ],
  },
  {
    group: 'search & extraction',
    items: [
      { title: 'Web & news search', href: '/docs/web-search/' },
      { title: 'Image & video search', href: '/docs/image-video/' },
      { title: 'Fetch URL & retry chain', href: '/docs/fetch-url/' },
      { title: 'Multi-engine search', href: '/docs/multi-engine/' },
    ],
  },
  {
    group: 'integrations',
    items: [
      { title: 'GitHub extraction', href: '/docs/github/' },
      { title: 'Social platforms', href: '/docs/social/' },
    ],
  },
  {
    group: 'reference',
    items: [
      { title: 'CLI reference', href: '/docs/cli-reference/' },
      { title: 'Configuration & credentials', href: '/docs/configuration/' },
      { title: 'Output & JSON shapes', href: '/docs/output/' },
      { title: 'Programmatic API', href: '/docs/api/' },
    ],
  },
]

export const docsPages: DocsNavItem[] = docsNav.flatMap(g => g.items)

export function pagerFor(href: string): { prev?: DocsNavItem; next?: DocsNavItem } {
  const i = docsPages.findIndex(p => p.href === href)
  if (i === -1) return {}
  return {
    prev: i > 0 ? docsPages[i - 1] : undefined,
    next: i < docsPages.length - 1 ? docsPages[i + 1] : undefined,
  }
}
