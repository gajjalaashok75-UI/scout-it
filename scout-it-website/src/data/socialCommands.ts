// Seeded from scout_it/social.py + the README's social/platform commands section.

export interface SocialCommand {
  usage: string
  tier: string
  needs: string
  notes: string
}

export const socialCommands: SocialCommand[] = [
  {
    usage: 'telegram-channel --channel NAME [--max]',
    tier: '0 \u2014 works now',
    needs: 'nothing',
    notes: 'Public t.me/s/ preview. Retries 3x then falls back to a richer parser if 0 posts are found.',
  },
  {
    usage: 'telegram-channel --query "..." [--max] [--posts-per-channel]',
    tier: '0 \u2014 works now',
    needs: 'nothing',
    notes: 'Finds public channels via a site:t.me search.',
  },
  {
    usage: 'discord-channel --channel-id ID [--max]',
    tier: '1 \u2014 needs a key',
    needs: 'DISCORD_BOT_TOKEN',
    notes: 'Bot must already be invited into the target server. No cross-server topic search exists \u2014 Discord has no anonymous read API at all.',
  },
  {
    usage: 'reddit-search --query "..." [--subreddit] [--max]',
    tier: '2 \u2014 best-effort',
    needs: 'optional REDDIT_COOKIE',
    notes: 'Reddit blocks most anonymous requests as of 2026; a cookie improves reliability but isn\u2019t required.',
  },
]

export const unsupportedPlatforms = [
  'Twitter / X', 'Instagram', 'TikTok',
]
