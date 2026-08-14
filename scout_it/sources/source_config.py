"""Source-specific configuration — extends the scout-it config system.

Manages per-source settings (API keys, base URL overrides, enable/disable)
stored in ``~/.scout-it/sources.json``, separate from the general
``credentials.json``.

Each source can be:
  - **enabled/disabled** — disabled sources are skipped in multi-source search
  - **API key configured** — for sources that need one (Semantic Scholar, etc.)
  - **base URL overridden** — for self-hosted instances (e.g. local Zenodo)

Usage::

    from scout_it.sources.source_config import get_source_config

    cfg = get_source_config("semantic_scholar")
    # cfg = {"api_key": "...", "base_url": "", "enabled": True}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# ─── Storage paths ───────────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".scout-it"
SOURCES_FILE = CONFIG_DIR / "sources.json"

# ─── Source credential registry ──────────────────────────────────────────────
# Each entry describes a source that can be configured via `scout-it config`.
# Sources with no API key requirement are listed as free (no key needed).

SOURCE_CREDENTIALS: List[Dict[str, Any]] = [
    # ── Academic & research ──────────────────────────────────────────────
    {
        "name": "openalex",
        "display_name": "OpenAlex",
        "content_type": "academic",
        "requires_key": False,
        "api_key_env": "",
        "description": "~250M scholarly works — the free academic Google replacement. No API key needed (polite pool with email).",
        "get_it": "https://openalex.org — no key required, just provide an email for the polite pool",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "semantic_scholar",
        "display_name": "Semantic Scholar",
        "content_type": "academic",
        "requires_key": True,
        "api_key_env": "SEMANTIC_SCHOLAR_API_KEY",
        "description": "200M+ papers with citation graphs, TLDRs, and influence scores. Free API key increases rate limits.",
        "get_it": "https://www.semanticscholar.org/product/api — free, 1 req/sec without key, 100 req/sec with key",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "arxiv",
        "display_name": "arXiv",
        "content_type": "academic",
        "requires_key": False,
        "api_key_env": "",
        "description": "2.4M+ preprint papers in physics, math, CS, biology. Open Atom API, no key needed.",
        "get_it": "https://arxiv.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "crossref",
        "display_name": "Crossref",
        "content_type": "academic",
        "requires_key": False,
        "api_key_env": "",
        "description": "150M+ DOI-registered works. Free API, polite pool with email gets higher rate limit.",
        "get_it": "https://www.crossref.org — no key required, provide email for polite pool",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "unpaywall",
        "display_name": "Unpaywall",
        "content_type": "academic",
        "requires_key": False,
        "api_key_env": "UNPAYWALL_EMAIL",
        "description": "Open-access full-text PDF links for ~30M articles. Free, requires an email address.",
        "get_it": "https://unpaywall.org — provide your email as the API key",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "core",
        "display_name": "CORE",
        "content_type": "academic",
        "requires_key": True,
        "api_key_env": "CORE_API_KEY",
        "description": "200M+ open-access papers with full text. Free API key required.",
        "get_it": "https://core.ac.uk/services/api — free registration",
        "free_tier": True,
        "default_enabled": False,
    },
    {
        "name": "europe_pmc",
        "display_name": "Europe PMC",
        "content_type": "academic",
        "requires_key": False,
        "api_key_env": "",
        "description": "40M+ biomedical and life science articles. Free, no key needed.",
        "get_it": "https://europepmc.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    # ── Datasets ─────────────────────────────────────────────────────────
    {
        "name": "huggingface",
        "display_name": "Hugging Face Datasets",
        "content_type": "dataset",
        "requires_key": False,
        "api_key_env": "HF_TOKEN",
        "description": "100k+ datasets for ML/AI. Free, no key needed (token increases rate limits).",
        "get_it": "https://huggingface.co/settings/tokens — optional, free",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "zenodo",
        "display_name": "Zenodo",
        "content_type": "dataset",
        "requires_key": False,
        "api_key_env": "",
        "description": "Research data repository — datasets, software, publications. Free, no key needed.",
        "get_it": "https://zenodo.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "data_gov",
        "display_name": "data.gov (CKAN)",
        "content_type": "dataset",
        "requires_key": False,
        "api_key_env": "",
        "description": "US government open data — 300k+ datasets. Free CKAN API, no key needed.",
        "get_it": "https://data.gov — no key required",
        "free_tier": True,
        "default_enabled": False,
    },
    # ── Knowledge graphs ─────────────────────────────────────────────────
    {
        "name": "wikidata",
        "display_name": "Wikidata (SPARQL)",
        "content_type": "knowledge",
        "requires_key": False,
        "api_key_env": "",
        "description": "100M+ entities with structured relations. Free SPARQL endpoint, no key needed.",
        "get_it": "https://wikidata.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    # ── Books & long-form ────────────────────────────────────────────────
    {
        "name": "open_library",
        "display_name": "Open Library",
        "content_type": "book",
        "requires_key": False,
        "api_key_env": "",
        "description": "30M+ book records with metadata and availability. Free, no key needed.",
        "get_it": "https://openlibrary.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "gutenberg",
        "display_name": "Project Gutenberg",
        "content_type": "book",
        "requires_key": False,
        "api_key_env": "",
        "description": "70k+ free full-text ebooks. Free, no key needed.",
        "get_it": "https://gutenberg.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    # ── Events & real-time ───────────────────────────────────────────────
    {
        "name": "gdelt",
        "display_name": "GDELT",
        "content_type": "event",
        "requires_key": False,
        "api_key_env": "",
        "description": "Global events database — monitors worldwide news in real time. Free, no key needed.",
        "get_it": "https://gdeltproject.org — no key required",
        "free_tier": True,
        "default_enabled": False,
    },
    # ── Media ─────────────────────────────────────────────────────────────
    {
        "name": "internet_archive",
        "display_name": "Internet Archive",
        "content_type": "media",
        "requires_key": False,
        "api_key_env": "",
        "description": "Digital archive of websites, books, audio, video, software. Free, no key needed.",
        "get_it": "https://archive.org — no key required",
        "free_tier": True,
        "default_enabled": False,
    },
    # ── Podcasts ─────────────────────────────────────────────────────────
    {
        "name": "listennotes",
        "display_name": "ListenNotes",
        "content_type": "podcast",
        "requires_key": True,
        "api_key_env": "LISTENNOTES_API_KEY",
        "description": "2.5M+ podcasts and episodes with transcripts. Free tier: 1000 requests/month.",
        "get_it": "https://listennotes.com/api/ — free tier available",
        "free_tier": True,
        "default_enabled": False,
    },
    # ── Geo ──────────────────────────────────────────────────────────────
    {
        "name": "openstreetmap",
        "display_name": "OpenStreetMap",
        "content_type": "geo",
        "requires_key": False,
        "api_key_env": "",
        "description": "Geographic data — places, POIs, boundaries. Free Nominatim/Overpass API, no key needed.",
        "get_it": "https://openstreetmap.org — no key required",
        "free_tier": True,
        "default_enabled": False,
    },
    # ── New no-auth sources (from public-apis/public-apis) ───────────────
    {
        "name": "hackernews",
        "display_name": "Hacker News",
        "content_type": "event",
        "requires_key": False,
        "api_key_env": "",
        "description": "CS/entrepreneurship social news — stories, comments, discussions.",
        "get_it": "https://hn.algolia.com/api — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "stackexchange",
        "display_name": "Stack Exchange",
        "content_type": "knowledge",
        "requires_key": False,
        "api_key_env": "",
        "description": "Q&A sites — Stack Overflow, Math, Science, Ask Ubuntu, etc.",
        "get_it": "https://api.stackexchange.com — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "open_fda",
        "display_name": "openFDA",
        "content_type": "knowledge",
        "requires_key": False,
        "api_key_env": "",
        "description": "US FDA open data — drug adverse events, recalls, device data.",
        "get_it": "https://open.fda.gov — no key required (key optional for higher limits)",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "open_meteo",
        "display_name": "Open-Meteo",
        "content_type": "geo",
        "requires_key": False,
        "api_key_env": "",
        "description": "Global weather forecasts — current conditions + 16-day forecast.",
        "get_it": "https://open-meteo.com — no key required (non-commercial)",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "usgs_earthquakes",
        "display_name": "USGS Earthquakes",
        "content_type": "event",
        "requires_key": False,
        "api_key_env": "",
        "description": "Real-time earthquake data — magnitude, location, depth, time.",
        "get_it": "https://earthquake.usgs.gov — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "musicbrainz",
        "display_name": "MusicBrainz",
        "content_type": "media",
        "requires_key": False,
        "api_key_env": "",
        "description": "Open music metadata — recordings, artists, releases, works.",
        "get_it": "https://musicbrainz.org — no key required (1 req/sec)",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "open_food_facts",
        "display_name": "Open Food Facts",
        "content_type": "knowledge",
        "requires_key": False,
        "api_key_env": "",
        "description": "Food products database — nutrition, ingredients, allergens.",
        "get_it": "https://openfoodfacts.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "spaceflight_news",
        "display_name": "Spaceflight News",
        "content_type": "event",
        "requires_key": False,
        "api_key_env": "",
        "description": "Spaceflight news — articles about launches, missions, space science.",
        "get_it": "https://spaceflightnewsapi.net — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "art_institute_chicago",
        "display_name": "Art Institute of Chicago",
        "content_type": "media",
        "requires_key": False,
        "api_key_env": "",
        "description": "Art collection — paintings, sculptures, artifacts with images.",
        "get_it": "https://api.artic.edu — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "met_museum",
        "display_name": "Metropolitan Museum of Art",
        "content_type": "media",
        "requires_key": False,
        "api_key_env": "",
        "description": "Met Museum collection — 490k+ artworks with images and metadata.",
        "get_it": "https://metmuseum.github.io — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "jikan",
        "display_name": "Jikan (MyAnimeList)",
        "content_type": "media",
        "requires_key": False,
        "api_key_env": "",
        "description": "Anime/manga database — titles, scores, synopses, genres.",
        "get_it": "https://jikan.moe — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "doaj",
        "display_name": "DOAJ",
        "content_type": "academic",
        "requires_key": False,
        "api_key_env": "",
        "description": "Directory of Open Access Journals — 8M+ OA articles.",
        "get_it": "https://doaj.org/api — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
    # ── Code repositories ────────────────────────────────────────────────
    {
        "name": "gitlab",
        "display_name": "GitLab",
        "content_type": "code",
        "requires_key": False,
        "api_key_env": "GITLAB_TOKEN",
        "description": "Git repositories, CI/CD pipelines, and open-source projects. Public search is free; set GITLAB_TOKEN for higher rate limits.",
        "get_it": "https://gitlab.com — public search needs no key; token at https://gitlab.com/-/user_settings/personal_access_tokens",
        "free_tier": True,
        "default_enabled": True,
    },
    {
        "name": "bitbucket",
        "display_name": "Bitbucket",
        "content_type": "code",
        "requires_key": False,
        "api_key_env": "",
        "description": "Git repositories and code collaboration (Atlassian). Free, no key needed.",
        "get_it": "https://bitbucket.org — no key required",
        "free_tier": True,
        "default_enabled": True,
    },
]

SOURCE_NAMES = {s["name"] for s in SOURCE_CREDENTIALS}
SOURCE_BY_NAME = {s["name"]: s for s in SOURCE_CREDENTIALS}


def load_sources_config() -> Dict[str, Dict[str, Any]]:
    """Load the per-source config from ``~/.scout-it/sources.json``.

    Returns a dict mapping source name → {api_key, base_url, enabled, ...}.
    Never raises; returns {} if file doesn't exist.
    """
    if not SOURCES_FILE.exists():
        return {}
    try:
        data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_sources_config(config: Dict[str, Dict[str, Any]]) -> None:
    """Write the per-source config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
    try:
        import stat
        os.chmod(SOURCES_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, NotImplementedError):
        pass


