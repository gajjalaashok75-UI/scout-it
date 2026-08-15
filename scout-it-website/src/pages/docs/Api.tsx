import DocsLayout from '../../components/DocsLayout'
import CopyCommand from '../../components/CopyCommand'
import { SITE } from '../../data/site'

const toc = [
  { id: 'web-search', label: 'web search' },
  { id: 'image-search', label: 'image search' },
  { id: 'extraction', label: 'direct extraction' },
  { id: 'cleaning', label: 'text cleaning' },
  { id: 'exports', label: 'full export list' },
]

export default function Api() {
  return (
    <DocsLayout
      title="scout-it programmatic API — Python usage"
      description="Use scout-it as a Python library: EnterpriseSearchEngine, ImageSearchEngine, ExtractionEngine, and the full public API export list."
      heading="programmatic API"
      lede="Every CLI capability is also a plain Python import — no subprocess calls required."
      toc={toc}
    >
      <h2 id="web-search">web search with content extraction</h2>
      <p>The top-level functions mirror the CLI subcommands and return a <code>(results, stats)</code> tuple:</p>
      <pre><code>{`from scout_it import web_search

# Returns (results, stats)
results, stats = web_search("machine learning", max_results=5)

for r in results:
    print(f"{r['title']} (confidence: {r.get('confidence_score', 0):.2f})")
    print(r.get('cleaned_content', '')[:200])
    print("---")`}</code></pre>

      <h2 id="image-search">image search</h2>
      <pre><code>{`from scout_it import image_search

images, stats = image_search("mountain landscape", max_results=10, min_width=1024)
for img in images:
    print(img.get('image'), img.get('dimensions'))`}</code></pre>

      <h2 id="extraction">direct content extraction from a URL</h2>
      <pre><code>{`from scout_it import fetch_url

result = fetch_url("https://example.com/article", max_fetch_retries=3)
print(result.get('cleaned_content', '')[:500])`}</code></pre>
      <p>For lower-level control, <code>ExtractionEngine.extract_content(url, html_content, timeout)</code> expects the HTML to already be fetched — it returns <code>(content, method, confidence)</code>. The end-to-end fetch+extract path is <code>fetch_url()</code> / <code>web_search()</code>.</p>

      <h2 id="cleaning">text cleaning and processing</h2>
      <pre><code>{`from scout_it import advanced_clean_text

raw_text = "   Hello   world   with   extra    spaces   "
cleaned = advanced_clean_text(raw_text)
print(cleaned)  # normalized whitespace`}</code></pre>

      <h2 id="exports">full export list</h2>
      <p>Everything importable from the top-level <code>scout_it</code> package:</p>
      <pre><code>{`from scout_it import (
    # engines & extraction
    EnterpriseSearchEngine, EnterpriseResult,
    ExtractionEngine, ImageSearchEngine, ImageSearchResult,
    DDGS, fetch_resilient, process_results, advanced_clean_text,

    # CLI-equivalent functions (each mirrors its subcommand's flags)
    web_search, image_search, news_search, video_search,
    video_extract, fetch_url, multi_search, wikipedia_search,

    # multi-engine
    list_engines, multi_engine_search,

    # GitHub
    github_repo, github_commits, github_commit, github_pull_request,
    github_prs, github_issues, github_issue, github_file_content,
    github_folder, github_search_code, github_search_repos,
    github_discussions, github_rate_limit,

    # social
    telegram_channel, telegram_search, discord_channel_messages, reddit_search,

    # credentials & output
    credential_status, run_config_wizard, clear_credential, clear_all_credentials,
    render_markdown, resolve_output_path, write_json_output,

    # dedicated sources
    wikimedia_search, WikimediaExtractor, SITE_MAP,
    google_news_search, fetch_toi_news, LOCATION_FEEDS,
)`}</code></pre>
      <p>Each CLI-equivalent function (<code>web_search</code>, <code>github_repo</code>, <code>wikipedia_search</code>, etc.) mirrors its subcommand's flags as keyword arguments, so the CLI reference pages double as the function reference.</p>

      <div style={{ marginTop: 32, padding: 24, background: 'var(--surface-card)', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}>
        <p style={{ fontWeight: 500, marginBottom: 12 }}>install scout-it</p>
        <CopyCommand command={SITE.installCommand} />
      </div>
    </DocsLayout>
  )
}
