#!/usr/bin/env python3
"""
Tests for PlaywrightBrowserPool - Thread-Local Browser Reuse

Verifies that:
1. Browser pool can be started and stopped
2. Each thread gets its own browser instance
3. Pages can be created and used within threads
4. Performance improvement from browser reuse is measurable
5. No greenlet threading errors occur
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from scout_it.browser_pool import PlaywrightBrowserPool


class TestBrowserPool:
    """Test browser pool functionality."""
    
    def test_browser_pool_singleton(self):
        """Browser pool should use singleton pattern."""
        pool1 = PlaywrightBrowserPool.get_instance()
        pool2 = PlaywrightBrowserPool.get_instance()
        assert pool1 is pool2
    
    def test_browser_pool_start_stop(self):
        """Browser pool should start and stop cleanly."""
        pool = PlaywrightBrowserPool.get_instance()
        
        # Should not be available before starting
        assert not pool.is_available()
        
        # Start pool
        pool.start()
        assert pool.is_available()
        
        # Stop pool
        pool.stop()
        assert not pool.is_available()
    
    def test_browser_pool_page_creation(self):
        """Browser pool should create pages successfully."""
        pytest.importorskip("playwright")
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        try:
            # Create and use a page
            with pool.get_page() as page:
                page.goto("about:blank")
                html = page.content()
                assert "<html" in html.lower()
        finally:
            pool.stop()
    
    def test_browser_pool_multiple_pages_same_thread(self):
        """Browser pool should reuse browser for multiple pages in same thread."""
        pytest.importorskip("playwright")
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        try:
            # Create multiple pages in same thread
            for i in range(3):
                with pool.get_page() as page:
                    page.goto("about:blank")
                    html = page.content()
                    assert "<html" in html.lower()
        finally:
            pool.stop()
    
    def test_browser_pool_with_threading(self):
        """Browser pool should work correctly with ThreadPoolExecutor."""
        pytest.importorskip("playwright")
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        results = []
        
        def fetch_page(url_index):
            """Fetch a page using browser pool."""
            try:
                with pool.get_page() as page:
                    page.goto("about:blank")
                    html = page.content()
                    results.append({
                        "index": url_index,
                        "success": True,
                        "thread_id": threading.get_ident()
                    })
            except Exception as e:
                results.append({
                    "index": url_index,
                    "success": False,
                    "error": str(e),
                    "thread_id": threading.get_ident()
                })
        
        try:
            # Use ThreadPoolExecutor with 3 workers
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(fetch_page, i) for i in range(6)]
                for future in futures:
                    future.result()  # Wait for completion
            
            # All fetches should succeed
            assert len(results) == 6
            assert all(r["success"] for r in results)
            
            # Should have used multiple threads
            thread_ids = {r["thread_id"] for r in results}
            assert len(thread_ids) >= 2  # At least 2 different threads
            
        finally:
            pool.stop()
    
    def test_browser_pool_performance_improvement(self):
        """Browser pool should provide measurable performance improvement."""
        pytest.importorskip("playwright")
        
        # Skip this test if we're in an asyncio event loop (test environment issue)
        import asyncio
        try:
            asyncio.get_running_loop()
            pytest.skip("Cannot test performance in asyncio event loop")
        except RuntimeError:
            pass
        
        # Test WITHOUT browser pool (launch browser per URL)
        start_no_pool = time.time()
        
        def fetch_without_pool():
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto("about:blank")
                page.close()
                browser.close()
        
        # Just 2 URLs to keep test fast
        for _ in range(2):
            fetch_without_pool()
        
        time_without_pool = time.time() - start_no_pool
        
        # Test WITH browser pool (reuse browser)
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        start_with_pool = time.time()
        
        try:
            for _ in range(2):
                with pool.get_page() as page:
                    page.goto("about:blank")
        finally:
            pool.stop()
        
        time_with_pool = time.time() - start_with_pool
        
        # Browser pool should be faster (at least 20% improvement)
        improvement = (time_without_pool - time_with_pool) / time_without_pool
        assert improvement > 0.20, f"Expected >20% improvement, got {improvement*100:.1f}%"
    
    def test_browser_pool_no_greenlet_error(self):
        """Browser pool should not raise greenlet threading errors."""
        pytest.importorskip("playwright")
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        errors = []
        
        def fetch_in_thread(index):
            try:
                with pool.get_page() as page:
                    page.goto("about:blank")
                    html = page.content()
                    assert len(html) > 0
            except Exception as e:
                errors.append({
                    "index": index,
                    "error": str(e),
                    "type": type(e).__name__
                })
        
        try:
            # Run in parallel threads
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(fetch_in_thread, i) for i in range(10)]
                for future in futures:
                    future.result()
            
            # Should have no greenlet errors
            greenlet_errors = [e for e in errors if "greenlet" in e["error"].lower()]
            assert len(greenlet_errors) == 0, f"Greenlet errors found: {greenlet_errors}"
            
            # Should have no errors at all
            assert len(errors) == 0, f"Errors found: {errors}"
            
        finally:
            pool.stop()
    
    def test_browser_pool_custom_user_agent(self):
        """Browser pool should accept custom user agent."""
        pytest.importorskip("playwright")
        
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        custom_ua = "CustomBot/1.0"
        
        try:
            with pool.get_page(user_agent=custom_ua) as page:
                page.goto("about:blank")
                # Just verify page was created successfully
                assert page is not None
        finally:
            pool.stop()
    
    def test_browser_pool_reset(self):
        """Browser pool reset should clean up properly."""
        pool = PlaywrightBrowserPool.get_instance()
        pool.start()
        
        # Reset should stop the pool
        PlaywrightBrowserPool.reset()
        
        # Get new instance
        new_pool = PlaywrightBrowserPool.get_instance()
        assert new_pool is not pool
        assert not new_pool.is_available()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
