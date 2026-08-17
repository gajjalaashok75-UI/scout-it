// Seeded from scout_it/social/ package (unified social-search command) + the README's social/platform commands section.

export interface SocialCommand {
  usage: string
  tier: string
  needs: string
  notes: string
}

export const socialCommands: SocialCommand[] = [
  {
    usage: 'social-search --query "..." [--platform telegram,reddit,discord,instagram] [--max] [--out] [--markdown] [--json]',
    tier: 'unified',
    needs: 'varies by platform',
    notes: 'Searches one or more social platforms at once. --platform is comma-separated (default: all enabled providers). Each provider picks the source arg it supports (--channel, --channel-id, --subreddit, --profile) and falls back to public query discovery if an unsupported arg is passed.',
  },
  {
    usage: 'social-search --platform telegram --channel NAME [--max] [--posts-per-channel] [--max-fetch-retries]',
    tier: '0 — works now',
    needs: 'nothing',
    notes: 'Public t.me/s/ preview. Retries 3x then falls back to a richer parser if 0 posts are found. Or use --query to find public channels via a site:t.me search.',
  },
  {
    usage: 'social-search --platform discord --channel-id ID [--max] [--before]',
    tier: '1 — needs a key',
    needs: 'DISCORD_BOT_TOKEN',
    notes: 'Bot must already be invited into the target server. Query-based discovery works without a token via web search (fewer results).',
  },
  {
    usage: 'social-search --platform reddit --query "..." [--subreddit] [--user] [--sort] [--max] [--extract-full]',
    tier: '2 — best-effort',
    needs: 'optional REDDIT_COOKIE',
    notes: 'RSS-first discovery (subreddit / user / search feeds). A cookie improves reliability against Reddit\'s anonymous-request blocking. --extract-full pulls full page content for each top result (slower).',
  },
  {
    usage: 'social-search --platform instagram --query "..." [--profile NAME]',
    tier: '2 — best-effort',
    needs: 'optional INSTAGRAM_SESSION_ID',
    notes: 'Query search works without login via DDGS. --profile NAME does a 3-tier fallback scrape (requests → Playwright → DDGS); set INSTAGRAM_SESSION_ID for reliable profile access.',
  },
]

export const unsupportedPlatforms = [
  'Twitter / X', 'TikTok',
]
