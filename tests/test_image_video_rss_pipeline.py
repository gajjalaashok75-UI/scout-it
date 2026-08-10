"""Tests for the unified image/video RSS discovery + ranking pipeline.

These tests are fully offline: RSS parsing is exercised against inline XML
fixtures, and the parallel transport / DDGS discovery layers are mocked so the
unified discover -> rank -> output flow is deterministic.
"""

from unittest import mock

import pytest

from scout_it.commands import image_rss, video_rss
from scout_it.commands.image_search_feed import IMAGE_SEARCH_FEEDS, flickr_tag_feed
from scout_it.commands.video_search_feed import VIDEO_SEARCH_FEEDS, youtube_channel_feed
from scout_it.commands.image_category_providers import (
    get_available_image_categories,
    get_image_category_feeds,
    fetch_image_category_feeds,
)
from scout_it.commands.video_category_providers import (
    get_available_video_categories,
    get_video_category_feeds,
    fetch_video_category_feeds,
)


FLICKR_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Flickr test feed</title>
    <item>
      <title>Sunset over mountains</title>
      <link>https://www.flickr.com/photos/user/123/</link>
      <pubDate>Mon, 10 Aug 2026 10:00:00 GMT</pubDate>
      <media:content url="https://live.staticflickr.com/1/123_b.jpg" width="1024" height="768" medium="image"/>
      <media:thumbnail url="https://live.staticflickr.com/1/123_s.jpg" width="75" height="75"/>
    </item>
    <item>
      <title>Forest canopy</title>
      <link>https://www.flickr.com/photos/user/456/</link>
      <pubDate>Mon, 09 Aug 2026 10:00:00 GMT</pubDate>
      <media:content url="https://live.staticflickr.com/1/456_b.jpg" width="800" height="600" medium="image"/>
    </item>
  </channel>
</rss>
"""

YOUTUBE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <title>Test channel</title>
  <entry>
    <title>How rockets work</title>
    <link href="https://www.youtube.com/watch?v=abc12345678" rel="alternate"/>
    <published>2026-08-10T10:00:00+00:00</published>
    <author><name>Test Author</name></author>
    <media:group>
      <media:description>Rocket engineering explained.</media:description>
      <media:thumbnail url="https://i1.ytimg.com/vi/abc12345678/hqdefault.jpg"/>
    </media:group>
  </entry>
  <entry>
    <title>Space telescopes</title>
    <link href="https://www.youtube.com/watch?v=def45678901" rel="alternate"/>
    <published>2026-08-09T10:00:00+00:00</published>
    <media:thumbnail url="https://i1.ytimg.com/vi/def45678901/hqdefault.jpg"/>
  </entry>
</feed>
"""


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------
def test_image_search_feeds_populated():
    assert IMAGE_SEARCH_FEEDS, "image feed registry should not be empty"
    for category, feeds in IMAGE_SEARCH_FEEDS.items():
        assert isinstance(category, str) and category
        assert feeds, f"category {category!r} has no feeds"
        for entry in feeds:
            assert entry["url"].startswith("https://"), entry


def test_video_search_feeds_populated():
    assert VIDEO_SEARCH_FEEDS, "video feed registry should not be empty"
    for category, feeds in VIDEO_SEARCH_FEEDS.items():
        assert feeds, f"category {category!r} has no feeds"
        for entry in feeds:
            url = entry["url"]
            assert "youtube.com/feeds/videos.xml" in url, url


def test_flickr_tag_feed_builder():
    assert flickr_tag_feed("nature") == (
        "https://www.flickr.com/services/feeds/photos_public.gne?tags=nature&format=rss_200"
    )


def test_youtube_channel_feed_builder():
    assert youtube_channel_feed("UC123") == (
        "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"
    )


def test_image_category_providers_registry():
    cats = get_available_image_categories()
    assert "nature" in cats and "space" in cats
    assert get_image_category_feeds("nature"), "nature should have providers"
    assert get_image_category_feeds("does-not-exist") == []


def test_video_category_providers_registry():
    cats = get_available_video_categories()
    assert "technology" in cats and "science" in cats
    assert get_video_category_feeds("science"), "science should have providers"
    assert get_video_category_feeds("nope") == []


