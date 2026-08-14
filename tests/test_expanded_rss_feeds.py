"""
Test that expanded RSS feeds from news-rss-feeds.py are correctly integrated
and work with the news-search command.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

_skip_without_integration = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS", "0") != "1",
    reason="Requires live RSS access; set RUN_INTEGRATION_TESTS=1 to enable.",
)


def test_feeds_expanded():
    """Test that TECHCRUNCH_FEEDS has been expanded with new sources."""
    import importlib
    _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
    TECHCRUNCH_FEEDS = _tech_crunch_rss.TECHCRUNCH_FEEDS
    
    print("\n" + "="*70)
    print("TEST 1: Verify RSS Feeds Were Expanded")
    print("="*70)
    
    # Check key categories have multiple feeds now
    test_categories = {
        "cloud": {"old_count": 1, "new_min_count": 4},
        "ai": {"old_count": 2, "new_min_count": 6},
        "startups": {"old_count": 1, "new_min_count": 3},
        "security": {"old_count": 1, "new_min_count": 4},
        "all": {"old_count": 1, "new_min_count": 5},
    }
    
    for category, expectations in test_categories.items():
        feeds = TECHCRUNCH_FEEDS.get(category, [])
        count = len(feeds)
        new_min = expectations["new_min_count"]
        assert count >= new_min, (
            f"{category}: expected >= {new_min} feeds, got {count}"
        )


def test_cloud_feeds_detail():
    """Test cloud category specifically - this is the user's example."""
    import importlib
    _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
    TECHCRUNCH_FEEDS = _tech_crunch_rss.TECHCRUNCH_FEEDS
    
    print("\n" + "="*70)
    print("TEST 2: Detailed Cloud Category Feed Check")
    print("="*70)
    
    cloud_feeds = TECHCRUNCH_FEEDS.get("cloud", [])
    
    print(f"\nCloud category has {len(cloud_feeds)} RSS feed URLs:\n")
    
    expected_sources = [
        "techcrunch.com",
        "aws.amazon.com",
        "cloud.google.com",
        "azure.microsoft.com"
    ]
    
    found_sources = set()
    for i, feed in enumerate(cloud_feeds, 1):
        url = feed.get("url", "")
        verified = feed.get("verified", False)
        notes = feed.get("notes", "")
        
        print(f"{i}. {url}")
        print(f"   Verified: {verified}")
        print(f"   Notes: {notes}\n")
        
        # Track which expected sources we found
        for source in expected_sources:
            if source in url:
                found_sources.add(source)
    
    print(f"Expected sources found: {len(found_sources)}/{len(expected_sources)}")
    for source in expected_sources:
        status = "✅" if source in found_sources else "❌"
        print(f"  {status} {source}")
    
    print("\n" + "="*70)
    assert len(found_sources) >= 3, f"Expected >= 3 cloud providers, got {len(found_sources)}"


def test_provider_integration():
    """Test that category_providers.py can use the expanded feeds."""
    import importlib
    _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
    TechCrunchRSSProvider = _tech_crunch_rss.TechCrunchRSSProvider
    
    print("\n" + "="*70)
    print("TEST 3: Provider Integration Test")
    print("="*70)
    
    provider = TechCrunchRSSProvider()
    
    # Test getting URLs for cloud category
    cloud_urls = provider.get_feed_urls("cloud")
    
    print(f"\nTechCrunchRSSProvider.get_feed_urls('cloud') returned {len(cloud_urls)} URLs:")
    for i, url in enumerate(cloud_urls[:5], 1):
        print(f"  {i}. {url}")
    
    if len(cloud_urls) > 5:
        print(f"  ... and {len(cloud_urls) - 5} more")
    
    # Verify we got multiple URLs
    success = len(cloud_urls) >= 4
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} - Provider returns {len(cloud_urls)} URLs for cloud category (expected >= 4)")
    
    print("\n" + "="*70)
    assert len(cloud_urls) >= 4, f"Expected >= 4 cloud URLs, got {len(cloud_urls)}"


@_skip_without_integration
def test_get_all_feed_entries():
    """Test that get_all_feed_entries works with expanded feeds."""
    import importlib
    _tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')
    get_all_feed_entries = _tech_crunch_rss.get_all_feed_entries

    entries = get_all_feed_entries(domains=["cloud"], limit=50)
    assert entries, "get_all_feed_entries returned no cloud entries"


def test_category_provider_function():
    """Test that category_providers.py functions work with new feeds."""
    from scout_it.category_providers import techcrunch_cloud_provider

    results = techcrunch_cloud_provider(query="kubernetes", max_results=50)
    assert results, "techcrunch_cloud_provider returned no entries"

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("EXPANDED RSS FEEDS INTEGRATION TEST SUITE")
    print("="*70)
    print("\nThis test verifies that the new RSS feeds from news-rss-feeds.py")
    print("are correctly integrated into tech_crunch_rss.py and work with")
    print("the news-search command flow.")
    print("\n" + "="*70)
    
    results = {}
    
    # Run tests
    results["Feeds Expanded"] = test_feeds_expanded()
    results["Cloud Feeds Detail"] = test_cloud_feeds_detail()
    results["Provider Integration"] = test_provider_integration()
    results["get_all_feed_entries"] = test_get_all_feed_entries()
    results["Category Provider Function"] = test_category_provider_function()
    
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
        print("\n🎉 All tests passed! The expanded RSS feeds are working correctly.")
        print("\nYou can now use commands like:")
        print('  scout-it news-search -q "cloud updates" --category cloud')
        print('  scout-it news-search -q "AI news" --category ai')
        print('  scout-it news-search -q "startup funding" --category startups')
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
    
    print("\n" + "="*70)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
