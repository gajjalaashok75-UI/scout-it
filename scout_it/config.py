#!/usr/bin/env python3
"""
🔐 CONFIG / CREDENTIAL STORAGE — ~/.data-scout/credentials.json
================================================================

Every API key/token this project can use (GITHUB_TOKEN, BRAVE_API_KEY,
BING_API_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, SERPAPI_KEY,
DISCORD_BOT_TOKEN, REDDIT_COOKIE) is read via ``os.environ.get(...)``
throughout the codebase. This module adds a persistent, local alternative
to setting them as real environment variables every session:

- ``data-scout config`` runs an interactive wizard that asks for each key
  one at a time (Enter to skip any you don't have).
- Values are saved to ``~/.data-scout/credentials.json``, permissioned
  ``0600`` (owner read/write only) on POSIX systems — this is "secure
  storage" in the sense of "not world-readable on disk", not encryption;
  anyone with access to your user account/OS-level file permissions (e.g.
  root, or a backup that ignores permissions) could still read it. If you
  need stronger guarantees, keep using real environment variables or a
  proper secrets manager instead.
- ``load_stored_credentials_into_env()`` is called once at CLI startup and
  populates ``os.environ`` for any key that isn't *already* set — a real
  environment variable always takes precedence over the stored file, so
  CI/scripting setups that export env vars directly are unaffected.
"""

import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_DIR = Path.home() / ".data-scout"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

# (env_var_name, human description, which command(s) need it)
KNOWN_CREDENTIALS: List[Dict[str, str]] = [
    {"key": "GITHUB_TOKEN", "desc": "GitHub personal access token — raises the GitHub API rate limit from 60/hr to 5,000/hr, and is REQUIRED for github-discussions and github-search-code", "get_it": "https://github.com/settings/tokens (no special scopes needed for public repos)"},
    {"key": "BRAVE_API_KEY", "desc": "Brave Search API key — used by multi-search --engines brave", "get_it": "https://api.search.brave.com/app/keys (free tier: ~2,000 queries/month)"},
    {"key": "BING_API_KEY", "desc": "Bing Web Search API key (Azure) — used by multi-search --engines bing", "get_it": "Azure Portal → create a 'Bing Search v7' resource"},
    {"key": "GOOGLE_API_KEY", "desc": "Google API key for Custom Search JSON API — used by multi-search --engines google (paired with GOOGLE_CSE_ID)", "get_it": "https://programmablesearchengine.google.com (free tier: 100 queries/day)"},
    {"key": "GOOGLE_CSE_ID", "desc": "Google Programmable Search Engine ID — paired with GOOGLE_API_KEY", "get_it": "https://programmablesearchengine.google.com"},
    {"key": "SERPAPI_KEY", "desc": "SerpAPI key — used by multi-search --engines serpapi (proxies real Google/Bing/Yahoo/Baidu/Yandex results)", "get_it": "https://serpapi.com (free tier: 100 searches/month)"},
    {"key": "DISCORD_BOT_TOKEN", "desc": "Discord bot token — required for discord-channel (the bot must already be a member of the target server)", "get_it": "https://discord.com/developers/applications"},
    {"key": "REDDIT_COOKIE", "desc": "A logged-in Reddit session's Cookie header — improves (does not guarantee) reddit-search success", "get_it": "copy the 'Cookie' request header from a logged-in browser session (DevTools → Network tab)"},
]
KNOWN_KEYS = {c["key"] for c in KNOWN_CREDENTIALS}


def load_credentials_file() -> Dict[str, str]:
    """Read the stored credentials file, if any. Never raises."""
    if not CREDENTIALS_FILE.exists():
        return {}
    try:
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, str) and v}
    except Exception:
        return {}


def save_credentials_file(creds: Dict[str, str]) -> None:
    """Write credentials to disk, creating ~/.data-scout/ if needed and
    restricting file permissions to owner-only where the OS supports it."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2), encoding="utf-8")
    try:
        os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except (OSError, NotImplementedError):
        pass  # e.g. Windows — best effort only, not fatal
    try:
        os.chmod(CONFIG_DIR, stat.S_IRWXU)  # 0700
    except (OSError, NotImplementedError):
        pass


def load_stored_credentials_into_env() -> None:
    """Populate os.environ from the stored credentials file for any key
    that isn't already set in the real environment. Call once at CLI
    startup. A real environment variable always wins over the stored file."""
    stored = load_credentials_file()
    for key, value in stored.items():
        if key not in os.environ or not os.environ.get(key):
            os.environ[key] = value


def credential_status() -> List[Dict[str, Any]]:
    """Report each known credential's configuration status and *source*
    (real env var vs. stored file vs. not configured), without ever
    printing the actual secret value."""
    stored = load_credentials_file()
    out = []
    for c in KNOWN_CREDENTIALS:
        key = c["key"]
        env_value = os.environ.get(key)
        stored_value = stored.get(key)
        if env_value and (not stored_value or env_value != stored_value):
            source = "environment variable"
            configured = True
        elif stored_value:
            source = f"stored config ({CREDENTIALS_FILE})"
            configured = True
        else:
            source = None
            configured = False
        out.append({
            "key": key, "description": c["desc"], "get_it": c["get_it"],
            "configured": configured, "source": source,
        })
    return out


def clear_credential(key: str) -> bool:
    """Remove one credential from the stored file (does not touch real env vars)."""
    stored = load_credentials_file()
    if key in stored:
        del stored[key]
        save_credentials_file(stored)
        return True
    return False


def clear_all_credentials() -> None:
    save_credentials_file({})


def run_config_wizard() -> None:
    """Interactive setup: ask for each known credential one at a time,
    Enter to skip. Existing stored values are shown (masked) and kept if
    you just press Enter."""
    print("\n🔐 data-scout configuration")
    print(f"   Credentials are stored at: {CREDENTIALS_FILE}")
    print("   Press Enter to skip any key you don't have (or want to leave unchanged).\n")

    stored = load_credentials_file()

    for c in KNOWN_CREDENTIALS:
        key = c["key"]
        existing = stored.get(key)
        env_override = os.environ.get(key)

        print(f"--- {key} ---")
        print(f"   {c['desc']}")
        print(f"   Get one: {c['get_it']}")
        if env_override and env_override != existing:
            print(f"   ⚠️  Currently set via a real environment variable, which always takes precedence over this wizard.")
        if existing:
            masked = existing[:4] + "…" + existing[-2:] if len(existing) > 8 else "****"
            print(f"   Currently stored: {masked}")

        try:
            value = input(f"   Enter value (or press Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSetup cancelled — nothing further was changed.")
            return

        if value:
            stored[key] = value
            print(f"   ✅ Saved.\n")
        else:
            print(f"   ⏭️  Skipped.\n")

    save_credentials_file(stored)
    configured_count = len([v for v in stored.values() if v])
    print(f"✅ Configuration saved to {CREDENTIALS_FILE} ({configured_count}/{len(KNOWN_CREDENTIALS)} keys configured).")
    print("   Run `data-scout config --show` any time to review status, or `data-scout list-engines` for search engines specifically.\n")


def print_credential_status() -> None:
    print(f"\n🔐 Credential status ({CREDENTIALS_FILE})\n")
    for info in credential_status():
        status = f"✅ configured (via {info['source']})" if info["configured"] else "⚪ not configured"
        print(f"  {info['key']:<20} {status}")
        if not info["configured"]:
            print(f"      → {info['get_it']}")
    print("\nRun `data-scout config` to set up missing keys interactively.\n")
