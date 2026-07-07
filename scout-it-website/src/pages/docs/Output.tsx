import DocsLayout from '../../components/DocsLayout'
import { outputSettings } from '../../data/configuration'

const toc = [
  { id: 'output-location', label: 'where output goes' },
  { id: 'chunking', label: 'line-length-safe json' },
  { id: 'markdown-export', label: 'markdown export' },
  { id: 'web-shape', label: 'web search output' },
  { id: 'image-shape', label: 'image search output' },
  { id: 'news-video-shape', label: 'news / video output' },
  { id: 'fetch-shape', label: 'fetch url output' },
]

export default function Output() {
  return (
    <DocsLayout
      title="scout-it output formats & JSON shapes"
      description="Where scout-it writes output files, the line-length-safe JSON chunking rule, markdown export, and the JSON shape for every search type."
      heading="output & json shapes"
      lede="Structured JSON by default, saved under .scout-it/ unless you say otherwise — with an optional readable markdown mode."
      toc={toc}
    >
      <h2 id="output-location">where output goes, and in what format</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">option</th>
              <th scope="col">what it does</th>
            </tr>
          </thead>
          <tbody>
            {outputSettings.map(o => (
              <tr key={o.key}>
                <td><code>{o.key}</code></td>
                <td>{o.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>Every command's default <code>--out</code> path lives under <code>.scout-it/</code>, created automatically next to wherever you run the command — e.g. <code>.scout-it/web_search_results.json</code>.</p>

      <h2 id="chunking">line-length-safe json</h2>
      <p>Any string field over 500 characters (a long article body, extracted page content, etc.) is broken into an array of ≤500-char chunks at word boundaries instead of one giant single-line value — still fully standard, valid JSON, since an array just serializes one element per line. Diff <code>patch</code> text is left as-is, since it already has a structured <code>patch_lines</code> breakdown for readability instead.</p>

      <h2 id="markdown-export">markdown export</h2>
      <p>Add <code>--markdown</code> to any command to save a readable <code>.md</code> file instead of JSON — tables for lists of uniform records, fenced code blocks for file/diff content. <code>--out file.md</code> also works without the <code>--markdown</code> flag. Combining <code>--markdown</code> with an explicit <code>--out ....json</code> is rejected with a clear error.</p>
      <pre><code>{`scout-it github-repo --repo psf/requests --markdown          # .scout-it/github_repo_results.md
scout-it web-search --query "rust vs go" --out report.md     # markdown, no --markdown flag needed
scout-it web-search --query "x" --markdown --out result.json # ERROR: conflicting formats`}</code></pre>

      <h2 id="web-shape">web search output (results.json)</h2>
      <p>Top-level: <code>query</code>, <code>search_type</code> (<code>"web"</code>), <code>parameters</code>, <code>stats</code>, <code>structured_results</code> (list).</p>
      <p>Each item in <code>structured_results</code> includes: <code>title</code>, <code>url</code>, <code>final_url</code>, <code>cleaned_content</code>, <code>paragraphs</code>, <code>content_sections</code>, <code>top_keywords</code>, <code>readability_metrics</code>, <code>quality_signals</code>, <code>content_quality_score</code>. News search shares this same shape with <code>search_type: "news"</code>.</p>

      <h2 id="image-shape">image search output (image_search_results.json)</h2>
      <p>Top-level: <code>query</code>, <code>search_type</code> (<code>"image"</code>), <code>parameters</code>, <code>stats</code>, <code>image_results</code>.</p>
      <p>Each image item includes: <code>title</code>, <code>image_url</code>, <code>source_url</code>, <code>thumbnail_url</code>, <code>width</code>, <code>height</code>, <code>image_size</code>.</p>

      <h2 id="news-video-shape">news / video output</h2>
      <p><code>news_results.json</code> and <code>video_results.json</code> both include: <code>query</code>, <code>search_type</code> (<code>"news"</code> or <code>"video"</code>), <code>parameters</code>, <code>stats</code>, and a result array (<code>news_results</code> or <code>video_results</code>).</p>

      <h2 id="fetch-shape">fetch url output (url_fetch_result.json)</h2>
      <p>Includes: <code>url</code>, <code>search_type</code> (<code>"fetch"</code>), and a <code>result</code> object containing the extracted/cleaned fields plus fetch stats — including which tier of the resilient fetch chain succeeded.</p>
    </DocsLayout>
  )
}
