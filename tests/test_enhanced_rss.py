#!/usr/bin/env python3
"""Test script for enhanced TechCrunch RSS module."""

import json
import importlib

_tech_crunch_rss = importlib.import_module('.tech_crunch_rss', 'scout_it.news-search')

# Import all needed items
globals().update({name: getattr(_tech_crunch_rss, name) for name in [
    'RSSConfig', 'TechCrunchRSSProvider', 'get_available_domains',
    'get_feed_urls', 'validate_domain', 'validate_feed', 'validate_all_feeds',
    'fetch_feed', 'fetch_multiple_feeds', 'parse_feed', 'get_latest_entries',
    'search_entries', 'rank_entries', 'filter_entries', 'search_feeds',
    'deduplicate_entries', 'sort_entries', 'get_feed_statistics',
    'get_feed_metadata', 'get_feed_health', 'to_json', 'export_json',
    'filter_by_date', 'filter_by_domain', 'get_all_feed_entries',
]})

def test_basic_functionality():
    """Test basic RSS functionality."""
    print("=" * 60)
    print("TEST 1: Basic Functionality")
    print("=" * 60)
    
    # Get available domains
    domains = get_available_domains()
    print(f"✓ Available domains: {len(domains)}")
    print(f"  Sample: {domains[:5]}")
    
    # Get latest entries
    entries = get_latest_entries("ai", limit=10)
    print(f"✓ Latest AI entries: {len(entries)}")
    if entries:
        print(f"  First entry: {entries[0].get('title', 'N/A')[:60]}...")
    
    return entries


def test_enhanced_search():
    """Test enhanced search with operators and fuzzy matching."""
    print("\n" + "=" * 60)
    print("TEST 2: Enhanced Search Features")
    print("=" * 60)
    
    entries = get_latest_entries("ai", limit=20)
    
    # Test basic search
    results = search_entries(entries, "openai")
    print(f"✓ Basic search 'openai': {len(results)} results")
    if results:
        print(f"  Top result score: {results[0].get('score', 0)}")
        print(f"  Matched terms: {results[0].get('matched_terms', [])}")
        print(f"  Ranking breakdown: {results[0].get('ranking_breakdown', {})}")
    
    # Test phrase search
    results = search_entries(entries, '"artificial intelligence"')
    print(f"✓ Phrase search: {len(results)} results")
    
    # Test operators
    results = search_entries(entries, '+AI -funding')
    print(f"✓ Operator search '+AI -funding': {len(results)} results")
    
    # Test combined
    results = search_entries(entries, '+openai "machine learning"')
    print(f"✓ Combined search: {len(results)} results")


def test_filtering():
    """Test new filtering functions."""
    print("\n" + "=" * 60)
    print("TEST 3: Filtering Functions")
    print("=" * 60)
    
    entries = get_latest_entries(limit=50)
    print(f"Total entries fetched: {len(entries)}")
    
    # Filter by date
    recent = filter_by_date(entries, days=7)
    print(f"✓ Last 7 days: {len(recent)} entries")
    
    # Filter by domain
    ai_entries = filter_by_domain(entries, "ai")
    print(f"✓ AI domain: {len(ai_entries)} entries")
    
    # Filter by keyword
    openai_entries = filter_by_keyword(entries, "openai")
    print(f"✓ Keyword 'openai': {len(openai_entries)} entries")
    
    # Filter by author
    if entries and entries[0].get("author"):
        author = entries[0]["author"]
        by_author = filter_by_author(entries, author)
        print(f"✓ By author '{author}': {len(by_author)} entries")


def test_analytics():
    """Test analytics functions."""
    print("\n" + "=" * 60)
    print("TEST 4: Analytics Functions")
    print("=" * 60)
    
    entries = get_latest_entries(limit=100)
    
    # Top authors
    authors = get_top_authors(entries, limit=5)
    print(f"✓ Top authors: {len(authors)}")
    for i, author_data in enumerate(authors[:3], 1):
        print(f"  {i}. {author_data['author']}: {author_data['count']} articles")
    
    # Top keywords
    keywords = get_top_keywords(entries, limit=10)
    print(f"✓ Top keywords: {len(keywords)}")
    print(f"  Sample: {[k['keyword'] for k in keywords[:5]]}")
    
    # Feed activity
    activity = get_feed_activity(entries)
    print(f"✓ Feed activity:")
    print(f"  Total entries: {activity['total_entries']}")
    print(f"  Unique feeds: {len(activity['by_feed'])}")
    print(f"  Domains: {len(activity['by_domain'])}")
    
    # Feed distribution
    distribution = get_feed_distribution(entries)
    print(f"✓ Distribution:")
    print(f"  Unique feeds: {distribution['unique_feeds']}")
    print(f"  Unique domains: {distribution['unique_domains']}")
    print(f"  Unique authors: {distribution['unique_authors']}")


