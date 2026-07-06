import DocsLayout from '../../components/DocsLayout'
import { githubCommands } from '../../data/githubCommands'

const toc = [
  { id: 'auth', label: 'authentication' },
  { id: 'commands', label: 'commands' },
  { id: 'examples', label: 'examples' },
]

export default function GitHub() {
  return (
    <DocsLayout
      title="scout-it GitHub extraction — repos, commits, diffs, discussions"
      description="Mine GitHub repos, commits, pull requests, issues, files, and discussions with scout-it, using the official REST and GraphQL APIs — no scraping."
      heading="github extraction"
      lede="Full repo context — metadata, diffs, issues, discussions, and code search — through GitHub's official APIs, structured as JSON."
      toc={toc}
    >
      <h2 id="auth">authentication</h2>
      <p>GitHub extraction uses GitHub's official REST and GraphQL APIs — no scraping. It works unauthenticated at 60 requests/hour; set <code>GITHUB_TOKEN</code> (a personal access token, no special scopes needed for public repos) for 5,000/hour.</p>
      <p><strong>GitHub Discussions specifically requires <code>GITHUB_TOKEN</code></strong> — GraphQL has no anonymous access at all, even for public repos. That's a GitHub platform rule, not a scout-it limitation.</p>
      <p>Run <code>scout-it config</code> to store <code>GITHUB_TOKEN</code> once instead of exporting it every session — see <a href="/docs/configuration/">configuration &amp; credentials</a>.</p>

      <h2 id="commands">commands</h2>
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
                <td><code>{c.usage}</code></td>
                <td>{c.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="examples">examples</h2>
      <pre><code>{`scout-it github-repo --repo pytorch/pytorch              # full overview: branches, contributors, releases, etc.
scout-it github-commit --repo psf/requests --sha <sha>   # full diff for one commit, line-by-line +/- structure
scout-it github-folder --repo psf/requests --path src/ --include-content --max-files 10
GITHUB_TOKEN=ghp_xxx scout-it github-discussions --repo pytorch/pytorch`}</code></pre>
      <p>Commit and PR diffs include both the raw unified <code>patch</code> text and a structured <code>patch_lines</code> array, with each line tagged <code>added</code>, <code>removed</code>, <code>context</code>, or <code>hunk_header</code> — useful for building diff viewers or feeding line-accurate context to an LLM.</p>
    </DocsLayout>
  )
}
