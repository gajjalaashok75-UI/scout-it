"""Tests for the unified Wikipedia/Wikimedia RSS discovery + ranking pipeline.

Fully offline: RSS parsing is exercised against inline XML fixtures, and the
parallel transport / MediaWiki Action API layers are mocked so the unified
discover -> rank -> enrich -> output flow is deterministic.
"""

from unittest import mock

import pytest
import types

from scout_it.commands import wiki_rss
from scout_it.commands.wiki_search_feed import (
    WIKI_SEARCH_FEEDS,
    WIKI_FEED_CATEGORIES,
    recent_changes_feed,
)
from scout_it.commands.wiki_category_providers import (
    get_available_wiki_categories,
    get_wiki_category_feeds,
    fetch_wiki_category_feeds,
)
from scout_it.staged_ranker import rank_candidates_initial


WIKI_RC_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Recent changes - Wikipedia</title>
    <item>
      <title>Quantum computing</title>
      <link>https://en.wikipedia.org/w/index.php?title=Quantum_computing&amp;diff=1&amp;oldid=2</link>
      <guid isPermaLink="false">https://en.wikipedia.org/w/index.php?title=Quantum_computing&amp;diff=1&amp;oldid=2</guid>
      <pubDate>Mon, 10 Aug 2026 19:11:46 GMT</pubDate>
      <description>&lt;span class="autocomment"&gt;Intro: &lt;/span&gt; fixed typo in qubit section&lt;table data-mw-interface=""&gt;diff junk&lt;/table&gt;</description>
    </item>
    <item>
      <title>User:Someone/sandbox</title>
      <link>https://en.wikipedia.org/w/index.php?title=User:Someone/sandbox&amp;diff=3&amp;oldid=4</link>
      <pubDate>Mon, 10 Aug 2026 19:11:45 GMT</pubDate>
      <description>&lt;span class="autocomment"&gt;test edit&lt;/span&gt;</description>
    </item>
    <item>
      <title>Quantum computing</title>
      <link>https://en.wikipedia.org/w/index.php?title=Quantum_computing&amp;diff=5&amp;oldid=6</link>
      <pubDate>Mon, 10 Aug 2026 19:10:00 GMT</pubDate>
      <description>&lt;span class="autocomment"&gt;History: &lt;/span&gt; added dates&lt;table data-mw-interface=""&gt;more diff&lt;/table&gt;</description>
    </item>
    <item>
      <title>Quantum entanglement</title>
      <link>https://en.wikipedia.org/w/index.php?title=Quantum_entanglement&amp;diff=7&amp;oldid=8</link>
      <pubDate>Mon, 10 Aug 2026 18:00:00 GMT</pubDate>
      <description>&lt;p&gt;Quantum entanglement is a phenomenon in quantum physics.&lt;/p&gt;</description>
    </item>
  </channel>
