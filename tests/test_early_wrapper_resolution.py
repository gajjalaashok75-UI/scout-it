#!/usr/bin/env python3
"""
Test early wrapper URL resolution in news search pipeline.

Verifies that wrapper URLs (MSN, Yahoo, AOL) are resolved to original
publisher URLs BEFORE ranking, not during extraction.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestEarlyWrapperResolution:
    """Test wrapper resolution happens before ranking."""
    
    @patch('scout_it.cli._ddgs_list_search_with_retry')
    @patch('scout_it.cli._extract_news_content')
    @patch('scout_it.staged_ranker.rank_candidates_initial')
    def test_msn_urls_resolved_before_ranking(
        self,
        mock_rank,
        mock_extract,
        mock_ddgs,
    ):
        """Verify MSN URLs are resolved before ranking is called."""
        from scout_it.cli import news_search
        
        # Mock DDGS returning MSN URL
        mock_ddgs.return_value = (
            [
                {
                    'title': 'Test Article',
                    'url': 'https://www.msn.com/article?url=https://cbsnews.com/tech-story',
                    'href': 'https://www.msn.com/article?url=https://cbsnews.com/tech-story',
                    'body': 'Summary',
                    'source': 'MSN',
                }
            ],
            {'total': 1, 'execution_time': 1.0}
        )
        
        # Mock ranking to capture what it receives
        mock_rank.return_value = [
            {
                'title': 'Test Article',
                'url': 'https://cbsnews.com/tech-story',  # Should be resolved
                'href': 'https://cbsnews.com/tech-story',
                'body': 'Summary',
            }
        ]
        
        # Mock extraction
        mock_extract.return_value = []
        
        # Run news search
        news_search(
            query="test query",
            max_results=1,
            retry_on_zero_success=False,
        )
        
        # Verify ranking received resolved URL, not MSN URL
        assert mock_rank.called
        candidates = mock_rank.call_args[0][0]
        
        # Should have resolved CBS News URL
        assert len(candidates) == 1
        assert 'cbsnews.com' in candidates[0]['url']
        assert candidates[0].get('was_resolved') is True
        assert candidates[0].get('original_wrapper_url') is not None
        assert 'msn.com' in candidates[0]['original_wrapper_url']
    
    @patch('scout_it.cli._ddgs_list_search_with_retry')
    @patch('scout_it.cli._extract_news_content')
    @patch('scout_it.staged_ranker.rank_candidates_initial')
    def test_unresolved_wrappers_dropped(
        self,
        mock_rank,
        mock_extract,
        mock_ddgs,
    ):
        """Verify unresolved wrapper URLs are dropped from candidates."""
        from scout_it.cli import news_search
        
        # Mock DDGS returning MSN URL without resolvable parameters
        mock_ddgs.return_value = (
            [
                {
                    'title': 'Test Article 1',
                    'url': 'https://www.msn.com/article/abc123',  # No url parameter
                    'href': 'https://www.msn.com/article/abc123',
                    'body': 'Summary',
                },
                {
                    'title': 'Test Article 2',
                    'url': 'https://techcrunch.com/article',  # Regular URL
                    'href': 'https://techcrunch.com/article',
                    'body': 'Summary',
                },
            ],
            {'total': 2, 'execution_time': 1.0}
        )
        
        # Mock ranking
        mock_rank.return_value = []
        
        # Mock extraction
        mock_extract.return_value = []
        
        # Run news search
        news_search(
            query="test query",
            max_results=5,
            retry_on_zero_success=False,
        )
        
        # Verify ranking only received 1 candidate (MSN dropped, TechCrunch kept)
        assert mock_rank.called
        candidates = mock_rank.call_args[0][0]
        
        assert len(candidates) == 1
        assert 'techcrunch.com' in candidates[0]['url']
        assert candidates[0].get('was_resolved') is not True
    
    @patch('scout_it.cli._ddgs_list_search_with_retry')
    @patch('scout_it.cli._extract_news_content')
    @patch('scout_it.staged_ranker.rank_candidates_initial')
    def test_duplicate_after_resolution_dropped(
        self,
        mock_rank,
        mock_extract,
        mock_ddgs,
    ):
        """Verify duplicate URLs after resolution are dropped."""
        from scout_it.cli import news_search
        
        # Mock DDGS returning 2 MSN URLs that resolve to same publisher
        mock_ddgs.return_value = (
            [
                {
                    'title': 'Article via MSN',
                    'url': 'https://www.msn.com/article?url=https://reuters.com/story',
                    'href': 'https://www.msn.com/article?url=https://reuters.com/story',
                    'body': 'Summary',
                },
                {
                    'title': 'Same Article Direct',
                    'url': 'https://reuters.com/story',  # Same as resolved MSN
                    'href': 'https://reuters.com/story',
                    'body': 'Summary 2',
                },
            ],
            {'total': 2, 'execution_time': 1.0}
        )
        
        # Mock ranking
        mock_rank.return_value = []
        
        # Mock extraction
        mock_extract.return_value = []
        
        # Run news search
        news_search(
            query="test query",
            max_results=5,
            retry_on_zero_success=False,
        )
        
        # Verify only 1 candidate reaches ranking (duplicate dropped)
        assert mock_rank.called
        candidates = mock_rank.call_args[0][0]
        
        assert len(candidates) == 1
        assert 'reuters.com' in candidates[0]['url']


class TestWrapperResolutionIntegration:
    """Integration tests for wrapper resolution in full pipeline."""
    
    def test_wrapper_domains_list_complete(self):
        """Verify all major wrapper domains are supported."""
        from scout_it.source_resolvers import WRAPPER_DOMAINS
        
        assert 'msn.com' in WRAPPER_DOMAINS
        assert 'www.msn.com' in WRAPPER_DOMAINS
        assert 'news.yahoo.com' in WRAPPER_DOMAINS
        assert 'aol.com' in WRAPPER_DOMAINS
        assert 'news.google.com' in WRAPPER_DOMAINS
    
    def test_resolution_methods_exist(self):
        """Verify resolution functions are accessible."""
        from scout_it.source_resolvers import (
            is_wrapper_domain,
            resolve_source_url,
            resolve_msn,
            resolve_yahoo,
            resolve_aol,
        )
        
        # All functions should be callable
        assert callable(is_wrapper_domain)
        assert callable(resolve_source_url)
        assert callable(resolve_msn)
        assert callable(resolve_yahoo)
        assert callable(resolve_aol)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
