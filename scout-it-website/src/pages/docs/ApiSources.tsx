import DocsLayout from '../../components/DocsLayout'
import { apiSourceProviders } from '../../data/searchFlags'

const toc = [
  { id: 'overview', label: 'overview' },
  { id: 'source-vs-sources', label: '--source vs --sources' },
  { id: 'providers', label: 'the six providers' },
  { id: 'setup', label: 'setup' },
  { id: 'examples', label: 'examples' },
  { id: 'behaviour', label: 'behaviour' },
]

export default function ApiSources() {
  return (
    <DocsLayout
      title="scout-it API search sources — Tavily, Exa, Firecrawl, Linkup, Langsearch, Serper via --source"
      description="Six API-backed search providers run as parallel discovery streams alongside DuckDuckGo via the --source flag on web-search, news-search, image-search, video-search, and multi-search. Free tiers, clean skip on missing keys, full untruncated content + metadata in the output."
      heading="API search sources"
      lede="Six API-backed search providers run alongside DuckDuckGo as parallel discovery streams — added with --source (singular), not --sources (plural)."
      toc={toc}
    >
      <h2 id="overview">overview</h2>
      <p>scout-it ships with six API-key-based search providers: <strong>Tavily</strong>, <strong>Exa</strong>, <strong>Firecrawl</strong>, <strong>Linkup</strong>, <strong>Langsearch</strong>, and <strong>Serper</strong>. Each runs as a parallel discovery stream alongside DuckDuckGo (and alongside <code>--source wikimedia</code> or <code>--source google-news</code> where supported), with the results merged and ranked together through the same semantic + composite re-ranking pipeline as everything else.</p>
      <p>They are available on <code>web-search</code>, <code>news-search</code>, <code>image-search</code>, <code>video-search</code>, and <code>multi-search</code> via the <code>--source</code> flag (singular), which accepts comma-separated values:</p>
      <pre><code>{`scout-it web-search --query "AI regulation" --source tavily,exa,firecrawl,serper -m 15
scout-it news-search --query "climate" --source google-news,tavily,serper
scout-it image-search --query "landscape" --source tavily,firecrawl,linkup
scout-it video-search --query "python tutorial" --source serper
scout-it multi-search --query "rust vs go" --engines duckduckgo --source wikimedia,tavily`}</code></pre>

      <h2 id="source-vs-sources">--source vs --sources</h2>
      <p>These two flags do different things, and the API providers belong on the singular one:</p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">what it runs</th>
              <th scope="col">examples</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>--source</code> (singular)</td>
              <td>Parallel discovery streams alongside DuckDuckGo — Wikimedia, Google News RSS, and the six API providers (tavily, exa, firecrawl, linkup, langsearch, serper). Comma-separated. Results are merged and ranked together.</td>
              <td><code>--source wikimedia,tavily,serper</code></td>
            </tr>
            <tr>
              <td><code>--sources</code> (plural)</td>
              <td>The 31 free academic/dataset/knowledge source plugins, merged with BM25F+vector re-ranking. Run <code>scout-it sources</code> to list them.</td>
              <td><code>--sources openalex,arxiv</code></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p>The API providers are deliberately excluded from <code>--sources</code> (plural) and from the <code>scout-it sources</code> list. They are only reachable through <code>--source</code> (singular). The two flags can be combined on the same command if you want both free plugins and API providers in one run.</p>

      <h2 id="providers">the six providers</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">provider</th>
              <th scope="col">search types</th>
              <th scope="col">API key env var</th>
              <th scope="col">get a key</th>
              <th scope="col">sdk</th>
            </tr>
          </thead>
          <tbody>
            {apiSourceProviders.map(p => (
              <tr key={p.name}>
                <td><strong>{p.name}</strong></td>
                <td>{p.searchTypes.join(', ')}</td>
                <td><code>{p.envVar}</code></td>
                <td><a href={p.getKeyUrl} target="_blank" rel="noopener noreferrer">{p.getKeyUrl.replace(/^https?:\/\//, '')}</a><br /><span style={{ color: 'var(--muted-soft)' }}>{p.getKeyNote}</span></td>
                <td><code>{p.sdk}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {apiSourceProviders.map(p => (
        <div key={p.name} style={{ marginTop: 16 }}>
          <h3 id={`provider-${p.name}`} style={{ fontSize: '1.05rem' }}><code>{p.name}</code></h3>
          <p>{p.blurb}</p>
        </div>
      ))}

      <h2 id="setup">setup</h2>
      <p>Store each key once with the config wizard (press Enter to skip any you don't have):</p>
      <pre><code>{`scout-it config
# or set them directly for CI
export TAVILY_API_KEY=tvly-...
export EXA_API_KEY=...
export FIRECRAWL_API_KEY=fc-...
export LINKUP_API_KEY=...
export LANGSEARCH_API_KEY=...
export SERPER_API_KEY=...`}</code></pre>
      <p>As with every other credential, a real environment variable always takes precedence over a stored one, and the values are written to <code>~/.scout-it/credentials.json</code> with owner-only permissions. See <a href="/docs/configuration/">configuration &amp; credentials</a> for the full picture.</p>

      <h2 id="examples">examples</h2>
      <pre><code>{`# all six API providers at once (where each supports the search type)
scout-it web-search --query "transformer architecture" --source tavily,exa,firecrawl,linkup,langsearch,serper -m 15

# mix a free stream with API providers
scout-it web-search --query "quantum computing" --source wikimedia,tavily,serper -m 10

# news — Google News RSS + Tavily + Serper news
scout-it news-search --query "AI regulation" --source google-news,tavily,serper -m 15

# images — Tavily, Firecrawl, and Linkup support image search
scout-it image-search --query "northern lights" --source tavily,firecrawl,linkup --max 20

# video — Serper is the only --source provider that supports video-search
scout-it video-search --query "python tutorial" --source serper --max 10

# multi-search — engines + an API provider
scout-it multi-search --query "rust async runtime" --engines duckduckgo --source tavily --max 15`}</code></pre>

      <h2 id="behaviour">behaviour</h2>
      <ul>
        <li><strong>Credential-gated</strong> — each provider checks for its API key in <code>~/.scout-it/credentials.json</code> (set via <code>scout-it config</code>). When the key is missing, the provider is <strong>skipped with a clear message</strong> telling you how to enable it. The rest of the pipeline (DuckDuckGo + any other sources) continues unaffected.</li>
        <li><strong>Error isolation</strong> — rate-limit (429 / quota), auth (401/403), and network errors are caught per-provider. The failing provider returns no results and prints a concise error; the others continue.</li>
        <li><strong>No truncation</strong> — the <strong>complete provider payload</strong> is preserved untruncated in the output via dedicated passthrough fields: <code>api_content</code> (the full content: Tavily chunks, Exa text, Firecrawl markdown, Langsearch summary, Linkup source snippets, Serper snippet) and <code>api_metadata</code> (the full metadata dict: Tavily answer/score, Exa highlights/author, Firecrawl structured_json/favicon, Serper thumbnail/channel, etc.), plus <code>api_authority_score</code> and <code>api_timestamp</code>. These appear <strong>alongside</strong> the independently extracted <code>cleaned_content</code>, so consumers get both the provider's own content and the re-fetched page content. Available in both snippets mode (<code>--snippets</code>) and full extraction mode. Any new <code>--source</code> provider added in future automatically gets this preservation for free.</li>
        <li><strong>Search-type support varies</strong> — Tavily (web/news/image/multi), Exa (web/news/multi, no image/video), Firecrawl (web/news/image/multi), Linkup (web/image/multi), Langsearch (web/multi), Serper (web/news/image/video/multi — the only one supporting video). Providers that don't support the search type you're running are silently skipped even when listed in <code>--source</code>.</li>
        <li><strong>Parallel</strong> — the API providers are fetched in parallel with each other and with DuckDuckGo, then merged and ranked together.</li>
      </ul>
    </DocsLayout>
  )
}
