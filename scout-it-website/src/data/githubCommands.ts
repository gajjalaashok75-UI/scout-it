// Seeded from scout_it/github_extract.py + the README's GitHub extraction section.

export interface GithubCommand {
  usage: string
  description: string
}

export const githubCommands: GithubCommand[] = [
  {
    usage: 'github-repo --repo owner/repo [--quick] [--file-tree] [--max-chars] [--max-size] [--out] [--markdown] [--json]',
    description: 'Full repo overview by default: metadata, branches, ~commit count, accurately-split open issue/PR counts, top contributors, latest release, language breakdown. Pass --quick for just the fast single-call metadata. Pass --file-tree for the full, untruncated file tree.',
  },
  {
    usage: 'github-commits --repo owner/repo [--branch] [--path] [--author] [--since] [--until] [--max] [--out] [--markdown] [--json]',
    description: 'List commits with full, untruncated commit messages.',
  },
  {
    usage: 'github-commit --repo owner/repo --sha SHA [--no-patch] [--out] [--markdown] [--json]',
    description: 'Full details for one commit: stats, changed files, and unified diff patches.',
  },
  {
    usage: 'github-pr --repo owner/repo --number N [--no-diff] [--out] [--markdown] [--json]',
    description: 'Get a pull request, including its full diff and changed files.',
  },
  {
    usage: 'github-prs --repo owner/repo [--state] [--sort] [--max] [--out] [--markdown] [--json]',
    description: 'List pull requests in a GitHub repo (PR-specific fields, unlike github-issues).',
  },
  {
    usage: 'github-issues --repo owner/repo [--state] [--labels] [--max] [--include-prs] [--out] [--markdown] [--json]',
    description: 'List issues in a repo.',
  },
  {
    usage: 'github-issue --repo owner/repo --number N [--no-comments] [--out] [--markdown] [--json]',
    description: 'Get one issue, including its full body and comments.',
  },
  {
    usage: 'github-file --repo owner/repo --path PATH [--ref REF] [--out] [--markdown] [--json]',
    description: 'Fetch a single file\'s contents from a GitHub repo.',
  },
  {
    usage: 'github-folder --repo owner/repo --path src/ [--ref] [--no-recursive] [--include-content] [--max-files] [--max-chars/--max-size] [--save-path-dir] [--out] [--markdown] [--json]',
    description: 'List (and optionally fetch) every file under a folder. --max-files requires --include-content; without it, --include-content fetches every file found. --save-path-dir also writes fetched files to disk, preserving the repo-relative tree. Each fetched file gets a detected_type.',
  },
  {
    usage: 'github-search-code --query "..." [--max] [--out] [--markdown] [--json]',
    description: 'Search code across GitHub (requires GITHUB_TOKEN, 10 requests/min).',
  },
  {
    usage: 'github-search-repos --query "language:python stars:>1000" [--sort] [--max] [--out] [--markdown] [--json]',
    description: 'Repository search — each hit carries the same full metadata as github-repo.',
  },
  {
    usage: 'github-discussions --repo owner/repo [--max] [--out] [--markdown] [--json]',
    description: 'List GitHub Discussions for a repo. Requires GITHUB_TOKEN — GraphQL has no anonymous access at all, even for public repos.',
  },
]
