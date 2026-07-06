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

import json
import os
import pytest
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import scout_it
from scout_it.cleaner import (
    _is_content_section,
    _is_nav_paragraph,
    advanced_clean_text,
    extract_content_sections,
    paragraphs,
    process_results,
)

# Import modules to test
from scout_it.cli import (
    _check_max_size_warning,
    _extract_html_title,
    fatchurl,
    fetch_url,
    image_search,
    news_search,
    video_search,
    web_search,
)
from scout_it.extraction import (
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
        with mock.patch('scout_it.cli.EnterpriseSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_search.return_value = []
            mock_instance.stats = {'total': 0, 'success': 0}
            mock_engine.return_value = mock_instance
            
            with mock.patch('scout_it.cli.process_results') as mock_process:
                mock_process.return_value = ([], {'successful': 0, 'failed': 0})
                
                results, stats = web_search("test query", max_results=10, workers=2)
                
                assert isinstance(results, list)
                assert isinstance(stats, dict)
                assert 'search_engine' in stats
                assert 'cleaner' in stats
    
    def test_web_search_with_custom_parameters(self):
        """Test web_search with custom max_results and workers"""
        with mock.patch('scout_it.cli.EnterpriseSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_search.return_value = []
            mock_instance.stats = {'total': 0, 'success': 0}
            mock_engine.return_value = mock_instance
            
            with mock.patch('scout_it.cli.process_results') as mock_process:
                mock_process.return_value = ([], {})
                
                web_search("query", max_results=50, workers=4)

                # Verify engine was instantiated with correct workers (plus the
                # new resilient-fetch config, which defaults to 3 retries / JS fallback on)
                mock_engine.assert_called_once_with(max_workers=4, max_fetch_retries=3, enable_js_fallback=True)
                # Verify execute_search was called
                assert mock_instance.execute_search.called


class TestImageSearch:
    """Test image_search function"""
    
    def test_image_search_function_exists(self):
        """Test that image_search function is callable"""
        assert callable(image_search)
    
    def test_image_search_returns_tuple(self):
        """Test that image_search returns (results, stats) tuple"""
        with mock.patch('scout_it.cli.ImageSearchEngine') as mock_engine:
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
        with mock.patch('scout_it.cli.ImageSearchEngine') as mock_engine:
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
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test Page</title><body>Content</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"<html><title>Test Page</title><body>Content</body></html>"
            mock_get.return_value = mock_response
            
            with mock.patch('scout_it.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Test content", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('scout_it.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    result = fetch_url("https://example.com")

                    assert "result" in result
                    assert "stats" in result
                    assert result["result"]["title"] == "Test Page"
    
    def test_fetch_url_http_scheme(self):
        """Test fetch_url accepts HTTP scheme validation"""
        with mock.patch('scout_it.cli.requests.get', side_effect=Exception("network blocked")):
            result = fetch_url("http://example.com/test")
            # Should fail gracefully without raising
            assert isinstance(result, dict)
            assert "error" in result
    
    def test_fetch_url_https_scheme(self):
        """Test fetch_url accepts HTTPS scheme validation"""
        with mock.patch('scout_it.cli.requests.get', side_effect=Exception("network blocked")):
            result = fetch_url("https://example.com/test")
            # Should fail gracefully without raising
            assert isinstance(result, dict)
            assert "error" in result
    
    def test_fetch_url_with_max_chars(self):
        """Test fetch_url with max_chars parameter - verifies truncation"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test</title><body>Long content here</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"<html><title>Test</title><body>Long content here</body></html>"
            mock_get.return_value = mock_response
            
            with mock.patch('scout_it.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                # Return long content that should be truncated
                long_content = "This is a very long content that should be truncated to verify the truncation works"
                mock_extract_instance.extract_content.return_value = (long_content, "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('scout_it.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    result = fetch_url("https://example.com", max_chars=20)
                    
                    # Content should be truncated to 20 chars
                    assert len(result["result"]["main_content"]) == 20
    
    def test_fetch_url_with_max_size(self):
        """Test fetch_url with max_size parameter - truncates response"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            # Large HTML response (2000 bytes)
            large_html = "<html>" + ("x" * 1950) + "</html>"
            mock_response.text = large_html
            mock_response.url = "https://example.com"
            mock_response.content = large_html.encode('utf-8')
            mock_get.return_value = mock_response
            
            with mock.patch('scout_it.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Content", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('scout_it.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    
                    # Request with max_size of 1kb (1024 bytes) - should truncate
                    result = fetch_url("https://example.com", max_size="1kb")
                    
                    # Should successfully process even though content was truncated
                    assert isinstance(result, dict)
                    assert "result" in result
    
    def test_fetch_url_with_max_size_small_content(self):
        """Test fetch_url with max_size parameter when content is smaller than limit"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test</title><body>Small</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"x" * 500  # 500 bytes
            mock_get.return_value = mock_response
            
            with mock.patch('scout_it.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Content", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance
                
                with mock.patch('scout_it.cli.process_results') as mock_process:
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

    def test_fetch_url_error_http_404(self):
        """Test fetch_url with HTTP 404 error"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 404
            mock_response.url = "https://example.com/404"
            http_error = requests.HTTPError("404 Client Error")
            http_error.response = mock_response
            mock_get.side_effect = http_error

            result = fetch_url("https://example.com/404")
            assert "error" in result
            assert "HTTP 404" in result["error"]
            assert "404" in result["error"]

    def test_fetch_url_error_connection_refused(self):
        """Test fetch_url with connection refused"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError("Connection refused")

            result = fetch_url("https://example.com:9999")
            assert "error" in result
            assert "Connection refused" in result["error"]

    def test_fetch_url_error_timeout(self):
        """Test fetch_url with timeout"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_get.side_effect = requests.Timeout("Request timed out")

            result = fetch_url("https://example.com", timeout=3)
            assert "error" in result
            assert "timed out" in result["error"].lower()

    def test_fetch_url_max_size_warning(self):
        """Test max-size generates content warning"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><body><p>" + "word " * 30 + "</p></body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"<html><body><p>" + b"word " * 30 + b"</p></body></html>"
            mock_get.return_value = mock_response

            with mock.patch('scout_it.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("word " * 25, "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance

                with mock.patch('scout_it.cli.process_results') as mock_process:
                    mock_process.return_value = ([], {})
                    result = fetch_url("https://example.com", max_size="50kb")

                    assert "result" in result
                    assert "stats" in result
                    warning = result["stats"].get("extraction_max_size_warning")
                    assert warning is not None
                    assert "max-size" in warning

    def test_check_max_size_warning_no_size(self):
        """Test _check_max_size_warning returns None without max_size"""
        assert _check_max_size_warning(None, "some content") is None

    def test_check_max_size_warning_sufficient_content(self):
        """Test _check_max_size_warning returns None with enough content"""
        content = "word " * 100  # 100 words
        assert _check_max_size_warning("500kb", content) is None

    def test_check_max_size_warning_too_short(self):
        """Test _check_max_size_warning warns on short content"""
        content = "word " * 25  # 25 words
        warning = _check_max_size_warning("50kb", content)
        assert warning is not None
        assert "max-size" in warning
        assert "25" in warning


class TestSizeParsingUtility:
    """Test _parse_size_string utility function"""
    
    def test_parse_size_string_bytes(self):
        """Test parsing size in bytes"""
        from scout_it.cli import _parse_size_string
        
        assert _parse_size_string("1024b") == 1024
        assert _parse_size_string("100B") == 100
        assert _parse_size_string("512 b") == 512
    
    def test_parse_size_string_kilobytes(self):
        """Test parsing size in kilobytes"""
        from scout_it.cli import _parse_size_string
        
        assert _parse_size_string("1kb") == 1024
        assert _parse_size_string("100kb") == 102400
        assert _parse_size_string("1 kb") == 1024
        assert _parse_size_string("1.5KB") == 1536
    
    def test_parse_size_string_megabytes(self):
        """Test parsing size in megabytes"""
        from scout_it.cli import _parse_size_string
        
        assert _parse_size_string("1mb") == 1024 ** 2
        assert _parse_size_string("5mb") == 5 * (1024 ** 2)
        assert _parse_size_string("1 mb") == 1024 ** 2
        assert _parse_size_string("2.5MB") == int(2.5 * (1024 ** 2))
    
    def test_parse_size_string_gigabytes(self):
        """Test parsing size in gigabytes"""
        from scout_it.cli import _parse_size_string
        
        assert _parse_size_string("1gb") == 1024 ** 3
        assert _parse_size_string("2gb") == 2 * (1024 ** 3)
        assert _parse_size_string("1 gb") == 1024 ** 3
    
    def test_parse_size_string_invalid(self):
        """Test parsing invalid size strings"""
        from scout_it.cli import _parse_size_string
        
        assert _parse_size_string(None) is None
        assert _parse_size_string("") is None
        assert _parse_size_string("invalid") is None
        assert _parse_size_string("100tb") is None  # Unsupported unit
        assert _parse_size_string("abc mb") is None


class TestBackwardCompatibility:
    """Test backward compatibility"""
    
    def test_fatchurl_calls_fetch_url(self):
        """Test that fatchurl (old name) still works"""
        with mock.patch('scout_it.cli.fetch_url') as mock_fetch:
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


class TestNavFiltering:
    """Test navigation/boilerplate filtering in cleaner"""

    def test_is_nav_paragraph_language_links(self):
        """Detect Wikipedia language-link bars"""
        text = "Afrikaans | Alemannisch | Amharic | Arabic | Armenian | Azerbaijani | Basque | Belarusian | Bengali | Bosnian"
        assert _is_nav_paragraph(text) is True

    def test_is_nav_paragraph_pipe_separated(self):
        """Detect pipe-separated nav menus"""
        text = "Home | About | Products | Services | Contact | Blog | Careers"
        assert _is_nav_paragraph(text) is True

    def test_is_nav_paragraph_real_content(self):
        """Do NOT flag real article text"""
        text = "Python is a high-level, general-purpose programming language. Its design philosophy emphasizes code readability with the use of significant indentation. Python is dynamically typed and garbage-collected."
        assert _is_nav_paragraph(text) is False

    def test_is_nav_paragraph_short_empty(self):
        """Reject empty or very short paragraphs"""
        assert _is_nav_paragraph("") is True
        assert _is_nav_paragraph("Hi") is True

    def test_is_nav_paragraph_cookie_banner(self):
        """Detect cookie/consent banners"""
        text = "This website uses cookies to improve your experience. Accept all cookies?"
        assert _is_nav_paragraph(text) is True

    def test_is_nav_paragraph_breadcrumbs(self):
        """Detect breadcrumb navigation"""
        text = "Home > Products > Electronics > Laptops"
        assert _is_nav_paragraph(text) is True

    def test_is_nav_paragraph_symbol_lines(self):
        """Detect pure symbol separator lines"""
        text = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        assert _is_nav_paragraph(text) is True

    def test_is_content_section_real(self):
        """Content sections with real sentences are identified"""
        assert _is_content_section("History", [
            "Python was created in the late 1980s by Guido van Rossum."
        ]) is True  # Single item > 150 chars
        assert _is_content_section("Features", [
            "Python is dynamically typed.",
            "It has automatic memory management."
        ]) is True  # 2 items with sentence punctuation
        assert _is_content_section("Design Philosophy", [
            "The Zen of Python guides its design.",
            "It emphasizes readability and simplicity.",
            "There should be one obvious way to do something."
        ]) is True  # 3 real items

    def test_is_content_section_nav(self):
        """Nav sections without real content are filtered"""
        assert _is_content_section("General", [
            "Home", "About", "Contact", "Privacy"
        ]) is False  # All short, no sentences
        assert _is_content_section("Languages", [
            "English | Spanish | French | German | Italian"
        ]) is False  # Single short line, no sentence
        assert _is_content_section("Navigation", [
            "Main page", "Contents", "Current events",
            "Random article", "About Wikipedia"
        ]) is False  # Link items, no sentence structure

    def test_is_content_section_edge_cases(self):
        """Edge cases for content section detection"""
        # Empty
        assert _is_content_section("Empty", []) is False
        # Mixed lengths (varied = likely content)
        assert _is_content_section("Resources", [
            "Short link",
            "Python is a programming language used for web development.",
            "Another short link",
            "It supports multiple paradigms including OOP and functional."
        ]) is True  # Varied lengths with some long items
        # Single short item
        assert _is_content_section("Reference", [
            "Just a quick ref."
        ]) is False  # Single short item, no real paragraph

    def test_paragraphs_filters_nav(self):
        """paragraphs() filters out nav paragraphs"""
        content = (
            "Afrikaans | Alemannisch | Amharic | Arabic | Armenian | Azerbaijani\n\n"
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation.\n\n"
            "Python features dynamic typing and garbage collection. "
            "It supports multiple programming paradigms."
        )
        result = paragraphs(content)
        assert len(result) >= 2
        assert all("Afrikaans" not in p for p in result)
        assert all("Python is a high-level" in p or "Python features" in p for p in result)

    def test_extract_content_sections_filters_nav(self):
        """extract_content_sections filters nav sections by content quality"""
        content = (
            "Toggle the table of contents\n\n"
            "Some intro text.\n\n"
            "History\n\n"
            "Python was created in the late 1980s by Guido van Rossum. "
            "It was designed as a successor to the ABC language.\n\n"
            "Features\n\n"
            "Python is dynamically typed. It has automatic memory management."
        )
        sections = extract_content_sections(content)
        # Real content sections should be preserved
        found_real = any("History" in k or "Features" in k for k in sections)
        assert found_real, "Real content sections should be preserved"
        # Nav-header sections should be merged into Main Content
        nav_keys = [k for k in sections if k.lower() in (
            'toggle the table of contents', 'appearance', 'tools'
        )]
        assert len(nav_keys) == 0, f"Nav sections should be filtered: {nav_keys}"
        # Real section items should still be present (merged into Main if needed)
        all_items = []
        for items in sections.values():
            all_items.extend(items)
        assert any("Python was created" in i for i in all_items), "Content should not be lost"


class TestIntegration:
    """Integration tests"""
    
    def test_full_pipeline_with_mock_data(self):
        """Test the full pipeline with mocked data"""
        with mock.patch('scout_it.extraction.EnterpriseSearchEngine'):
            with mock.patch('scout_it.cli.process_results') as mock_process:
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
        with mock.patch('scout_it.extraction._ddgs_list_search') as mock_ddgs:
            mock_ddgs.return_value = ([{'title': 'news'}], {'total': 1, 'success': 1, 'execution_time': 0.1})
            results, stats = news_search('economy', max_results=5)

            assert len(results) == 0  # no URL → extraction_status failed → filtered out
            assert stats['search_engine']['success'] == 1
            call_args, call_kwargs = mock_ddgs.call_args
            assert call_args[0] == 'news'
            assert call_kwargs['max_results'] == 5

    def test_video_search_uses_ddgs_wrapper(self):
        with mock.patch('scout_it.extraction._ddgs_list_search') as mock_ddgs:
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

        monkeypatch.setattr(scout_it.extraction, 'DDGS', DummyDDGS)

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

        monkeypatch.setattr(scout_it.extraction, 'DDGS', DummyDDGS)

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
        mock_response.status_code = 200
        mock_response.text = '<html><body>Empty</body></html>'
        mock_response.raise_for_status.return_value = None

        engine = EnterpriseSearchEngine(max_workers=1, enable_js_fallback=False)
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


class TestRawHtml:
    """Test --raw-html flag for fetch_url"""

    RAW_HTML = "<html><title>Test Page</title><body><p>Paragraph 1</p><p>Paragraph 2</p></body></html>"

    def test_raw_html_mode_key_present(self):
        """Test raw_html key is present when raw_html=True"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = self.RAW_HTML
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True)
            assert "raw_html" in result["result"]
            assert result["result"]["extraction_method"] == "raw-html"

    def test_raw_html_starts_with_html_tag(self):
        """Test raw_html output starts with typical HTML markup"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = self.RAW_HTML
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True)
            raw = result["result"]["raw_html"]
            assert raw.strip().startswith("<html>") or raw.strip().startswith("<!DOCTYPE")

    def test_raw_html_is_multi_line(self):
        """Test raw_html has multiple lines (prettified, not single-line)"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = self.RAW_HTML
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True)
            raw = result["result"]["raw_html"]
            assert "\n" in raw
            # Prettified HTML should have multiple lines of actual content
            lines = [l for l in raw.split("\n") if l.strip()]
            assert len(lines) > 1

    def test_raw_html_with_max_chars_truncation(self):
        """Test raw_html respects max_chars truncation"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = self.RAW_HTML * 50  # Make it long
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True, max_chars=100)
            raw = result["result"]["raw_html"]
            assert len(raw) <= 100

    def test_raw_html_counts_words_correctly(self):
        """Test raw_html mode reports correct word count"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = self.RAW_HTML
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True)
            assert result["result"]["content_word_count"] > 0

    def test_raw_html_has_no_cleaner_keys(self):
        """Test raw_html mode does not contain cleaner-specific keys"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = self.RAW_HTML
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True)
            assert "cleaned_content" not in result["result"]
            assert "content_sections" not in result["result"]
            assert "extraction_status" in result["result"]


class TestJsonOutputValidity:
    """Test that all CLI functions produce valid strict-mode JSON output"""

    def test_fetch_url_default_json_valid(self):
        """fetch_url (default) output serializes to valid strict JSON"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test</title><body>Line1\nLine2\nLine3</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b"<html><body>Line1\nLine2\nLine3</body></html>"
            mock_get.return_value = mock_response

            with mock.patch('scout_it.extraction.ExtractionEngine') as mock_extractor:
                mock_extractor.USER_AGENTS = ['test-agent']
                mock_extract_instance = mock.Mock()
                mock_extract_instance.extract_content.return_value = ("Line1\nLine2\nLine3", "trafilatura", 0.9)
                mock_extractor.return_value = mock_extract_instance

                with mock.patch('scout_it.cli.process_results') as mock_process:
                    mock_process.return_value = ([{
                        "cleaned_content": "Line1\nLine2\nLine3",
                        "content_sections": {},
                        "top_keywords": [],
                        "sentences_count": 3,
                        "sample_sentences": ["Line1", "Line2"],
                    }], {})

                    result = fetch_url("https://example.com", raw_html=False)
                    # Serialize as the CLI handler does (no .replace)
                    dumped = json.dumps(result, indent=2, ensure_ascii=False)
                    # Must load with strict=True (no literal newlines in strings)
                    loaded = json.loads(dumped, strict=True)
                    assert "result" in loaded
                    assert "error" not in loaded

    def test_fetch_url_raw_html_json_valid(self):
        """fetch_url with raw_html=True output serializes to valid strict JSON"""
        with mock.patch('scout_it.cli.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = "<html><title>Test</title><body>Content</body></html>"
            mock_response.url = "https://example.com"
            mock_response.content = b""
            mock_get.return_value = mock_response

            result = fetch_url("https://example.com", raw_html=True)
            dumped = json.dumps(result, indent=2, ensure_ascii=False)
            loaded = json.loads(dumped, strict=True)
            assert "result" in loaded
            assert "error" not in loaded

    def test_web_search_output_json_valid(self):
        """web_search output serializes to valid strict JSON"""
        with mock.patch('scout_it.cli.EnterpriseSearchEngine') as mock_engine:
            mock_instance = mock.Mock()
            mock_instance.execute_search.return_value = [
                EnterpriseResult(
                    position=1,
                    title="Test",
                    url="https://example.com",
                    snippet="Test snippet",
                    source="web",
                    main_content="Hello\nWorld\nTest",
                    extraction_status="success",
                )
            ]
            mock_instance.stats = {'total': 1, 'success': 1}
            mock_engine.return_value = mock_instance

            with mock.patch('scout_it.cli.process_results') as mock_process:
                mock_process.return_value = ([{
                    "position": 1,
                    "title": "Test",
                    "url": "https://example.com",
                    "cleaned_content": "Hello\nWorld\nTest",
                    "content_sections": {},
                    "top_keywords": [],
                    "sentences_count": 3,
                    "sample_sentences": ["Hello", "World"],
                }], {"total": 1, "successful": 1, "failed": 0})

                result = web_search(query="test", max_results=1)
                # The output dict includes query, structured_results, stats
                output = {
                    'query': "test",
                    'structured_results': result[0],
                    'stats': {'cleaner_stats': result[1]}
                }
                dumped = json.dumps(output, indent=2, ensure_ascii=False)
                loaded = json.loads(dumped, strict=True)
                assert "structured_results" in loaded
                assert len(loaded["structured_results"]) == 1


class TestWriteOutputProducesValidJson:
    """Regression tests for the _write_output JSON-corruption bug: it used to
    word-wrap long strings (collapsing embedded newlines via str.split()) and
    then blindly replace every escaped '\\n' in the whole serialized JSON
    with a raw newline character -- corrupting multi-line values (diff
    patches, commit messages, article bodies) into invalid JSON with raw
    control characters. _write_output must now always produce clean,
    standard, round-trippable JSON."""

    def _tmp_json_path(self):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # _write_output must create it fresh
        return Path(path)

    def test_multiline_string_round_trips(self):
        from scout_it.cli import _write_output
        data = {"patch": "@@ -1,2 +1,3 @@\n-old line\n+new line one\n+new line two\n context line"}
        out = self._tmp_json_path()
        try:
            _write_output(out, data)
            loaded = json.loads(out.read_text(encoding="utf-8"))  # must not raise
            assert loaded == data
            assert loaded["patch"].count("\n") == 4
        finally:
            out.unlink(missing_ok=True)

    def test_long_single_line_string_is_chunked_but_content_preserved(self):
        """Long strings are now intentionally chunked into a JSON array of
        <=500-char pieces (word-boundary safe) so no single line in the
        output file is unreasonably long -- while staying fully valid,
        round-trippable JSON. Short strings are left as plain strings."""
        from scout_it.cli import _write_output
        long_str = " ".join(["word"] * 200)  # ~1000 chars
        data = {"title": long_str}
        out = self._tmp_json_path()
        try:
            _write_output(out, data)
            loaded = json.loads(out.read_text(encoding="utf-8"))
            assert isinstance(loaded["title"], list)
            assert all(len(chunk) <= 500 for chunk in loaded["title"])
            assert " ".join(loaded["title"]) == long_str
        finally:
            out.unlink(missing_ok=True)

    def test_short_string_is_not_chunked(self):
        from scout_it.cli import _write_output
        data = {"title": "a short title"}
        out = self._tmp_json_path()
        try:
            _write_output(out, data)
            loaded = json.loads(out.read_text(encoding="utf-8"))
            assert loaded["title"] == "a short title"
        finally:
            out.unlink(missing_ok=True)

    def test_nested_structures_round_trip(self):
        from scout_it.cli import _write_output
        data = {
            "results": [
                {"body": "line one\nline two\nline three", "title": "t1"},
                {"body": "another\nmulti\nline\nvalue", "title": "t2"},
            ]
        }
        out = self._tmp_json_path()
        try:
            _write_output(out, data)
            loaded = json.loads(out.read_text(encoding="utf-8"))
            assert loaded == data
        finally:
            out.unlink(missing_ok=True)

    def test_creates_parent_directories(self):
        from scout_it.cli import _write_output
        import tempfile
        base = Path(tempfile.mkdtemp())
        out = base / "nested" / "dir" / "out.json"
        try:
            _write_output(out, {"a": 1})
            assert out.exists()
            assert json.loads(out.read_text(encoding="utf-8")) == {"a": 1}
        finally:
            import shutil
            shutil.rmtree(base, ignore_errors=True)


class TestEnhanceVideoDescriptions:
    """Test _enhance_video_descriptions behaviour"""

    def test_empty_results(self):
        """empty list returns immediately"""
        from scout_it.cli import _enhance_video_descriptions
        assert _enhance_video_descriptions([]) == []

    @mock.patch('scout_it.cli._fetch_youtube_metadata')
    def test_skips_non_youtube(self, mock_fetch):
        """non-YouTube URLs are not fetched"""
        from scout_it.cli import _enhance_video_descriptions
        results = [{"content": "https://vimeo.com/12345", "description": "short"}]
        out = _enhance_video_descriptions(results)
        mock_fetch.assert_not_called()
        assert out[0]["description"] == "short"

    @mock.patch('scout_it.cli._fetch_youtube_metadata')
    def test_enhances_youtube(self, mock_fetch):
        """YouTube URLs get full description injected"""
        from scout_it.cli import _enhance_video_descriptions
        mock_fetch.return_value = {"description": "full " * 100}
        results = [{"content": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "description": "short"}]
        out = _enhance_video_descriptions(results)
        mock_fetch.assert_called_once()
        # Regression guard: must be called with the bare 11-char video ID,
        # not the full URL (the function builds the watch URL itself).
        called_arg = mock_fetch.call_args[0][0]
        assert called_arg == "dQw4w9WgXcQ", f"expected bare video ID, got {called_arg!r}"
        assert out[0]["description"] == "full " * 100

    @mock.patch('scout_it.cli._fetch_youtube_metadata')
    def test_error_keeps_original(self, mock_fetch):
        """fetch error keeps original truncated description"""
        from scout_it.cli import _enhance_video_descriptions
        mock_fetch.return_value = {"error": "network_error"}
        results = [{"content": "https://youtu.be/dQw4w9WgXcQ", "description": "short desc"}]
        out = _enhance_video_descriptions(results)
        assert out[0]["description"] == "short desc"


class TestExtractNewsContent:
    """Test _extract_news_content behaviour"""

    def test_empty_results(self):
        """empty list returns immediately"""
        from scout_it.cli import _extract_news_content
        assert _extract_news_content([]) == []

    @mock.patch('scout_it.cli.ExtractionEngine')
    @mock.patch('scout_it.cli.fetch_resilient')
    def test_enriches_result(self, mock_fetch, mock_engine_cls):
        """article URL is fetched, extracted, and enriched with process_results-compatible keys"""
        from scout_it.cli import _extract_news_content

        mock_fetch.return_value = {
            "html": "<html>full article</html>", "final_url": "https://example.com/article",
            "status": "success", "tier": "requests", "attempts": 1, "errors": [],
        }

        mock_engine = mock.MagicMock()
        mock_engine.extract_content.return_value = ("full " * 100, "trafilatura", 0.95)
        mock_engine_cls.return_value = mock_engine

        results = [{"url": "https://example.com/article", "body": "short trunc..."}]
        out = _extract_news_content(results)
        assert out[0]["main_content"] == "full " * 100
        assert out[0]["extraction_status"] == "success"
        assert out[0]["confidence_score"] == 0.95
        assert out[0]["extraction_method"] == "trafilatura (requests)"
        assert out[0]["content_word_count"] == 100

    @mock.patch('scout_it.cli.ExtractionEngine')
    @mock.patch('scout_it.cli.fetch_resilient')
    def test_empty_url_failed(self, mock_fetch, mock_engine_cls):
        """empty URL results in extraction_status failed"""
        from scout_it.cli import _extract_news_content

        results = [{"url": "", "body": "no url"}]
        out = _extract_news_content(results)
        assert out[0]["extraction_status"] == "failed"
        assert out[0]["main_content"] == ""
        mock_fetch.assert_not_called()

    @mock.patch('scout_it.cli.ExtractionEngine')
    @mock.patch('scout_it.cli.fetch_resilient')
    def test_http_error_failed(self, mock_fetch, mock_engine_cls):
        """all fetch tiers exhausted results in extraction_status failed"""
        from scout_it.cli import _extract_news_content

        mock_fetch.return_value = {
            "html": "", "final_url": "https://example.com/article",
            "status": "failed", "tier": "none", "attempts": 7,
            "errors": ["requests attempt 1: HTTP 403 (blocked-looking response)"],
        }

        results = [{"url": "https://example.com/article"}]
        out = _extract_news_content(results)
        assert out[0]["extraction_status"] == "failed"
        assert out[0]["main_content"] == ""
        assert "errors" in out[0]

    @mock.patch('scout_it.cli.ExtractionEngine')
    @mock.patch('scout_it.cli.fetch_resilient')
    def test_preserves_original_order(self, mock_fetch, mock_engine_cls):
        """output list preserves the order of input results"""
        from scout_it.cli import _extract_news_content

        mock_fetch.return_value = {
            "html": "<html>content</html>", "final_url": "https://example.com",
            "status": "success", "tier": "requests", "attempts": 1, "errors": [],
        }

        mock_engine = mock.MagicMock()
        mock_engine.extract_content.return_value = ("article body", "trafilatura", 0.9)
        mock_engine_cls.return_value = mock_engine

        results = [
            {"url": "https://example.com/a", "title": "first"},
            {"url": "https://example.com/b", "title": "second"},
            {"url": "https://example.com/c", "title": "third"},
        ]
        out = _extract_news_content(results)
        assert out[0]["title"] == "first"
        assert out[1]["title"] == "second"
        assert out[2]["title"] == "third"
        assert all(r["extraction_status"] == "success" for r in out)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
