import { Link } from 'react-router-dom'
import { SITE } from '../data/site'

const columns = [
  {
    title: 'get started',
    links: [
      { href: '/docs/', label: 'overview' },
      { href: '/docs/installation/', label: 'installation' },
      { href: '/docs/quickstart/', label: 'quickstart' },
      { href: '/docs/multi-engine/', label: 'multi-engine search' },
    ],
  },
  {
    title: 'search & extraction',
    links: [
      { href: '/docs/web-search/', label: 'web & news search' },
      { href: '/docs/image-video/', label: 'image & video search' },
      { href: '/docs/fetch-url/', label: 'fetch url & retry chain' },
      { href: '/docs/github/', label: 'github extraction' },
      { href: '/docs/social/', label: 'social platforms' },
    ],
  },
  {
    title: 'reference',
    links: [
      { href: '/docs/cli-reference/', label: 'cli reference' },
      { href: '/docs/configuration/', label: 'configuration' },
      { href: '/docs/output/', label: 'output & json shapes' },
      { href: '/docs/api/', label: 'programmatic api' },
    ],
  },
  {
    title: 'project',
    links: [
      { href: SITE.github, label: 'github' },
      { href: SITE.pypiUrl, label: 'pypi' },
      { href: `${SITE.github}/blob/main/LICENSE`, label: 'license' },
      { href: `${SITE.github}/issues`, label: 'issues' },
    ],
  },
]

function isExternal(href: string) {
  return href.startsWith('http')
}

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="container">
        <div className="footer-grid">
          {columns.map(col => (
            <div className="footer-col" key={col.title}>
              <h4>{col.title}</h4>
              <ul>
                {col.links.map(l =>
                  isExternal(l.href) ? (
                    <li key={l.label}>
                      <a href={l.href} rel="noopener">{l.label}</a>
                    </li>
                  ) : (
                    <li key={l.label}>
                      <Link to={l.href}>{l.label}</Link>
                    </li>
                  )
                )}
              </ul>
            </div>
          ))}
        </div>
        <div className="footer-bottom">
          <span className="brand">
            <img src="/scout-it-mark.svg" alt="" width="18" height="18" />
            <span>scout-it</span>
            <span className="ver">v{SITE.version}</span>
          </span>
          <span className="sep">&middot;</span>
          <span>search &amp; extraction toolkit, built by <a href={SITE.github} rel="noopener">Ashok-gakr</a></span>
          <span className="sep">&middot;</span>
          <span>MIT licensed. structured JSON out.</span>
        </div>
      </div>
    </footer>
  )
}
