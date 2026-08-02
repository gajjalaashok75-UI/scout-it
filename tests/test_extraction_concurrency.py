#!/usr/bin/env python3
"""
Test extraction concurrency to verify parallel processing.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor


class TestExtractionConcurrency:
    """Test that extraction runs concurrently, not sequentially."""
    
    @patch('scout_it.cli.fetch_resilient')
    @patch('scout_it.cli.ExtractionEngine')
    def test_extraction_uses_threadpool(self, mock_engine_class, mock_fetch):
        """Verify extraction uses ThreadPoolExecutor for parallel processing."""
        from scout_it.cli import _extract_news_content
        
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        
        # Mock fetch to simulate realistic timing
        def slow_fetch(*args, **kwargs):
            time.sleep(0.1)  # Simulate 100ms per fetch
            return {
                'status': 'success',
                'html': '<html><body>Article content</body></html>',
                'final_url': args[0],
                'tier': 'requests',
                'errors': [],
            }
        
        mock_fetch.side_effect = slow_fetch
        
        # Mock extraction
        mock_engine.extract_content.return_value = (
            "Article content with many words " * 50,
            "heuristic",
            0.9,
        )
        
        # Create 10 test articles
        results = [
            {
                'url': f'https://example.com/article-{i}',
                'title': f'Article {i}',
                'body': 'Summary',
            }
            for i in range(10)
        ]
        
        # Measure extraction time
        start = time.time()
        enriched = _extract_news_content(
            results,
            max_workers=5,
            enable_js_fallback=True,
            max_fetch_retries=1,
        )
        elapsed = time.time() - start
        
        # Verify results
        assert len(enriched) == 10
        
        # Sequential would take 10 * 0.1 = 1.0s
        # Parallel with 5 workers should take ~0.2s (2 batches)
        # Allow some overhead, but it should be much faster than sequential
        assert elapsed < 0.6, f"Extraction took {elapsed:.2f}s, expected <0.6s (parallel with 5 workers)"
        print(f"✅ Parallel extraction completed in {elapsed:.2f}s (expected ~0.2-0.4s)")
    
    def test_threadpool_executor_max_workers_parameter(self):
        """Verify ThreadPoolExecutor respects max_workers parameter."""
        from scout_it.cli import _extract_news_content
        from unittest.mock import patch
        
        with patch('scout_it.cli.ThreadPoolExecutor') as mock_executor_class:
            mock_executor = MagicMock()
            mock_executor_class.return_value.__enter__.return_value = mock_executor
            mock_executor.submit.return_value.result.return_value = {
                'url': 'test',
                'extraction_status': 'success',
                'main_content': 'content',
            }
            
            # Call with max_workers=3
            _extract_news_content(
                [{'url': 'test1'}, {'url': 'test2'}],
                max_workers=3,
                enable_js_fallback=True,
                max_fetch_retries=1,
            )
            
            # Verify ThreadPoolExecutor was created with max_workers=3
            mock_executor_class.assert_called_once_with(max_workers=3)


class TestExtractionPerformance:
    """Test extraction performance characteristics."""
    
    def test_extraction_scaling(self):
        """Document expected extraction scaling with parallel workers."""
        # This is a documentation test showing expected performance
        
        scenarios = [
            # (num_urls, max_workers, expected_time_range)
            (5, 5, "4-8s"),      # All parallel: ~1-2s per URL
            (10, 5, "8-16s"),    # 2 batches: ~1-2s per URL × 2
            (20, 5, "16-32s"),   # 4 batches: ~1-2s per URL × 4
        ]
        
        print("\n📊 Expected Extraction Scaling (with ThreadPoolExecutor):")
        print("=" * 60)
        for num_urls, workers, time_range in scenarios:
            print(f"  {num_urls} URLs with {workers} workers: {time_range}")
        
        print("\n⚠️  Note: Actual times depend on:")
        print("  • Network latency")
        print("  • Playwright launch time")
        print("  • Page load speed")
        print("  • Content extraction complexity")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