</rss>
"""


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------
def test_wiki_search_feeds_populated():
    assert WIKI_SEARCH_FEEDS, "wiki feed registry should not be empty"
    for category, feeds in WIKI_SEARCH_FEEDS.items():
        assert isinstance(category, str) and category
        assert feeds, f"category {category!r} has no feeds"
        for entry in feeds:
            assert entry["url"].startswith("https://"), entry
            assert entry.get("notes")


def test_wiki_feed_categories_match_registry():
    assert set(WIKI_FEED_CATEGORIES) == set(WIKI_SEARCH_FEEDS.keys())


def test_recent_changes_feed_language_scoped():
    url = recent_changes_feed("wikipedia", language="en")
    assert url == "https://en.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50"
    assert "feed=rss" in url


def test_recent_changes_feed_custom_limit():
    url = recent_changes_feed("wiktionary", language="fr", limit=10)
    assert url == "https://fr.wiktionary.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=10"


def test_recent_changes_feed_fixed_host_projects():
    # commons / wikidata / mediawiki / wikispecies / wikifunctions are fixed-host.
    assert "commons.wikimedia.org" in recent_changes_feed("commons")
    assert "www.wikidata.org" in recent_changes_feed("wikidata")
    assert "www.mediawiki.org" in recent_changes_feed("mediawiki")
    assert "species.wikimedia.org" in recent_changes_feed("wikispecies")
    assert "www.wikifunctions.org" in recent_changes_feed("wikifunctions")


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------
def test_parse_wiki_feed_extracts_clean_entries():
    entries = wiki_rss.parse_wiki_feed(WIKI_RC_RSS, feed_url="https://en.wikipedia.org/x")
    # User: namespace skipped + duplicate "Quantum computing" deduped -> 2 unique.
    titles = [e["title"] for e in entries]
    assert titles == ["Quantum computing", "Quantum entanglement"]


def test_parse_wiki_feed_builds_canonical_href():
    entries = wiki_rss.parse_wiki_feed(WIKI_RC_RSS, feed_url="https://en.wikipedia.org/x")
    for e in entries:
        assert e["href"].startswith("https://en.wikipedia.org/wiki/")
        assert "&" not in e["href"] or "%26" in e["href"]
    assert entries[0]["href"].endswith("/Quantum_computing")


def test_parse_wiki_feed_cleans_diff_html():
    entries = wiki_rss.parse_wiki_feed(WIKI_RC_RSS, feed_url="https://en.wikipedia.org/x")
    body = entries[0]["body"]
    assert "<table" not in body
    assert "diff junk" not in body
    assert body  # not empty


def test_parse_wiki_feed_skips_blocked_namespaces():
    entries = wiki_rss.parse_wiki_feed(WIKI_RC_RSS, feed_url="https://en.wikipedia.org/x")
    assert not any("User:" in e["title"] for e in entries)


def test_parse_wiki_feed_empty_and_malformed():
    assert wiki_rss.parse_wiki_feed("") == []
    assert wiki_rss.parse_wiki_feed("<not xml<<<") == []


def test_parse_wiki_feed_atom_entry():
    atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Atom topic page</title>
    <link href="https://en.wikipedia.org/w/index.php?title=Atom_topic_page&amp;diff=1" rel="alternate"/>
    <published>2026-08-10T19:00:00Z</published>
    <summary>An atom summary.</summary>
  </entry>
</feed>"""
    entries = wiki_rss.parse_wiki_feed(atom, feed_url="https://en.wikipedia.org/x")
    assert len(entries) == 1
    assert entries[0]["title"] == "Atom topic page"
    assert entries[0]["href"].endswith("/Atom_topic_page")


# ---------------------------------------------------------------------------
# Fetch transport tests (mocked)
# ---------------------------------------------------------------------------
def _make_fake_tcr(feed_map):
    """Build a fake tech_crunch_rss module whose provider returns feed_map."""
    fake_provider = mock.Mock()

    def _fetch(urls, timeout=15.0, max_workers=8):
        return [(url, feed_map.get(url, "")) for url in urls]

    fake_provider.fetch_multiple_feeds.side_effect = _fetch
    return types.SimpleNamespace(
        TechCrunchRSSProvider=lambda: fake_provider,
        RSSProvider=lambda: fake_provider,
    )


def test_fetch_wiki_feed_entries_dedupes_by_href():
    from scout_it.commands import wiki_rss as wiki_mod
    feed_url = "https://en.wikipedia.org/x"
    fake_tcr = _make_fake_tcr({feed_url: WIKI_RC_RSS})
    with mock.patch("importlib.import_module", return_value=fake_tcr):
        entries = wiki_mod.fetch_wiki_feed_entries([feed_url, feed_url], limit=100)
    hrefs = [e["href"] for e in entries]
    assert len(hrefs) == len(set(hrefs)), "entries must be deduped by href"
    assert any(h.endswith("/Quantum_computing") for h in hrefs)


def test_fetch_wiki_feed_entries_via_transport():
    from scout_it.commands import wiki_rss as wiki_mod
    url1 = "https://en.wikipedia.org/x"
    url2 = "https://en.wiktionary.org/x"
    fake_tcr = _make_fake_tcr({url1: WIKI_RC_RSS, url2: ""})
    with mock.patch("importlib.import_module", return_value=fake_tcr):
        entries = wiki_mod.fetch_wiki_feed_entries([url1, url2], limit=100)
    hrefs = [e["href"] for e in entries]
    assert len(hrefs) == len(set(hrefs)), "entries must be deduped by href"
    assert any(h.endswith("/Quantum_computing") for h in hrefs)


def test_fetch_wiki_feed_entries_empty_urls():
    assert wiki_rss.fetch_wiki_feed_entries([], limit=100) == []


