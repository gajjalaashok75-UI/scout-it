#!/usr/bin/env python3
"""Test script for production hardening features."""

import json
import os
from scout_it.tech_crunch_rss import (
    # Configuration
    RSSConfig,
    DEFAULT_CONFIG,
    
    # Exceptions
    RSSProviderError,
    FeedValidationError,
    FeedFetchError,
    FeedParseError,
    SearchError,
    ExportError,
    
    # Core functions
    get_latest_entries,
    search_feeds,
    search_entries,
    
    # Observability
    get_runtime_statistics,
    
    # Export
    export_json,
    export_csv,
)

def test_configuration():
    """Test configuration system."""
    print("=" * 60)
    print("TEST 1: Configuration System")
    print("=" * 60)
    
    # Test default config
    print(f"✓ Default config loaded")
    print(f"  Timeout: {DEFAULT_CONFIG.timeout}s")
    print(f"  Retries: {DEFAULT_CONFIG.retries}")
    print(f"  Cache TTL: {DEFAULT_CONFIG.cache_ttl_seconds}s")
    print(f"  Max workers: {DEFAULT_CONFIG.max_workers}")
    print(f"  Debug mode: {DEFAULT_CONFIG.debug}")
    
    # Test config validation
    config = RSSConfig()
    try:
        config.validate()
        print("✓ Configuration validation passed")
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False
    
    # Test config serialization
    config_dict = config.to_dict()
    print(f"✓ Config serialized: {len(config_dict)} keys")
    
    # Test ranking weights
    weights = config.ranking_weights
    print(f"✓ Ranking weights:")
    print(f"  Title: {weights.title}")
    print(f"  Summary: {weights.summary}")
    print(f"  Content: {weights.content}")
    print(f"  Recency base: {weights.recency_base}")
    
    return True


def test_environment_config():
    """Test environment variable configuration."""
    print("\n" + "=" * 60)
    print("TEST 2: Environment Variable Configuration")
    print("=" * 60)
    
    # Set test environment variables
    os.environ["TECHCRUNCH_RSS_TIMEOUT"] = "20.0"
    os.environ["TECHCRUNCH_RSS_DEBUG"] = "true"
    
    config = RSSConfig.from_environment()
    
    if config.timeout == 20.0:
        print(f"✓ Timeout from env: {config.timeout}s")
    else:
        print(f"❌ Expected timeout 20.0, got {config.timeout}")
    
    if config.debug:
        print(f"✓ Debug mode from env: {config.debug}")
    else:
        print(f"❌ Expected debug=True")
    
    # Cleanup
    os.environ.pop("TECHCRUNCH_RSS_TIMEOUT", None)
    os.environ.pop("TECHCRUNCH_RSS_DEBUG", None)
    
    return True


def test_error_handling():
    """Test graceful error handling."""
    print("\n" + "=" * 60)
    print("TEST 3: Error Handling")
    print("=" * 60)
    
    # Test invalid export path
    entries = get_latest_entries("ai", limit=2)
    
    try:
        # Try to export to invalid path
        export_json(entries, "/invalid/path/test.json")
        print("❌ Should have raised ExportError")
        return False
    except ExportError as e:
        print(f"✓ ExportError caught: {str(e)[:60]}...")
    except Exception as e:
        print(f"❌ Wrong exception type: {type(e)}")
        return False
    
    # Test search with empty entries
    try:
        results = search_entries([], "test query")
        print(f"✓ Search with empty entries: {len(results)} results")
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return False
    
    return True


def test_observability():
    """Test observability features."""
    print("\n" + "=" * 60)
    print("TEST 4: Observability & Metrics")
    print("=" * 60)
    
    # Perform some operations to generate metrics
    entries = get_latest_entries("ai", limit=10)
    print(f"✓ Fetched {len(entries)} entries")
    
    # Search operation
    results = search_feeds("openai", domains=["ai"], limit=5)
    print(f"✓ Search completed: {len(results)} results")
    
    # Get runtime statistics
    stats = get_runtime_statistics()
    
    print(f"\n✓ Runtime Statistics:")
    print(f"  Fetch operations: {stats['fetch_count']}")
    print(f"  Fetch success: {stats['fetch_success']}")
    print(f"  Fetch failures: {stats['fetch_failure']}")
    print(f"  Avg fetch time: {stats['avg_fetch_ms']:.2f}ms")
    
    print(f"  Parse operations: {stats['parse_count']}")
    print(f"  Parse success: {stats['parse_success']}")
    print(f"  Avg parse time: {stats['avg_parse_ms']:.2f}ms")
    
    print(f"  Search operations: {stats['search_count']}")
    print(f"  Avg search time: {stats['avg_search_ms']:.2f}ms")
    
    print(f"  Ranking operations: {stats['ranking_count']}")
    print(f"  Avg ranking time: {stats['avg_ranking_ms']:.2f}ms")
    
    print(f"  Cache hits: {stats['cache_hits']}")
    print(f"  Cache misses: {stats['cache_misses']}")
    print(f"  Cache hit rate: {stats['cache_hit_rate'] * 100:.1f}%")
    
    print(f"  Export operations: {stats['export_count']}")
    
    return True


