import DocsLayout from '../../components/DocsLayout'
import { imageSearchFlags, videoSearchFlags, videoExtractFlags, type FlagGroup } from '../../data/searchFlags'

const toc = [
  { id: 'image-search', label: 'image-search' },
  { id: 'dimension-rules', label: 'dimension filtering rules' },
  { id: 'video-search', label: 'video-search' },
  { id: 'video-extract', label: 'video-extract' },
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

export default function ImageVideo() {
  return (
    <DocsLayout
      title="scout-it image-search, video-search & video-extract reference"
      description="Full CLI reference for scout-it image-search, video-search, and video-extract: dimension filters, license filters, YouTube metadata and transcripts."
      heading="image & video search"
      lede="Image search with dimension and license filtering, video search, and full YouTube metadata and transcript extraction."
      toc={toc}
    >
      <h2 id="image-search">image-search</h2>
      <FlagTable group={imageSearchFlags} />

      <h2 id="dimension-rules">dimension filtering rules</h2>
      <p>When any dimension filter (<code>--min-width</code>, <code>--max-width</code>, <code>--min-height</code>, <code>--max-height</code>) is enabled:</p>
      <ul>
        <li>Images missing width/height are excluded.</li>
        <li>Range checks are inclusive.</li>
        <li>Invalid negative or unknown numeric dimensions are treated as missing.</li>
      </ul>
      <p>If no dimension filters are enabled, missing dimensions are allowed through.</p>

      <h2 id="video-search">video-search</h2>
      <FlagTable group={videoSearchFlags} />

      <h2 id="video-extract">video-extract</h2>
      <FlagTable group={videoExtractFlags} />
      <p>Only YouTube is currently supported; other platforms return a clear <code>unsupported_platform</code> error rather than failing silently.</p>
    </DocsLayout>
  )
}
