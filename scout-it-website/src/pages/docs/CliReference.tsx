import DocsLayout from '../../components/DocsLayout'
import { githubCommands } from '../../data/githubCommands'
import { socialCommands } from '../../data/socialCommands'
import { configCommands } from '../../data/configuration'

const toc = [
  { id: 'usage', label: 'usage' },
  { id: 'search', label: 'search commands' },
  { id: 'discovery', label: 'discovery streams' },
  { id: 'github', label: 'github commands' },
  { id: 'social', label: 'social commands' },
  { id: 'utility', label: 'utility commands' },
]

const searchCommands = [
  { usage: 'web-search --query <text>', href: '/docs/web-search/', description: 'DuckDuckGo text search plus content extraction.' },
  { usage: 'news-search --query <text>', href: '/docs/web-search/', description: 'DuckDuckGo news search with article extraction.' },
  { usage: 'image-search --query <text>', href: '/docs/image-video/', description: 'DuckDuckGo image search with dimension/license filters.' },
  { usage: 'video-search --query <text>', href: '/docs/image-video/', description: 'DuckDuckGo video search (YouTube fallback).' },
  { usage: 'video-extract --url <youtube-url>', href: '/docs/image-video/', description: 'Full YouTube metadata and transcripts.' },
  { usage: 'fetch-url --url <url>', href: '/docs/fetch-url/', description: 'Direct extraction from a single URL.' },
  { usage: 'multi-search --query <text> --engines ...', href: '/docs/multi-engine/', description: 'Search across several engines in parallel.' },
  { usage: 'wikipedia-search --query <text>', href: '/docs/wikipedia/', description: 'Search any Wikimedia project (12 projects) via the MediaWiki Action API.' },
  { usage: 'social-search --query <text>', href: '/docs/social/', description: 'Unified search across Telegram, Discord, Reddit, and Instagram.' },
  { usage: 'list-engines', href: '/docs/multi-engine/', description: 'Show which search engines are configured.' },
  { usage: 'sources [--json]', href: '/docs/wikipedia/', description: 'List the 31 free academic/dataset/knowledge source plugins (for --sources).' },
  { usage: 'index --query <text>', href: '/docs/wikipedia/', description: 'Index results into the persistent semantic store (LanceDB).' },
  { usage: 'semantic-search --query <text>', href: '/docs/wikipedia/', description: 'Hybrid BM25+vector search over an indexed corpus.' },
]

const discoveryCommands = [
  { usage: '--source wikimedia', href: '/docs/web-search/', description: 'Wikimedia as a parallel discovery stream on web/news/image/multi-search.' },
  { usage: '--source google-news', href: '/docs/web-search/', description: 'Google News RSS as a parallel discovery stream on news-search.' },
  { usage: '--source tavily,exa,firecrawl', href: '/docs/api-sources/', description: 'API search providers (Tavily, Exa, Firecrawl) as parallel discovery streams on web/news/image/multi-search. Need API keys via scout-it config.' },
  { usage: '--sources openalex,arxiv,...', href: '/docs/wikipedia/', description: 'Free source plugins merged with BM25F+vector re-ranking (31 plugins). Use scout-it sources to list them.' },
  { usage: '--auto-sources', href: '/docs/web-search/', description: 'Let the source-selection bandit pick the best --sources for the query type.' },
]

const utilityCommands = [
  ...configCommands,
  { usage: 'scout-it stats [--domain] [--export] [--reset <domain>] [--reset-all] [--sources]', description: 'Show per-domain fetch-strategy statistics from the local bandit cache. --sources shows source-selection bandit stats.' },
  { usage: 'scout-it doctor', description: 'Run a self-check: Playwright availability, proxy config, cache health, credentials, DNS/connectivity.' },
]

export default function CliReference() {
  return (
    <DocsLayout
      title="scout-it CLI reference — all commands"
      description="Complete command reference for scout-it: every search, GitHub, social, and utility subcommand in one place, grouped by category with links to full flag documentation."
      heading="CLI reference"
      lede="Every scout-it subcommand at a glance. Each links to its full flag reference and examples."
      toc={toc}
    >
      <h2 id="usage">usage</h2>
      <pre><code>{`scout-it <command> [options]

# global help
scout-it --help

# help for one command
scout-it web-search --help`}</code></pre>

      <h2 id="search">search commands</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">command</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {searchCommands.map(c => (
              <tr key={c.usage}>
                <td><code>{c.usage}</code></td>
                <td>{c.description} <a href={c.href}>full reference →</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="discovery">discovery streams</h2>
      <p>Two flags add extra results to the search commands. <code>--source</code> (singular) runs parallel discovery streams alongside DuckDuckGo (Wikimedia, Google News RSS, and the API providers). <code>--sources</code> (plural) runs the free source plugins through a BM25F+vector re-ranking pipeline. See <a href="/docs/api-sources/">API search sources</a> for the full Tavily/Exa/Firecrawl reference.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {discoveryCommands.map(c => (
              <tr key={c.usage}>
                <td><code>{c.usage}</code></td>
                <td>{c.description} <a href={c.href}>reference →</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="github">github commands</h2>
      <p>See <a href="/docs/github/">GitHub extraction</a> for authentication requirements and full examples.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">command</th>
              <th scope="col">what it does</th>
            </tr>
          </thead>
          <tbody>
            {githubCommands.map(c => (
              <tr key={c.usage}>
                <td><code>{c.usage.split(' ')[0]}</code></td>
                <td>{c.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="social">social commands</h2>
      <p>See <a href="/docs/social/">social platforms</a> for tiers and setup requirements.</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">command</th>
              <th scope="col">tier</th>
              <th scope="col">needs</th>
            </tr>
          </thead>
          <tbody>
            {socialCommands.map(c => (
              <tr key={c.usage}>
                <td><code>{c.usage}</code></td>
                <td>{c.tier}</td>
                <td>{c.needs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="utility">utility commands</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">command</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {utilityCommands.map(c => (
              <tr key={c.usage}>
                <td><code>{c.usage}</code></td>
                <td>{c.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>See <a href="/docs/configuration/">configuration &amp; credentials</a> for the full picture, including environment variables and precedence rules.</p>
    </DocsLayout>
  )
}
