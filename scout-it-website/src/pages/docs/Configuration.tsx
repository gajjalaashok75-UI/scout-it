import DocsLayout from '../../components/DocsLayout'
import { envVars, configCommands } from '../../data/configuration'

const toc = [
  { id: 'config-wizard', label: 'the config wizard' },
  { id: 'env-vars', label: 'environment variables' },
  { id: 'precedence', label: 'precedence' },
  { id: 'storage', label: 'where credentials live' },
]

export default function Configuration() {
  return (
    <DocsLayout
      title="scout-it configuration — credentials & environment variables"
      description="Store scout-it credentials once with the interactive config wizard, or use environment variables for CI. Full reference for GITHUB_TOKEN, BRAVE_API_KEY, SERPAPI_API_KEY, and more."
      heading="configuration & credentials"
      lede="Several commands need an API key or token. Store them once with the config wizard, or export environment variables for CI and scripting."
      toc={toc}
    >
      <h2 id="config-wizard">the config wizard</h2>
      <p>Instead of exporting environment variables every session, run:</p>
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
      <p>The interactive wizard lets you press Enter to skip any key you don't have — you don't need every credential to use scout-it.</p>

      <h2 id="env-vars">environment variables</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">variable</th>
              <th scope="col">purpose</th>
            </tr>
          </thead>
          <tbody>
            {envVars.map(v => (
              <tr key={v.name}>
                <td><code>{v.name}</code></td>
                <td>{v.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="precedence">precedence</h2>
      <p>A real environment variable always takes precedence over a stored credential, so CI and scripting setups that export env vars directly are unaffected by whatever is stored locally. Every command that needs a key tells you exactly which one is missing and how to get it.</p>

      <h2 id="storage">where credentials live</h2>
      <p>Values are stored at <code>~/.data-scout/credentials.json</code>, with owner-only file permissions on POSIX systems, and loaded automatically on every future run.</p>
      <pre><code>{`scout-it config              # interactive wizard -- Enter to skip any key you don't have
scout-it config --show       # check what's configured (no secrets printed)
scout-it config --clear GITHUB_TOKEN   # remove one stored key
scout-it config --clear-all            # remove everything`}</code></pre>
    </DocsLayout>
  )
}