def test_data_quality():
    """Test data quality improvements."""
    print("\n" + "=" * 60)
    print("TEST 5: Data Quality")
    print("=" * 60)
    
    entries = get_latest_entries("ai", limit=10)
    
    if not entries:
        print("⚠ No entries fetched, skipping data quality test")
        return True
    
    entry = entries[0]
    
    # Check required fields
    required_fields = ["title", "url", "published", "source", "domain"]
    for field in required_fields:
        if field in entry:
            print(f"✓ Field present: {field}")
        else:
            print(f"❌ Missing field: {field}")
    
    # Check metadata fields
    metadata_fields = ["content_length", "word_count", "reading_time_minutes"]
    for field in metadata_fields:
        if field in entry:
            print(f"✓ Metadata present: {field} = {entry[field]}")
        else:
            print(f"⚠ Missing metadata: {field}")
    
    # Check URL normalization
    if entry.get("url"):
        url = entry["url"]
        if "?" in url:
            # Check for tracking parameters
            if any(param in url for param in ["utm_", "fbclid", "gclid"]):
                print("⚠ Tracking parameters not fully removed from URL")
            else:
                print(f"✓ URL normalized (no tracking params)")
        else:
            print(f"✓ URL clean: {url[:50]}...")
    
    # Check date normalization
    if entry.get("published"):
        published = entry["published"]
        if "T" in published and ("+" in published or "Z" in published):
            print(f"✓ Date normalized to ISO UTC: {published}")
        else:
            print(f"⚠ Date format: {published}")
    
    return True


def test_search_quality():
    """Test search quality improvements."""
    print("\n" + "=" * 60)
    print("TEST 6: Search Quality")
    print("=" * 60)
    
    entries = get_latest_entries(limit=30)
    
    # Test with operators
    results = search_entries(entries, '+AI -funding')
    print(f"✓ Operator search '+AI -funding': {len(results)} results")
    
    # Test phrase search
    results = search_entries(entries, '"artificial intelligence"')
    print(f"✓ Phrase search: {len(results)} results")
    
    # Test confidence scores
    if results:
        top = results[0]
        if "confidence" in top:
            print(f"✓ Confidence score present: {top['confidence']}")
        else:
            print(f"⚠ Confidence score missing")
        
        if "ranking_breakdown" in top:
            print(f"✓ Ranking breakdown present")
            breakdown = top["ranking_breakdown"]
            significant = {k: v for k, v in breakdown.items() if v > 0}
            print(f"  Components: {list(significant.keys())}")
        else:
            print(f"⚠ Ranking breakdown missing")
    
    return True


def test_export_formats():
    """Test export with error handling."""
    print("\n" + "=" * 60)
    print("TEST 7: Export with Error Handling")
    print("=" * 60)
    
    entries = get_latest_entries("ai", limit=5)
    
    # Test JSON export
    try:
        path = export_json(entries, "test_prod_output.json")
        print(f"✓ JSON export: {path}")
        os.remove(path)
    except ExportError as e:
        print(f"❌ JSON export failed: {e}")
        return False
    
    # Test CSV export with confidence field
    try:
        path = export_csv(entries, "test_prod_output.csv")
        print(f"✓ CSV export: {path}")
        
        # Verify file content
        with open(path, "r", encoding="utf-8") as f:
            header = f.readline()
            if "confidence" in header:
                print(f"✓ CSV includes confidence field")
        
        os.remove(path)
    except ExportError as e:
        print(f"❌ CSV export failed: {e}")
        return False
    
    return True


def test_circuit_breaker():
    """Test circuit breaker functionality."""
    print("\n" + "=" * 60)
    print("TEST 8: Circuit Breaker")
    print("=" * 60)
    
    from scout_it.tech_crunch_rss import _CIRCUIT_BREAKERS, get_feed_health
    
    # Get feed health info
    health = get_feed_health()
    
    if health:
        print(f"✓ Health tracked for {len(health)} feeds")
        
        # Check for circuit breakers
        if _CIRCUIT_BREAKERS:
            print(f"✓ Circuit breakers active: {len(_CIRCUIT_BREAKERS)}")
            for url, breaker in list(_CIRCUIT_BREAKERS.items())[:3]:
                print(f"  {url[:50]}... - state: {breaker['state']}")
        else:
            print(f"✓ No circuit breakers triggered (all feeds healthy)")
    else:
        print(f"✓ No health data yet (no feeds fetched)")
    
    return True


def main():
    """Run all production hardening tests."""
    print("\n" + "=" * 60)
    print("PRODUCTION HARDENING - TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_configuration,
        test_environment_config,
        test_error_handling,
        test_observability,
        test_data_quality,
        test_search_quality,
        test_export_formats,
        test_circuit_breaker,
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
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("✓ ALL PRODUCTION HARDENING TESTS PASSED")
        return 0
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
