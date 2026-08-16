"""
Tests for the unified ``social-search`` architecture:

  - Provider capability declarations (Telegram/Reddit/Discord).
  - Capability-based fallback: an unsupported source arg falls back to query
    search; a provider with no public query path reports a failure.
  - The provider registry (register / get / resolve_platforms).
  - The normalized unified result schema.
  - The ``social_search`` orchestrator (parallel multi-provider aggregation,
    resilience to a single provider failing, unknown-platform reporting).
  - Backwards compatibility: the legacy flat functions
    (``telegram_channel``, ``telegram_search``, ``discord_channel_messages``,
    ``reddit_search``) and parsers are still importable from ``scout_it.social``.

All HTTP calls are mocked — no real network access.
"""
import json
import os
from unittest import mock

import pytest

from scout_it import social
from scout_it.social import (
    DiscordProvider,
    RedditProvider,
    SocialProvider,
    TelegramProvider,
    available_platforms,
    discord_channel_messages,
    get,
    normalize_item,
    provider_result,
    reddit_search,
    register,
    resolve_platforms,
    social_search,
)
from scout_it.social.discord import discord_bot_search
from scout_it.social.base import (
    CAP_CHANNEL,
    CAP_CHANNEL_ID,
    CAP_QUERY,
    CAP_SUBREDDIT,
    CAP_USER,
)


class _FakeResp:
    def __init__(self, status_code=200, json_data=None, headers=None, text=None):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text if text is not None else (
            json.dumps(json_data) if json_data is not None else "")

    def json(self):
        return self._json


# ---------------------------------------------------------------------------
# Capability declarations
# ---------------------------------------------------------------------------

class TestCapabilityDeclarations:
    def test_telegram_supports_query_and_channel(self):
        assert TelegramProvider.SUPPORTED_CAPABILITIES == {CAP_QUERY, CAP_CHANNEL}

    def test_reddit_supports_query_and_subreddit(self):
        assert RedditProvider.SUPPORTED_CAPABILITIES == {CAP_QUERY, CAP_SUBREDDIT, CAP_USER}

    def test_discord_supports_channel_id_and_query(self):
        assert DiscordProvider.SUPPORTED_CAPABILITIES == {CAP_CHANNEL_ID, CAP_QUERY}

    def test_discord_has_query_fallback(self):
        # DDGS gives Discord a public discovery path -> falls back to query search.
        assert DiscordProvider.FALLBACK_CAPABILITY == CAP_QUERY

    def test_telegram_and_reddit_fall_back_to_query(self):
        assert TelegramProvider.FALLBACK_CAPABILITY == CAP_QUERY
        assert RedditProvider.FALLBACK_CAPABILITY == CAP_QUERY


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_builtins_registered(self):
        assert "telegram" in available_platforms()
        assert "reddit" in available_platforms()
        assert "discord" in available_platforms()

    def test_get_is_case_insensitive(self):
        assert isinstance(get("Telegram"), TelegramProvider)
        assert isinstance(get("REDDIT"), RedditProvider)

    def test_get_unknown_returns_none(self):
        assert get("nonexistent") is None

    def test_resolve_platforms_none_means_all(self):
        assert resolve_platforms(None) == available_platforms()
        assert resolve_platforms("") == available_platforms()

    def test_resolve_platforms_comma_separated(self):
        assert resolve_platforms("telegram,reddit") == ["telegram", "reddit"]

    def test_resolve_platforms_strips_whitespace_and_lowercases(self):
        assert resolve_platforms(" Telegram , Reddit ") == ["telegram", "reddit"]

    def test_resolve_platforms_keeps_unknown_names(self):
        # Unknown names are returned as-is so the orchestrator can report them.
        assert "unknown" in resolve_platforms("telegram,unknown")

    def test_register_custom_provider(self):
        class FakeProvider(SocialProvider):
            platform = "fake"
            SUPPORTED_CAPABILITIES = {CAP_QUERY}

            def _execute(self, capability, params):
                return provider_result("fake", query=params.get("query"),
                                       results=[normalize_item("fake", content="x")],
                                       capabilities_used=[CAP_QUERY])

        register(FakeProvider())
        try:
            assert "fake" in available_platforms()
            assert isinstance(get("fake"), FakeProvider)
        finally:
            # Clean up so this doesn't leak into other tests.
            from scout_it.social import registry as _reg
            _reg._REGISTRY.pop("fake", None)


# ---------------------------------------------------------------------------
# Normalized result schema
# ---------------------------------------------------------------------------

class TestNormalizedSchema:
    def test_normalize_item_has_all_fields(self):
        item = normalize_item("telegram", author="a", content="c", url="u",
                              timestamp="t", metadata={"k": "v"})
        assert item == {
            "platform": "telegram", "author": "a", "content": "c",
            "url": "u", "timestamp": "t", "metadata": {"k": "v"},
        }

    def test_normalize_item_defaults(self):
        item = normalize_item("reddit")
        assert item["platform"] == "reddit"
        assert item["author"] is None
        assert item["metadata"] == {}

    def test_provider_result_success_envelope(self):
        res = provider_result("telegram", query="q",
                              results=[normalize_item("telegram", content="x")],
                              capabilities_used=[CAP_CHANNEL])
        assert res["platform"] == "telegram"
        assert res["result_count"] == 1
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_CHANNEL]

    def test_provider_result_failure_envelope(self):
        res = provider_result("discord", error="auth_required",
                              error_message="no token")
        assert res["error"] == "auth_required"
        assert res["result_count"] == 0
        assert res["results"] == []


# ---------------------------------------------------------------------------
# Telegram provider (channel + query, with fallback)
# ---------------------------------------------------------------------------

_TELEGRAM_CHANNEL_RAW = {
    "channel": "durov", "title": "Durov", "description": "d",
    "post_count_returned": 1, "parser_used": "primary",
    "posts": [{"id": "durov/1", "url": "https://t.me/durov/1",
               "text": "hello", "date": "2026-01-01", "views": "1K"}],
}

_TELEGRAM_SEARCH_RAW = {
    "query": "AI", "channel_count": 1,
    "channels": [{
        "channel": "aichan", "title": "AI Chan", "description": "d",
        "post_count_returned": 1, "posts": [
            {"id": "aichan/1", "url": "https://t.me/aichan/1",
             "text": "ai post", "date": "2026-01-02", "views": "5"}],
    }],
}


