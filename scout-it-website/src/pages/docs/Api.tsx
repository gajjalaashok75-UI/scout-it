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
      <pre><code>{`from scout_it.extraction import EnterpriseSearchEngine
from scout_it.cleaner import process_results

engine = EnterpriseSearchEngine()
results = engine.search(
    query="machine learning",
    max_results=5,
    extraction_timeout=10
)

# Clean and structure results
cleaned_results = process_results(results)

for result in cleaned_results:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Quality Score: {result['quality_score']}")
    print()`}</code></pre>

      <h2 id="image-search">image search</h2>
      <pre><code>{`from scout_it.extraction import ImageSearchEngine

engine = ImageSearchEngine()
results = engine.search(
    query="mountain landscape",
    max_results=10,
    min_width=1024,
    min_height=768
)

for result in results:
    print(f"Title: {result.title}")
    print(f"Size: {result.dimensions}")
    print(f"Image URL: {result.image_url}")
    print()`}</code></pre>

      <h2 id="extraction">direct content extraction from a URL</h2>
      <pre><code>{`from scout_it.extraction import ExtractionEngine

engine = ExtractionEngine()
content, method, confidence = engine.extract(
    url="https://example.com/article",
    timeout=5
)

print(f"Extraction Method: {method}")
print(f"Confidence Score: {confidence:.2%}")
print(f"Content:\\n{content[:500]}...")`}</code></pre>

      <h2 id="cleaning">text cleaning and processing</h2>
      <pre><code>{`from scout_it.cleaner import advanced_clean_text

raw_text = "   Hello   world   with   extra    spaces   "
cleaned = advanced_clean_text(raw_text)
print(cleaned)  # Output: "Hello world with extra spaces"`}</code></pre>

      <h2 id="exports">full export list</h2>
      <p>Everything importable from the top-level <code>scout_it</code> package:</p>
      <pre><code>{`from scout_it import (
    # engines & extraction
    EnterpriseSearchEngine, EnterpriseResult,
    ExtractionEngine, ImageSearchEngine, ImageSearchResult,
    DDGS, fetch_resilient, process_results, advanced_clean_text,

    # CLI-equivalent functions
    web_search, image_search, news_search, video_search,
    video_extract, fetch_url, multi_search,

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
)`}</code></pre>
      <p>Each CLI-equivalent function (<code>web_search</code>, <code>github_repo</code>, etc.) mirrors its subcommand's flags as keyword arguments, so the CLI reference pages double as the function reference.</p>

      <div style={{ marginTop: 32, padding: 24, background: 'var(--surface-card)', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}>
        <p style={{ fontWeight: 500, marginBottom: 12 }}>install scout-it</p>
        <CopyCommand command={SITE.installCommand} />
      </div>
    </DocsLayout>
  )
}
