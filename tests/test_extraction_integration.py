#!/usr/bin/env python3
"""
Integration tests for extraction quality validation and source resolution.

Tests the complete extraction pipeline including:
1. Source URL resolution (MSN, Yahoo, AOL wrappers)
2. Quality validation and automatic Playwright escalation
3. Domain-level learning
4. End-to-end extraction flow
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from scout_it.extraction_quality import (
    assess_extraction_quality,
    should_escalate_to_playwright,
    record_domain_extraction,
    should_skip_to_playwright,
)
from scout_it.source_resolvers import (
    is_wrapper_domain,
    resolve_source_url,
    get_domain_ranking_multiplier,
)


class TestExtractionQualityIntegration:
    """Test extraction quality validation in realistic scenarios."""
    
    def test_short_extraction_triggers_escalation(self):
        """Verify short extractions trigger Playwright escalation."""
        # Simulate Ars Technica scenario: requests gets 26 words
        short_content = " ".join(["word"] * 26)
        
        should_escalate, reason = should_escalate_to_playwright(
            content=short_content,
            expected_title="Important Technology Article",
            extraction_tier="requests",
        )
        
        assert should_escalate is True
        assert "insufficient_words" in reason
    
    def test_blocked_page_triggers_escalation(self):
        """Verify blocked pages trigger Playwright escalation."""
        blocked_content = """
        Checking your browser before accessing the website.
        Cloudflare DDoS protection is active.
        """
        
        should_escalate, reason = should_escalate_to_playwright(
            content=blocked_content,
            expected_title="Article Title",
            extraction_tier="requests",
        )
        
        assert should_escalate is True
        assert "blocked_page_detected" in reason
    
    def test_paywall_detected_no_escalation(self):
        """Verify paywalls are detected but NOT escalated (Playwright won't help)."""
        paywall_content = """
        Breaking News Article Title
        
        This is the introduction to an important article...
        
        Subscribe to read the full article. Premium members only.
        """
        
        should_escalate, reason = should_escalate_to_playwright(
            content=paywall_content,
            expected_title="Breaking News Article",
            extraction_tier="requests",
        )
        
        assert should_escalate is False
        assert "paywall_detected" in reason
    
    def test_high_quality_no_escalation(self):
        """Verify high-quality extractions don't trigger escalation."""
        # Generate realistic article content (300 words)
        paragraphs = []
        for i in range(5):
            paragraphs.append(" ".join([f"word{j}" for j in range(60)]))
        good_content = "\n\n".join(paragraphs)
        
        should_escalate, reason = should_escalate_to_playwright(
            content=good_content,
            expected_title="word0 word1 word2",  # Words from title in content
            extraction_tier="requests",
        )
        
        assert should_escalate is False
        assert "quality_acceptable" in reason or "already_using" in reason
    
    def test_playwright_tier_no_escalation(self):
        """Verify already-Playwright extractions don't re-escalate."""
        short_content = "short"
        
        should_escalate, reason = should_escalate_to_playwright(
            content=short_content,
            expected_title="Article",
            extraction_tier="playwright",
        )
        
        assert should_escalate is False
        assert "already_using_playwright" in reason
    
    def test_poor_title_match_triggers_escalation(self):
        """Verify poor title-content match triggers escalation."""
        # Content has no words from the title
        content = "Lorem ipsum dolor sit amet consectetur adipiscing elit " * 50
        
        should_escalate, reason = should_escalate_to_playwright(
            content=content,
            expected_title="Artificial Intelligence Machine Learning Neural Networks",
            extraction_tier="requests",
        )
        
        # Should escalate due to poor title match
        assert should_escalate is True
        assert "poor_title_match" in reason


class TestSourceResolutionIntegration:
    """Test source URL resolution in realistic scenarios."""
    
    def test_msn_wrapper_detected_and_resolved(self):
        """Verify MSN wrapper URLs are detected and resolved."""
        msn_url = "https://www.msn.com/en-us/news/technology/article?url=https://cbsnews.com/tech-story"
        
        # Detection
        assert is_wrapper_domain(msn_url) is True
        
        # Resolution
        resolved = resolve_source_url(msn_url)
        assert resolved == "https://cbsnews.com/tech-story"
        
        # Ranking penalty for unresolved
        penalty_unresolved = get_domain_ranking_multiplier(msn_url, was_resolved=False)
        assert penalty_unresolved == 0.25
        
        # No penalty for resolved
        penalty_resolved = get_domain_ranking_multiplier(msn_url, was_resolved=True)
        assert penalty_resolved == 1.0
    
    def test_yahoo_wrapper_detected_and_resolved(self):
        """Verify Yahoo wrapper URLs are detected and resolved."""
        yahoo_url = "https://news.yahoo.com/article-123.html"
        html = '<link rel="canonical" href="https://reuters.com/tech/story" />'
        
        # Detection
        assert is_wrapper_domain(yahoo_url) is True
        
        # Resolution with HTML
        resolved = resolve_source_url(yahoo_url, html=html)
        assert resolved == "https://reuters.com/tech/story"
    
    def test_regular_domain_no_resolution(self):
        """Verify regular domains are not treated as wrappers."""
        regular_url = "https://techcrunch.com/2024/article"
        
        # Not a wrapper
        assert is_wrapper_domain(regular_url) is False
        
        # No resolution
        resolved = resolve_source_url(regular_url)
        assert resolved is None
        
        # No ranking penalty
        multiplier = get_domain_ranking_multiplier(regular_url)
        assert multiplier == 1.0


class TestDomainLearning:
    """Test domain-level learning functionality."""
    
    def test_domain_learning_skip_to_playwright(self):
        """Verify domain learning recommends Playwright for JS-heavy sites."""
        test_url = "https://js-heavy-site.example.com/article"
        
        # Record multiple failed requests attempts
        for _ in range(5):
            record_domain_extraction(
                url=test_url,
                tier="requests",
                success=False,
                word_count=30,
            )
        
        # Record successful Playwright attempts
        for _ in range(5):
            record_domain_extraction(
                url=test_url,
                tier="playwright",
                success=True,
                word_count=1500,
            )
        
        # Should now recommend skipping to Playwright
        skip, confidence = should_skip_to_playwright(test_url)
        assert skip is True
        assert confidence > 0.8
    
    def test_domain_learning_continue_requests(self):
        """Verify domain learning continues using requests for working sites."""
        test_url = "https://good-site.example.com/article"
        
        # Record successful requests attempts
        for _ in range(10):
            record_domain_extraction(
                url=test_url,
                tier="requests",
                success=True,
                word_count=1200,
            )
        
        # Should NOT skip to Playwright
        skip, confidence = should_skip_to_playwright(test_url)
        assert skip is False


class TestEndToEndExtraction:
    """Test complete extraction flow with mocked HTTP calls."""
    
    @patch('scout_it.cli.fetch_resilient')
    @patch('scout_it.cli.ExtractionEngine')
    def test_extraction_with_quality_escalation(self, mock_engine_class, mock_fetch):
        """Test extraction with automatic Playwright escalation."""
        # Setup mocks
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        
        # First call (requests): returns short content
        mock_fetch.side_effect = [
            {
                'status': 'success',
                'html': '<html><body>Short content</body></html>',
                'final_url': 'https://example.com/article',
                'tier': 'requests',
                'errors': [],
            },
            # Second call (Playwright escalation): returns full content
            {
                'status': 'success',
                'html': '<html><body>' + ('Long content word ' * 200) + '</body></html>',
                'final_url': 'https://example.com/article',
                'tier': 'playwright',
                'errors': [],
            },
        ]
        
        # Mock extraction
        mock_engine.extract_content.side_effect = [
            ("Short content", "heuristic", 0.5),  # First extraction
            ("Long content " * 200, "heuristic", 0.9),  # Second extraction
        ]
        
        # Import and call extraction function
        from scout_it.cli import _extract_news_content
        
        results = [
            {
                'url': 'https://example.com/article',
                'title': 'Test Article',
                'body': 'Summary',
            }
        ]
        
        enriched = _extract_news_content(
            results,
            max_workers=1,
            enable_js_fallback=True,
            max_fetch_retries=2,
        )
        
        # Verify escalation occurred (fetch_resilient called twice)
        assert mock_fetch.call_count == 2
        
        # Verify second call had force_js=True
        second_call_kwargs = mock_fetch.call_args_list[1][1]
        assert second_call_kwargs['force_js'] is True
    
    @patch('scout_it.cli.fetch_resilient')
    @patch('scout_it.cli.ExtractionEngine')
    def test_extraction_with_wrapper_resolution(self, mock_engine_class, mock_fetch):
        """Test extraction with MSN wrapper resolution."""
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        
        # Mock fetch
        mock_fetch.return_value = {
            'status': 'success',
            'html': '<html><body>' + ('Article content ' * 100) + '</body></html>',
            'final_url': 'https://cbsnews.com/tech/story',
            'tier': 'requests',
            'errors': [],
        }
        
        # Mock extraction
        mock_engine.extract_content.return_value = (
            "Article content " * 100,
            "heuristic",
            0.9,
        )
        
        from scout_it.cli import _extract_news_content
        
        results = [
            {
                'url': 'https://www.msn.com/article?url=https://cbsnews.com/tech/story',
                'title': 'Tech News Story',
                'body': 'Summary',
            }
        ]
        
        enriched = _extract_news_content(
            results,
            max_workers=1,
            enable_js_fallback=True,
            max_fetch_retries=2,
        )
        
        # Verify wrapper was detected and URL updated
        assert enriched[0].get('original_wrapper_url') is not None
        # Resolved URL should be used
        assert 'cbsnews.com' in enriched[0]['url']


class TestQualityScoring:
    """Test quality scoring algorithm."""
    
    def test_quality_score_excellent(self):
        """Test scoring for excellent content."""
        # 1000 words, 10 paragraphs, good title match
        content = "\n\n".join([" ".join(["word"] * 100) for _ in range(10)])
        
        quality = assess_extraction_quality(
            content=content,
            expected_title="word word word",
            html="<html></html>",
        )
        
        assert quality.word_count >= 1000
        assert quality.paragraph_count >= 10
        assert quality.quality_score >= 0.75  # High quality (adjusted threshold)
        assert quality.should_escalate is False
    
    def test_quality_score_acceptable(self):
        """Test scoring for acceptable content."""
        # 300 words, 5 paragraphs, better title match
        content = "\n\n".join([" ".join(["word"] * 60) for _ in range(5)])
        
        quality = assess_extraction_quality(
            content=content,
            expected_title="word word other",  # 2/3 words match = 0.67 similarity
            html="<html></html>",
        )
        
        assert quality.word_count >= 200
        assert quality.paragraph_count >= 3
        # Should be acceptable (>0.50) with good word count and structure
        assert quality.quality_score >= 0.50
        assert quality.should_escalate is False
    
    def test_quality_score_poor(self):
        """Test scoring for poor content."""
        # Very short content
        content = "Just a few words here"
        
        quality = assess_extraction_quality(
            content=content,
            expected_title="Long Article About Technology",
            html="<html></html>",
        )
        
        assert quality.word_count < 150
        assert quality.quality_score < 0.50
        assert quality.should_escalate is True


def test_all_modules_importable():
    """Verify all extraction modules can be imported."""
    try:
        from scout_it import extraction_quality
        from scout_it import source_resolvers
        assert hasattr(extraction_quality, 'should_escalate_to_playwright')
        assert hasattr(source_resolvers, 'resolve_source_url')
        print("✅ All extraction modules imported successfully")
    except ImportError as e:
        pytest.fail(f"Failed to import modules: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
