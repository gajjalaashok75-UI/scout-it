import DocsLayout from '../../components/DocsLayout'
import { multiSearchFlags } from '../../data/searchFlags'
import { engines } from '../../data/engines'

const toc = [
  { id: 'how-it-works', label: 'how it works' },
  { id: 'multi-search', label: 'multi-search' },
  { id: 'engines', label: 'supported engines' },
  { id: 'list-engines', label: 'list-engines' },
]

export default function MultiEngine() {
  return (
    <DocsLayout
      title="scout-it multi-engine search — multi-search & list-engines"
      description="Query DuckDuckGo, Brave, Google, Bing, Yahoo, Baidu, and Yandex in parallel with scout-it multi-search, and check what's configured with list-engines."
      heading="multi-engine search"
      lede="Query several search engines at once, merge and dedupe by URL, then run the same extraction pipeline as web-search."
      toc={toc}
    >
      <h2 id="how-it-works">how it works</h2>
      <p><code>multi-search</code> queries several search engines <strong>in parallel</strong>, merges and dedupes results by URL, then runs the same content-extraction pipeline as <code>web-search</code>. DuckDuckGo needs no setup; the others need a free or paid API key set as an environment variable, or stored once with <code>scout-it config</code>.</p>

      <h2 id="multi-search">multi-search</h2>
      <p>{multiSearchFlags.intro}</p>
      <pre><code>{multiSearchFlags.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {multiSearchFlags.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p><strong>Example:</strong></p>
      <pre><code>{multiSearchFlags.example}</code></pre>

      <h2 id="engines">supported engines</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">engine</th>
              <th scope="col">setup</th>
              <th scope="col">notes</th>
            </tr>
          </thead>
          <tbody>
            {engines.map(e => (
              <tr key={e.id}>
                <td><strong>{e.name}</strong></td>
                <td><code>{e.setup}</code></td>
                <td>{e.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="list-engines">list-engines</h2>
      <p>Check which engines are configured before running a multi-search:</p>
      <pre><code>{`scout-it list-engines
BRAVE_API_KEY=xxx scout-it list-engines   # check what's configured`}</code></pre>
      <p>Store keys once instead of exporting them every session — see <a href="/docs/configuration/">configuration &amp; credentials</a>.</p>
    </DocsLayout>
  )
}
