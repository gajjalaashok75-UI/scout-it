#!/usr/bin/env python3
"""
Tests for domain learning system.
"""

import pytest
import tempfile
from pathlib import Path
from scout_it.domain_routing import DomainLearningSystem, normalize_domain, BANNED_DOMAINS


class TestDomainLearning:
    """Test domain learning functionality."""
    
    def test_normalize_domain(self):
        """Domain normalization should remove www. prefix."""
        assert normalize_domain("www.example.com") == "example.com"
        assert normalize_domain("Example.com") == "example.com"
        assert normalize_domain("WWW.TEST.COM") == "test.com"
        assert normalize_domain("example.com") == "example.com"
    
    def test_get_domain(self):
        """Extract and normalize domain from URLs."""
        learning = DomainLearningSystem()
        
        assert learning.get_domain("https://www.example.com/article") == "example.com"
        assert learning.get_domain("https://example.com/article") == "example.com"
        assert learning.get_domain("http://WWW.TEST.COM/page") == "test.com"
    
    def test_banned_domains(self):
        """Banned domains should return banned strategy."""
        learning = DomainLearningSystem()
        
        for domain in BANNED_DOMAINS:
            strategy, confidence = learning.get_strategy(f"https://{domain}/article")
            assert strategy == "banned"
            assert confidence == 1.0
    
    def test_strategy_unknown_no_data(self):
        """Unknown domains should return unknown strategy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            learning = DomainLearningSystem(stats_file=stats_file)
            
            strategy, confidence = learning.get_strategy("https://newsite.com/article")
            assert strategy == "unknown"
            assert confidence == 0.0
    
    def test_strategy_playwright(self):
        """Domains with failed requests and successful Playwright should use Playwright."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            learning = DomainLearningSystem(stats_file=stats_file)
            
            # Record failed requests
            for _ in range(5):
                learning.record_extraction("https://jssite.com/page", "requests", False, 50)
            
            # Record successful Playwright
            for _ in range(5):
                learning.record_extraction("https://jssite.com/page", "playwright", True, 800)
            
            strategy, confidence = learning.get_strategy("https://jssite.com/other")
            assert strategy == "playwright"
            assert confidence >= 0.80
    
    def test_strategy_requests(self):
        """Domains with successful requests should use requests strategy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            learning = DomainLearningSystem(stats_file=stats_file)
            
            # Record successful requests
            for _ in range(5):
                learning.record_extraction("https://simplesite.com/page", "requests", True, 600)
            
            strategy, confidence = learning.get_strategy("https://simplesite.com/other")
            assert strategy == "requests"
            assert confidence >= 0.80
    
    def test_strategy_banned_calculation(self):
        """Domains where Playwright never works should be banned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            learning = DomainLearningSystem(stats_file=stats_file)
            
            # Record 5 failed Playwright attempts
            for _ in range(5):
                learning.record_extraction("https://blocked.com/page", "playwright", False, 0)
            
            strategy, confidence = learning.get_strategy("https://blocked.com/other")
            assert strategy == "banned"
            assert confidence == 1.0
    
    def test_www_normalization_merge(self):
        """www. and non-www. versions should be merged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            learning = DomainLearningSystem(stats_file=stats_file)
            
            # Record with www
            learning.record_extraction("https://www.example.com/page1", "requests", True, 500)
            learning.record_extraction("https://www.example.com/page2", "requests", True, 600)
            
            # Record without www
            learning.record_extraction("https://example.com/page3", "requests", True, 700)
            
            # Should be merged under example.com
            assert "example.com" in learning.domains
            assert "www.example.com" not in learning.domains
            assert learning.domains["example.com"]["requests_attempts"] == 3
            assert learning.domains["example.com"]["requests_successes"] == 3
    
    def test_persistence(self):
        """Domain learning should persist across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            
            # First instance - record data
            learning1 = DomainLearningSystem(stats_file=stats_file)
            for _ in range(5):
                learning1.record_extraction("https://persistent.com/page", "requests", True, 600)
            learning1.force_save()
            
            # Second instance - load data
            learning2 = DomainLearningSystem(stats_file=stats_file)
            strategy, confidence = learning2.get_strategy("https://persistent.com/other")
            assert strategy == "requests"
            assert confidence >= 0.80
    
    def test_stats_summary(self):
        """Stats summary should categorize domains correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "domain_learning.json"
            learning = DomainLearningSystem(stats_file=stats_file)
            
            # Playwright domain
            for _ in range(5):
                learning.record_extraction("https://pw.com/page", "requests", False)
                learning.record_extraction("https://pw.com/page", "playwright", True, 800)
            
            # Requests domain
            for _ in range(5):
                learning.record_extraction("https://req.com/page", "requests", True, 600)
            
            # Banned domain
            for _ in range(5):
                learning.record_extraction("https://banned.com/page", "playwright", False)
            
            summary = learning.get_stats_summary()
            assert summary['playwright_domains'] >= 1
            assert summary['requests_domains'] >= 1
            assert summary['banned_domains'] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