class TestTelegramProvider:
    def test_channel_capability_executes(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value=_TELEGRAM_CHANNEL_RAW):
            res = TelegramProvider().search(channel="durov", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_CHANNEL]
        assert res["result_count"] == 1
        assert res["results"][0]["platform"] == "telegram"
        assert res["results"][0]["content"] == "hello"
        assert res["results"][0]["url"] == "https://t.me/durov/1"

    def test_query_capability_executes(self):
        with mock.patch("scout_it.social.telegram.telegram_search",
                        return_value=_TELEGRAM_SEARCH_RAW):
            res = TelegramProvider().search(query="AI", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]
        assert res["result_count"] == 1
        assert res["results"][0]["author"] == "aichan"

    def test_query_fallback_when_channel_unsupported_arg_passed(self):
        # Telegram doesn't support --subreddit, so it should fall back to query.
        with mock.patch("scout_it.social.telegram.telegram_search",
                        return_value=_TELEGRAM_SEARCH_RAW):
            res = TelegramProvider().search(query="AI", subreddit="python",
                                            max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]

    def test_no_input_reports_error(self):
        res = TelegramProvider().search()
        assert res["error"] == "no_input"

    def test_channel_error_propagates(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value={"error": "fetch_failed",
                                      "error_message": "boom"}):
            res = TelegramProvider().search(channel="bad", max_results=5)
        assert res["error"] == "fetch_failed"
        assert res["result_count"] == 0


# ---------------------------------------------------------------------------
# Telegram enhancements: pagination, not-found detection, fallback, metadata
# (logic ported from PythonicCafe/tchan + AlexSaite/telegram_scrapper_notoken)
# ---------------------------------------------------------------------------

class TestTelegramEnhancements:
    def test_convert_count_handles_k_m_commas(self):
        from scout_it.social.telegram import _convert_count
        assert _convert_count("1.2K") == 1200
        assert _convert_count("3M") == 3000000
        assert _convert_count("5,432") == 5432
        assert _convert_count(None) is None
        assert _convert_count("notanumber") is None

    def test_normalize_channel_handles_all_input_formats(self):
        from scout_it.social.telegram import _normalize_channel
        assert _normalize_channel("@durov") == "durov"
        assert _normalize_channel("https://t.me/durov") == "durov"
        assert _normalize_channel("https://t.me/s/durov") == "durov"
        assert _normalize_channel("t.me/durov/") == "durov"
        assert _normalize_channel("https://t.me/s/durov/123") == "durov"
        assert _normalize_channel("") == ""
        assert _normalize_channel(None) == ""

    def test_not_found_detection_flags_missing_channel(self):
        from scout_it.social.telegram import _looks_like_not_found
        from bs4 import BeautifulSoup
        notfound = "<html><body>If you have <strong>Telegram</strong></body></html>"
        soup = BeautifulSoup(notfound, "html.parser")
        assert _looks_like_not_found(notfound, soup) is True

    def test_not_found_detection_does_not_flag_real_channel(self):
        from scout_it.social.telegram import _looks_like_not_found
        from bs4 import BeautifulSoup
        real = '<div class="tgme_widget_message_wrap"></div>'
        soup = BeautifulSoup(real, "html.parser")
        assert _looks_like_not_found(real, soup) is False

    def test_not_found_detection_does_not_flag_existing_empty_channel(self):
        # A channel that exists but has no posts (has a header) is NOT not-found.
        from scout_it.social.telegram import _looks_like_not_found
        from bs4 import BeautifulSoup
        html = '<div class="tgme_channel_info_header_title">Empty</div>'
        soup = BeautifulSoup(html, "html.parser")
        assert _looks_like_not_found(html, soup) is False

    def test_channel_not_found_returns_distinct_error(self):
        from scout_it.social import telegram
        notfound_html = ('<html><body>If you have <strong>Telegram</strong>, '
                         'you can contact</body></html>')
        with mock.patch("scout_it.extraction.fetch_resilient", return_value={
            "html": notfound_html, "final_url": "u", "status": "success",
            "tier": "requests", "attempts": 1, "errors": [],
        }):
            out = telegram.telegram_channel("nonexistentxyz", max_fetch_retries=1)
        assert out["error"] == "channel_not_found"

    def test_existing_empty_channel_returns_metadata_not_failure(self):
        from scout_it.social import telegram
        html = ('<meta property="og:title" content="Empty Channel" />'
                '<div class="tgme_channel_info_header_title">Empty Channel</div>')
        with mock.patch("scout_it.extraction.fetch_resilient", return_value={
            "html": html, "final_url": "u", "status": "success",
            "tier": "requests", "attempts": 1, "errors": [],
        }):
            out = telegram.telegram_channel("chan", max_fetch_retries=1)
        assert out["post_count_returned"] == 0
        assert out["parser_used"] == "none_found"
        assert out["title"] == "Empty Channel"

    def test_pagination_fetches_multiple_pages(self):
        """--max larger than one preview page (~20) triggers ?before= pagination."""
        from scout_it.social import telegram
        page1 = ('<div class="tgme_widget_message_wrap">'
                 '<div class="tgme_widget_message" data-post="c/10">'
                 '<div class="tgme_widget_message_text">post10</div>'
                 '<time datetime="2026-01-01T00:00:00+00:00"></time></div></div>')
        page2 = ('<div class="tgme_widget_message_wrap">'
                 '<div class="tgme_widget_message" data-post="c/5">'
                 '<div class="tgme_widget_message_text">post5</div>'
                 '<time datetime="2026-01-02T00:00:00+00:00"></time></div></div>')
        page3 = '<div class="tgme_channel_info_header_title">C</div>'
        calls = {"n": 0}

        def fake_fetch(url, **kw):
            calls["n"] += 1
            html = [page1, page2, page3][min(calls["n"] - 1, 2)]
            return {"html": html, "final_url": url, "status": "success",
                    "tier": "requests", "attempts": 1, "errors": []}

        with mock.patch("scout_it.extraction.fetch_resilient", side_effect=fake_fetch):
            out = telegram.telegram_channel("c", max_results=45, max_fetch_retries=1)
        assert calls["n"] >= 2  # paginated beyond the first page
        assert out["post_count_returned"] == 2

    def test_channel_metadata_includes_subscribers(self):
        from scout_it.social import telegram
        html = '''
        <div class="tgme_channel_info_header_title">Big Chan</div>
        <div class="tgme_channel_info_counters">
          <div class="tgme_channel_info_counter">
            <span class="counter_value">12.5K</span>
            <span class="counter_type">subscribers</span>
          </div>
        </div>
        <div class="tgme_widget_message_wrap">
          <div class="tgme_widget_message" data-post="big/1">
            <div class="tgme_widget_message_text">hi</div>
            <time datetime="2026-01-01T00:00:00+00:00"></time>
            <span class="tgme_widget_message_views">1.2K</span>
          </div>
        </div>
        '''
        with mock.patch("scout_it.extraction.fetch_resilient", return_value={
            "html": html, "final_url": "u", "status": "success",
            "tier": "requests", "attempts": 1, "errors": [],
        }):
            out = telegram.telegram_channel("big", max_results=5, max_fetch_retries=1)
        assert out["subscribers"] == 12500
        assert out["posts"][0]["views_count"] == 1200

    def test_channel_failure_falls_back_to_query_search(self):
        """The user-requested behaviour: a wrong/empty --channel falls back
        to public query search so the user still gets relevant channels."""
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value={"error": "channel_not_found",
                                      "error_message": "no"}), \
                mock.patch("scout_it.social.telegram.telegram_search",
                           return_value={
                               "query": "wrongname", "channel_count": 1,
                               "channels": [{"channel": "realchan", "title": "Real",
                                     "posts": [{"id": "realchan/1",
                                                "url": "https://t.me/realchan/1",
                                                "text": "found via fallback",
                                                "date": "2026-01-01",
                                                "views": "10"}]}]}):
            res = TelegramProvider()._execute(
                "channel", {"channel": "wrongname", "query": None, "max_results": 5})
        assert res["result_count"] == 1
        assert "channel" in res["capabilities_used"]
        assert "query" in res["capabilities_used"]
        assert res["results"][0]["author"] == "realchan"
        assert "fell back to query search" in res["note"]

    def test_channel_failure_with_query_uses_explicit_query_for_fallback(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value={"error": "channel_not_found",
                                      "error_message": "no"}), \
                mock.patch("scout_it.social.telegram.telegram_search",
                           return_value={"query": "AI", "channel_count": 0,
                                         "channels": []}):
            res = TelegramProvider()._execute(
                "channel", {"channel": "wrongname", "query": "AI", "max_results": 5})
        # Both failed -> error reported, but capabilities show fallback was tried.
        assert res["result_count"] == 0
        assert "query" in res["capabilities_used"]
        assert "fell back to query search 'AI'" in res["note"]