# ---------------------------------------------------------------------------
# Parser tests (offline, inline fixtures)
# ---------------------------------------------------------------------------
def test_parse_image_feed_extracts_media():
    entries = image_rss.parse_image_feed(FLICKR_RSS, feed_url="https://flickr.com/test")
    assert len(entries) == 2
    first = entries[0]
    assert first["title"] == "Sunset over mountains"
    assert first["image_url"] == "https://live.staticflickr.com/1/123_b.jpg"
    assert first["thumbnail_url"] == "https://live.staticflickr.com/1/123_s.jpg"
    assert first["source_url"].startswith("https://www.flickr.com/")
    assert first["width"] == 1024 and first["height"] == 768
    assert first["publish_date"]
    # Ranking fields present
    assert "body" in first and "source" in first


def test_parse_image_feed_skips_items_without_media():
    rss_no_media = """<rss version="2.0"><channel>
      <item><title>No image here</title><link>https://example.com/x</link></item>
    </channel></rss>"""
    assert image_rss.parse_image_feed(rss_no_media) == []


def test_parse_image_feed_empty_and_garbage():
    assert image_rss.parse_image_feed("") == []
    assert image_rss.parse_image_feed("not xml at all") == []


def test_parse_video_feed_extracts_youtube():
    entries = video_rss.parse_video_feed(YOUTUBE_ATOM, feed_url="https://youtube.com/test")
    assert len(entries) == 2
    first = entries[0]
    assert first["title"] == "How rockets work"
    assert first["url"] == "https://www.youtube.com/watch?v=abc12345678"
    assert first["thumbnail"] == "https://i1.ytimg.com/vi/abc12345678/hqdefault.jpg"
    assert "Rocket engineering" in first["description"]
    assert first["publish_date"].startswith("2026-08-10")


def test_parse_video_feed_skips_entries_without_link():
    atom_no_link = """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Orphan</title><published>2026-08-10T10:00:00Z</published></entry>
    </feed>"""
    assert video_rss.parse_video_feed(atom_no_link) == []


# ---------------------------------------------------------------------------
# Parallel transport tests (mocked)
# ---------------------------------------------------------------------------
def test_fetch_image_feed_entries_dedupes_by_image_url():
    feed_url = "https://example.com/img.rss"
    from scout_it.commands import image_rss as img_mod
    import types
    fake_provider = mock.Mock()
    fake_provider.fetch_multiple_feeds.return_value = [
        (feed_url, FLICKR_RSS), (feed_url, FLICKR_RSS),
    ]
    fake_tcr = types.SimpleNamespace(
        TechCrunchRSSProvider=lambda: fake_provider,
        RSSProvider=lambda: fake_provider,
    )
    with mock.patch("importlib.import_module", return_value=fake_tcr):
        entries = img_mod.fetch_image_feed_entries([feed_url], limit=50)
    urls = [e["image_url"] for e in entries]
    assert len(urls) == len(set(urls)), "image URLs should be deduped"
    assert len(entries) == 2


def test_fetch_video_feed_entries_dedupes_by_url():
    feed_url = "https://example.com/vid.xml"
    from scout_it.commands import video_rss as vid_mod
    import types
    fake_provider = mock.Mock()
    fake_provider.fetch_multiple_feeds.return_value = [(feed_url, YOUTUBE_ATOM)]
    fake_tcr = types.SimpleNamespace(
        TechCrunchRSSProvider=lambda: fake_provider,
        RSSProvider=lambda: fake_provider,
    )
    with mock.patch("importlib.import_module", return_value=fake_tcr):
        entries = vid_mod.fetch_video_feed_entries([feed_url], limit=50)
    assert len(entries) == 2
    assert entries[0]["url"].startswith("https://www.youtube.com/watch")


# ---------------------------------------------------------------------------
# Category provider orchestration tests (mocked)
# ---------------------------------------------------------------------------
def test_fetch_image_category_feeds_aggregates_and_dedupes():
    feed_url = IMAGE_SEARCH_FEEDS["nature"][0]["url"]
    with mock.patch(
        "scout_it.commands.image_category_providers.fetch_image_feed_entries",
        return_value=[
            {"title": "a", "image_url": "http://x/1.jpg", "source_url": "http://x/1"},
            {"title": "b", "image_url": "http://x/2.jpg", "source_url": "http://x/2"},
        ],
    ):
        results = fetch_image_category_feeds(["nature"], "nature", max_results=50)
    assert len(results) == 2
    assert {r["image_url"] for r in results} == {"http://x/1.jpg", "http://x/2.jpg"}


def test_fetch_video_category_feeds_aggregates_and_dedupes():
    with mock.patch(
        "scout_it.commands.video_category_providers.fetch_video_feed_entries",
        return_value=[
            {"title": "a", "url": "http://y/1", "content": "http://y/1"},
            {"title": "b", "url": "http://y/2", "content": "http://y/2"},
            {"title": "dup", "url": "http://y/1", "content": "http://y/1"},
        ],
    ):
        results = fetch_video_category_feeds(["science"], "science", max_results=50)
    assert len(results) == 2  # the duplicate URL is dropped
    assert {r["url"] for r in results} == {"http://y/1", "http://y/2"}


