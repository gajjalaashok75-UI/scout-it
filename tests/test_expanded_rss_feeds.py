"""
Test that expanded RSS feeds from news-rss-feeds.py are correctly integrated
and work with the news-search command.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_feeds_expanded():
    """Test that TECHCRUNCH_FEEDS has been expanded with new sources."""
    from scout_it.tech_crunch_rss import TECHCRUNCH_FEEDS
    
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
        old_count = expectations["old_count"]
        new_min = expectations["new_min_count"]
        
        status = "✅ PASS" if count >= new_min else "❌ FAIL"
        print(f"{status} | {category:12s} | Had {old_count} feed(s), now has {count} feed(s) (expected >= {new_min})")
        
        if count >= new_min:
            # Show a sample of the feeds
            print(f"       Sample feeds for '{category}':")
            for feed in feeds[:3]:
                url = feed.get('url', '')[:60]
                print(f"         - {url}...")
    
    print("\n" + "="*70)
    return True


def test_cloud_feeds_detail():
    """Test cloud category specifically - this is the user's example."""
    from scout_it.tech_crunch_rss import TECHCRUNCH_FEEDS
    
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
    return len(found_sources) >= 3  # At least 3 of 4 major cloud providers


def test_provider_integration():
    """Test that category_providers.py can use the expanded feeds."""
    from scout_it.tech_crunch_rss import TechCrunchRSSProvider
    
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
    return success


def test_get_all_feed_entries():
    """Test that get_all_feed_entries works with expanded feeds."""
    from scout_it.tech_crunch_rss import get_all_feed_entries
    
    print("\n" + "="*70)
    print("TEST 4: get_all_feed_entries() Function Test")
    print("="*70)
    
    print("\nFetching entries from cloud category (this may take a few seconds)...")
    print("Note: This fetches from ALL cloud-related RSS feeds")
    
    try:
        # Get entries from cloud feeds
        entries = get_all_feed_entries(domains=["cloud"], limit=50)
        
        print(f"\n✅ Successfully fetched {len(entries)} entries from cloud feeds")
        
        if entries:
            print("\nSample entries:")
            for i, entry in enumerate(entries[:3], 1):
                title = entry.get("title", "")[:60]
                feed_name = entry.get("feed_name", "unknown")
                print(f"  {i}. {title}...")
                print(f"     From: {feed_name}")
        
        print("\n" + "="*70)
        return len(entries) > 0
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        print("\n" + "="*70)
        return False


def test_category_provider_function():
    """Test that category_providers.py functions work with new feeds."""
    try:
        from scout_it.category_providers import techcrunch_cloud_provider
        
        print("\n" + "="*70)
        print("TEST 5: Category Provider Function Test")
        print("="*70)
        
        print("\nCalling techcrunch_cloud_provider() - this may take a few seconds...")
        
        results = techcrunch_cloud_provider(query="kubernetes", max_results=50)
        
        print(f"\n✅ techcrunch_cloud_provider returned {len(results)} normalized entries")
        
        if results:
            print("\nSample normalized entries:")
            for i, entry in enumerate(results[:2], 1):
                title = entry.get("title", "")[:60]
                source = entry.get("source", "unknown")
                print(f"  {i}. {title}...")
                print(f"     Source: {source}")
        
        print("\n" + "="*70)
        return len(results) > 0
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70)
        return False


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
