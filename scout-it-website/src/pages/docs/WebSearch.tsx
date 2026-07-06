import DocsLayout from '../../components/DocsLayout'
import { webSearchFlags, newsSearchFlags, type FlagGroup } from '../../data/searchFlags'

const toc = [
  { id: 'web-search', label: 'web-search' },
  { id: 'news-search', label: 'news-search' },
  { id: 'pipeline', label: 'extraction pipeline' },
]

function FlagTable({ group }: { group: FlagGroup }) {
  return (
    <>
      <p>{group.intro}</p>
      <pre><code>{group.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {group.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p><strong>Example:</strong></p>
      <pre><code>{group.example}</code></pre>
    </>
  )
}

export default function WebSearch() {
  return (
    <DocsLayout
      title="scout-it web-search & news-search reference"
      description="Full CLI reference for scout-it web-search and news-search: flags, zero-result retry, content extraction, and examples."
      heading="web & news search"
      lede="DuckDuckGo text and news search, each with full content extraction and cleaning built in."
      toc={toc}
    >
      <h2 id="web-search">web-search</h2>
      <FlagTable group={webSearchFlags} />

      <h2 id="news-search">news-search</h2>
      <FlagTable group={newsSearchFlags} />

      <h2 id="pipeline">extraction pipeline</h2>
      <p>Both commands follow the same shape:</p>
      <ol style={{ paddingLeft: 20, listStyle: 'decimal', display: 'grid', gap: 8 }}>
        <li><code>EnterpriseSearchEngine</code> queries DDGS text or news.</li>
        <li>Result URLs are fetched in parallel (<code>--workers</code> controls concurrency for web-search).</li>
        <li><code>ExtractionEngine</code> pulls main content using layered extraction methods — trafilatura first, then justext, boilerpy3, and heuristic fallbacks.</li>
        <li><code>main_content_cleaner.process_results</code> filters failed extractions and structures the surviving text.</li>
        <li>Output is written as JSON (or Markdown with <code>--markdown</code>).</li>
      </ol>
      <p>Every individual page fetch behind these two commands goes through the shared resilient fetch chain — see <a href="/docs/fetch-url/">fetch URL &amp; retry chain</a> for the full three-tier breakdown.</p>
      <p>Each item in the output's <code>structured_results</code> includes <code>title</code>, <code>url</code>, <code>final_url</code>, <code>cleaned_content</code>, <code>paragraphs</code>, <code>content_sections</code>, <code>top_keywords</code>, <code>readability_metrics</code>, <code>quality_signals</code>, and <code>content_quality_score</code> — see <a href="/docs/output/">output &amp; JSON shapes</a> for the full schema.</p>
    </DocsLayout>
  )
}
