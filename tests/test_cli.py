#!/usr/bin/env python3
"""
Comprehensive test suite for web search, image search, and URL fetch functionality.

Run tests with: pytest tests/test_cli.py -v

Coverage:
- web_search() function
- image_search() function  
- fetch_url() function
- backward compatibility (fatchurl)
- Error handling and edge cases
"""

import sys
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gakr_ddgs
from gakr_ddgs.cleaner import advanced_clean_text, process_results

# Import modules to test
from gakr_ddgs.cli import (
    _extract_html_title,
    fatchurl,
    fetch_url,
    image_search,
    news_search,
    video_search,
    web_search,
)
from gakr_ddgs.extraction import (
    EnterpriseResult,
    EnterpriseSearchEngine,
    ImageSearchEngine,
    ImageSearchResult,
)


class TestWebSearch:
    """Test web_search function"""
    
    def test_web_search_function_exists(self):
        """Test that web_search function is callable"""
        assert callable(web_search)
    
    def test_web_search_returns_tuple(self):
        """Test that web_search returns (results, stats) tuple"""
        with mock.patch('gakr_ddgs.cli.EnterpriseSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_search.return_value = []
            mock_instance.stats = {'total': 0, 'success': 0}
            mock_engine.return_value = mock_instance
            
            with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                mock_process.return_value = ([], {'successful': 0, 'failed': 0})
                
                results, stats = web_search("test query", max_results=10, workers=2)
                
                assert isinstance(results, list)
                assert isinstance(stats, dict)
                assert 'search_engine' in stats
                assert 'cleaner' in stats
    
    def test_web_search_with_custom_parameters(self):
        """Test web_search with custom max_results and workers"""
        with mock.patch('gakr_ddgs.cli.EnterpriseSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_search.return_value = []
            mock_instance.stats = {'total': 0, 'success': 0}
            mock_engine.return_value = mock_instance
            
            with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                mock_process.return_value = ([], {})
                
                web_search("query", max_results=50, workers=4)

                # Verify engine was instantiated with correct workers
                mock_engine.assert_called_once_with(max_workers=4)
                # Verify execute_search was called
                assert mock_instance.execute_search.called


class TestImageSearch:
    """Test image_search function"""
    
    def test_image_search_function_exists(self):
        """Test that image_search function is callable"""
        assert callable(image_search)
    
    def test_image_search_returns_tuple(self):
        """Test that image_search returns (results, stats) tuple"""
        with mock.patch('gakr_ddgs.cli.ImageSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_image_search.return_value = []
            mock_instance.stats = {'total': 0, 'success': 0, 'execution_time': 0.5}
            mock_engine.return_value = mock_instance
            
            results, stats = image_search("sunset", max_results=20)
            
            assert isinstance(results, list)
            assert isinstance(stats, dict)
            assert 'search_engine' in stats
    
    def test_image_search_calls_engine_with_correct_params(self):
        """Test that image_search calls ImageSearchEngine with correct parameters"""
        with mock.patch('gakr_ddgs.cli.ImageSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_image_search.return_value = []
            mock_instance.stats = {'total': 0, 'success': 0, 'execution_time': 0.1}
            mock_engine.return_value = mock_instance
            
            image_search("landscape", max_results=30)

            # Verify engine was instantiated
            assert mock_engine.called
            # Verify execute_image_search was called
            assert mock_instance.execute_image_search.called


class TestFetchUrl:
    """Test fetch_url function"""
    
    def test_fetch_url_function_exists(self):
        """Test that fetch_url function is callable"""
        assert callable(fetch_url)
    
    def test_fetch_url_invalid_url(self):
        """Test fetch_url with invalid URL"""
        result = fetch_url("not-a-valid-url")
        assert "error" in result
        assert "Invalid URL" in result["error"]
    
    def test_fetch_url_valid_url_structure(self):
        """Test fetch_url with valid URL structure"""
        with mock.patch('gakr_ddgs.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test Page</title><body>Content</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"<html><title>Test Page</title><body>Content</body></html>"
            mock_get.return_value = mock_response
            
            with mock.patch('gakr_ddgs.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Test content", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    result = fetch_url("https://example.com")

                    assert "result" in result
                    assert "stats" in result
                    assert result["result"]["title"] == "Test Page"
    
    def test_fetch_url_http_scheme(self):
        """Test fetch_url accepts HTTP scheme validation"""
        with mock.patch('gakr_ddgs.cli.requests.get', side_effect=Exception("network blocked")):
            result = fetch_url("http://example.com/test")
            # Should fail gracefully without raising
            assert isinstance(result, dict)
            assert "error" in result
    
    def test_fetch_url_https_scheme(self):
        """Test fetch_url accepts HTTPS scheme validation"""
        with mock.patch('gakr_ddgs.cli.requests.get', side_effect=Exception("network blocked")):
            result = fetch_url("https://example.com/test")
            # Should fail gracefully without raising
            assert isinstance(result, dict)
            assert "error" in result
    
    def test_fetch_url_with_max_chars(self):
        """Test fetch_url with max_chars parameter - verifies truncation"""
        with mock.patch('gakr_ddgs.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test</title><body>Long content here</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"<html><title>Test</title><body>Long content here</body></html>"
            mock_get.return_value = mock_response
            
            with mock.patch('gakr_ddgs.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                # Return long content that should be truncated
                long_content = "This is a very long content that should be truncated to verify the truncation works"
                mock_extract_instance.extract_content.return_value = (long_content, "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    result = fetch_url("https://example.com", max_chars=20)
                    
                    # Content should be truncated to 20 chars
                    assert len(result["result"]["main_content"]) == 20
    
    def test_fetch_url_with_max_size(self):
        """Test fetch_url with max_size parameter - truncates response"""
        with mock.patch('gakr_ddgs.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            # Large HTML response (2000 bytes)
            large_html = "<html>" + ("x" * 1950) + "</html>"
            mock_response.text = large_html
            mock_response.url = "https://example.com"
            mock_response.content = large_html.encode('utf-8')
            mock_get.return_value = mock_response
            
            with mock.patch('gakr_ddgs.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Content", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    # Request with max_size of 1kb (1024 bytes) - should truncate
                    result = fetch_url("https://example.com", max_size="1kb")
                    
                    # Should successfully process even though content was truncated
                    assert isinstance(result, dict)
                    assert "result" in result
    
    def test_fetch_url_with_max_size_small_content(self):
        """Test fetch_url with max_size parameter when content is smaller than limit"""
        with mock.patch('gakr_ddgs.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test</title><body>Small</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"x" * 500  # 500 bytes
            mock_get.return_value = mock_response
            
            with mock.patch('gakr_ddgs.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Content", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    result = fetch_url("https://example.com", max_size="1mb")  # 1mb should allow 500 bytes
                    
                    assert "result" in result
                    assert "error" not in result

    def test_fetch_url_with_both_max_chars_and_max_size_error(self):
        """Test fetch_url rejects when both max_chars and max_size are provided"""
        # This should return an error immediately without making any requests
        result = fetch_url(
            "https://example.com",
            max_chars=10000,
            max_size="500kb"
        )
        
        # Should have error key and no result key
        assert "error" in result
        assert "Cannot use both --max-chars and --max-size together" in result["error"]
        assert "--max-chars" in result["error"]
        assert "--max-size" in result["error"]


class TestSizeParsingUtility:
    """Test _parse_size_string utility function"""
    
    def test_parse_size_string_bytes(self):
        """Test parsing size in bytes"""
        from gakr_ddgs.cli import _parse_size_string
        
        assert _parse_size_string("1024b") == 1024
        assert _parse_size_string("100B") == 100
        assert _parse_size_string("512 b") == 512
    
    def test_parse_size_string_kilobytes(self):
        """Test parsing size in kilobytes"""
        from gakr_ddgs.cli import _parse_size_string
        
        assert _parse_size_string("1kb") == 1024
        assert _parse_size_string("100kb") == 102400
        assert _parse_size_string("1 kb") == 1024
        assert _parse_size_string("1.5KB") == 1536
    
    def test_parse_size_string_megabytes(self):
        """Test parsing size in megabytes"""
        from gakr_ddgs.cli import _parse_size_string
        
        assert _parse_size_string("1mb") == 1024 ** 2
        assert _parse_size_string("5mb") == 5 * (1024 ** 2)
        assert _parse_size_string("1 mb") == 1024 ** 2
        assert _parse_size_string("2.5MB") == int(2.5 * (1024 ** 2))
    
    def test_parse_size_string_gigabytes(self):
        """Test parsing size in gigabytes"""
        from gakr_ddgs.cli import _parse_size_string
        
        assert _parse_size_string("1gb") == 1024 ** 3
        assert _parse_size_string("2gb") == 2 * (1024 ** 3)
        assert _parse_size_string("1 gb") == 1024 ** 3
    
    def test_parse_size_string_invalid(self):
        """Test parsing invalid size strings"""
        from gakr_ddgs.cli import _parse_size_string
        
        assert _parse_size_string(None) is None
        assert _parse_size_string("") is None
        assert _parse_size_string("invalid") is None
        assert _parse_size_string("100tb") is None  # Unsupported unit
        assert _parse_size_string("abc mb") is None


class TestBackwardCompatibility:
    """Test backward compatibility"""
    
    def test_fatchurl_calls_fetch_url(self):
        """Test that fatchurl (old name) still works"""
        with mock.patch('gakr_ddgs.cli.fetch_url') as mock_fetch:
            mock_fetch.return_value = {"result": "test"}
            
            result = fatchurl("https://example.com")
            
            mock_fetch.assert_called_once_with("https://example.com", 25)


class TestHtmlTitleExtraction:
    """Test _extract_html_title function"""
    
    def test_extract_title_from_html(self):
        """Test extracting title from HTML"""
        html = "<html><head><title>Test Page Title</title></head></html>"
        title = _extract_html_title(html)
        assert title == "Test Page Title"
    
    def test_extract_title_with_extra_whitespace(self):
        """Test extracting title with extra whitespace"""
        html = "<html><title>  Test   Title   </title></html>"
        title = _extract_html_title(html)
        assert "Test" in title and "Title" in title
    
    def test_extract_title_missing(self):
        """Test when title tag is missing"""
        html = "<html><body>No title here</body></html>"
        title = _extract_html_title(html)
        assert title == ""
    
    def test_extract_title_empty_html(self):
        """Test with empty HTML"""
        title = _extract_html_title("")
        assert title == ""
    
    def test_extract_title_case_insensitive(self):
        """Test that title extraction is case insensitive"""
        html = "<html><TITLE>Test Title</TITLE></html>"
        title = _extract_html_title(html)
        assert title == "Test Title"


class TestEnterpriseSearchEngine:
    """Test EnterpriseSearchEngine class"""
    
    def test_engine_initialization(self):
        """Test EnterpriseSearchEngine initialization"""
        engine = EnterpriseSearchEngine(max_workers=4)
        assert engine.max_workers == 4
        assert engine.timeout == 25
        assert len(engine.results) == 0
    
    def test_engine_stats_structure(self):
        """Test that engine stats have expected structure"""
        engine = EnterpriseSearchEngine()
        assert 'total' in engine.stats
        assert 'success' in engine.stats
        assert 'high_quality' in engine.stats
        assert 'avg_confidence' in engine.stats


class TestImageSearchEngine:
    """Test ImageSearchEngine class"""
    
    def test_image_engine_initialization(self):
        """Test ImageSearchEngine initialization"""
        engine = ImageSearchEngine(timeout=30)
        assert engine.timeout == 30
        assert len(engine.results) == 0
    
    def test_image_engine_stats_structure(self):
        """Test that image engine stats have expected structure"""
        engine = ImageSearchEngine()
        assert 'total' in engine.stats
        assert 'success' in engine.stats
        assert 'failed' in engine.stats
        assert 'execution_time' in engine.stats


class TestContentCleaning:
    """Test content cleaning functions"""
    
    def test_advanced_clean_text_basic(self):
        """Test advanced_clean_text with basic content"""
        text = "This is a   test\n\nWith multiple   spaces"
        cleaned = advanced_clean_text(text)
        assert cleaned  # Should return something
        assert "test" in cleaned.lower()
    
    def test_advanced_clean_text_empty(self):
        """Test advanced_clean_text with empty string"""
        cleaned = advanced_clean_text("")
        assert cleaned == ""
    
    def test_advanced_clean_text_none(self):
        """Test advanced_clean_text with None"""
        cleaned = advanced_clean_text(None)
        assert cleaned == ""


class TestProcessResults:
    """Test process_results function"""
    
    def test_process_results_empty_list(self):
        """Test process_results with empty list"""
        results, stats = process_results([])
        assert isinstance(results, list)
        assert isinstance(stats, dict)
        assert stats['total_input'] == 0
    
    def test_process_results_filters_failed(self):
        """Test that process_results filters out failed extractions"""
        results = [
            {
                'extraction_status': 'success',
                'main_content': 'Valid content here',
                'url': 'https://example.com',
                'title': 'Title',
                'position': 1,
                'confidence_score': 0.9
            },
            {
                'extraction_status': 'failed',
                'main_content': '',
                'url': 'https://example2.com',
                'title': 'Title 2',
                'position': 2,
                'confidence_score': 0.3
            }
        ]
        
        processed, stats = process_results(results)
        assert stats['successful'] == 1
        assert stats['failed'] == 1


class TestFunctionAvailable:
    """Test that all expected functions are available"""
    
    def test_web_search_available(self):
        """Test web_search is available in search module"""
        import references.search as search
        assert hasattr(search, 'web_search')
    
    def test_image_search_available(self):
        """Test image_search is available in search module"""
        import references.search as search
        assert hasattr(search, 'image_search')
    
    def test_fetch_url_available(self):
        """Test fetch_url is available in search module"""
        import references.search as search
        assert hasattr(search, 'fetch_url')
    
    def test_fatchurl_backward_compat(self):
        """Test fatchurl is still available for backward compatibility"""
        import references.search as search
        assert hasattr(search, 'fatchurl')


class TestIntegration:
    """Integration tests"""
    
    def test_full_pipeline_with_mock_data(self):
        """Test the full pipeline with mocked data"""
        with mock.patch('gakr_ddgs.extraction.EnterpriseSearchEngine'):
            with mock.patch('gakr_ddgs.cli.process_results') as mock_process:
                mock_process.return_value = (
                    [
                        {
                            'title': 'Test Result',
                            'url': 'https://example.com',
                            'cleaned_content': 'Test content'
                        }
                    ],
                    {'successful': 1, 'failed': 0}
                )
                
                results, stats = web_search("test", max_results=10, workers=2)
                
                assert len(results) == 1
                assert results[0]['title'] == 'Test Result'


class TestAdvancedSearchFeatures:
    """Tests for retry and advanced DDGS feature wiring."""

    def test_news_search_uses_ddgs_wrapper(self):
        with mock.patch('gakr_ddgs.cli._ddgs_list_search') as mock_ddgs:
            mock_ddgs.return_value = ([{'title': 'news'}], {'total': 1, 'success': 1, 'execution_time': 0.1})
            results, stats = news_search('economy', max_results=5)

            assert len(results) == 1
            assert stats['search_engine']['success'] == 1
            call_args, call_kwargs = mock_ddgs.call_args
            assert call_args[0] == 'news'
            assert call_kwargs['max_results'] == 5

    def test_ddgs_list_search_query_only_fallback(self, monkeypatch):
        import references.search as search

        class DummyDDGS:
            def __init__(self, timeout=None):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def news(self, query):
                return [
                    {'title': f'{query}-1'},
                    {'title': f'{query}-2'},
                    {'title': f'{query}-3'},
                ]

        monkeypatch.setattr(search, 'DDGS', DummyDDGS)

        results, stats = search._ddgs_list_search('news', 'dog', max_results=2)
        assert len(results) == 2
        assert stats['success'] == 2

    def test_video_search_uses_ddgs_wrapper(self):
        with mock.patch('gakr_ddgs.cli._ddgs_list_search') as mock_ddgs:
            mock_ddgs.return_value = ([{'title': 'video'}], {'total': 1, 'success': 1, 'execution_time': 0.2})
            results, stats = video_search('dogs', max_results=3, duration='short')

            assert len(results) == 1
            assert stats['search_engine']['success'] == 1
            call_args, call_kwargs = mock_ddgs.call_args
            assert call_args[0] == 'videos'
            assert call_kwargs['options']['duration'] == 'short'

    def test_image_engine_retries_when_first_attempt_empty(self, monkeypatch):
        class DummyDDGS:
            attempts = 0

            def __init__(self, timeout=None):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def images(self, *args, **kwargs):
                DummyDDGS.attempts += 1
                if DummyDDGS.attempts == 1:
                    return []
                return [{
                    'title': 'Dog',
                    'image': 'https://example.com/dog.jpg',
                    'url': 'https://example.com',
                    'width': 1024,
                    'height': 768,
                }]

        monkeypatch.setattr(gakr_ddgs.extraction, 'DDGS', DummyDDGS)

        engine = ImageSearchEngine()
        results = engine.execute_image_search(
            'dog',
            max_results=3,
            retry_on_zero_success=True,
            max_zero_success_retries=1,
            retry_backoff_seconds=0,
        )

        assert len(results) == 1
        assert engine.stats['attempts'] == 2

    def test_image_engine_dimension_filters(self, monkeypatch):
        class DummyDDGS:
            def __init__(self, timeout=None):
                self.timeout = timeout

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def images(self, *args, **kwargs):
                return [
                    {'title': 'small', 'image': 'https://example.com/a.jpg', 'url': 'https://example.com/a', 'width': 320, 'height': 200},
                    {'title': 'good', 'image': 'https://example.com/b.jpg', 'url': 'https://example.com/b', 'width': 1280, 'height': 720},
                    {'title': 'missing', 'image': 'https://example.com/c.jpg', 'url': 'https://example.com/c'},
                ]

        monkeypatch.setattr(gakr_ddgs.extraction, 'DDGS', DummyDDGS)

        engine = ImageSearchEngine()
        results = engine.execute_image_search(
            'dog',
            max_results=5,
            retry_on_zero_success=False,
            min_width=800,
            min_height=600,
        )

        assert len(results) == 1
        assert results[0].title == 'good'
        assert engine.stats['filtered_out_by_dimensions'] == 2

    def test_image_engine_invalid_dimension_range(self):
        engine = ImageSearchEngine()
        with pytest.raises(ValueError):
            engine.execute_image_search('dog', min_width=900, max_width=800)

    def test_web_engine_retries_when_extracted_content_is_empty(self, monkeypatch):
        def fake_phase_search(self, query, max_results, search_options=None):
            self.results = [
                EnterpriseResult(
                    position=1,
                    title='Only result',
                    url='https://example.com',
                    snippet='stub',
                )
            ]

        monkeypatch.setattr(EnterpriseSearchEngine, '_phase_search', fake_phase_search)

        mock_response = mock.Mock()
        mock_response.url = 'https://example.com'
        mock_response.text = '<html><body>Empty</body></html>'
        mock_response.raise_for_status.return_value = None

        engine = EnterpriseSearchEngine(max_workers=1)
        engine.extractor.session.get = mock.Mock(return_value=mock_response)
        engine.extractor.extract_content = mock.Mock(return_value=('', 'trafilatura', 0.9))

        engine.execute_search(
            'dog',
            max_results=1,
            retry_on_zero_success=True,
            max_zero_success_retries=1,
            retry_backoff_seconds=0,
        )

        assert engine.stats['success'] == 0
        assert engine.stats['attempts'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
