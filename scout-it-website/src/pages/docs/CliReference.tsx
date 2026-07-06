import DocsLayout from '../../components/DocsLayout'
import { githubCommands } from '../../data/githubCommands'
import { socialCommands } from '../../data/socialCommands'
import { configCommands } from '../../data/configuration'

const toc = [
  { id: 'usage', label: 'usage' },
  { id: 'search', label: 'search commands' },
  { id: 'github', label: 'github commands' },
  { id: 'social', label: 'social commands' },
  { id: 'utility', label: 'utility commands' },
]

const searchCommands = [
  { usage: 'web-search --query <text>', href: '/docs/web-search/', description: 'DuckDuckGo text search plus content extraction.' },
  { usage: 'news-search --query <text>', href: '/docs/web-search/', description: 'DuckDuckGo news search with article extraction.' },
  { usage: 'image-search --query <text>', href: '/docs/image-video/', description: 'DuckDuckGo image search with dimension/license filters.' },
  { usage: 'video-search --query <text>', href: '/docs/image-video/', description: 'DuckDuckGo video search.' },
  { usage: 'video-extract --url <youtube-url>', href: '/docs/image-video/', description: 'Full YouTube metadata and transcripts.' },
  { usage: 'fetch-url --url <url>', href: '/docs/fetch-url/', description: 'Direct extraction from a single URL.' },
  { usage: 'multi-search --query <text> --engines ...', href: '/docs/multi-engine/', description: 'Search across several engines in parallel.' },
  { usage: 'list-engines', href: '/docs/multi-engine/', description: 'Show which search engines are configured.' },
]

export default function CliReference() {
  return (
    <DocsLayout
      title="scout-it CLI reference — all 22 commands"
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
            {configCommands.map(c => (
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