# ---------------------------------------------------------------------------
# Reddit provider (query + subreddit, with fallback)
# ---------------------------------------------------------------------------

_REDDIT_RAW = {
    "query": "python", "subreddit": None, "result_count": 1,
    "posts": [{"title": "T", "subreddit": "python", "author": "bob", "score": 5,
               "num_comments": 2, "url": "http://x",
               "permalink": "/r/python/comments/a", "created_utc": 123,
               "selftext": "body"}],
}


class TestRedditProvider:
    def test_query_capability_executes(self):
        with mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru:
            rg.return_value = _FakeResp(200, {
                "data": {"children": [{"data": {
                    "title": "T", "subreddit": "python", "author": "bob",
                    "score": 5, "num_comments": 2, "url": "http://x",
                    "permalink": "/r/python/comments/a", "created_utc": 123,
                    "selftext": "body",
                }}]}
            })
            ru.quote = lambda s: s
            res = RedditProvider().search(query="python", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]
        assert res["result_count"] == 1
        assert res["results"][0]["platform"] == "reddit"
        assert res["results"][0]["author"] == "bob"
        assert "T" in res["results"][0]["content"]

    def test_subreddit_capability_executes(self):
        with mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru:
            rg.return_value = _FakeResp(200, {
                "data": {"children": [{"data": {
                    "title": "T", "subreddit": "learnpython", "author": "bob",
                    "score": 1, "num_comments": 0, "url": "http://x",
                    "permalink": "/r/learnpython/comments/a", "created_utc": 1,
                    "selftext": "",
                }}]}
            })
            ru.quote = lambda s: s
            res = RedditProvider().search(query="tips", subreddit="learnpython",
                                          max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_SUBREDDIT]

    def test_subreddit_without_query_now_works_via_rss(self):
        """A subreddit listing no longer requires a --query: the RSS feed
        itself is the listing (changed from the old .json-only behaviour)."""
        rss_xml = ('<feed xmlns="http://www.w3.org/2005/Atom">'
                   '<entry><title>Post A</title>'
                   '<link href="https://www.reddit.com/r/learnpython/comments/a"/>'
                   '<author><name>/u/bob</name></author>'
                   '<published>2026-01-01T00:00:00+00:00</published>'
                   '<id>t3_a</id><content type="html">body</content></entry>'
                   '</feed>')
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": rss_xml, "status": "success",
                                      "status_code": 200, "errors": []}):
            res = RedditProvider().search(subreddit="learnpython", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_SUBREDDIT]
        assert res["result_count"] == 1
        assert res["results"][0]["author"] == "bob"

    def test_403_reports_honest_failure(self):
        with mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru:
            rg.return_value = _FakeResp(403)
            ru.quote = lambda s: s
            res = RedditProvider().search(query="python", max_results=5)
        assert res["error"] == "blocked"
        assert "2026" in res["error_message"] or "REDDIT_COOKIE" in res["error_message"]

    def test_channel_arg_falls_back_to_query(self):
        # Reddit doesn't support --channel; with a --query it should fall back.
        with mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru:
            rg.return_value = _FakeResp(200, {"data": {"children": []}})
            ru.quote = lambda s: s
            res = RedditProvider().search(query="AI", channel="durov",
                                          max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]


# ---------------------------------------------------------------------------
# Reddit RSS enhancements (primary RSS path, user capability, ranking,
# extraction, json fallback) -- logic ported from datavorous/yars + the
# Reddit public .rss feed format.
# ---------------------------------------------------------------------------

_REDDIT_RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>python</title>
  <entry>
    <title>Python async tips and tricks</title>
    <link href="https://www.reddit.com/r/python/comments/abc/async_tips/"/>
    <author><name>/u/guido</name></author>
    <published>2026-08-14T10:00:00+00:00</published>
    <id>t3_abc</id>
    <content type="html">&lt;p&gt;async is great&lt;/p&gt; submitted by &lt;a href="/u/guido"&gt;/u/guido&lt;/a&gt; &lt;span&gt;&lt;a href="https://example.com/blog"&gt;[link]&lt;/a&gt;&lt;/span&gt;</content>
  </entry>
  <entry>
    <title>Unrelated post about cats</title>
    <link href="https://www.reddit.com/r/python/comments/def/cats/"/>
    <author><name>/u/alice</name></author>
    <published>2026-08-13T10:00:00+00:00</published>
    <id>t3_def</id>
    <content type="html">&lt;p&gt;cats&lt;/p&gt;</content>
  </entry>
  <entry>
    <title>More async patterns</title>
    <link href="https://www.reddit.com/r/python/comments/ghi/async_patterns/"/>
    <author><name>/u/bob</name></author>
    <published>2026-08-12T10:00:00+00:00</published>
    <id>t3_ghi</id>
    <content type="html">&lt;p&gt;patterns&lt;/p&gt;</content>
  </entry>
