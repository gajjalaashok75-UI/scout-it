import DocsLayout from '../../components/DocsLayout'
import { socialCommands, unsupportedPlatforms } from '../../data/socialCommands'

const toc = [
  { id: 'commands', label: 'commands' },
  { id: 'examples', label: 'examples' },
  { id: 'not-supported', label: "what's not supported" },
]

export default function Social() {
  return (
    <DocsLayout
      title="scout-it social platforms — Telegram, Discord, Reddit"
      description="Read public Telegram channels, Discord servers (with a bot token), and Reddit content with scout-it, and see which platforms aren't supported and why."
      heading="social platforms"
      lede="Public and low-config access to Telegram, Discord, and Reddit — tiered by how much setup each one honestly requires."
      toc={toc}
    >
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
      <pre><code>{`scout-it telegram-channel --channel durov --max 10
scout-it telegram-channel --query "machine learning" --max 10   # find & preview matching public channels
DISCORD_BOT_TOKEN=xxx scout-it discord-channel --channel-id 123456789012345678
scout-it reddit-search --query "python" --subreddit programming   # best-effort, see --help`}</code></pre>
      <p>Discord intentionally has no <code>--query</code> topic-search mode: unlike Telegram's public preview pages, Discord has no anonymous read API of any kind — a bot always has to already be invited into the specific server, so there's no cross-server search this library could legitimately offer.</p>

      <h2 id="not-supported">what's not supported</h2>
      <p>{unsupportedPlatforms.join(', ')}, and similar platforms are <strong>not implemented</strong>. None of them currently offer a working zero-config or affordable-API path — all require either a paid official API or a logged-in browser session with cookie management, which is out of scope for this library. Adding one for real would mean either paying for API access or building an authenticated Playwright session manager.</p>
    </DocsLayout>
  )
}
