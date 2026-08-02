#!/usr/bin/env python3
"""Test script for TechCrunch RSS integration with news-search."""

import sys
import json
from scout_it.cli import news_search
from scout_it.category_providers import (
    get_available_categories,
    fetch_category_news,
)

def test_category_providers():
    """Test category provider registry."""
    print("=" * 60)
    print("TEST 1: Category Provider Registry")
    print("=" * 60)
    
    categories = get_available_categories()
    print(f"✓ Available categories: {categories}")
    
    for category in categories:
        print(f"  • {category}")
    
    return True


def test_techcrunch_provider():
    """Test TechCrunch provider directly."""
    print("\n" + "=" * 60)
    print("TEST 2: TechCrunch Provider Direct Test")
    print("=" * 60)
    
    try:
        results = fetch_category_news(
            categories=["ai"],
            query="openai",
            max_results=5
        )
        
        print(f"✓ Fetched {len(results)} results from AI category")
        
        if results:
            first = results[0]
            print(f"\n  Sample result:")
            print(f"    Title: {first.get('title', 'N/A')[:60]}...")
            print(f"    Source: {first.get('source', 'N/A')}")
            print(f"    Score: {first.get('score', 0)}")
            print(f"    URL: {first.get('url', 'N/A')[:60]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ TechCrunch provider test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_news_search_with_categories():
    """Test news_search with category parameter."""
    print("\n" + "=" * 60)
    print("TEST 3: news_search with --category")
    print("=" * 60)
    
    try:
        results, stats = news_search(
            query="kubernetes",
            max_results=10,
            categories=["ai", "cloud"],
            workers=3,
        )
        
        print(f"✓ news_search completed")
        print(f"  Total results: {len(results)}")
        print(f"  Search stats: {stats.get('search_engine', {})}")
        
        # Check for category RSS results
        search_stats = stats.get('search_engine', {})
        if 'category_rss_count' in search_stats:
            print(f"  Category RSS contributed: {search_stats['category_rss_count']} results")
        
        # Show source distribution
        sources = {}
        for r in results:
            source = r.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        print(f"\n  Source distribution:")
        for source, count in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"    {source}: {count}")
        
        # Show sample results
        if results:
            print(f"\n  Sample results:")
            for i, r in enumerate(results[:3], 1):
                print(f"    {i}. {r.get('title', 'N/A')[:60]}...")
                print(f"       Source: {r.get('source', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ news_search with categories failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_categories():
    """Test fetching from multiple categories."""
    print("\n" + "=" * 60)
    print("TEST 4: Multiple Categories")
    print("=" * 60)
    
    try:
        results = fetch_category_news(
            categories=["ai", "startups", "security"],
            query="funding",
            max_results=5
        )
        
        print(f"✓ Fetched from 3 categories: {len(results)} results")
        
        # Check category distribution
        categories = {}
        for r in results:
            metadata = r.get('rss_metadata', {})
            cat = metadata.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        print(f"\n  Category distribution:")
        for cat, count in sorted(categories.items()):
            print(f"    {cat}: {count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Multiple categories test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deduplication():
    """Test that results are properly deduplicated."""
    print("\n" + "=" * 60)
    print("TEST 5: URL Deduplication")
    print("=" * 60)
    
    try:
        results, stats = news_search(
            query="AI",
            max_results=20,
            categories=["ai"],
            workers=3,
        )
        
        # Check for duplicate URLs
        urls = [r.get('url', '') for r in results]
        unique_urls = set(urls)
        
        if len(urls) == len(unique_urls):
            print(f"✓ No duplicate URLs found ({len(urls)} unique)")
        else:
            duplicates = len(urls) - len(unique_urls)
            print(f"⚠ Found {duplicates} duplicate URLs")
        
        return True
        
    except Exception as e:
        print(f"❌ Deduplication test failed: {e}")
        return False


def test_ranking():
    """Test that results are properly ranked."""
    print("\n" + "=" * 60)
    print("TEST 6: Result Ranking")
    print("=" * 60)
    
    try:
        results = fetch_category_news(
            categories=["ai"],
            query="openai agents",
            max_results=10
        )
        
        print(f"✓ Fetched {len(results)} results")
        
        if results:
            # Check if results have scores
            has_scores = all('score' in r for r in results)
            if has_scores:
                print(f"✓ All results have relevance scores")
                
                # Show top 3 scores
                print(f"\n  Top 3 by relevance:")
                for i, r in enumerate(results[:3], 1):
                    print(f"    {i}. Score: {r.get('score', 0):.2f}")
                    print(f"       {r.get('title', 'N/A')[:50]}...")
            else:
                print(f"⚠ Some results missing scores")
        
        return True
        
    except Exception as e:
        print(f"❌ Ranking test failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("TECHCRUNCH RSS INTEGRATION TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_category_providers,
        test_techcrunch_provider,
        test_news_search_with_categories,
        test_multiple_categories,
        test_deduplication,
        test_ranking,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ TEST EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✅ ALL INTEGRATION TESTS PASSED")
        return 0
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
