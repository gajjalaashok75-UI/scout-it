#!/usr/bin/env python3
"""
Integration test for complete optimization stack.

Tests that all 3 optimizations work together:
1. Browser pool (thread-local browser reuse)
2. Domain routing (skip to optimal tier)
3. Faster Playwright navigation (domcontentloaded + article selectors)
"""

import pytest
from scout_it.browser_pool import PlaywrightBrowserPool
from scout_it.domain_routing import DomainRouter, ALWAYS_PLAYWRIGHT_DOMAINS, ALWAYS_REQUESTS_DOMAINS


class TestOptimizationStack:
    """Test complete optimization stack integration."""
    
    def test_browser_pool_available(self):
        """Browser pool module should be importable."""
        pool = PlaywrightBrowserPool.get_instance()
        assert pool is not None
        assert not pool.is_available()  # Not started yet
    
    def test_domain_router_available(self):
        """Domain router module should be importable."""
        router = DomainRouter()
        assert router is not None
        assert hasattr(router, 'should_use_playwright')
        assert hasattr(router, 'record_extraction')
    
    def test_hardcoded_domains_loaded(self):
        """Hardcoded domain lists should be populated."""
        assert len(ALWAYS_PLAYWRIGHT_DOMAINS) > 0
        assert len(ALWAYS_REQUESTS_DOMAINS) > 0
        
        # Verify some known domains
        assert "arstechnica.com" in ALWAYS_PLAYWRIGHT_DOMAINS
        assert "techcrunch.com" in ALWAYS_REQUESTS_DOMAINS
    
    def test_domain_routing_integration(self):
        """Domain routing should recommend correct tier."""
        router = DomainRouter()
        
        # JS-heavy domain should use Playwright
        should_use_pw, reason, conf = router.should_use_playwright("https://arstechnica.com/article")
        assert should_use_pw is True
        assert conf == 1.0
        
        # Simple domain should use requests
        should_use_pw, reason, conf = router.should_use_playwright("https://techcrunch.com/article")
        assert should_use_pw is False
        assert conf == 1.0
    
    def test_optimization_modules_importable(self):
        """All optimization modules should be importable without errors."""
        try:
            from scout_it.browser_pool import PlaywrightBrowserPool
            from scout_it.domain_routing import DomainRouter, get_domain_router
            from scout_it.extraction import fetch_resilient, EnterpriseSearchEngine
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import optimization modules: {e}")
    
    def test_browser_pool_singleton(self):
        """Browser pool should use singleton pattern."""
        pool1 = PlaywrightBrowserPool.get_instance()
        pool2 = PlaywrightBrowserPool.get_instance()
        assert pool1 is pool2
    
    def test_domain_router_persistence_path(self):
        """Domain router should have valid persistence path."""
        router = DomainRouter()
        assert router.stats_file is not None
        assert str(router.stats_file).endswith("domain_stats.json")
    
    def test_extraction_pipeline_components(self):
        """Verify the unified extraction pipeline has all optimization components."""
        import inspect
        from scout_it.extraction import EnterpriseSearchEngine

        # The unified engine is the extraction entrypoint for both web-search
        # and news-search flows.
        sig = inspect.signature(EnterpriseSearchEngine.__init__)
        params = list(sig.parameters.keys())

        assert 'max_workers' in params
        assert 'enable_js_fallback' in params
        assert 'max_fetch_retries' in params
        assert hasattr(EnterpriseSearchEngine, 'execute_search_from_urls')
    def test_optimization_configuration(self):
        """Test optimization configuration."""
        from scout_it.browser_pool import PlaywrightBrowserPool
        from scout_it.domain_routing import get_domain_router
        
        # Browser pool configuration
        pool = PlaywrightBrowserPool.get_instance()
        assert hasattr(pool, 'thread_local')
        assert hasattr(pool, 'enabled')
        
        # Domain router configuration
        router = get_domain_router()
        assert hasattr(router, 'stats')
        assert hasattr(router, 'stats_file')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