</feed>"""


class TestRedditRSSEnhancements:
    def test_parse_reddit_feed_extracts_atom_entries(self):
        from scout_it.social.reddit import _parse_reddit_feed
        items = _parse_reddit_feed(_REDDIT_RSS_SAMPLE, 10)
        assert len(items) == 3
        assert items[0]["title"] == "Python async tips and tricks"
        assert items[0]["author"] == "guido"
        assert items[0]["url"] == "https://www.reddit.com/r/python/comments/abc/async_tips/"
        assert items[0]["external_url"] == "https://example.com/blog"
        assert items[0]["id"] == "t3_abc"

    def test_parse_reddit_feed_handles_rss2_items(self):
        from scout_it.social.reddit import _parse_reddit_feed
        rss2 = ('<?xml version="1.0"?><rss version="2.0" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
                '<item><title>T</title><link>http://x</link>'
                '<description>&lt;p&gt;desc&lt;/p&gt;</description>'
                '<dc:creator>alice</dc:creator><pubDate>Mon, 01 Jan 2026 00:00:00 GMT</pubDate>'
                '<guid>g1</guid></item>'
                '</channel></rss>')
        items = _parse_reddit_feed(rss2, 10)
        assert len(items) == 1
        assert items[0]["title"] == "T"
        assert items[0]["selftext"] == "desc"
        assert items[0]["author"] == "alice"

    def test_parse_reddit_feed_empty_or_invalid(self):
        from scout_it.social.reddit import _parse_reddit_feed
        assert _parse_reddit_feed("", 10) == []
        assert _parse_reddit_feed("not xml at all", 10) == []

    def test_build_feed_url_for_each_source(self):
        from scout_it.social.reddit import _build_feed_url
        assert _build_feed_url(subreddit="python") == "https://www.reddit.com/r/python/.rss"
        assert _build_feed_url(subreddit="python+programming") == "https://www.reddit.com/r/python+programming/.rss"
        assert _build_feed_url(user="spez") == "https://www.reddit.com/user/spez/.rss"
        assert "search.rss" in _build_feed_url(query="AI news")
        assert "?sort=new" in _build_feed_url(subreddit="python", sort="new")

    def test_rank_posts_prioritizes_query_matches(self):
        from scout_it.social.reddit import _rank_posts
        posts = [
            {"title": "cats", "selftext": "", "published": "2026-08-13"},
            {"title": "Python async tips", "selftext": "", "published": "2026-08-14"},
            {"title": "More async patterns", "selftext": "async here", "published": "2026-08-12"},
        ]
        ranked = _rank_posts(posts, "async", 3)
        # "async" appears in title+body for "More async patterns" (highest),
        # title-only for "Python async tips", and not at all for "cats".
        assert ranked[0]["title"] == "More async patterns"
        assert ranked[-1]["title"] == "cats"

    def test_strip_html_decodes_entities(self):
        from scout_it.social.reddit import _strip_html
        assert _strip_html("&lt;p&gt;hello &amp; world&lt;/p&gt;") == "hello & world"
        assert _strip_html("") == ""
        assert _strip_html(None) == ""

    def test_query_via_rss_returns_posts(self):
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": _REDDIT_RSS_SAMPLE, "status": "success",
                                      "status_code": 200, "errors": []}):
            res = RedditProvider().search(query="python", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]
        assert res["result_count"] == 3
        assert res["results"][0]["platform"] == "reddit"

    def test_subreddit_via_rss_no_query_needed(self):
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": _REDDIT_RSS_SAMPLE, "status": "success",
                                      "status_code": 200, "errors": []}):
            res = RedditProvider().search(subreddit="python", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_SUBREDDIT]
        assert res["result_count"] == 3

    def test_user_capability_via_rss(self):
        """--user fetches that user's posts/comments via user/{name}.rss."""
        user_feed = ('<feed xmlns="http://www.w3.org/2005/Atom">'
                     '<entry><title>My comment</title>'
                     '<link href="https://www.reddit.com/r/x/comments/1/mine/"/>'
                     '<author><name>/u/spez</name></author>'
                     '<published>2026-08-14T10:00:00+00:00</published>'
                     '<id>t1_1</id><content type="html">comment body</content></entry>'
                     '</feed>')
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": user_feed, "status": "success",
                                      "status_code": 200, "errors": []}):
            res = RedditProvider().search(user="spez", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_USER]
        assert res["result_count"] == 1
        assert res["results"][0]["author"] == "spez"

    def test_rss_blocked_falls_back_to_json(self):
        """When RSS is blocked (403/429), the .json path is tried."""
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": "", "status": "failed",
                                      "status_code": 429,
                                      "errors": ["HTTP 429 (rate-limited)"]}), \
                mock.patch("scout_it.social.reddit._reddit_json_search",
                           return_value={"query": "python", "result_count": 1,
                                         "posts": [{"title": "T", "author": "bob",
                                                    "url": "http://x", "selftext": "",
                                                    "published": "2026-01-01", "id": "1"}]}):
            res = RedditProvider().search(query="python", max_results=5)
        assert res["error"] is None
        assert res["result_count"] == 1
        assert ".json" in (res.get("note") or "")

    def test_both_rss_and_json_fail_reports_blocked(self):
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": "", "status": "failed",
                                      "status_code": 403, "errors": ["HTTP 403"]}), \
                mock.patch("scout_it.social.reddit._reddit_json_search",
                           return_value={"error": "blocked", "error_message": "blocked"}):
            res = RedditProvider().search(query="python", max_results=5)
        assert res["error"] == "blocked"

    def test_extract_full_enriches_top_posts(self):
        """--extract-full triggers full-page extraction for top results."""
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": _REDDIT_RSS_SAMPLE, "status": "success",
                                      "status_code": 200, "errors": []}), \
                mock.patch("scout_it.social.reddit._enrich_with_full_content",
                           side_effect=lambda posts, m: [{**p, "full_content": "FULL"} for p in posts]):
            res = reddit_search("python", max_results=3, extract_full=True)
        assert res["result_count"] == 3
        assert all(p.get("full_content") == "FULL" for p in res["posts"])

    def test_no_input_reports_error(self):
        res = RedditProvider().search()
        assert res["error"] == "no_input"

    def test_social_search_passes_user_to_reddit(self):
        """The orchestrator forwards --user to the Reddit provider."""
        user_feed = ('<feed xmlns="http://www.w3.org/2005/Atom">'
                     '<entry><title>U post</title>'
                     '<link href="https://www.reddit.com/r/x/comments/9/u/"/>'
                     '<author><name>/u/spez</name></author>'
                     '<published>2026-08-14T10:00:00+00:00</published>'
                     '<id>t3_9</id><content type="html">u</content></entry>'
                     '</feed>')
        with mock.patch("scout_it.social.reddit._fetch_feed",
                        return_value={"xml": user_feed, "status": "success",
                                      "status_code": 200, "errors": []}):
            result = social_search(platform="reddit", user="spez", max_results=5)
        assert result["total_results"] == 1
        assert "reddit" in result["platforms"]


# ---------------------------------------------------------------------------
# Discord provider (channel-id only, no query fallback)
# ---------------------------------------------------------------------------

_DISCORD_RAW = {
    "channel_id": "123", "message_count": 1,
    "messages": [{"id": "1", "author": "alice", "content": "hi",
                  "timestamp": "t", "edited_timestamp": None,
                  "attachments": [], "reply_to": None}],
}


