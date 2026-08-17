import DocsLayout from '../../components/DocsLayout'
import { wikipediaSearchFlags, indexFlags, semanticSearchFlags, sourcesFlags } from '../../data/searchFlags'

const toc = [
  { id: 'wikipedia-search', label: 'wikipedia-search' },
  { id: 'sources', label: 'sources' },
  { id: 'index', label: 'index' },
  { id: 'semantic-search', label: 'semantic-search' },
]

export default function Wikipedia() {
  return (
    <DocsLayout
      title="scout-it Wikimedia & semantic search — wikipedia-search, sources, index, semantic-search"
      description="Search the 12 Wikimedia projects, plug in 31 academic/dataset/knowledge sources, and build a persistent semantic corpus with index + semantic-search."
      heading="Wikimedia & semantic search"
      lede="Knowledge-base search beyond DuckDuckGo: the full Wikimedia family, 31 free source plugins, and a persistent hybrid BM25+vector index."
      toc={toc}
    >
      <h2 id="wikipedia-search">wikipedia-search</h2>
      <p>{wikipediaSearchFlags.intro}</p>
      <pre><code>{wikipediaSearchFlags.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {wikipediaSearchFlags.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p><strong>Example:</strong></p>
      <pre><code>{wikipediaSearchFlags.example}</code></pre>

      <h2 id="sources">sources</h2>
      <p>{sourcesFlags.intro}</p>
      <pre><code>{sourcesFlags.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {sourcesFlags.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <pre><code>{sourcesFlags.example}</code></pre>
      <p>Pass any listed source to <code>--sources</code> on <code>web-search</code>, <code>news-search</code>, <code>image-search</code>, <code>video-search</code>, or <code>multi-search</code>. Sources needing a key (e.g. <code>semantic_scholar</code>, <code>core</code>) show ❌ until configured; free sources are ready immediately.</p>
      <p>Three API search providers — <code>tavily</code>, <code>exa</code>, <code>firecrawl</code> — are <strong>not</strong> in the <code>scout-it sources</code> list. They run as parallel discovery streams via <code>--source</code> (singular) instead, alongside DuckDuckGo. See <a href="/docs/api-sources/">API search sources</a> for the full reference.</p>

      <h2 id="index">index</h2>
      <p>{indexFlags.intro}</p>
      <pre><code>{indexFlags.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {indexFlags.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <pre><code>{indexFlags.example}</code></pre>

      <h2 id="semantic-search">semantic-search</h2>
      <p>{semanticSearchFlags.intro}</p>
      <pre><code>{semanticSearchFlags.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {semanticSearchFlags.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <pre><code>{semanticSearchFlags.example}</code></pre>
      <p>The typical workflow is: <code>scout-it index</code> to build the corpus, then <code>scout-it semantic-search</code> to query it. The corpus persists at <code>~/.scout-it/semantic/lancedb/</code> across runs.</p>
    </DocsLayout>
  )
}