def test_fetch_wiki_feed_entries_transport_failure_returns_empty():
    with mock.patch("importlib.import_module", side_effect=ImportError("no transport")):
        assert wiki_rss.fetch_wiki_feed_entries(["https://x"], limit=100) == []


# ---------------------------------------------------------------------------
# Category provider tests
# ---------------------------------------------------------------------------
def test_get_available_wiki_categories_sorted():
    cats = get_available_wiki_categories()
    assert cats == sorted(cats)
    assert "wikipedia" in cats
    assert len(cats) >= 12


def test_get_wiki_category_feeds_returns_providers():
    providers = get_wiki_category_feeds("wikipedia")
    assert providers and callable(providers[0])
    assert get_wiki_category_feeds("nonexistent") == []


def test_fetch_wiki_category_feeds_merges_and_dedupes():
    fake_tcr = _make_fake_tcr({
        "https://en.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50": WIKI_RC_RSS,
        "https://simple.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50": WIKI_RC_RSS,
    })
    with mock.patch("importlib.import_module", return_value=fake_tcr):
        entries = fetch_wiki_category_feeds(["wikipedia"], "quantum", max_results=100)
    hrefs = [e["href"] for e in entries]
    assert len(hrefs) == len(set(hrefs)), "final hrefs must be unique across providers"


def test_fetch_wiki_category_feeds_unknown_category_returns_empty():
    fake_tcr = _make_fake_tcr({})
    with mock.patch("importlib.import_module", return_value=fake_tcr):
        assert fetch_wiki_category_feeds(["nope"], "q", max_results=10) == []


# ---------------------------------------------------------------------------
# Ranking integration
# ---------------------------------------------------------------------------
def test_rank_candidates_orders_wiki_entries():
    candidates = wiki_rss.parse_wiki_feed(WIKI_RC_RSS, feed_url="https://en.wikipedia.org/x")
    ranked = rank_candidates_initial(candidates, "quantum computing", top_k=10)
    titles = [r["title"] for r in ranked]
    assert set(titles) == {"Quantum computing", "Quantum entanglement"}
    assert all("initial_rank_score" in r for r in ranked)
    # Ranking must be stable / deterministic (no ties changing order across calls).
    assert ranked == rank_candidates_initial(candidates, "quantum computing", top_k=10)


def test_rank_candidates_body_match_boosts_relevant_entry():
    # "Quantum entanglement" body mentions "quantum physics" (query term match)
    # while "Quantum computing" body is only "Intro: fixed typo" — so the
    # body-relevant entry should outrank the title-only match.
    candidates = wiki_rss.parse_wiki_feed(WIKI_RC_RSS, feed_url="https://en.wikipedia.org/x")
    ranked = rank_candidates_initial(candidates, "quantum entanglement", top_k=10)
    assert ranked[0]["title"] == "Quantum entanglement"


# ---------------------------------------------------------------------------
# Unified wikipedia_search pipeline tests (mocked API + RSS)
# ---------------------------------------------------------------------------
def _api_search_results(query):
    """Mock MediaWiki Action API search_pages result for the default search mode."""
    from scout_it.wikimedia_source import RequestResult
    return RequestResult(
        ok=True, endpoint="wikipedia_search",
        data=[
            {"source_project": "wikipedia", "title": "Python (programming language)",
             "pageid": 23862, "snippet": "Python is a high-level programming language",
             "timestamp": "2026-08-09T10:00:00Z"},
            {"source_project": "wikipedia", "title": "Python (mythology)",
             "pageid": 12345, "snippet": "Python is a serpent in Greek mythology",
             "timestamp": "2026-08-08T10:00:00Z"},
        ],
    )


def test_wikipedia_search_unified_ranks_api_results():
    from scout_it.commands.wikipedia import wikipedia_search
    with mock.patch(
        "scout_it.wikimedia_source.WikimediaExtractor.search_pages",
        return_value=_api_search_results("python"),
    ):
        results, stats = wikipedia_search("python", max_results=5, include_rss=False)
    assert stats.get("pipeline") == "unified"
    assert stats.get("api_candidates") == 2
    assert stats.get("rss_candidates") == 0
    assert len(results) == 2
    for r in results:
        assert r["href"].startswith("https://en.wikipedia.org/wiki/")
        assert r["source"].startswith("wikimedia:")
        assert "initial_rank_score" in r


