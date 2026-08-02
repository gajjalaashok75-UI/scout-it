#!/usr/bin/env python3
"""
Test staged ranking system for news search.

Verifies:
1. staged_ranker module structure
2. Initial ranking (fast, metadata-only)
3. Final ranking (with content)
4. Performance characteristics
5. Integration with news_search
"""

import sys
import time
from pathlib import Path

print("=" * 70)
print("STAGED RANKING TEST SUITE")
print("=" * 70)

# ============================================================================
# TEST 1: Module Structure
# ============================================================================
print("\n" + "=" * 70)
print("TEST 1: Module Structure")
print("=" * 70)

try:
    from scout_it import staged_ranker
    print("✅ scout_it.staged_ranker module exists")
    
    # Check functions
    assert hasattr(staged_ranker, 'rank_candidates_initial'), "Missing rank_candidates_initial"
    print("✅ rank_candidates_initial() exists")
    
    assert hasattr(staged_ranker, 'rank_candidates_final'), "Missing rank_candidates_final"
    print("✅ rank_candidates_final() exists")
    
    assert hasattr(staged_ranker, 'staged_ranking_pipeline'), "Missing staged_ranking_pipeline"
    print("✅ staged_ranking_pipeline() exists")
    
    assert hasattr(staged_ranker, 'tokenize_query'), "Missing tokenize_query"
    print("✅ tokenize_query() exists")
    
    assert hasattr(staged_ranker, 'score_text_relevance'), "Missing score_text_relevance"
    print("✅ score_text_relevance() exists")
    
except Exception as e:
    print(f"❌ Module structure test failed: {e}")
    sys.exit(1)

# ============================================================================
# TEST 2: Query Tokenization
# ============================================================================
print("\n" + "=" * 70)
print("TEST 2: Query Tokenization")
print("=" * 70)

try:
    from scout_it.staged_ranker import tokenize_query
    
    # Test 1: Simple query
    required, excluded, phrases = tokenize_query("openai agents")
    assert required == ['openai', 'agents'], f"Expected ['openai', 'agents'], got {required}"
    print("✅ Simple query: 'openai agents'")
    print(f"   Required: {required}")
    
    # Test 2: With operators
    required, excluded, phrases = tokenize_query('+openai -microsoft "AI agents"')
    assert 'openai' in required, "Expected +openai in required"
    assert 'microsoft' in excluded, "Expected -microsoft in excluded"
    assert 'ai agents' in phrases, "Expected 'AI agents' in phrases"
    print("✅ Query with operators: '+openai -microsoft \"AI agents\"'")
    print(f"   Required: {required}")
    print(f"   Excluded: {excluded}")
    print(f"   Phrases: {phrases}")
    
