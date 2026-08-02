#!/usr/bin/env python3
"""Test source URL resolvers for wrapper sites (MSN, Yahoo, AOL)."""

import pytest
from scout_it.source_resolvers import (
    is_wrapper_domain,
    resolve_msn,
    resolve_yahoo,
    resolve_aol,
    resolve_source_url,
    get_domain_ranking_multiplier,
    WRAPPER_DOMAINS,
    LOW_VALUE_DOMAINS,
)


class TestWrapperDetection:
    """Test wrapper domain detection."""
    
    def test_msn_detected(self):
        assert is_wrapper_domain("https://www.msn.com/article/123")
        assert is_wrapper_domain("https://msn.com/article/123")
    
    def test_yahoo_detected(self):
        assert is_wrapper_domain("https://news.yahoo.com/article/123")
        assert is_wrapper_domain("https://yahoo.com/article/123")
    
    def test_aol_detected(self):
        assert is_wrapper_domain("https://www.aol.com/article/123")
        assert is_wrapper_domain("https://aol.com/article/123")
    
    def test_google_news_detected(self):
        assert is_wrapper_domain("https://news.google.com/articles/123")
    
    def test_regular_domain_not_detected(self):
        assert not is_wrapper_domain("https://techcrunch.com/article")
        assert not is_wrapper_domain("https://reuters.com/article")
        assert not is_wrapper_domain("https://arstechnica.com/article")


class TestMSNResolver:
    """Test MSN URL resolution."""
    
    def test_resolve_from_url_parameter(self):
        msn_url = "https://www.msn.com/en-us/news/technology/article?url=https://www.cbsnews.com/news/ai-security/"
        resolved = resolve_msn(msn_url)
        assert resolved == "https://www.cbsnews.com/news/ai-security/"
    
    def test_resolve_from_original_url_parameter(self):
        msn_url = "https://www.msn.com/article?originalUrl=https://reuters.com/technology/ai-news/"
        resolved = resolve_msn(msn_url)
        assert resolved == "https://reuters.com/technology/ai-news/"
    
    def test_resolve_from_html_canonical(self):
        msn_url = "https://www.msn.com/article/123"
        html = '''
        <html>
        <head>
            <link rel="canonical" href="https://www.cbsnews.com/news/tech-story/" />
        </head>
        </html>
        '''
        resolved = resolve_msn(msn_url, html)
        assert resolved == "https://www.cbsnews.com/news/tech-story/"
    
    def test_resolve_from_html_og_url(self):
        msn_url = "https://www.msn.com/article/123"
        html = '''
        <html>
        <head>
            <meta property="og:url" content="https://www.reuters.com/technology/story/" />
        </head>
        </html>
        '''
        resolved = resolve_msn(msn_url, html)
        assert resolved == "https://www.reuters.com/technology/story/"
    
    def test_resolve_from_html_data_attribute(self):
        msn_url = "https://www.msn.com/article/123"
        html = '''
        <div data-original-url="https://apnews.com/article/tech-123"></div>
        '''
        resolved = resolve_msn(msn_url, html)
        assert resolved == "https://apnews.com/article/tech-123"
    
    def test_resolve_from_continue_reading_link(self):
        msn_url = "https://www.msn.com/article/123"
        html = '''
        <a href="https://www.cnbc.com/tech/article.html">Continue reading at CNBC</a>
        '''
        resolved = resolve_msn(msn_url, html)
        assert resolved == "https://www.cnbc.com/tech/article.html"
    
    def test_no_resolution_possible(self):
        msn_url = "https://www.msn.com/article/123"
        resolved = resolve_msn(msn_url)
        assert resolved is None
    
    def test_ignores_msn_canonical_loop(self):
        msn_url = "https://www.msn.com/article/123"
        html = '''
        <link rel="canonical" href="https://www.msn.com/article/123" />
        '''
        resolved = resolve_msn(msn_url, html)
        assert resolved is None  # Should not resolve to itself


