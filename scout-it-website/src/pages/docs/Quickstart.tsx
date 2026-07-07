import DocsLayout from '../../components/DocsLayout'

const toc = [
  { id: 'first-search', label: 'run your first search' },
  { id: 'json-output', label: 'get json output' },
  { id: 'fetch-a-page', label: 'fetch a single page' },
  { id: 'store-credentials', label: 'store credentials' },
  { id: 'next-steps', label: 'next steps' },
]

export default function Quickstart() {
  return (
    <DocsLayout
      title="scout-it quickstart — first search in under a minute"
      description="Run your first scout-it search, get structured JSON output, fetch a single URL, and store credentials for GitHub and multi-engine search."
      heading="quickstart"
      lede="From a fresh install to structured search results in under a minute."
      toc={toc}
    >
      <h2 id="first-search">1. run your first search</h2>
      <p>Web search with content extraction, three results:</p>
      <pre><code>scout-it web-search --query "dog" --max-results 3</code></pre>
      <p>scout-it queries DuckDuckGo, fetches each result page, extracts the main content, and writes a structured file under <code>.scout-it/web_search_results.json</code> next to wherever you ran the command.</p>

      <h2 id="json-output">2. get json output</h2>
      <p>Add <code>--json</code> to print structured results straight to stdout instead of writing a file — handy for piping into <code>jq</code> or another tool:</p>
      <pre><code>scout-it web-search --query "machine learning" --max-results 10 --json</code></pre>
      <p>Prefer a human-readable file? Add <code>--markdown</code> instead, and scout-it writes a <code>.md</code> file with tables and fenced code blocks rather than raw JSON.</p>

      <h2 id="fetch-a-page">3. fetch a single page</h2>
      <p>Already have a URL and just want its extracted content?</p>
      <pre><code>scout-it fetch-url --url "https://en.wikipedia.org/wiki/Dog"</code></pre>
      <p>This goes through the same resilient three-tier fetch chain as every other command — see <a href="/docs/fetch-url/">fetch URL &amp; retry chain</a> for how it decides between plain requests and a headless-browser fallback.</p>

      <h2 id="store-credentials">4. store credentials (optional)</h2>
      <p>Commands like <code>github-discussions</code>, <code>multi-search</code>, and <code>discord-channel</code> need an API key. Instead of exporting environment variables every session, run the interactive wizard once:</p>
      <pre><code>scout-it config</code></pre>
      <p>Values are stored at <code>~/.scout-it/credentials.json</code> with owner-only file permissions and loaded automatically on every future run. Real environment variables always take precedence, so CI setups are unaffected.</p>

      <h2 id="next-steps">next steps</h2>
      <ul>
        <li><strong><a href="/docs/web-search/">Web &amp; news search</a></strong> — full flag reference for text and news search</li>
        <li><strong><a href="/docs/image-video/">Image &amp; video search</a></strong> — dimension filters, YouTube metadata and transcripts</li>
        <li><strong><a href="/docs/multi-engine/">Multi-engine search</a></strong> — query DuckDuckGo, Brave, and Google in parallel</li>
        <li><strong><a href="/docs/github/">GitHub extraction</a></strong> — repos, commits, diffs, issues, and discussions</li>
        <li><strong><a href="/docs/cli-reference/">CLI reference</a></strong> — every one of the 22 subcommands in one place</li>
      </ul>
    </DocsLayout>
  )
}