def test_wikipedia_search_unified_with_rss_merges_streams():
    from scout_it.commands.wikipedia import wikipedia_search
    fake_tcr = _make_fake_tcr({
        "https://en.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50": WIKI_RC_RSS,
        "https://simple.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50": "",
    })
    with mock.patch(
        "scout_it.wikimedia_source.WikimediaExtractor.search_pages",
        return_value=_api_search_results("python"),
    ), mock.patch("importlib.import_module", return_value=fake_tcr):
        results, stats = wikipedia_search("python", max_results=10, include_rss=True)
    assert stats.get("pipeline") == "unified"
    assert stats["api_candidates"] == 2
    assert stats["rss_candidates"] >= 1, "RSS stream should add candidates"
    assert stats["total_candidates"] == stats["api_candidates"] + stats["rss_candidates"]
    # API results (query-relevant "python" snippets) should rank above the
    # unrelated "Quantum ..." RC entries.
    assert results[0]["title"] == "Python (programming language)"
    hrefs = [r["href"] for r in results]
    assert len(hrefs) == len(set(hrefs)), "final output must be deduped by href"


def test_wikipedia_search_with_explicit_categories():
    from scout_it.commands.wikipedia import wikipedia_search
    fake_tcr = _make_fake_tcr({
        "https://en.wiktionary.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50": WIKI_RC_RSS,
    })
    with mock.patch(
        "scout_it.wikimedia_source.WikimediaExtractor.search_pages",
        return_value=_api_search_results("python"),
    ), mock.patch("importlib.import_module", return_value=fake_tcr):
        results, stats = wikipedia_search(
            "python", max_results=10, categories=["wiktionary"],
        )
    assert stats["rss_categories"] == ["wiktionary"]
    assert stats["rss_candidates"] >= 1


def test_wikipedia_search_unified_api_error_still_uses_rss():
    from scout_it.commands.wikipedia import wikipedia_search
    from scout_it.wikimedia_source import RequestResult
    fake_tcr = _make_fake_tcr({
        "https://en.wikipedia.org/w/index.php?title=Special:RecentChanges&feed=rss&limit=50": WIKI_RC_RSS,
    })
    with mock.patch(
        "scout_it.wikimedia_source.WikimediaExtractor.search_pages",
        return_value=RequestResult(ok=False, endpoint="wikipedia_search", error="maxlag"),
    ), mock.patch("importlib.import_module", return_value=fake_tcr):
        results, stats = wikipedia_search("python", max_results=10, include_rss=True)
    assert stats.get("errors"), "API failure should be surfaced as errors"
    assert stats["api_candidates"] == 0
    assert stats["rss_candidates"] >= 1
    assert len(results) >= 1


def test_wikipedia_search_summary_mode_bypasses_pipeline():
    """Single-page modes do not run the unified ranking pipeline."""
    from scout_it.commands.wikipedia import wikipedia_search
    from scout_it.wikimedia_source import RequestResult
    with mock.patch(
        "scout_it.wikimedia_source.WikimediaExtractor.wikipedia_summary",
        return_value=RequestResult(ok=True, endpoint="summary",
                                   data={"title": "Python", "extract": "A programming language.",
                                         "description": "lang", "thumbnail": {"source": "x"}}),
    ):
        results, stats = wikipedia_search("python", summary=True, include_rss=True)
    assert stats.get("mode") == "summary"
    assert stats.get("pipeline") != "unified"
    assert len(results) == 1
    assert results[0]["title"] == "Python"


def test_wikipedia_search_bundle_mode_bypasses_pipeline():
    from scout_it.commands.wikipedia import wikipedia_search
    from scout_it.wikimedia_source import RequestResult
    bundle_data = {"data": {"wikipedia_search": [{"title": "Python (programming language)",
                                                   "snippet": "a language", "pageid": 1}]}}
    with mock.patch(
        "scout_it.wikimedia_source.WikimediaExtractor.bundle_topic",
        return_value=RequestResult(ok=True, endpoint="bundle_topic", data=bundle_data),
    ):
        results, stats = wikipedia_search("python", bundle=True, include_rss=True)
    assert stats.get("bundle") is True
    assert stats.get("pipeline") != "unified"
    assert len(results) == 1
