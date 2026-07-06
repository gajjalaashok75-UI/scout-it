// Seeded from scout_it/config.py and the README's config/credentials sections.

export interface EnvVar {
  name: string
  description: string
}

export const envVars: EnvVar[] = [
  { name: 'GITHUB_TOKEN', description: 'Personal access token for GitHub extraction. Unauthenticated works at 60 req/hour; with a token, 5,000/hour. Required (no exceptions) for github-discussions and github-search-code.' },
  { name: 'BRAVE_API_KEY', description: 'Enables the brave engine in multi-search.' },
  { name: 'SERPAPI_API_KEY', description: 'Enables google/bing/yahoo/baidu/yandex engines in multi-search via SerpApi.' },
  { name: 'DISCORD_BOT_TOKEN', description: 'Bot token for discord-channel. The bot must already be a member of the target server.' },
  { name: 'REDDIT_COOKIE', description: 'Optional session cookie that improves reddit-search reliability against anonymous-request blocking.' },
]

export interface ConfigCommand {
  usage: string
  description: string
}

export const configCommands: ConfigCommand[] = [
  { usage: 'scout-it config', description: 'Interactive wizard \u2014 press Enter to skip any key you don\u2019t have.' },
  { usage: 'scout-it config --show', description: 'Check what\u2019s configured. No secret values are ever printed.' },
  { usage: 'scout-it config --clear GITHUB_TOKEN', description: 'Remove one stored key.' },
  { usage: 'scout-it config --clear-all', description: 'Remove every stored credential.' },
]

export interface OutputSetting {
  key: string
  description: string
}

export const outputSettings: OutputSetting[] = [
  { key: '--out, -o <path>', description: 'Explicit output path, always honored exactly as given \u2014 overrides the per-command default under .data-scout/.' },
  { key: '--json', description: 'Print raw JSON straight to stdout instead of writing a file.' },
  { key: '--markdown', description: 'Save a readable .md file instead of JSON (tables for uniform records, fenced code blocks for file/diff content). Rejected if combined with an explicit --out ....json.' },
]
