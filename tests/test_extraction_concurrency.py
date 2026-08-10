#!/usr/bin/env python3
"""
Test extraction concurrency to verify parallel processing.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import ThreadPoolExecutor


class TestExtractionConcurrency:
    """Test that the unified EnterpriseSearchEngine extraction runs concurrently."""

    @staticmethod
    def _no_domain_learning():
        learning = MagicMock()
        learning.get_strategy.return_value = ("requests", 0.0)
        return learning

    @patch('scout_it.domain_routing.get_domain_learning')
    @patch('scout_it.extraction.search.fetch_resilient')
    @patch('scout_it.extraction.search.ExtractionEngine')
    def test_extraction_uses_threadpool(self, mock_engine_class, mock_fetch, mock_learning):
        """Verify EnterpriseSearchEngine extracts in parallel (ThreadPoolExecutor)."""
        from scout_it.extraction import EnterpriseSearchEngine

        mock_learning.return_value = self._no_domain_learning()
        engine = EnterpriseSearchEngine(
            max_workers=5,
            enable_js_fallback=False,
            enable_alternate_source=False,
            enable_dns_fallback=False,
            enable_bandit=False,
        )

        def slow_fetch(*args, **kwargs):
            time.sleep(0.1)  # Simulate 100ms per fetch
            return {
                'status': 'success',
                'html': '<html><body>Article content</body></html>',
                'final_url': args[0],
                'tier': 'requests',
                'attempts': 1,
                'errors': [],
            }

        mock_fetch.side_effect = slow_fetch
        mock_engine = MagicMock()
        mock_engine.extract_content.return_value = ("article word " * 60, "heuristic", 0.9)
        engine.extractor = mock_engine

        seeds = [
            {'url': f'https://example.com/article-{i}', 'title': f'Article {i}', 'body': 'Summary'}
            for i in range(10)
        ]

        start = time.time()
        out = engine.execute_search_from_urls(seeds)
        elapsed = time.time() - start

        assert len(out) == 10
        # Sequential would take 10 * 0.1 = 1.0s; 5 workers in parallel ~0.2-0.4s
        assert elapsed < 0.6, f"Extraction took {elapsed:.2f}s, expected <0.6s (parallel with 5 workers)"
        print(f"Parallel extraction completed in {elapsed:.2f}s (expected ~0.2-0.4s)")

    @patch('scout_it.domain_routing.get_domain_learning')
    @patch('scout_it.extraction.search.fetch_resilient')
    @patch('scout_it.extraction.search.ExtractionEngine')
    def test_threadpool_executor_max_workers_parameter(self, mock_engine_class, mock_fetch, mock_learning):
        """Verify EnterpriseSearchEngine caps ThreadPoolExecutor workers at max_workers."""
        from concurrent.futures import ThreadPoolExecutor as _RealTPE
        from scout_it.extraction import EnterpriseSearchEngine
        import scout_it.extraction.search as search_mod

        mock_learning.return_value = self._no_domain_learning()
        captured = {}

        real_tpe = _RealTPE

        class _CapturingTPE(real_tpe):
            def __init__(self, *a, **kw):
                captured.update(kw)
                super().__init__(*a, **kw)

        mock_fetch.return_value = {
            'status': 'success', 'html': '<html>x</html>', 'final_url': 'u',
            'tier': 'requests', 'attempts': 1, 'errors': [],
        }
        mock_engine = MagicMock()
        mock_engine.extract_content.return_value = ("article word " * 60, "heuristic", 0.9)

        with patch.object(search_mod, 'ThreadPoolExecutor', _CapturingTPE):
            engine = EnterpriseSearchEngine(
                max_workers=3,
                enable_js_fallback=False,
                enable_alternate_source=False,
                enable_dns_fallback=False,
                enable_bandit=False,
            )
            engine.extractor = mock_engine
            engine.execute_search_from_urls([{'url': 'u1'}, {'url': 'u2'}])

        assert captured.get('max_workers') == 3, f"ThreadPoolExecutor max_workers={captured.get('max_workers')!r}, expected 3"


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
