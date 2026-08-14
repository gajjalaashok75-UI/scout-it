"""
Test web search RSS integration with --category support.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_web_feeds_loaded():
    """Test that web search RSS feeds are loaded."""
    import importlib
    _web_search_feed = importlib.import_module('.web_search_feed', 'scout_it.web-search')
    WEB_SEARCH_FEEDS = _web_search_feed.WEB_SEARCH_FEEDS

    assert len(WEB_SEARCH_FEEDS) > 0, "No feeds loaded"
    
    key_categories = ['ai', 'engineering', 'cloud', 'devops', 'research']
    for cat in key_categories:
        assert cat in WEB_SEARCH_FEEDS, f"Missing category: {cat}"
        feeds = WEB_SEARCH_FEEDS[cat]
        assert feeds, f"Category {cat} has no feeds"

    total = sum(len(feeds) for feeds in WEB_SEARCH_FEEDS.values())
    assert total > 0


def test_web_rss_provider():
    """Test WebSearchRSSProvider."""
    import importlib
    _web_search_rss = importlib.import_module('.web_search_rss', 'scout_it.web-search')
    WebSearchRSSProvider = _web_search_rss.WebSearchRSSProvider
    get_available_web_categories = _web_search_rss.get_available_web_categories

    provider = WebSearchRSSProvider()

    ai_urls = provider.get_feed_urls('ai')
    assert ai_urls, "AI category returned no feed URLs"

    cloud_urls = provider.get_feed_urls('cloud')
    assert cloud_urls, "Cloud category returned no feed URLs"

    categories = get_available_web_categories()
    assert categories, "No web categories available"
    for expected in ['ai', 'engineering', 'cloud']:
        assert expected in categories, f"Missing category {expected}"


def test_web_category_providers():
    """Test web category provider functions."""
    from scout_it.web_category_providers import (
        get_available_web_categories,
        get_web_category_providers
    )

    categories = get_available_web_categories()
    assert categories, "No web categories available"

    for cat in ['ai', 'engineering', 'cloud']:
        providers = get_web_category_providers(cat)
        assert providers, f"Category {cat} returned no providers"


def main():
    """Run all tests (asserts inside each test_* function raise on failure)."""
    test_web_feeds_loaded()
    test_web_rss_provider()
    test_web_category_providers()
    print("All web search RSS integration tests passed.")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
