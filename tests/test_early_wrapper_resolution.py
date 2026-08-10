#!/usr/bin/env python3
"""
Test early wrapper URL resolution in the unified news-search pipeline.

Verifies that wrapper URLs (MSN, Yahoo, AOL, Google News) are resolved to
original publisher URLs BEFORE ranking, not during extraction. These tests
exercise the real news_search flow (which uses EnterpriseSearchEngine, the
same unified pipeline as web-search) with discovery + ranking + extraction
mocked so wrapper-resolution behaviour can be asserted offline.
"""

import pytest
from unittest import mock
import importlib


# news_search lives in the hyphenated scout_it/news-search/ package and binds
# its discovery + ranking helpers into its own namespace. Patch that module's
# attributes directly (not scout_it.cli.*) so the mocks actually take effect.
_news_mod = importlib.import_module('.news-search.news_search', package='scout_it')


class TestEarlyWrapperResolution:
    """Test wrapper resolution happens before ranking."""

    @staticmethod
    def _mock_engine():
        m = mock.Mock()
        m.execute_search_from_urls.return_value = []
        return m

    def test_msn_urls_resolved_before_ranking(self):
        """Verify MSN URLs are resolved before ranking is called."""
        from scout_it.cli import news_search

        with mock.patch.object(_news_mod, '_ddgs_list_search_with_retry') as mock_ddgs, \
             mock.patch.object(_news_mod, 'rank_candidates_initial') as mock_rank, \
             mock.patch('scout_it.extraction.EnterpriseSearchEngine') as mock_engine_cls:
            mock_ddgs.return_value = (
                [{
                    'title': 'Test Article',
                    'url': 'https://www.msn.com/article?url=https://cbsnews.com/tech-story',
                    'href': 'https://www.msn.com/article?url=https://cbsnews.com/tech-story',
                    'body': 'Summary',
                    'source': 'MSN',
                }],
                {'total': 1, 'execution_time': 1.0},
            )
            mock_rank.return_value = [{
                'title': 'Test Article',
                'url': 'https://cbsnews.com/tech-story',
                'href': 'https://cbsnews.com/tech-story',
                'body': 'Summary',
            }]
            mock_engine_cls.return_value = self._mock_engine()

            news_search(query="test query", max_results=1, retry_on_zero_success=False)

            assert mock_rank.called
            candidates = mock_rank.call_args[0][0]
            assert len(candidates) == 1
            assert 'cbsnews.com' in candidates[0]['url']
            assert candidates[0].get('was_resolved') is True
            assert candidates[0].get('original_wrapper_url') is not None
            assert 'msn.com' in candidates[0]['original_wrapper_url']

    def test_unresolved_wrappers_dropped(self):
        """Verify unresolved wrapper URLs are dropped from candidates."""
        from scout_it.cli import news_search

        with mock.patch.object(_news_mod, '_ddgs_list_search_with_retry') as mock_ddgs, \
             mock.patch.object(_news_mod, 'rank_candidates_initial') as mock_rank, \
             mock.patch('scout_it.extraction.EnterpriseSearchEngine') as mock_engine_cls:
            mock_ddgs.return_value = (
                [
                    {'title': 'Test Article 1', 'url': 'https://www.msn.com/article/abc123',
                     'href': 'https://www.msn.com/article/abc123', 'body': 'Summary'},
                    {'title': 'Test Article 2', 'url': 'https://techcrunch.com/article',
                     'href': 'https://techcrunch.com/article', 'body': 'Summary'},
                ],
                {'total': 2, 'execution_time': 1.0},
            )
            mock_rank.return_value = []
            mock_engine_cls.return_value = self._mock_engine()

            news_search(query="test query", max_results=5, retry_on_zero_success=False)

            assert mock_rank.called
            candidates = mock_rank.call_args[0][0]
            assert len(candidates) == 1
            assert 'techcrunch.com' in candidates[0]['url']
            assert candidates[0].get('was_resolved') is not True

    def test_duplicate_after_resolution_dropped(self):
        """Verify duplicate URLs after resolution are dropped."""
        from scout_it.cli import news_search

        with mock.patch.object(_news_mod, '_ddgs_list_search_with_retry') as mock_ddgs, \
             mock.patch.object(_news_mod, 'rank_candidates_initial') as mock_rank, \
             mock.patch('scout_it.extraction.EnterpriseSearchEngine') as mock_engine_cls:
            mock_ddgs.return_value = (
                [
                    {'title': 'Article via MSN', 'url': 'https://www.msn.com/article?url=https://reuters.com/story',
                     'href': 'https://www.msn.com/article?url=https://reuters.com/story', 'body': 'Summary'},
                    {'title': 'Same Article Direct', 'url': 'https://reuters.com/story',
                     'href': 'https://reuters.com/story', 'body': 'Summary 2'},
                ],
                {'total': 2, 'execution_time': 1.0},
            )
            mock_rank.return_value = []
            mock_engine_cls.return_value = self._mock_engine()

            news_search(query="test query", max_results=5, retry_on_zero_success=False)

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

        assert callable(is_wrapper_domain)
        assert callable(resolve_source_url)
        assert callable(resolve_msn)
        assert callable(resolve_yahoo)
        assert callable(resolve_aol)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
