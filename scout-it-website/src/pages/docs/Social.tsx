import DocsLayout from '../../components/DocsLayout'
import { socialCommands, unsupportedPlatforms } from '../../data/socialCommands'

const toc = [
  { id: 'overview', label: 'overview' },
  { id: 'commands', label: 'commands' },
  { id: 'examples', label: 'examples' },
  { id: 'not-supported', label: "what's not supported" },
]

export default function Social() {
  return (
    <DocsLayout
      title="scout-it social platforms — Telegram, Discord, Reddit, Instagram"
      description="Read public Telegram channels, Discord servers (with a bot token), Reddit, and Instagram with scout-it's unified social-search command, and see which platforms aren't supported and why."
      heading="social platforms"
      lede="A unified social-search command reaches Telegram, Discord, Reddit, and Instagram — tiered by how much setup each one honestly requires."
      toc={toc}
    >
      <h2 id="overview">overview</h2>
      <p><code>social-search</code> is a single command that reaches every supported social platform. By default all enabled providers run in parallel; pass <code>--platform telegram,reddit</code> (comma-separated) to select a subset. Each provider picks the source argument it supports (<code>--channel</code>, <code>--channel-id</code>, <code>--subreddit</code>, <code>--profile</code>) and, if a requested argument is unsupported, falls back to public query-based discovery rather than being skipped. Results are normalized to a common schema across platforms.</p>
      <p>Supported platforms: <strong>telegram</strong> (query, channel), <strong>reddit</strong> (query, subreddit, user), <strong>discord</strong> (channel-id, query — query works without a token via web search; set <code>DISCORD_BOT_TOKEN</code> for full results), <strong>instagram</strong> (query, profile — query works without login via web search; set <code>INSTAGRAM_SESSION_ID</code> for direct profile scraping).</p>

      <h2 id="commands">commands</h2>
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
      <ul>
        {socialCommands.map(c => (
          <li key={c.usage}><code>{c.usage.split(' ')[0]}</code> — {c.notes}</li>
        ))}
      </ul>

      <h2 id="examples">examples</h2>
      <pre><code>{`# search all enabled platforms at once
scout-it social-search --query "machine learning" --max 10

# just telegram — a specific channel, or query discovery
scout-it social-search --platform telegram --channel durov --max 10
scout-it social-search --platform telegram --query "machine learning" --max 10

# discord needs a bot token (bot must already be in the server)
DISCORD_BOT_TOKEN=xxx scout-it social-search --platform discord --channel-id 123456789012345678

# reddit — best-effort; a cookie improves reliability
scout-it social-search --platform reddit --query "python" --subreddit programming
scout-it social-search --platform reddit --user spez --sort top

# instagram — query works without login; --profile scrapes (set INSTAGRAM_SESSION_ID for reliability)
scout-it social-search --platform instagram --query "natgeo"
scout-it social-search --platform instagram --profile natgeo`}</code></pre>
      <p>Discord's <code>--query</code> mode works without a token via web search but returns fewer results than a token-backed <code>--channel-id</code> read. Discord has no anonymous read API, so a bot always has to already be invited into the specific server for full results.</p>

      <h2 id="not-supported">what's not supported</h2>
      <p>{unsupportedPlatforms.join(', ')}, and similar platforms are <strong>not implemented</strong>. None of them currently offer a working zero-config or affordable-API path — all require either a paid official API or a logged-in browser session with cookie management, which is out of scope for this library. Adding one for real would mean either paying for API access or building an authenticated Playwright session manager.</p>
    </DocsLayout>
  )
}