class TestDiscordProvider:
    def test_channel_id_capability_executes(self):
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            with mock.patch("scout_it.social.discord.requests.get") as rg:
                rg.return_value = _FakeResp(200, [
                    {"id": "1", "author": {"username": "alice"}, "content": "hi",
                     "timestamp": "t", "attachments": []}
                ])
                res = DiscordProvider().search(channel_id="123", max_results=5)
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_CHANNEL_ID]
        assert res["result_count"] == 1
        assert res["results"][0]["platform"] == "discord"
        assert res["results"][0]["author"] == "alice"

    def test_no_channel_id_and_no_query_reports_no_input(self):
        # No channel-id AND no query -> nothing to search (query is now the
        # fallback, but it's empty).
        res = DiscordProvider().search(max_results=5)
        assert res["error"] == "no_input"
        assert res["result_count"] == 0

    def test_channel_arg_with_query_falls_back_to_ddgs(self):
        # --channel is unsupported, but a --query is present -> falls back to
        # the query (DDGS) path. Mock DDGS so no network call is made.
        with mock.patch("scout_it.social.discord.discord_ddgs_search",
                        return_value={"query": "AI", "result_count": 1,
                                      "results": [{"title": "AI server",
                                                   "content": "discuss AI",
                                                   "url": "https://discord.com/channels/x"}],
                                      "source": "ddgs_web"}):
            res = DiscordProvider().search(query="AI", channel="durov", max_results=5)
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]
        assert res["result_count"] == 1
        assert "DISCORD_BOT_TOKEN" in (res.get("note") or "")

    def test_channel_arg_without_query_reports_no_input(self):
        # --channel unsupported, no query -> no_input (was unsupported_capability
        # before Discord had a query fallback).
        res = DiscordProvider().search(channel="durov")
        assert res["error"] == "no_input"

    def test_auth_required_propagates(self):
        os.environ.pop("DISCORD_BOT_TOKEN", None)
        res = DiscordProvider().search(channel_id="123", max_results=5)
        assert res["error"] == "auth_required"


# ---------------------------------------------------------------------------
# Discord DDGS + bot-guild-search enhancements
# ---------------------------------------------------------------------------

class TestDiscordQueryEnhancements:
    def test_query_no_token_uses_ddgs_and_notes_token(self):
        """Without a token, --query runs DDGS and the note tells the user to
        set DISCORD_BOT_TOKEN for better results."""
        os.environ.pop("DISCORD_BOT_TOKEN", None)
        try:
            with mock.patch("scout_it.social.discord.discord_ddgs_search",
                            return_value={"query": "AI", "result_count": 1,
                                          "results": [{"title": "AI discord",
                                                       "content": "discuss AI here",
                                                       "url": "https://discord.com/channels/1/2/3"}],
                                          "source": "ddgs_web"}):
                res = DiscordProvider().search(query="AI", max_results=5)
        finally:
            pass
        assert res["error"] is None
        assert res["capabilities_used"] == [CAP_QUERY]
        assert res["result_count"] == 1
        assert "DISCORD_BOT_TOKEN" in (res.get("note") or "")
        assert res["results"][0]["url"] == "https://discord.com/channels/1/2/3"

    def test_query_with_token_runs_bot_search_and_ddgs(self):
        """With a token, --query runs both bot guild search AND DDGS, merging
        results from both sources."""
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            with mock.patch("scout_it.social.discord.discord_bot_search",
                            return_value={"query": "AI", "result_count": 1,
                                          "guilds_scanned": 2,
                                          "messages": [{"content": "AI is great",
                                                        "author": "alice",
                                                        "channel_id": "1",
                                                        "channel_name": "general",
                                                        "guild_id": "10",
                                                        "guild_name": "MyServer",
                                                        "id": "100", "timestamp": "t"}]}), \
                    mock.patch("scout_it.social.discord.discord_ddgs_search",
                            return_value={"query": "AI", "result_count": 1,
                                          "results": [{"title": "Public AI server",
                                                       "content": "AI discussion",
                                                       "url": "https://discord.com/channels/x"}],
                                          "source": "ddgs_web"}):
                res = DiscordProvider().search(query="AI", max_results=10)
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)
        assert res["error"] is None
        assert res["result_count"] == 2  # 1 bot + 1 ddgs
        sources = [r["metadata"].get("source") for r in res["results"]]
        assert "bot_guild_search" in sources
        assert "ddgs_web" in sources
        assert "scanned 2 guild" in (res.get("note") or "")

    def test_ddgs_search_dedupes_by_url(self):
        from scout_it.social.discord import discord_ddgs_search, _ddgs_text
        with mock.patch("scout_it.social.discord._ddgs_text",
                        side_effect=lambda q, m: (
                            [{"href": "https://discord.com/a", "title": "A", "body": "AI"}]
                            if "site:discord.com" in q else
                            [{"href": "https://discord.com/a", "title": "A2", "body": "AI"},
                             {"href": "https://discord.com/b", "title": "B", "body": "other"}]
                        )):
            r = discord_ddgs_search("AI", max_results=5)
        # URL /discord.com/a appears in both searches -> deduped to 2 unique.
        assert r["result_count"] == 2
        urls = [x["url"] for x in r["results"]]
        assert len(set(urls)) == 2

    def test_rank_discord_results_prioritizes_query_match(self):
        from scout_it.social.discord import _rank_discord_results
        items = [
            {"title": "unrelated", "content": "cats"},
            {"title": "AI discussion", "content": "talk about AI"},
            {"title": "general", "content": "AI and ML"},
        ]
        ranked = _rank_discord_results(items, "AI", 3)
        assert ranked[0]["title"] == "AI discussion"
        assert ranked[-1]["title"] == "unrelated"

    def test_normalize_message_uses_embed_when_no_content(self):
        from scout_it.social.discord import _normalize_message
        m = {"id": "1", "author": {"username": "bob"}, "content": "",
             "embeds": [{"title": "Embed Title", "description": "Embed desc"}],
             "timestamp": "t"}
        norm = _normalize_message(m, "123", "10", "Guild", "general")
        assert norm["content"] == "Embed Title\nEmbed desc"
        assert norm["author"] == "bob"
        assert norm["channel_name"] == "general"
        assert norm["guild_name"] == "Guild"

    def test_channel_id_pagination_fetches_multiple_pages(self):
        """When max_results > 100, multiple pages are fetched via the before
        cursor until the limit is reached."""
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            page1 = [{"id": str(i), "author": {"username": "u"}, "content": f"msg {i}",
                      "timestamp": "t", "attachments": []} for i in range(100, 0, -1)]
            page2 = [{"id": str(i), "author": {"username": "u"}, "content": f"old {i}",
                      "timestamp": "t", "attachments": []} for i in range(50, 0, -1)]
            with mock.patch("scout_it.social.discord._api_get") as ag:
                # channel meta, then page1, then page2 (<100 = exhausted)
                ag.side_effect = [
                    {"ok": False, "data": None, "status_code": 403, "error": "no"},  # channel meta
                    {"ok": True, "data": page1, "status_code": 200, "error": None},
                    {"ok": True, "data": page2, "status_code": 200, "error": None},
                ]
                res = discord_channel_messages("123", max_results=150)
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)
        assert res["message_count"] == 150
        # 3 _api_get calls: channel-meta (failed), page1, page2.
        assert ag.call_count == 3

    def test_bot_search_filters_by_query(self):
        """discord_bot_search only keeps messages whose content matches the query."""
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            with mock.patch("scout_it.social.discord._api_get") as ag:
                ag.side_effect = [
                    {"ok": True, "data": [{"id": "1", "name": "G"}], "status_code": 200, "error": None},  # guilds
                    {"ok": True, "data": [{"id": "10", "name": "general", "type": 0}], "status_code": 200, "error": None},  # channels
                    {"ok": True, "data": [
                        {"id": "1", "author": {"username": "a"}, "content": "AI is cool", "timestamp": "t"},
                        {"id": "2", "author": {"username": "b"}, "content": "cats", "timestamp": "t"},
                    ], "status_code": 200, "error": None},  # messages
                ]
                r = discord_bot_search("AI", max_results=10)
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)
        assert r["result_count"] == 1
        assert r["messages"][0]["content"] == "AI is cool"
        assert r["guilds_scanned"] == 1

    def test_bot_search_requires_token(self):
        os.environ.pop("DISCORD_BOT_TOKEN", None)
        r = discord_bot_search("AI")
        assert r["error"] == "auth_required"

    def test_extract_full_enriches_ddgs_urls(self):
        os.environ.pop("DISCORD_BOT_TOKEN", None)
        try:
            with mock.patch("scout_it.social.discord.discord_ddgs_search",
                            return_value={"query": "AI", "result_count": 1,
                                          "results": [{"title": "AI", "content": "x",
                                                       "url": "https://discord.com/channels/1"}],
                                          "source": "ddgs_web"}), \
                    mock.patch("scout_it.social.discord._enrich_discord_with_full_content",
                               side_effect=lambda items, m: [{**i, "full_content": "FULL"} for i in items]):
                res = DiscordProvider().search(query="AI", max_results=5, extract_full=True)
        finally:
            pass
        assert res["error"] is None
        assert res["result_count"] == 1