def get_source_config(source_name: str) -> Dict[str, Any]:
    """Get the merged config for a source.

    Merges defaults from SOURCE_CREDENTIALS with the stored config file
    and any environment variable overrides.
    """
    defaults = SOURCE_BY_NAME.get(source_name, {})
    stored = load_sources_config().get(source_name, {})

    cfg = {
        "api_key": "",
        "base_url": defaults.get("base_url", ""),
        "enabled": defaults.get("default_enabled", True),
    }
    cfg.update(stored)

    # Environment variable override for API key.
    env_var = defaults.get("api_key_env", "")
    if env_var and os.environ.get(env_var):
        cfg["api_key"] = os.environ[env_var]

    return cfg


def set_source_config(
    source_name: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> None:
    """Update one source's config and persist to disk."""
    config = load_sources_config()
    if source_name not in config:
        config[source_name] = {}
    if api_key is not None:
        config[source_name]["api_key"] = api_key
    if base_url is not None:
        config[source_name]["base_url"] = base_url
    if enabled is not None:
        config[source_name]["enabled"] = enabled
    save_sources_config(config)


def enable_source(source_name: str) -> None:
    set_source_config(source_name, enabled=True)


def disable_source(source_name: str) -> None:
    set_source_config(source_name, enabled=False)


def is_source_enabled(source_name: str) -> bool:
    return get_source_config(source_name).get("enabled", True)


def source_status() -> List[Dict[str, Any]]:
    """Report each source's configuration status (no secrets printed)."""
    stored = load_sources_config()
    out = []
    for src in SOURCE_CREDENTIALS:
        name = src["name"]
        env_var = src.get("api_key_env", "")
        env_key = os.environ.get(env_var) if env_var else None
        stored_cfg = stored.get(name, {})
        stored_key = stored_cfg.get("api_key")
        configured = bool(env_key or stored_key) if src["requires_key"] else True
        source = "environment variable" if env_key else (
            f"stored config ({SOURCES_FILE})" if stored_key else None
        )
        out.append({
            "name": name,
            "display_name": src["display_name"],
            "content_type": src["content_type"],
            "requires_key": src["requires_key"],
            "configured": configured,
            "source": source,
            "enabled": is_source_enabled(name),
            "free_tier": src.get("free_tier", True),
            "description": src["description"],
            "get_it": src["get_it"],
        })
    return out