def test_fetch_category_feeds_unknown_category_returns_empty():
    assert fetch_image_category_feeds(["nonexistent"], "x") == []
    assert fetch_video_category_feeds(["nonexistent"], "x") == []


# ---------------------------------------------------------------------------
# Unified command flow tests (mocked DDGS + RSS)
# ---------------------------------------------------------------------------
def test_image_search_unified_pipeline_with_categories():
    from dataclasses import dataclass, field
    from scout_it.commands.image import image_search

    @dataclass
    class FakeImg:
        title: str
        image_url: str
        source_url: str
        thumbnail_url: str
        width: int
        height: int
        image_size: str = ""

    fake_result = FakeImg("ddgs photo", "http://ddgs/1.jpg", "http://ddgs/1",
                          "http://ddgs/1t.jpg", 1000, 800)
    with mock.patch("scout_it.commands.image.ImageSearchEngine") as mock_engine:
        inst = mock.Mock()
        inst.execute_image_search.return_value = [fake_result]
        inst.stats = {"total": 1, "success": 1, "execution_time": 0.1}
        mock_engine.return_value = inst
        with mock.patch(
            "scout_it.commands.image.fetch_image_category_feeds",
            return_value=[
                {"title": "rss photo", "image_url": "http://rss/1.jpg",
                 "source_url": "http://rss/1", "thumbnail_url": "http://rss/1t.jpg",
                 "width": 50, "height": 50, "body": "nature", "source": "rss:flickr"},
            ],
        ):
            results, stats = image_search("nature", max_results=5, categories=["nature"])

    assert stats["pipeline"] == "unified"
    assert stats["ddgs_candidates"] == 1 and stats["rss_candidates"] == 1
    assert stats["total_candidates"] == 2
    urls = {r["image_url"] for r in results}
    assert "http://ddgs/1.jpg" in urls and "http://rss/1.jpg" in urls
    for r in results:
        assert "position" in r and "initial_rank_score" in r


def test_image_search_unified_pipeline_dimension_filter():
    from dataclasses import dataclass
    from scout_it.commands.image import image_search

    @dataclass
    class FakeImg:
        title: str
        image_url: str
        source_url: str
        thumbnail_url: str
        width: int
        height: int
        image_size: str = ""

    fake_big = FakeImg("big", "http://b/1.jpg", "http://b/1", "http://b/1t.jpg", 2000, 1500)
    with mock.patch("scout_it.commands.image.ImageSearchEngine") as mock_engine:
        inst = mock.Mock()
        inst.execute_image_search.return_value = [fake_big]
        inst.stats = {}
        mock_engine.return_value = inst
        results, stats = image_search("big", max_results=5, max_width=1000)
    assert results == [], "oversized image should be filtered out"


def test_video_search_unified_pipeline_with_categories():
    from scout_it.commands.video import video_search
    with mock.patch("scout_it.commands.video._ddgs_list_search_with_retry") as mock_ddgs:
        mock_ddgs.return_value = (
            [{"title": "ddgs vid", "content": "http://ddgs/v1", "description": "a video"}],
            {"total": 1, "success": 1, "execution_time": 0.1},
        )
        with mock.patch(
            "scout_it.commands.video.fetch_video_category_feeds",
            return_value=[
                {"title": "rss vid", "url": "http://rss/v2", "content": "http://rss/v2",
                 "description": "rss video", "thumbnail": "http://rss/t.jpg",
                 "body": "tech", "source": "rss:youtube"},
            ],
        ):
            results, stats = video_search("tech", max_results=5, categories=["technology"])

    assert stats["pipeline"] == "unified"
    assert stats["ddgs_candidates"] == 1 and stats["rss_candidates"] == 1
    urls = {r["url"] for r in results}
    assert "http://ddgs/v1" in urls and "http://rss/v2" in urls


def test_video_search_preserves_urlless_ddgs_results():
    """Stub DDGS results without a URL must not be silently dropped."""
    from scout_it.commands.video import video_search
    with mock.patch("scout_it.commands.video._ddgs_list_search_with_retry") as mock_ddgs:
        mock_ddgs.return_value = ([{"title": "stub video"}], {"success": 1})
        results, stats = video_search("dogs", max_results=3)
    assert len(results) == 1
    assert results[0]["title"] == "stub video"
