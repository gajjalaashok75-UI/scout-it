#!/usr/bin/env python3
"""
Integration tests for browser pool with news-search command.

Verifies that:
1. Browser pool integrates correctly with news-search
2. Extraction uses browser pool for Playwright tier
3. No threading errors occur during parallel extraction
"""

import pytest
import time
from unittest.mock import Mock


class TestBrowserPoolIntegration:
    """Test browser pool integration with news extraction."""
    
    def test_browser_pool_with_fetch_resilient_local_page(self):
        """fetch_resilient should use browser pool when provided."""
        pytest.importorskip("playwright")
        
        from scout_it.browser_pool import PlaywrightBrowserPool
        from scout_it.extraction import fetch_resilient
        
        # Start browser pool
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        try:
            # Fetch a simple local page (doesn't require network)
            result = fetch_resilient(
                url="about:blank",
                timeout=5,
                max_retries=1,
                enable_js_fallback=True,
                force_js=True,  # Force Playwright tier
                browser_pool=pool,
            )
            
            # Should succeed with Playwright tier
            assert result["status"] == "success"
            assert result["tier"] == "playwright"
            assert "html" in result or "errors" in result
            
        finally:
            pool.stop()
    
    def test_browser_pool_parallel_extraction_local(self):
        """Browser pool should work with parallel extraction."""
        pytest.importorskip("playwright")
        
        from concurrent.futures import ThreadPoolExecutor
        from scout_it.browser_pool import PlaywrightBrowserPool
        from scout_it.extraction import fetch_resilient
        
        # Start browser pool
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        test_urls = ["about:blank"] * 3
        
        results = []
        
        def extract_url(url):
            result = fetch_resilient(
                url=url,
                timeout=5,
                max_retries=1,
                enable_js_fallback=True,
                force_js=True,  # Force Playwright
                browser_pool=pool,
            )
            results.append(result)
            return result
        
        try:
            # Extract in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(extract_url, url) for url in test_urls]
                for future in futures:
                    future.result()
            
            # All extractions should succeed
            assert len(results) == 3
            assert all(r["status"] == "success" for r in results)
            assert all(r["tier"] == "playwright" for r in results)
            
        finally:
            pool.stop()
    
    def test_browser_pool_memory_leak_prevention(self):
        """Browser pool should not leak memory with many page creations."""
        pytest.importorskip("playwright")
        
        from scout_it.browser_pool import PlaywrightBrowserPool
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        try:
            # Create and close many pages
            for i in range(10):
                with pool.get_page() as page:
                    page.goto("about:blank")
                    html = page.content()
                    assert len(html) > 0
            
            # Should still be available after many operations
            assert pool.is_available()
            
        finally:
            pool.stop()
    
    def test_browser_pool_thread_safety(self):
        """Browser pool should be thread-safe."""
        pytest.importorskip("playwright")
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from scout_it.browser_pool import PlaywrightBrowserPool
        import threading
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        results = []
        lock = threading.Lock()
        
        def fetch_in_thread(index):
            thread_id = threading.get_ident()
            try:
                with pool.get_page() as page:
                    page.goto("about:blank")
                    html = page.content()
                    with lock:
                        results.append({
                            "index": index,
                            "thread_id": thread_id,
                            "success": True,
                            "html_length": len(html)
                        })
            except Exception as e:
                with lock:
                    results.append({
                        "index": index,
                        "thread_id": thread_id,
                        "success": False,
                        "error": str(e)
                    })
        
        try:
            # Run 15 fetches across 5 threads
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(fetch_in_thread, i) for i in range(15)]
                for future in as_completed(futures):
                    future.result()
            
            # All should succeed
            assert len(results) == 15
            successes = [r for r in results if r["success"]]
            failures = [r for r in results if not r["success"]]
            
            assert len(successes) == 15, f"Failures: {failures}"
            
            # Should have used multiple threads
            thread_ids = {r["thread_id"] for r in results}
            assert len(thread_ids) >= 3, f"Only used {len(thread_ids)} threads"
            
        finally:
            pool.stop()
    
    def test_browser_pool_integration_with_cli(self):
        """Test that browser pool is properly integrated with _extract_news_content."""
        pytest.importorskip("playwright")
        
        from scout_it.cli import _extract_news_content
        
        # Create mock results (minimal data needed for extraction)
        mock_results = [
            {
                "url": "about:blank",
                "title": "Test Article",
                "body": "Test content for extraction",
            }
        ]
        
        # Run extraction (should use browser pool internally)
        try:
            enriched = _extract_news_content(
                results=mock_results,
                max_workers=1,
                max_fetch_retries=1,
                enable_js_fallback=True,
            )
            
            # Should have processed the result
            assert len(enriched) == 1
            assert enriched[0] is not None
            
            # Check that extraction was attempted
            assert "extraction_status" in enriched[0]
            
        except Exception as e:
            # If there's an error, it should not be a greenlet error
            assert "greenlet" not in str(e).lower(), f"Greenlet error occurred: {e}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

