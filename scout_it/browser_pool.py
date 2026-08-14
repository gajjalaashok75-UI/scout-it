#!/usr/bin/env python3
"""
Playwright Browser Pool for Reusing Browser Instances (Per-Thread)

This module provides a thread-local browser pool to avoid launching
Chromium for every URL extraction. Each ThreadPoolExecutor worker thread
gets its own browser instance that is reused for all URLs in that thread.

Playwright's sync_playwright() uses greenlets which are thread-local,
so we cannot share a single browser across threads. Instead, we maintain
one browser per thread, reducing overhead from:
    - 10 URLs × 5s launch = 50s wasted
To:
    - 5 workers × 5s launch = 25s initial cost (60% reduction)
    - Each URL after first: ~0.5s page creation only

For 10 URLs with 5 workers:
    Before: 10 × 5s = 50s
    After:  5 × 5s + 10 × 0.5s = 30s (40% faster)
"""

import logging
import random
import threading
from typing import Optional, Any, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PlaywrightBrowserPool:
    """Thread-local Playwright browser pool for efficient extraction.
    
    Each thread gets its own browser instance that is reused for all
    pages created in that thread. This avoids the greenlet threading
    issue with Playwright's sync API while still providing significant
    performance gains.
    
    Thread 1: launch browser → page1, page2, page3 → close browser
    Thread 2: launch browser → page4, page5, page6 → close browser
    Thread 3: launch browser → page7, page8, page9 → close browser
    
    Expected savings: 50s → 30s for 10 URLs (40% faster)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.thread_local = threading.local()
        self.enabled = False
        # Track {thread_id: browser} for cleanup. The browser is created in
        # the owning thread (Playwright sync API is thread-local via greenlets),
        # so stop() closes each one from the thread that owns it would be
        # unsafe. Instead we close through the stored objects directly —
        # browser.close()/playwright.stop() are safe to call cross-thread for
        # the purpose of releasing the OS process.
        self._browsers: Dict[int, Any] = {}
        self._playwrights: Dict[int, Any] = {}
        self._registry_lock = threading.Lock()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        ]
    
    @classmethod
    def get_instance(cls):
        """Get or create singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def start(self):
        """Enable browser pool (browsers are created lazily per thread)."""
        self.enabled = True
        logger.info("Browser pool: Enabled (thread-local browsers will be created on-demand)")
    
    def stop(self):
        """Close all thread-local browsers and stop Playwright instances.

        Browsers launched by worker threads are tracked in ``self._browsers``
        and closed here so Chromium/Playwright OS processes are released —
        previously this was a no-op (``pass``) that leaked a headless
        Chromium process per worker thread on every ``web-search``/``news-search``
        with JS rendering enabled.
        """
        self.enabled = False
        with self._registry_lock:
            browsers = list(self._browsers.values())
            playwrights = list(self._playwrights.values())
            self._browsers.clear()
            self._playwrights.clear()

        for browser in browsers:
            try:
                browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser during pool stop: {e}")

        for pw in playwrights:
            try:
                pw.stop()
            except Exception as e:
                logger.warning(f"Error stopping Playwright during pool stop: {e}")

        logger.info(f"Browser pool: Disabled (closed {len(browsers)} browser(s), {len(playwrights)} playwright instance(s))")
    
    def _get_thread_browser(self):
        """Get or create browser for current thread."""
        if not hasattr(self.thread_local, 'pw'):
            # First time this thread is using the browser pool
            try:
                from playwright.sync_api import sync_playwright
                
                self.thread_local.pw = sync_playwright().start()
                self.thread_local.browser = self.thread_local.pw.chromium.launch(headless=True)
                
                thread_id = threading.get_ident()
                with self._registry_lock:
                    self._browsers[thread_id] = self.thread_local.browser
                    self._playwrights[thread_id] = self.thread_local.pw
                
                logger.info(f"Browser pool: Chromium launched for thread {thread_id}")
            except ImportError:
                logger.warning("Playwright not installed - browser pool unavailable")
                raise
            except Exception as e:
                logger.error(f"Failed to launch browser in thread: {e}")
                raise
        
        return self.thread_local.browser
    
    def _close_thread_browser(self):
        """Close browser for current thread (called automatically on thread exit)."""
        tid = threading.get_ident()
        if hasattr(self.thread_local, 'browser'):
            try:
                self.thread_local.browser.close()
                logger.info(f"Browser pool: Chromium closed for thread {tid}")
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            finally:
                self.thread_local.browser = None
                with self._registry_lock:
                    self._browsers.pop(tid, None)
        
        if hasattr(self.thread_local, 'pw'):
            try:
                self.thread_local.pw.stop()
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {e}")
            finally:
                self.thread_local.pw = None
                with self._registry_lock:
                    self._playwrights.pop(tid, None)
    
    @contextmanager
    def get_page(self, user_agent: Optional[str] = None):
        """Get a new page from the thread-local browser.
        
        Usage:
            pool = PlaywrightBrowserPool.get_instance()
            pool.start()
            
            # In each thread:
            with pool.get_page() as page:
                page.goto(url)
                html = page.content()
            
            pool.stop()
        """
        if not self.enabled:
            raise RuntimeError("Browser pool not enabled - call start() first")
        
        browser = self._get_thread_browser()
        ua = user_agent or random.choice(self.user_agents)
        page = None
        
        try:
            page = browser.new_page(user_agent=ua)
            
            # Apply stealth patches
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)
            
            yield page
        
        finally:
            if page:
                try:
                    page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")
    
    def is_available(self) -> bool:
        """Check if browser pool is enabled."""
        return self.enabled
    
    @classmethod
    def reset(cls):
        """Reset singleton instance (mainly for testing)."""
        if cls._instance:
            cls._instance.stop()
        cls._instance = None


# Convenience functions

def start_browser_pool():
    """Start the global browser pool."""
    pool = PlaywrightBrowserPool.get_instance()
    pool.start()
    return pool


def stop_browser_pool():
    """Stop the global browser pool."""
    pool = PlaywrightBrowserPool.get_instance()
    pool.stop()


@contextmanager
def get_browser_page(user_agent: Optional[str] = None):
    """Get a page from the global browser pool.
    
    Usage:
        with get_browser_page() as page:
            page.goto(url)
            html = page.content()
    """
    pool = PlaywrightBrowserPool.get_instance()
    with pool.get_page(user_agent=user_agent) as page:
        yield page
