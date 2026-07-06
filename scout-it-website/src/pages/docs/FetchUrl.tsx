import DocsLayout from '../../components/DocsLayout'
import { fetchUrlFlags } from '../../data/searchFlags'

const toc = [
  { id: 'fetch-url', label: 'fetch-url' },
  { id: 'search-retry', label: 'search-layer retry' },
  { id: 'fetch-chain', label: 'content-fetch fallback chain' },
  { id: 'ddgs-compat', label: 'ddgs signature compatibility' },
]

export default function FetchUrl() {
  return (
    <DocsLayout
      title="scout-it fetch-url & resilient fetch chain"
      description="How scout-it fetches and extracts a single URL, and the shared three-tier resilient fetch chain (requests, Playwright, last-resort) behind every command."
      heading="fetch url & retry chain"
      lede="Direct single-URL extraction, and the shared resilience layer every search command relies on underneath."
      toc={toc}
    >
      <h2 id="fetch-url">fetch-url</h2>
      <p>{fetchUrlFlags.intro}</p>
      <pre><code>{fetchUrlFlags.usage}</code></pre>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">flag</th>
              <th scope="col">description</th>
            </tr>
          </thead>
          <tbody>
            {fetchUrlFlags.flags.map(f => (
              <tr key={f.flag}>
                <td><code>{f.flag}{f.arg ? ` ${f.arg}` : ''}</code></td>
                <td>{f.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p><strong>Example:</strong></p>
      <pre><code>{fetchUrlFlags.example}</code></pre>

      <p>scout-it retries and falls back at <strong>two independent layers</strong> — it's worth understanding the difference:</p>
      <ol style={{ paddingLeft: 20, listStyle: 'decimal', display: 'grid', gap: 8 }}>
        <li>Search/discovery layer — did the search engine return any results at all?</li>
        <li>Content-fetch layer — for each individual result URL, can the page actually be downloaded and extracted?</li>
      </ol>

      <h2 id="search-retry">search-layer retry (zero-results retry)</h2>
      <p><code>web-search</code>, <code>image-search</code>, <code>news-search</code>, and <code>video-search</code> all share the same retry-on-zero-results behavior:</p>
      <ul>
        <li>Attempt 1 uses your configured options (<code>region</code>, <code>safesearch</code>, <code>timelimit</code>, etc.)</li>
        <li>If the search returns 0 results, later attempts progressively relax filters — dropping <code>timelimit</code>, then relaxing <code>safesearch</code> — to maximize the chance of a non-empty result set</li>
        <li>Stops as soon as an attempt returns results</li>
        <li>Controlled by <code>--retry-on-zero</code>/<code>--no-retry-on-zero</code>, <code>--retry-attempts</code> (default 2), <code>--retry-backoff</code> (default 1.0s)</li>
      </ul>
      <p>Previously, only web-search and image-search had this. news-search made exactly one attempt and video-search had no retry logic or flags at all — all four now have full parity.</p>

      <h2 id="fetch-chain">content-fetch layer: the resilient fetch chain</h2>
      <p>Every individual page fetch — web-search result extraction, news-search article extraction, <code>fetch-url</code>, and the YouTube page fetch behind <code>video-extract</code> — goes through a shared three-tier fallback chain:</p>
      <pre><code>{`Tier 1: requests            (up to --max-fetch-retries attempts, UA rotation, backoff)
   │  fails / looks bot-blocked (403/429/503, captcha, "enable JS", tiny body, etc.)
   ▼
Tier 2: Playwright (headless Chromium)   (up to --max-fetch-retries attempts)
   │  fails, or Playwright isn't installed, or the failure was a pure
   │  connection/DNS-level error where a browser can't do any better
   ▼
Tier 3: last-resort basic request        (one attempt, minimal non-fingerprinted headers)`}</code></pre>
      <p>Notes on the design:</p>
      <ul>
        <li><strong>Tier 2 is skipped automatically</strong> when every Tier 1 attempt failed at the connection level (DNS failure, connection refused, timeout) rather than getting an actual HTTP response — a browser hitting the same broken network path won't succeed either, so this avoids wasting three browser launches on an unreachable host. It's still tried whenever at least one Tier 1 attempt did get a response (e.g. a 403 or a bot-check page), since that's exactly the case Playwright is good at getting past.</li>
        <li>Every result records which tier actually succeeded, e.g. <code>extraction_method: "trafilatura (playwright)"</code>, so you can see how much the fallback chain is being used.</li>
        <li><code>--no-js-fallback</code> disables Tier 2 entirely — useful if Playwright/Chromium isn't installed, or you want fast-fail behavior.</li>
        <li>Playwright is optional: <code>pip install scout-it[js-render] && playwright install chromium</code>. If it isn't installed, Tier 2 is skipped with a note in the diagnostics and the chain still falls through to Tier 3.</li>
        <li><code>fetch-url --js-render</code> skips straight to Tier 2 instead of trying <code>requests</code> first — useful when you already know a page needs JS.</li>
      </ul>

      <h2 id="ddgs-compat">DDGS signature compatibility</h2>
      <p>scout-it prefers the <code>ddgs</code> package and falls back to the older <code>duckduckgo_search</code> package name automatically, attempting multiple call signatures for DDGS methods to support version differences between them.</p>
    </DocsLayout>
  )
}