# ---------------------------------------------------------------------------
# Instagram provider (DDGS query + profile scraping + Playwright fallback)
# ---------------------------------------------------------------------------

class TestInstagramProvider:
    """Capability declarations and registry for Instagram."""

    def test_capabilities(self):
        from scout_it.social.instagram import InstagramProvider
        from scout_it.social.base import CAP_QUERY, CAP_PROFILE
        assert CAP_QUERY in InstagramProvider.SUPPORTED_CAPABILITIES
        assert CAP_PROFILE in InstagramProvider.SUPPORTED_CAPABILITIES
        assert InstagramProvider.FALLBACK_CAPABILITY == CAP_QUERY

    def test_registered(self):
        from scout_it.social import get, available_platforms
        assert "instagram" in available_platforms()
        prov = get("instagram")
        assert prov is not None
        assert prov.platform == "instagram"

    def test_no_input_returns_error(self):
        from scout_it.social.instagram import InstagramProvider
        prov = InstagramProvider()
        res = prov.search(query=None, profile=None, max_results=5)
        assert res.get("error") == "no_input"

    def test_invalid_username(self):
        from scout_it.social.instagram import instagram_profile_search
        res = instagram_profile_search("invalid user name!", max_results=5)
        assert res.get("error") == "invalid_username"

    def test_empty_username(self):
        from scout_it.social.instagram import instagram_profile_search
        res = instagram_profile_search("", max_results=5)
        assert res.get("error") == "no_input"


class TestInstagramDDGS:
    """DDGS web discovery (query capability, no login)."""

    def test_ddgs_search_returns_results(self):
        from scout_it.social import instagram
        fake = [{"title": "Python on Instagram", "body": "python coding",
                 "href": "https://instagram.com/p/abc123/"},
                {"title": "Insta Python", "body": "python programming",
                 "href": "https://instagram.com/p/def456/"}]
        with mock.patch.object(instagram, "_ddgs_text", return_value=fake), \
                mock.patch.dict("os.environ", {}, clear=True):
            res = instagram.instagram_ddgs_search("python", max_results=10)
        assert res["result_count"] == 2
        assert res["source"] == "ddgs_web"
        assert res["results"][0]["url"].startswith("https://instagram.com")

    def test_ddgs_dedup_by_url(self):
        from scout_it.social import instagram
        fake = [{"title": "A", "body": "a", "href": "https://instagram.com/p/1/"},
                {"title": "B", "body": "b", "href": "https://instagram.com/p/1/"},
                {"title": "C", "body": "c", "href": "https://instagram.com/p/2/"}]
        with mock.patch.object(instagram, "_ddgs_text", return_value=fake):
            res = instagram.instagram_ddgs_search("test", max_results=10)
        assert res["result_count"] == 2  # dedup by URL

    def test_ddgs_ranking_title_over_body(self):
        from scout_it.social import instagram
        fake = [{"title": "cooking recipe", "body": "no match here",
                 "href": "https://instagram.com/p/1/"},
                {"title": "no match", "body": "cooking recipe ideas",
                 "href": "https://instagram.com/p/2/"}]
        with mock.patch.object(instagram, "_ddgs_text", return_value=fake):
            res = instagram.instagram_ddgs_search("cooking recipe", max_results=10)
        # title match scores higher than body match
        assert res["results"][0]["title"] == "cooking recipe"

    def test_ddgs_empty_query(self):
        from scout_it.social import instagram
        res = instagram.instagram_ddgs_search("", max_results=10)
        assert res.get("error") == "no_input"

    def test_ddgs_no_results(self):
        from scout_it.social import instagram
        with mock.patch.object(instagram, "_ddgs_text", return_value=[]):
            res = instagram.instagram_ddgs_search("zzz", max_results=5)
        assert res["result_count"] == 0
        assert res["results"] == []

    def test_provider_query_executes_ddgs(self):
        from scout_it.social.instagram import InstagramProvider
        from scout_it.social import instagram
        fake = [{"title": "AI Instagram", "body": "ai stuff",
                 "href": "https://instagram.com/p/1/"}]
        with mock.patch.object(instagram, "_ddgs_text", return_value=fake), \
                mock.patch.dict("os.environ", {}, clear=True):
            prov = InstagramProvider()
            res = prov.search(query="AI", max_results=5)
        assert res.get("platform") == "instagram"
        assert res["result_count"] == 1
        assert "INSTAGRAM_SESSION_ID is not set" in (res.get("note") or "")

    def test_provider_query_with_session_no_note(self):
        from scout_it.social.instagram import InstagramProvider
        from scout_it.social import instagram
        fake = [{"title": "AI", "body": "ai", "href": "https://instagram.com/p/1/"}]
        with mock.patch.object(instagram, "_ddgs_text", return_value=fake), \
                mock.patch.dict("os.environ", {"INSTAGRAM_SESSION_ID": "test123"}, clear=False):
            prov = InstagramProvider()
            res = prov.search(query="AI", max_results=5)
        assert res.get("note") is None  # no "not set" note when session present


