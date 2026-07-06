// Seeded from scout_it/github_extract.py + the README's GitHub extraction section.

export interface GithubCommand {
  usage: string
  description: string
}

export const githubCommands: GithubCommand[] = [
  {
    usage: 'github-repo --repo owner/repo',
    description: 'Full repo overview by default: metadata, branches, ~commit count, accurately-split open issue/PR counts, top contributors, latest release, language breakdown. Pass --quick for just the fast single-call metadata. Pass --file-tree for the full, untruncated file tree.',
  },
  {
    usage: 'github-commits --repo owner/repo [--branch] [--path] [--author] [--since] [--until] [--max]',
    description: 'List commits with full, untruncated commit messages.',
  },
  {
    usage: 'github-commit --repo owner/repo --sha SHA',
    description: 'Full diff for one commit: every changed file, +/- counts, raw unified patch text, and a structured patch_lines array tagged added / removed / context / hunk_header.',
  },
  {
    usage: 'github-pr --repo owner/repo --number N',
    description: 'PR metadata plus full diff/changed files, with the same patch_lines structuring as github-commit.',
  },
  {
    usage: 'github-prs --repo owner/repo [--state] [--sort] [--max]',
    description: 'List pull requests, including draft status and base/head branch \u2014 PR-specific fields github-issues doesn\u2019t carry.',
  },
  {
    usage: 'github-issues --repo owner/repo [--state] [--labels] [--max]',
    description: 'List issues in a repo.',
  },
  {
    usage: 'github-issue --repo owner/repo --number N',
    description: 'Full issue body plus all comments.',
  },
  {
    usage: 'github-file --repo owner/repo --path PATH [--ref REF]',
    description: 'Fetch and decode a single file\u2019s contents.',
  },
  {
    usage: 'github-folder --repo owner/repo --path src/ [--no-recursive] [--include-content] [--max-files] [--max-chars/--max-size] [--save-path-dir]',
    description: 'List (and optionally fetch) every file under a folder. --max-files requires --include-content; without it, --include-content fetches every file found. --save-path-dir also writes fetched files to disk, preserving the repo-relative tree. Each fetched file gets a detected_type.',
  },
  {
    usage: 'github-search-code --query "..."',
    description: 'Code search across GitHub. Requires GITHUB_TOKEN, 10 requests/min.',
  },
  {
    usage: 'github-search-repos --query "language:python stars:>1000"',
    description: 'Repository search \u2014 each hit carries the same full metadata as github-repo.',
  },
  {
    usage: 'github-discussions --repo owner/repo',
    description: 'List GitHub Discussions for a repo. Requires GITHUB_TOKEN \u2014 GraphQL has no anonymous access at all, even for public repos.',
  },
]