class TestYahooResolver:
    """Test Yahoo News URL resolution."""
    
    def test_resolve_from_url_parameter(self):
        yahoo_url = "https://news.yahoo.com/article?url=https://reuters.com/tech/story"
        resolved = resolve_yahoo(yahoo_url)
        assert resolved == "https://reuters.com/tech/story"
    
    def test_resolve_from_canonical(self):
        yahoo_url = "https://news.yahoo.com/article/123"
        html = '''
        <link rel="canonical" href="https://www.reuters.com/article/tech" />
        '''
        resolved = resolve_yahoo(yahoo_url, html)
        assert resolved == "https://www.reuters.com/article/tech"
    
    def test_resolve_from_source_link(self):
        yahoo_url = "https://news.yahoo.com/article/123"
        html = '''
        <a class="article-source-link" href="https://apnews.com/article/123">AP News</a>
        '''
        resolved = resolve_yahoo(yahoo_url, html)
        assert resolved == "https://apnews.com/article/123"


class TestAOLResolver:
    """Test AOL URL resolution."""
    
    def test_resolve_aol_uses_yahoo_logic(self):
        aol_url = "https://www.aol.com/news/article?url=https://reuters.com/tech"
        resolved = resolve_aol(aol_url)
        assert resolved == "https://reuters.com/tech"


class TestSourceURLResolver:
    """Test unified source URL resolver."""
    
    def test_resolve_msn_url(self):
        msn_url = "https://www.msn.com/article?url=https://cbsnews.com/tech"
        resolved = resolve_source_url(msn_url)
        assert resolved == "https://cbsnews.com/tech"
    
    def test_resolve_yahoo_url(self):
        yahoo_url = "https://news.yahoo.com/article?url=https://reuters.com/tech"
        resolved = resolve_source_url(yahoo_url)
        assert resolved == "https://reuters.com/tech"
    
    def test_no_resolution_for_regular_domain(self):
        regular_url = "https://techcrunch.com/article"
        resolved = resolve_source_url(regular_url)
        assert resolved is None
    
    def test_resolve_with_html_context(self):
        msn_url = "https://www.msn.com/article/123"
        html = '<link rel="canonical" href="https://apnews.com/article/123" />'
        resolved = resolve_source_url(msn_url, html)
        assert resolved == "https://apnews.com/article/123"


class TestRankingMultiplier:
    """Test domain ranking penalties/multipliers."""
    
    def test_wrapper_domain_penalty(self):
        msn_url = "https://www.msn.com/article/123"
        multiplier = get_domain_ranking_multiplier(msn_url, was_resolved=False)
        assert multiplier == 0.25  # Heavy penalty for unresolved wrapper
    
    def test_resolved_wrapper_no_penalty(self):
        msn_url = "https://www.msn.com/article/123"
        multiplier = get_domain_ranking_multiplier(msn_url, was_resolved=True)
        assert multiplier == 1.0  # No penalty when resolved
    
    def test_regular_domain_no_penalty(self):
        regular_url = "https://techcrunch.com/article"
        multiplier = get_domain_ranking_multiplier(regular_url, was_resolved=False)
        assert multiplier == 1.0  # No penalty for regular domains
    
    def test_yahoo_wrapper_penalty(self):
        yahoo_url = "https://news.yahoo.com/article/123"
        multiplier = get_domain_ranking_multiplier(yahoo_url, was_resolved=False)
        assert multiplier == 0.25


class TestRealWorldExamples:
    """Test with real-world URL patterns."""
    
    def test_msn_with_ocid_parameter(self):
        """MSN often uses ocid parameter with encoded URLs."""
        msn_url = "https://www.msn.com/en-us/news/technology/article/ar-AA123?ocid=something&url=https://cbsnews.com/news/story"
        resolved = resolve_msn(msn_url)
        # Should find the url parameter
        assert resolved is not None
    
    def test_complex_yahoo_redirect(self):
        """Yahoo uses complex redirect URLs."""
        yahoo_url = "https://news.yahoo.com/amphtml/story-123.html"
        html = '<link rel="canonical" href="https://www.reuters.com/article/tech-123" />'
        resolved = resolve_yahoo(yahoo_url, html)
        assert resolved == "https://www.reuters.com/article/tech-123"
    
    def test_multiple_resolution_attempts(self):
        """Should try multiple methods in order."""
        msn_url = "https://www.msn.com/article/123"
        html = '''
        <html>
        <head>
            <link rel="canonical" href="https://www.msn.com/article/123" />
            <meta property="og:url" content="https://www.cbsnews.com/real-article/" />
        </head>
        </html>
        '''
        resolved = resolve_msn(msn_url, html)
        # Should skip MSN canonical and use og:url
        assert resolved == "https://www.cbsnews.com/real-article/"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