class TestInstagramProfileScraping:
    """Profile scraping: requests → Playwright → DDGS fallback."""

    def test_profile_requests_success_json_ld(self):
        from scout_it.social import instagram
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type":"BlogPosting","headline":"My Post","articleBody":"Hello world",
         "datePublished":"2024-01-01T00:00:00Z","url":"https://instagram.com/p/abc/",
         "image":{"url":"https://example.com/img.jpg"},
         "author":{"name":"testuser"}}
        </script></head><body>...padding...</body></html>'''
        req_res = {"ok": True, "html": html, "status_code": 200, "error": None}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res), \
                mock.patch.dict("os.environ", {}, clear=True):
            res = instagram.instagram_profile_search("testuser", max_results=10)
        assert res["result_count"] >= 1
        assert res["posts"][0]["content"] == "Hello world"
        assert res["posts"][0]["author"] == "testuser"

    def test_profile_login_wall_falls_back_to_ddgs(self):
        from scout_it.social import instagram
        req_res = {"ok": False, "html": None, "status_code": 302,
                   "error": "login_wall"}
        pw_res = {"ok": False, "html": None, "error": "login_wall (Playwright redirected)"}
        ddgs_fake = [{"title": "testuser profile", "body": "see posts",
                      "href": "https://instagram.com/testuser/"}]
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res), \
                mock.patch.object(instagram, "_fetch_profile_playwright", return_value=pw_res), \
                mock.patch.object(instagram, "_ddgs_text", return_value=ddgs_fake), \
                mock.patch.dict("os.environ", {}, clear=True):
            res = instagram.instagram_profile_search("testuser", max_results=5)
        assert res["source"] == "ddgs_web"
        assert res["result_count"] >= 1
        assert "login_wall" in " ".join(res.get("notes", []))

    def test_profile_playwright_success(self):
        from scout_it.social import instagram
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type":"SocialMediaPosting","articleBody":"Playwright post",
         "datePublished":"2024-06-01T12:00:00Z","url":"https://instagram.com/p/xyz/",
         "author":{"name":"pwuser"}}
        </script></head><body>...padding...</body></html>'''
        req_res = {"ok": False, "html": None, "status_code": 302, "error": "login_wall"}
        pw_res = {"ok": True, "html": html, "error": None}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res), \
                mock.patch.object(instagram, "_fetch_profile_playwright", return_value=pw_res), \
                mock.patch.dict("os.environ", {}, clear=True):
            res = instagram.instagram_profile_search("pwuser", max_results=5)
        assert res["result_count"] >= 1
        assert res["posts"][0]["content"] == "Playwright post"
        assert "fetched via Playwright" in " ".join(res.get("notes", []))

    def test_profile_all_tiers_fail(self):
        from scout_it.social import instagram
        req_res = {"ok": False, "html": None, "status_code": 302, "error": "login_wall"}
        pw_res = {"ok": False, "html": None, "error": "login_wall"}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res), \
                mock.patch.object(instagram, "_fetch_profile_playwright", return_value=pw_res), \
                mock.patch.object(instagram, "_ddgs_text", return_value=[]), \
                mock.patch.dict("os.environ", {}, clear=True):
            res = instagram.instagram_profile_search("ghost", max_results=5)
        assert res["result_count"] == 0
        assert "INSTAGRAM_SESSION_ID is not set" in " ".join(res.get("notes", []))

    def test_profile_404(self):
        from scout_it.social import instagram
        req_res = {"ok": False, "html": None, "status_code": 404,
                   "error": "Instagram profile 'ghost' not found."}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res), \
                mock.patch.object(instagram, "_fetch_profile_playwright",
                                  return_value={"ok": False, "html": None, "error": "login_wall"}), \
                mock.patch.object(instagram, "_ddgs_text", return_value=[]), \
                mock.patch.dict("os.environ", {}, clear=True):
            res = instagram.instagram_profile_search("ghost", max_results=5)
        assert res["result_count"] == 0

    def test_profile_session_cookie_used(self):
        from scout_it.social import instagram
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type":"BlogPosting","articleBody":"Session post","author":{"name":"suser"},
         "url":"https://instagram.com/p/s1/"}
        </script></head><body>...padding...</body></html>'''
        req_res = {"ok": True, "html": html, "status_code": 200, "error": None}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res) as mock_req, \
                mock.patch.dict("os.environ", {"INSTAGRAM_SESSION_ID": "sess123"}, clear=False):
            res = instagram.instagram_profile_search("suser", max_results=5)
        assert res["result_count"] >= 1
        # No "not set" note when session is present
        assert "INSTAGRAM_SESSION_ID is not set" not in " ".join(res.get("notes", []))

    def test_provider_profile_executes(self):
        from scout_it.social.instagram import InstagramProvider
        from scout_it.social import instagram
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type":"BlogPosting","headline":"Post","articleBody":"Content",
         "author":{"name":"myuser"},"url":"https://instagram.com/p/a/"}
        </script></head><body>...padding...</body></html>'''
        req_res = {"ok": True, "html": html, "status_code": 200, "error": None}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res), \
                mock.patch.dict("os.environ", {}, clear=True):
            prov = InstagramProvider()
            res = prov.search(profile="myuser", max_results=5)
        assert res.get("platform") == "instagram"
        assert res["result_count"] >= 1
        assert res["results"][0]["author"] == "myuser"

    def test_json_ld_extraction_multiple_blocks(self):
        from scout_it.social import instagram
        html = '''<html><head>
        <script type="application/ld+json">
        {"@type":"BlogPosting","articleBody":"First","author":{"name":"u"},"url":"https://instagram.com/p/1/"}
        </script>
        <script type="application/ld+json">
        {"@type":"SocialMediaPosting","articleBody":"Second","author":{"name":"u"},"url":"https://instagram.com/p/2/"}
        </script></head><body>...padding...</body></html>'''
        blocks = instagram._extract_json_ld(html)
        assert len(blocks) == 2

    def test_json_ld_extraction_empty(self):
        from scout_it.social import instagram
        assert instagram._extract_json_ld("<html>no scripts</html>") == []

    def test_username_strips_at_prefix(self):
        from scout_it.social import instagram
        req_res = {"ok": False, "html": None, "status_code": 302, "error": "login_wall"}
        with mock.patch.object(instagram, "_fetch_profile_requests", return_value=req_res) as mr, \
                mock.patch.object(instagram, "_fetch_profile_playwright",
                                  return_value={"ok": False, "html": None, "error": "blocked"}), \
                mock.patch.object(instagram, "_ddgs_text", return_value=[]), \
                mock.patch.dict("os.environ", {}, clear=True):
            instagram.instagram_profile_search("@testuser", max_results=5)
        # Verify the username passed to _fetch_profile_requests has @ stripped
        call_args = mr.call_args
        assert call_args[0][0] == "testuser"  # first positional arg


