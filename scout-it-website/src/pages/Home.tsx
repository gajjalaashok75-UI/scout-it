import { useRef } from 'react'
import { Link } from 'react-router-dom'
import SEO from '../components/SEO'
import CopyCommand from '../components/CopyCommand'
import Terminal, { type TerminalLine } from '../components/Terminal'
import { SITE } from '../data/site'
import { useScrollReveal } from '../lib/useScrollReveal'
import { useMagnetic } from '../lib/useMagnetic'
import { useCardGlow } from '../lib/useCardGlow'

const features = [
  {
    title: 'five search modes, one CLI',
    body: 'web, image, news, video, and single-URL fetch — all through DuckDuckGo, all producing clean structured JSON.',
    href: '/docs/web-search/',
    link: 'web & news search',
  },
  {
    title: 'a three-tier fetch chain',
    body: 'requests → headless Playwright → last-resort basic request. every result records which tier actually won.',
    href: '/docs/fetch-url/',
    link: 'fetch url & retry chain',
  },
  {
    title: 'search across engines at once',
    body: 'duckduckgo needs nothing; brave, google, bing, yahoo, baidu, and yandex plug in with a key. merged, deduped, extracted.',
    href: '/docs/multi-engine/',
    link: 'multi-engine search',
  },
  {
    title: 'mine GitHub without scraping',
    body: 'repos, commits with full diffs, PRs, issues, discussions, code search — official REST + GraphQL, structured patch_lines included.',
    href: '/docs/github/',
    link: 'github extraction',
  },
  {
    title: 'credentials, stored once',
    body: 'an interactive wizard writes to ~/.data-scout/credentials.json so you stop exporting env vars every session.',
    href: '/docs/configuration/',
    link: 'configuration',
  },
  {
    title: 'JSON-first, markdown when you want it',
    body: 'structured output by default, or add --markdown for a readable file. long strings chunk cleanly instead of one giant line.',
    href: '/docs/output/',
    link: 'output & JSON shapes',
  },
]

const engineNames = [
  'DuckDuckGo', 'Brave', 'Google', 'Bing', 'Yahoo', 'Baidu', 'Yandex',
]

const terminalLines: TerminalLine[] = [
  { text: '# search, extract, and clean in one shot', variant: 'dim', break: true },
  { text: 'scout-it web-search -q "rust vs go" -m 5', prompt: '$', break: true },
  { text: 'querying duckduckgo…', prompt: '○' },
  { text: 'extracting 5 pages (8 workers)…', prompt: '○' },
  { text: 'done — results.json (4 trafilatura, 1 playwright)', prompt: '✔', break: true },
  { text: '# then mine a repo for context', variant: 'dim', break: true },
  { text: 'scout-it github-repo --repo psf/requests', prompt: '>' },
  { text: '  branches, contributors, releases…', variant: 'green' },
]

const jsonLd = [
  {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'scout-it',
    applicationCategory: 'DeveloperApplication',
    operatingSystem: 'macOS, Linux, Windows',
    description: SITE.description,
    url: SITE.url,
    author: { '@type': 'Person', name: 'Ashok-gakr', url: SITE.github },
  },
]

export default function Home() {
  const pageRef = useRef<HTMLDivElement>(null)
  const cardGridRef = useRef<HTMLDivElement>(null)
  const ghostCtaRef = useRef<HTMLAnchorElement>(null)

  useScrollReveal(pageRef)
  useCardGlow(cardGridRef)
  useMagnetic(ghostCtaRef)

  return (
    <div ref={pageRef}>
      <SEO title={SITE.title} description={SITE.description} jsonLd={jsonLd} />

      <section className="hero-band grid-bg">
        <div className="mesh-blobs" aria-hidden="true">
          <span className="mesh-blob mesh-blob--a" />
          <span className="mesh-blob mesh-blob--b" />
        </div>
        <div className="container">
          <div className="hero-grid">
            <div className="hero-content fade-up">
              <span className="eyebrow">
                <span className="spark" aria-hidden="true">✦</span>
                open source · MIT
                <span className="spark" aria-hidden="true">✦</span>
              </span>
              <h1 className="text-hero">search everything,<br /><span className="text-gradient">structure everything.</span></h1>
              <p>scout-it is a production-style Python toolkit that combines web, image, news, and video search with resilient content extraction, GitHub mining, and social scraping — all landing as clean, structured JSON.</p>
              <div className="hero-actions">
                <CopyCommand command={SITE.installCommand} />
                <Link to="/docs/" className="button button-ghost magnetic" ref={ghostCtaRef}>read the docs →</Link>
              </div>
              <div className="hero-foot fade-up fade-up-3">
                <span>python 3.9+ · macOS / linux / windows</span>
                <span className="sep" style={{ margin: '0 8px', color: 'var(--muted-soft)' }}>·</span>
                <span>MIT</span>
              </div>
            </div>
            <div className="fade-up fade-up-2">
              <Terminal lines={terminalLines} title="~/your-project" />
            </div>
          </div>
        </div>
      </section>

      <section className="section section-tint">
        <div className="container">
          <h2 className="text-heading" style={{ marginBottom: 48, textAlign: 'center' }} data-reveal>search across every major engine</h2>
          <ul className="provider-strip" data-reveal>
            {engineNames.map(name => (
              <li key={name}>{name}</li>
            ))}
          </ul>
          <p className="provider-foot" style={{ marginTop: 24, textAlign: 'center' }} data-reveal>
            <Link to="/docs/multi-engine/">see multi-engine search →</Link>
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="card-grid" ref={cardGridRef}>
            {features.map((f, i) => (
              <Link to={f.href} key={i} className="card" data-reveal>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
                <div className="card-foot">
                  <span>{f.link} →</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-tint">
        <div className="container" style={{ textAlign: 'center' }}>
          <div className="callout-card" data-reveal>
            <h2>one install, five search modes, twenty-two commands</h2>
            <p>no sign-up required. structured JSON from the first run.</p>
            <CopyCommand command={SITE.installCommand} />
          </div>
        </div>
      </section>
    </div>
  )
}