except Exception as e:
    print(f"❌ Query tokenization test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 3: Text Relevance Scoring
# ============================================================================
print("\n" + "=" * 70)
print("TEST 3: Text Relevance Scoring")
print("=" * 70)

try:
    from scout_it.staged_ranker import tokenize_query, score_text_relevance
    
    query_parts = tokenize_query("openai agents")
    
    # Test 1: High relevance text
    text1 = "OpenAI releases new autonomous agents for complex tasks"
    score1, matches1, terms1 = score_text_relevance(text1, query_parts)
    print(f"✅ High relevance text scored: {score1}")
    print(f"   Text: '{text1}'")
    print(f"   Matches: {matches1}, Terms: {terms1}")
    assert score1 > 0, "Expected positive score for relevant text"
    
    # Test 2: Low relevance text
    text2 = "Microsoft announces new features for Windows 11"
    score2, matches2, terms2 = score_text_relevance(text2, query_parts)
    print(f"✅ Low relevance text scored: {score2}")
    print(f"   Text: '{text2}'")
    print(f"   Matches: {matches2}, Terms: {terms2}")
    assert score1 > score2, "Expected higher score for more relevant text"
    
except Exception as e:
    print(f"❌ Text relevance scoring test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 4: Initial Ranking (Metadata-Only)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 4: Initial Ranking (Metadata-Only)")
print("=" * 70)

try:
    from scout_it.staged_ranker import rank_candidates_initial
    
    # Create mock candidates
    candidates = [
        {
            'title': 'OpenAI releases new autonomous agents',
            'body': 'OpenAI announced new AI agents that can perform complex tasks',
            'url': 'https://techcrunch.com/article1',
            'source': 'techcrunch:ai',
            'publish_date': '2026-08-02T10:00:00+00:00',
            'score': 95,
        },
        {
            'title': 'Microsoft updates Windows',
            'body': 'Microsoft releases new Windows update',
            'url': 'https://news.com/article2',
            'source': 'duckduckgo',
            'publish_date': '2026-08-01T10:00:00+00:00',
            'score': 50,
        },
        {
            'title': 'AI agents revolutionize automation',
            'body': 'New AI agent technology from OpenAI is changing how we automate tasks',
            'url': 'https://techcrunch.com/article3',
            'source': 'techcrunch:ai',
            'publish_date': '2026-08-02T12:00:00+00:00',
            'score': 90,
        },
    ]
    
    query = "openai agents"
    start_time = time.perf_counter()
    top_candidates = rank_candidates_initial(candidates, query, top_k=2)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    print(f"✅ Initial ranking completed in {elapsed_ms:.2f}ms")
    print(f"   Input: {len(candidates)} candidates")
    print(f"   Output: {len(top_candidates)} top candidates")
    
    # Check results
    assert len(top_candidates) == 2, f"Expected 2 results, got {len(top_candidates)}"
    assert 'initial_rank_score' in top_candidates[0], "Missing initial_rank_score"
    assert 'rank_breakdown' in top_candidates[0], "Missing rank_breakdown"
    assert 'matched_terms' in top_candidates[0], "Missing matched_terms"
    
    print(f"\n   Top candidate:")
    print(f"   - Title: {top_candidates[0]['title']}")
    print(f"   - Score: {top_candidates[0]['initial_rank_score']}")
    print(f"   - Breakdown: {top_candidates[0]['rank_breakdown']}")
    print(f"   - Matched terms: {top_candidates[0]['matched_terms']}")
    
    # Verify performance
    assert elapsed_ms < 100, f"Initial ranking too slow: {elapsed_ms}ms (target: <100ms)"
    print(f"✅ Performance: {elapsed_ms:.2f}ms < 100ms target")
    
except Exception as e:
    print(f"❌ Initial ranking test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 5: Final Ranking (With Content)
# ============================================================================
print("\n" + "=" * 70)
print("TEST 5: Final Ranking (With Content)")
print("=" * 70)

try:
    from scout_it.staged_ranker import rank_candidates_final
    
    # Create mock candidates with extracted content
    candidates_with_content = [
        {
            'title': 'OpenAI releases new autonomous agents',
            'body': 'OpenAI announced new AI agents',
            'url': 'https://techcrunch.com/article1',
            'source': 'techcrunch:ai',
            'publish_date': '2026-08-02T10:00:00+00:00',
            'initial_rank_score': 85.5,
            'rank_breakdown': {'title': 30, 'body': 20, 'source': 10, 'recency': 15},
            'matched_terms': ['openai', 'agents'],
            'cleaned_content': 'OpenAI has released revolutionary new autonomous agents that can perform complex multi-step tasks. These AI agents represent a major breakthrough in artificial intelligence and automation. The agents use advanced reasoning and can interact with multiple systems.',
            'quality_signals': {
                'has_content': True,
                'content_length': 250,
                'is_suspicious': False,
            },
            'word_count': 42,
        },
        {
            'title': 'AI agents revolutionize automation',
            'body': 'New AI agent technology',
            'url': 'https://techcrunch.com/article3',
            'source': 'techcrunch:ai',
            'publish_date': '2026-08-02T12:00:00+00:00',
            'initial_rank_score': 80.0,
            'rank_breakdown': {'title': 25, 'body': 15, 'source': 10, 'recency': 15},
            'matched_terms': ['agents'],
            'cleaned_content': 'AI agents are changing the automation landscape with minimal OpenAI involvement.',
            'quality_signals': {
                'has_content': True,
                'content_length': 100,
                'is_suspicious': False,
            },
            'word_count': 12,
        },
    ]
    
    query = "openai agents"
    start_time = time.perf_counter()
    final_results = rank_candidates_final(candidates_with_content, query, top_k=2)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    print(f"✅ Final ranking completed in {elapsed_ms:.2f}ms")
    print(f"   Input: {len(candidates_with_content)} candidates")
    print(f"   Output: {len(final_results)} top results")
    
    # Check results
    assert len(final_results) == 2, f"Expected 2 results, got {len(final_results)}"
    assert 'final_rank_score' in final_results[0], "Missing final_rank_score"
    assert 'keyword_density' in final_results[0], "Missing keyword_density"
    
    print(f"\n   Top result:")
    print(f"   - Title: {final_results[0]['title']}")
    print(f"   - Initial score: {final_results[0]['initial_rank_score']}")
    print(f"   - Final score: {final_results[0]['final_rank_score']}")
    print(f"   - Keyword density: {final_results[0]['keyword_density']}%")
    print(f"   - Matched terms: {final_results[0]['matched_terms']}")
    
    # Verify performance
    assert elapsed_ms < 50, f"Final ranking too slow: {elapsed_ms}ms (target: <50ms)"
    print(f"✅ Performance: {elapsed_ms:.2f}ms < 50ms target")
    
except Exception as e:
    print(f"❌ Final ranking test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 6: Source Quality Scores
# ============================================================================
print("\n" + "=" * 70)
print("TEST 6: Source Quality Scores")
print("=" * 70)

try:
    from scout_it.staged_ranker import get_source_quality_score
    
    sources = {
        'techcrunch:ai': 1.0,
        'google-news': 0.95,
        'duckduckgo': 0.90,
        'toi': 0.85,
        'unknown-source': 0.80,
    }
    
    for source, expected in sources.items():
        score = get_source_quality_score(source)
        print(f"✅ {source:20s} → {score:.2f} (expected: {expected:.2f})")
        assert score == expected, f"Score mismatch for {source}: {score} != {expected}"
    
except Exception as e:
    print(f"❌ Source quality test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 7: news_search Integration
# ============================================================================
print("\n" + "=" * 70)
print("TEST 7: news_search Integration")
print("=" * 70)

try:
    from scout_it.cli import news_search
    import inspect
    
    # Check function signature
    sig = inspect.signature(news_search)
    params = list(sig.parameters.keys())
    
    assert 'max_results' in params, "Missing max_results parameter"
    print("✅ max_results parameter exists")
    
    # Check default value
    default_max = sig.parameters['max_results'].default
    assert default_max == 10, f"Expected default max_results=10, got {default_max}"
    print(f"✅ Default max_results = {default_max}")
    
    print("\n✅ news_search ready for staged ranking integration")
    
except Exception as e:
    print(f"❌ news_search integration test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

print("""
✅ Module Structure: staged_ranker.py exists with all functions
✅ Query Tokenization: Operators (+, -, "phrase") working
✅ Text Relevance: Scoring algorithms correct
✅ Initial Ranking: Fast metadata-only ranking (<100ms)
✅ Final Ranking: Content-aware ranking (<50ms)
✅ Source Quality: Scoring working for all providers
✅ Integration: news_search ready with new default (max=10)

""")

print("=" * 70)
print("✅ ALL STAGED RANKING TESTS PASSED!")
print("=" * 70)

print("""
Staged Ranking Pipeline:

1. Provider Collection (each → 10 candidates)
   ├─ DDGS News → 10
   ├─ TechCrunch RSS → 10
   ├─ Google News → 10
   └─ ToI RSS → 10
   Total: ~40 candidates

2. Initial Ranking (metadata-only, <1s)
   └─ Fast scoring: title, summary, source, recency
   → Top 15 candidates

3. Content Extraction (<5s)
   └─ Only extract top 15 articles
   → 15 articles with full content

4. Final Ranking (with content, <1s)
   └─ Re-rank: content relevance, quality, density
   → Top 10 final results

Total target: <10s

Performance Characteristics:
- Initial ranking: <100ms ✅
- Final ranking: <50ms ✅
- Only 15 extractions instead of 40 (62% reduction)
- Significant speed improvement expected

Ready for production testing! 🚀
""")

print("\nSample command to test:")
print("  scout-it news-search -q 'openai agents' --category ai --max 10")
print()
