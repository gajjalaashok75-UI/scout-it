import DocsLayout from '../../components/DocsLayout'
import { SITE } from '../../data/site'
import CopyCommand from '../../components/CopyCommand'

const toc = [
  { id: 'how-it-works', label: 'how it works' },
  { id: 'query-types', label: 'query types' },
  { id: 'features', label: 'key features' },
  { id: 'architecture', label: 'architecture' },
]

export default function DocsHome() {
  return (
    <DocsLayout
      title="scout-it docs — search & extraction toolkit"
      description="Documentation for scout-it: a production-style Python toolkit combining DuckDuckGo search, resilient web extraction, GitHub API mining, and social scraping into structured JSON."
      heading="overview"
      lede="scout-it gives you an end-to-end search pipeline: search, fetch, extract, clean, and structure — all from one CLI or Python import."
      toc={toc}
    >
      <h2 id="how-it-works">how it works</h2>
      <p>Run a search from your terminal and get back more than links. scout-it queries DuckDuckGo (or several engines at once), fetches every result page through a resilient three-tier fallback chain, extracts the main content with multiple extraction strategies, cleans and scores it, and writes the result as structured JSON — ready for a data pipeline, an LLM context window, or a quick grep.</p>
      <p>It's not just search: the same toolkit pulls full repo context from GitHub (commits, diffs, issues, discussions) via the official API, and reads public Telegram, Discord, and Reddit content where a legitimate zero- or low-config path exists.</p>

      <h2 id="query-types">query types</h2>
      <ul>
        <li><strong>web-search</strong> — DuckDuckGo text search plus content extraction and cleaning</li>
        <li><strong>image-search</strong> — DuckDuckGo image search with dimension, color, and license filters</li>
        <li><strong>news-search</strong> — DuckDuckGo news search with full article extraction</li>
        <li><strong>video-search</strong> / <strong>video-extract</strong> — DuckDuckGo video search, plus full YouTube metadata and transcripts</li>
        <li><strong>fetch-url</strong> — direct extraction from a single URL</li>
        <li><strong>multi-search</strong> — the same pipeline, fanned out across several search engines in parallel</li>
      </ul>
      <p>See the <a href="/docs/web-search/">web &amp; news search</a>, <a href="/docs/image-video/">image &amp; video search</a>, and <a href="/docs/fetch-url/">fetch URL</a> guides for the full flag reference on each.</p>

      <h2 id="features">key features</h2>
      <ul>
        <li><strong>Multi-mode CLI</strong> — 22 subcommands across search, GitHub, and social platforms, all sharing one binary</li>
        <li><strong>Resilient fetching</strong> — a shared three-tier fallback chain (requests → Playwright → last-resort request) behind every page fetch</li>
        <li><strong>Zero-result retry</strong> — web, image, news, and video search all retry with progressively relaxed filters if the first attempt comes back empty</li>
        <li><strong>Multi-engine search</strong> — DuckDuckGo needs no setup; Brave, Google, Bing, Yahoo, Baidu, and Yandex plug in via API keys</li>
        <li><strong>GitHub mining without scraping</strong> — official REST + GraphQL, full diffs with structured <code>patch_lines</code>, discussions, code search</li>
        <li><strong>Stored credentials</strong> — an interactive wizard writes secrets once instead of re-exporting env vars every session</li>
        <li><strong>JSON-first output</strong> — with an opt-in <code>--markdown</code> mode and line-length-safe chunking for long text fields</li>
      </ul>

      <h2 id="architecture">architecture</h2>
      <p>Every pipeline follows the same shape: a search or fetch layer discovers URLs or reads a single one, a shared <code>fetch_resilient()</code> chain retrieves page content, a multi-strategy <code>ExtractionEngine</code> (trafilatura, justext, boilerpy3, heuristic fallbacks) pulls the main text, and <code>main_content_cleaner</code> structures and scores it before anything is written to disk. See <a href="/docs/fetch-url/">fetch URL &amp; retry chain</a> for the fallback tiers in detail.</p>

      <div style={{ marginTop: 32, padding: 24, background: 'var(--surface-card)', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}>
        <p style={{ fontWeight: 500, marginBottom: 12 }}>install scout-it</p>
        <CopyCommand command={SITE.installCommand} />
      </div>
    </DocsLayout>
  )
}
