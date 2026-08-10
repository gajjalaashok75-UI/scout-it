"""Wiki/Wikimedia RSS Feed Registry.

Every public MediaWiki wiki exposes a RecentChanges feed at
``<wiki>/w/index.php?title=Special:RecentChanges&feed=rss`` listing the most
recently edited pages. These are public, require no authentication, and
return RSS 2.0 with the page title as ``<title>`` and a diff ``<link>``.

This registry curates one feed per Wikimedia project (the 12 projects in
``wikimedia_source.SITE_MAP``), parameterized by language for the
language-scoped wikis. Feeds are keyed by project so the unified wiki-search
pipeline can discover recently-changed pages alongside the MediaWiki Action
API search results, then rank the merged candidate set by query relevance
- the same discover -> rank -> output flow used by web/news/image/video.

All feed URLs below have been verified to return HTTP 200 with parseable
``<item>`` entries.
"""

from typing import Any, Dict, List

__all__ = ["WIKI_SEARCH_FEEDS", "recent_changes_feed", "WIKI_FEED_CATEGORIES"]


def recent_changes_feed(project: str, language: str = "en", limit: int = 50) -> str:
    """Build a MediaWiki RecentChanges RSS feed URL for a project.

    Language-scoped wikis (wikipedia, wikivoyage, wiktionary, wikibooks,
    wikiversity, wikiquote, wikisource) resolve to
    ``{language}.{project}.org``; the fixed-host projects (commons,
    wikidata, mediawiki, wikispecies, wikifunctions) use their canonical host.
    """
    language_scoped = {
        "wikipedia", "wikivoyage", "wiktionary", "wikibooks",
        "wikiversity", "wikiquote", "wikisource",
    }
    if project in language_scoped:
        host = f"{language}.{project}.org"
    else:
        host = {
            "commons": "commons.wikimedia.org",
            "wikidata": "www.wikidata.org",
            "mediawiki": "www.mediawiki.org",
            "wikispecies": "species.wikimedia.org",
            "wikifunctions": "www.wikifunctions.org",
        }.get(project, f"en.{project}.org")
    return (
        f"https://{host}/w/index.php?title=Special:RecentChanges"
        f"&feed=rss&limit={limit}"
    )


# Category registry: each "category" is a Wikimedia project key, mapping to
# one RecentChanges feed. This mirrors image_search_feed / video_search_feed
# but the wiki notion of a category is the project itself (wikipedia, commons,
# wiktionary, ...) rather than a topical grouping.
WIKI_FEED_CATEGORIES: List[str] = [
    "wikipedia", "commons", "wikivoyage", "wiktionary", "wikibooks",
    "wikidata", "wikiversity", "wikiquote", "mediawiki", "wikisource",
    "wikispecies", "wikifunctions",
]


WIKI_SEARCH_FEEDS: Dict[str, List[Dict[str, Any]]] = {
    "wikipedia": [
        {"url": recent_changes_feed("wikipedia"), "notes": "English Wikipedia recent changes."},
        {"url": recent_changes_feed("wikipedia", "simple"), "notes": "Simple English Wikipedia recent changes."},
    ],
    "commons": [
        {"url": recent_changes_feed("commons"), "notes": "Wikimedia Commons recent changes (media)."},
    ],
    "wikivoyage": [
        {"url": recent_changes_feed("wikivoyage"), "notes": "English Wikivoyage recent changes (travel)."},
    ],
    "wiktionary": [
        {"url": recent_changes_feed("wiktionary"), "notes": "English Wiktionary recent changes (definitions)."},
    ],
    "wikibooks": [
        {"url": recent_changes_feed("wikibooks"), "notes": "English Wikibooks recent changes (textbooks)."},
    ],
    "wikidata": [
        {"url": recent_changes_feed("wikidata"), "notes": "Wikidata recent changes (structured knowledge)."},
    ],
    "wikiversity": [
        {"url": recent_changes_feed("wikiversity"), "notes": "English Wikiversity recent changes (learning)."},
    ],
    "wikiquote": [
        {"url": recent_changes_feed("wikiquote"), "notes": "English Wikiquote recent changes (quotations)."},
    ],
    "mediawiki": [
        {"url": recent_changes_feed("mediawiki"), "notes": "MediaWiki.org recent changes (software docs)."},
    ],
    "wikisource": [
        {"url": recent_changes_feed("wikisource"), "notes": "English Wikisource recent changes (source texts)."},
    ],
    "wikispecies": [
        {"url": recent_changes_feed("wikispecies"), "notes": "Wikispecies recent changes (taxonomy)."},
    ],
    "wikifunctions": [
        {"url": recent_changes_feed("wikifunctions"), "notes": "Wikifunctions recent changes (functions)."},
    ],
}
