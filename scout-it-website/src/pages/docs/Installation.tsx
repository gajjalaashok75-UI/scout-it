import DocsLayout from '../../components/DocsLayout'
import { SITE } from '../../data/site'

const toc = [
  { id: 'requirements', label: 'requirements' },
  { id: 'install-pypi', label: 'install from pypi' },
  { id: 'install-source', label: 'install from source' },
  { id: 'optional-extras', label: 'optional extras' },
  { id: 'verify', label: 'verify the install' },
  { id: 'troubleshooting', label: 'troubleshooting' },
]

export default function Installation() {
  return (
    <DocsLayout
      title="Install scout-it — pip, source, and optional extras"
      description="How to install scout-it with pip or from source, including the optional Playwright js-render extra, on macOS, Linux, and Windows."
      heading="install scout-it"
      lede="One pip command on macOS, Linux, or Windows. A development install works the same way from a clone."
      toc={toc}
    >
      <h2 id="requirements">requirements</h2>
      <ul>
        <li><strong>Python 3.9+</strong> — developed and tested against Python 3.13, but supports 3.9 and up.</li>
        <li><strong>pip</strong> — for installing from PyPI or in editable/development mode.</li>
        <li><strong>Internet access</strong> — required for live search and fetch operations.</li>
      </ul>
      <p>Core dependencies (installed automatically): <code>ddgs</code> (falls back to <code>duckduckgo_search</code> if unavailable), <code>trafilatura</code>, <code>requests</code>, <code>beautifulsoup4</code>, <code>justext</code>, <code>boilerpy3</code>, <code>rich</code>, <code>urllib3</code>, and <code>youtube-transcript-api</code>.</p>

      <h2 id="install-pypi">install from pypi</h2>
      <pre><code>{SITE.installCommand}</code></pre>
      <p>This installs the <code>scout-it</code> console script along with the <code>scout_it</code> Python package for programmatic use.</p>

      <h2 id="install-source">install from source</h2>
      <p>For development, or to track the latest unreleased changes:</p>
      <pre><code>{`git clone ${SITE.github}.git
cd scout-it

python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

pip install -e ".[dev]"`}</code></pre>
      <p>The <code>dev</code> extra adds <code>pytest</code>, <code>pytest-cov</code>, <code>black</code>, <code>flake8</code>, <code>mypy</code>, and <code>isort</code> for contributing.</p>

      <h2 id="optional-extras">optional extras</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">extra</th>
              <th scope="col">installs</th>
              <th scope="col">when you need it</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>scout-it[js-render]</code></td>
              <td><code>playwright&gt;=1.40.0</code></td>
              <td>Enables the Tier-2 headless-Chromium fallback for JS-heavy or bot-protected pages. Run <code>playwright install chromium</code> afterward.</td>
            </tr>
            <tr>
              <td><code>scout-it[legacy-ddgs]</code></td>
              <td><code>duckduckgo-search&gt;=3.9.0</code></td>
              <td>Fallback for environments still pinned to the old package name — scout_it tries <code>ddgs</code> first and falls back automatically.</td>
            </tr>
            <tr>
              <td><code>scout-it[dev]</code></td>
              <td>test &amp; lint tooling</td>
              <td>Contributing to the project.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <pre><code>{`pip install "scout-it[js-render]"
playwright install chromium`}</code></pre>

      <h2 id="verify">verify the install</h2>
      <pre><code>{`scout-it --help
python -c "from scout_it import EnterpriseSearchEngine; print('OK')"`}</code></pre>

      <h2 id="troubleshooting">troubleshooting</h2>
      <ul>
        <li><strong>Command not found</strong> — Ensure your Python scripts/bin directory is on <code>$PATH</code>. Inside a virtualenv this is automatic.</li>
        <li><strong>Import errors after install</strong> — Reinstall in development mode with <code>pip install -e ".[dev]"</code>, or verify with the Python snippet above.</li>
        <li><strong>Python version mismatch</strong> — Check with <code>python --version</code>; scout-it requires 3.9+.</li>
        <li><strong>Playwright missing</strong> — Tier 2 of the fetch chain is skipped automatically with a note in diagnostics; install the <code>js-render</code> extra if you need it.</li>
      </ul>
    </DocsLayout>
  )
}
