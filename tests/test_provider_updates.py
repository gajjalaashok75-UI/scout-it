#!/usr/bin/env python3
"""
Quick test to verify category providers return ALL RSS entries without query filtering.

This test verifies the fix for the premature filtering issue where RSS providers
were filtering by query before ranking, resulting in only 1 entry instead of 50+.
"""

import sys
import logging
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS", "0") != "1",
    reason="Requires live RSS access; set RUN_INTEGRATION_TESTS=1 to enable.",
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_ai_provider():
    """Test that AI provider returns ALL entries without query filtering."""
    from scout_it.category_providers import techcrunch_ai_provider
    
    print("\n" + "="*80)
    print("TEST 1: TechCrunch AI Provider")
    print("="*80)
    
    # Query that should NOT filter out most entries
    query = "anthropic claude updates"
    
    print(f"\nQuery: {query}")
    print("Expected: 50+ RSS entries (NO premature filtering)")
    
    results = techcrunch_ai_provider(query, max_results=500)
    
    print(f"\nResults: {len(results)} entries")
    
    if len(results) >= 20:
        print(f"✅ PASS: Got {len(results)} entries (expected 20+)")
    else:
        print(f"❌ FAIL: Got only {len(results)} entries (expected 20+)")
        return False
    
    # Verify structure
    if results:
        sample = results[0]
        required_keys = ['title', 'url', 'body', 'categories', 'rss_metadata']
        missing_keys = [k for k in required_keys if k not in sample]
        
        if missing_keys:
            print(f"❌ FAIL: Missing keys in result: {missing_keys}")
            return False
        
        print(f"✅ PASS: Result structure is correct")
        
        # Show sample entry
        print(f"\nSample entry:")
        print(f"  Title: {sample['title'][:80]}...")
        print(f"  URL: {sample['url']}")
        print(f"  Categories: {sample['categories']}")
        print(f"  Source: {sample['source']}")
    
    return True


def test_startups_provider():
    """Test that startups provider returns ALL entries without query filtering."""
    from scout_it.category_providers import techcrunch_startups_provider
    
    print("\n" + "="*80)
    print("TEST 2: TechCrunch Startups Provider")
    print("="*80)
    
    query = "startup funding"
    
    print(f"\nQuery: {query}")
    print("Expected: 20+ RSS entries (NO premature filtering)")
    
    results = techcrunch_startups_provider(query, max_results=500)
    
    print(f"\nResults: {len(results)} entries")
    
    if len(results) >= 10:
        print(f"✅ PASS: Got {len(results)} entries (expected 10+)")
        return True
    else:
        print(f"❌ FAIL: Got only {len(results)} entries (expected 10+)")
        return False


def test_security_provider():
    """Test that security provider returns ALL entries without query filtering."""
    from scout_it.category_providers import techcrunch_security_provider
    
    print("\n" + "="*80)
    print("TEST 3: TechCrunch Security Provider")
    print("="*80)
    
    query = "cybersecurity breach"
    
    print(f"\nQuery: {query}")
    print("Expected: 10+ RSS entries (NO premature filtering)")
    
    results = techcrunch_security_provider(query, max_results=500)
    
    print(f"\nResults: {len(results)} entries")
    
    if len(results) >= 10:
        print(f"✅ PASS: Got {len(results)} entries (expected 10+)")
        return True
    else:
        print(f"❌ FAIL: Got only {len(results)} entries (expected 10+)")
        return False


def test_cloud_provider():
    """Test that cloud provider returns ALL entries without query filtering."""
    from scout_it.category_providers import techcrunch_cloud_provider
    
    print("\n" + "="*80)
    print("TEST 4: TechCrunch Cloud Provider")
    print("="*80)
    
    query = "cloud computing"
    
    print(f"\nQuery: {query}")
    print("Expected: 10+ RSS entries (NO premature filtering)")
    
    results = techcrunch_cloud_provider(query, max_results=500)
    
    print(f"\nResults: {len(results)} entries")
    
    if len(results) >= 10:
        print(f"✅ PASS: Got {len(results)} entries (expected 10+)")
        return True
    else:
        print(f"❌ FAIL: Got only {len(results)} entries (expected 10+)")
        return False


def test_general_provider():
    """Test that general provider returns ALL entries without query filtering."""
    from scout_it.category_providers import techcrunch_general_provider
    
    print("\n" + "="*80)
    print("TEST 5: TechCrunch General Provider")
    print("="*80)
    
    query = "technology news"
    
    print(f"\nQuery: {query}")
    print("Expected: 50+ RSS entries (NO premature filtering)")
    
    results = techcrunch_general_provider(query, max_results=500)
    
    print(f"\nResults: {len(results)} entries")
    
    if len(results) >= 30:
        print(f"✅ PASS: Got {len(results)} entries (expected 30+)")
        return True
    else:
        print(f"❌ FAIL: Got only {len(results)} entries (expected 30+)")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TESTING CATEGORY PROVIDER UPDATES")
    print("Verifying NO premature query filtering before ranking")
    print("="*80)
    
    tests = [
        test_ai_provider,
        test_startups_provider,
        test_security_provider,
        test_cloud_provider,
        test_general_provider,
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
            print(f"\n❌ ERROR in {test_func.__name__}: {e}")
            failed += 1
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED!")
        print("\nThe category providers are now correctly returning ALL RSS entries")
        print("without premature query filtering. Entries will be filtered during")
        print("the ranking phase, not before.")
        return 0
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