def test_export_formats():
    """Test export functions."""
    print("\n" + "=" * 60)
    print("TEST 5: Export Functions")
    print("=" * 60)
    
    entries = get_latest_entries("ai", limit=5)
    
    # JSON export
    json_path = export_json(entries, "test_output.json")
    print(f"✓ JSON export: {json_path}")
    
    # CSV export
    csv_path = export_csv(entries, "test_output.csv")
    print(f"✓ CSV export: {csv_path}")
    
    # JSONL export
    jsonl_path = export_jsonl(entries, "test_output.jsonl")
    print(f"✓ JSONL export: {jsonl_path}")
    
    # YAML export (optional)
    try:
        yaml_path = export_yaml(entries, "test_output.yaml")
        print(f"✓ YAML export: {yaml_path}")
    except Exception as e:
        print(f"⚠ YAML export skipped: {e}")
    
    # Cleanup
    import os
    for path in ["test_output.json", "test_output.csv", "test_output.jsonl", "test_output.yaml"]:
        if os.path.exists(path):
            os.remove(path)
    print("✓ Cleanup completed")


def test_cache_management():
    """Test cache management."""
    print("\n" + "=" * 60)
    print("TEST 6: Cache Management")
    print("=" * 60)
    
    # Fetch some data to populate cache
    entries = get_latest_entries("ai", limit=5)
    print(f"✓ Fetched {len(entries)} entries (cache populated)")
    
    # Clear cache
    cleared = clear_cache()
    print(f"✓ Cache cleared:")
    for cache_type, count in cleared.items():
        print(f"  {cache_type}: {count} entries")


def test_feed_health():
    """Test feed health tracking."""
    print("\n" + "=" * 60)
    print("TEST 7: Feed Health Tracking")
    print("=" * 60)
    
    # Get feed statistics
    stats = get_feed_statistics()
    print(f"✓ Feed statistics:")
    print(f"  Total feeds: {stats['feed_count']}")
    print(f"  Valid feeds: {stats['valid_feeds']}")
    print(f"  Invalid feeds: {stats['invalid_feeds']}")
    
    # Get health for all feeds
    health = get_feed_health()
    print(f"✓ Health tracked for {len(health)} feeds")
    
    # Sample health data
    if health:
        sample_url = list(health.keys())[0]
        sample_health = health[sample_url]
        print(f"  Sample feed: {sample_url[:50]}...")
        print(f"    Success rate: {sample_health.get('success_rate', 0) * 100:.1f}%")
        print(f"    Avg response time: {sample_health.get('average_response_time', 0):.3f}s")


def test_ranking_details():
    """Test detailed ranking information."""
    print("\n" + "=" * 60)
    print("TEST 8: Detailed Ranking Information")
    print("=" * 60)
    
    entries = get_latest_entries("ai", limit=10)
    results = rank_entries(entries, "openai agents")
    
    if results:
        top_result = results[0]
        print(f"✓ Top result: {top_result.get('title', 'N/A')[:60]}...")
        print(f"  Score: {top_result.get('score', 0)}")
        print(f"  Matched terms: {top_result.get('matched_terms', [])}")
        print(f"  Match count: {top_result.get('match_count', 0)}")
        print(f"  Match locations: {top_result.get('match_locations', {})}")
        print(f"  Ranking breakdown:")
        for component, value in top_result.get('ranking_breakdown', {}).items():
            if value > 0:
                print(f"    {component}: {value}")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ENHANCED TECHCRUNCH RSS MODULE - TEST SUITE")
    print("=" * 60)
    
    try:
        test_basic_functionality()
        test_enhanced_search()
        test_filtering()
        test_analytics()
        test_export_formats()
        test_cache_management()
        test_feed_health()
        test_ranking_details()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