# ---------------------------------------------------------------------------
# Orchestrator: capability-based fallback across multiple providers
# ---------------------------------------------------------------------------

class TestSocialSearchOrchestrator:
    def test_channel_arg_telegram_executes_reddit_falls_back_discord_ddgs(self):
        """The exact scenario from the spec: --channel durov --query 'AI'
        across telegram,reddit,discord. Discord now falls back to its DDGS
        query path (no token) instead of hard-failing."""
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value=_TELEGRAM_CHANNEL_RAW), \
                mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru, \
                mock.patch("scout_it.social.discord.discord_ddgs_search",
                           return_value={"query": "AI", "result_count": 0,
                                         "results": [], "source": "ddgs_web"}), \
                mock.patch.dict("os.environ", {}, clear=True):
            rg.return_value = _FakeResp(200, {"data": {"children": []}})
            ru.quote = lambda s: s
            res = social_search(
                query="AI", platform="telegram,reddit,discord",
                channel="durov", max_results=5)

        by_plat = res["results_by_platform"]
        assert by_plat["telegram"]["capabilities_used"] == [CAP_CHANNEL]
        assert by_plat["reddit"]["capabilities_used"] == [CAP_QUERY]  # fallback
        # Discord now executes the query (DDGS) instead of failing.
        assert by_plat["discord"]["capabilities_used"] == [CAP_QUERY]
        assert by_plat["discord"]["error"] is None
        assert "DISCORD_BOT_TOKEN" in (by_plat["discord"].get("note") or "")

        assert res["total_results"] == 1  # telegram only (reddit+discord returned 0)
        # Discord is NOT a failure anymore (it ran the DDGS path).
        plat_names = {f["platform"] for f in res["failures"]}
        assert "discord" not in plat_names
        assert "telegram" not in plat_names
        assert "reddit" not in plat_names

    def test_all_platforms_default(self):
        with mock.patch("scout_it.social.telegram.telegram_search",
                        return_value=_TELEGRAM_SEARCH_RAW), \
                mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru, \
                mock.patch("scout_it.social.discord.discord_ddgs_search",
                           return_value={"query": "AI", "result_count": 0,
                                         "results": [], "source": "ddgs_web"}), \
                mock.patch("scout_it.social.instagram._ddgs_text",
                           return_value=[]), \
                mock.patch.dict("os.environ", {}, clear=True):
            rg.return_value = _FakeResp(200, {"data": {"children": []}})
            ru.quote = lambda s: s
            res = social_search(query="AI", max_results=5)
        assert set(res["platforms"]) == {"telegram", "reddit", "discord", "instagram"}
        # All four providers now run.
        assert res["provider_count"] == 4

    def test_single_platform(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value=_TELEGRAM_CHANNEL_RAW):
            res = social_search(platform="telegram", channel="durov",
                                max_results=5)
        assert res["platforms"] == ["telegram"]
        assert res["total_results"] == 1
        assert res["failures"] == []

    def test_unknown_platform_reported_as_failure(self):
        res = social_search(platform="telegram,fakemedia", query="AI",
                            max_results=2)
        unknown = [f for f in res["failures"]
                   if f["error"] == "unknown_platform"]
        assert len(unknown) == 1
        assert unknown[0]["platform"] == "fakemedia"

    def test_one_provider_failure_does_not_stop_others(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value=_TELEGRAM_CHANNEL_RAW), \
                mock.patch("scout_it.social.reddit.requests.get") as rg, \
                mock.patch("scout_it.social.reddit.requests.utils") as ru, \
                mock.patch.dict("os.environ", {}, clear=True):
            rg.return_value = _FakeResp(403)  # reddit blocked
            ru.quote = lambda s: s
            res = social_search(
                query="AI", platform="telegram,reddit",
                channel="durov", max_results=5)
        # Telegram still returns results; reddit is in failures.
        assert res["total_results"] == 1
        reddit_fail = [f for f in res["failures"] if f["platform"] == "reddit"]
        assert len(reddit_fail) == 1
        assert reddit_fail[0]["error"] == "blocked"

    def test_parallel_vs_sequential_same_results(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value=_TELEGRAM_CHANNEL_RAW):
            par = social_search(platform="telegram", channel="durov",
                                max_results=5, parallel=True)
            seq = social_search(platform="telegram", channel="durov",
                                max_results=5, parallel=False)
        assert par["total_results"] == seq["total_results"]
        assert par["results"] == seq["results"]

    def test_aggregated_results_normalized(self):
        with mock.patch("scout_it.social.telegram.telegram_channel",
                        return_value=_TELEGRAM_CHANNEL_RAW):
            res = social_search(platform="telegram", channel="durov",
                                max_results=5)
        for item in res["results"]:
            assert set(item.keys()) == {
                "platform", "author", "content", "url", "timestamp", "metadata"}

    def test_no_input_at_all(self):
        res = social_search()
        # Every provider reports no_input / unsupported; no results.
        assert res["total_results"] == 0
        assert len(res["failures"]) >= 1


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------

class TestBackwardsCompatibility:
    def test_legacy_functions_importable(self):
        assert callable(social.telegram_channel)
        assert callable(social.telegram_search)
        assert callable(social.discord_channel_messages)
        assert callable(social.reddit_search)

    def test_legacy_parsers_importable(self):
        assert callable(social._parse_telegram_primary)
        assert callable(social._parse_telegram_enhanced)

    def test_top_level_package_exports_social_search(self):
        import scout_it
        assert hasattr(scout_it, "social_search")
        assert callable(scout_it.social_search)

    def test_legacy_mock_patch_path_still_works(self):
        """Existing tests patch scout_it.social.requests.get — that path must
        still resolve because requests is re-exported on the package."""
        os.environ["DISCORD_BOT_TOKEN"] = "fake"
        try:
            with mock.patch("scout_it.social.requests.get") as rg:
                rg.return_value = _FakeResp(200, [
                    {"id": "1", "author": {"username": "a"}, "content": "hi",
                     "timestamp": "t", "attachments": []}
                ])
                out = social.discord_channel_messages("123456789012345678")
            assert out["message_count"] == 1
        finally:
            os.environ.pop("DISCORD_BOT_TOKEN", None)
