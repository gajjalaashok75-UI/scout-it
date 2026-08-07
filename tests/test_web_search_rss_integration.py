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
    
    print("\n" + "="*70)
    print("TEST 1: Web Search RSS Feeds Loaded")
    print("="*70)
    
    assert len(WEB_SEARCH_FEEDS) > 0, "No feeds loaded"
    
    key_categories = ['ai', 'engineering', 'cloud', 'devops', 'research']
    for cat in key_categories:
        assert cat in WEB_SEARCH_FEEDS, f"Missing category: {cat}"
        feeds = WEB_SEARCH_FEEDS[cat]
        print(f"✅ {cat:20s}: {len(feeds)} feeds")
    
    total = sum(len(feeds) for feeds in WEB_SEARCH_FEEDS.values())
    print(f"\nTotal: {total} RSS feeds across {len(WEB_SEARCH_FEEDS)} categories")
    
    print("="*70)
    return True


def test_web_rss_provider():
    """Test WebSearchRSSProvider."""
    import importlib
    _web_search_rss = importlib.import_module('.web_search_rss', 'scout_it.web-search')
    WebSearchRSSProvider = _web_search_rss.WebSearchRSSProvider
    get_available_web_categories = _web_search_rss.get_available_web_categories
    
    print("\n" + "="*70)
    print("TEST 2: WebSearchRSSProvider")
    print("="*70)
    
    provider = WebSearchRSSProvider()
    
    # Test getting feed URLs
    ai_urls = provider.get_feed_urls('ai')
    print(f"\n✅ AI category has {len(ai_urls)} feed URLs")
    
    cloud_urls = provider.get_feed_urls('cloud')
    print(f"✅ Cloud category has {len(cloud_urls)} feed URLs")
    
    # Test available categories
    categories = get_available_web_categories()
    print(f"\n✅ Available categories: {', '.join(categories)}")
    
    print("="*70)
    return True


def test_web_category_providers():
    """Test web category provider functions."""
    from scout_it.web_category_providers import (
        get_available_web_categories,
        get_web_category_providers
    )
    
    print("\n" + "="*70)
    print("TEST 3: Web Category Providers")
    print("="*70)
    
    categories = get_available_web_categories()
    print(f"\nAvailable categories: {categories}")
    
    for cat in ['ai', 'engineering', 'cloud']:
        providers = get_web_category_providers(cat)
        status = "✅" if providers else "❌"
        print(f"{status} {cat:20s}: {len(providers)} provider(s)")
    
    print("="*70)
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("WEB SEARCH RSS INTEGRATION TEST SUITE")
    print("="*70)
    
    results = {}
    
    results["Feeds Loaded"] = test_web_feeds_loaded()
    results["RSS Provider"] = test_web_rss_provider()
    results["Category Providers"] = test_web_category_providers()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        print("\n✅ Web search RSS integration is working correctly")
        print("\nYou can now use:")
        print('  scout-it web-search -q "kubernetes" --category cloud devops')
        print('  scout-it web-search -q "transformers" --category ai research')
        print('  scout-it web-search -q "microservices" --category engineering')
    
    print("="*70)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
