"""Tests for scout_it.heuristic_extract and scout_it.selector_cache."""
import tempfile
from pathlib import Path

import pytest

from scout_it import heuristic_extract as hx
from scout_it import selector_cache as sc


class TestHeuristicExtract:
    def test_extracts_main_article_over_nav_chrome(self):
        html = """
        <html><body>
        <nav><a href="/1">Home</a><a href="/2">About</a><a href="/3">Contact</a></nav>
        <article>
            <p>This is the very first paragraph of a genuinely long article about something interesting.</p>
            <p>Here is a second paragraph continuing the discussion with more substantial content and detail.</p>
            <p>And a third paragraph wrapping up the article with a strong concluding thought and summary.</p>
        </article>
        <footer>Copyright 2026 Example Corp. All rights reserved. <a href="/privacy">Privacy</a></footer>
        </body></html>
        """
        text, confidence = hx.extract(html)
        assert "first paragraph" in text
        assert "Home" not in text
        assert "Copyright" not in text
        assert confidence > 0

    def test_empty_html_returns_empty(self):
        text, confidence = hx.extract("<html><body></body></html>")
        assert text == ""
        assert confidence == 0.0

    def test_garbage_html_does_not_raise(self):
        text, confidence = hx.extract("<<<not even html")
        assert isinstance(text, str)
        assert isinstance(confidence, float)

    def test_link_heavy_block_scores_lower_than_content_block(self):
        html = """
        <html><body>
        <div class="sidebar-links">
            <a href="/1">Link one with some text</a>
            <a href="/2">Link two with some text</a>
            <a href="/3">Link three with some text</a>
            <a href="/4">Link four with some text</a>
        </div>
        <div class="article-content">
            <p>A real paragraph of substantial written content that a human actually wrote for readers.</p>
            <p>Another real paragraph continuing the thought with more detail and useful information here.</p>
        </div>
        </body></html>
        """
        text, confidence = hx.extract(html)
        assert "real paragraph" in text

    def test_confidence_never_exceeds_reasonable_ceiling(self):
        html = "<html><body><article>" + ("<p>Real content sentence here. </p>" * 200) + "</article></body></html>"
        text, confidence = hx.extract(html)
        assert confidence <= 0.95


class TestSelectorCache:
    def _tmp_db(self):
        return Path(tempfile.mkdtemp()) / "test_selector.db"

    def test_no_cached_selector_returns_none(self):
        db = self._tmp_db()
        assert sc.get_selector("https://example.com/a", db_path=db) is None

    def test_record_and_retrieve_selector(self):
        db = self._tmp_db()
        sc.record_success("https://example.com/a", "article.main-content", db_path=db)
        assert sc.get_selector("https://example.com/b", db_path=db) == "article.main-content"

    def test_try_cached_selector_extracts_matching_content(self):
        db = self._tmp_db()
        sc.record_success("https://example.com/a", ".article-body", db_path=db)
        html = '<html><body><div class="article-body">' + ("word " * 30) + '</div></body></html>'
        text = sc.try_cached_selector("https://example.com/b", html, db_path=db)
        assert text is not None
        assert "word" in text

    def test_try_cached_selector_returns_none_if_no_cache(self):
        db = self._tmp_db()
        html = "<html><body><div>content</div></body></html>"
        assert sc.try_cached_selector("https://example.com/a", html, db_path=db) is None

    def test_try_cached_selector_returns_none_if_selector_no_longer_matches(self):
        db = self._tmp_db()
        sc.record_success("https://example.com/a", ".no-longer-exists", db_path=db)
        html = "<html><body><div class='different'>content</div></body></html>"
        assert sc.try_cached_selector("https://example.com/b", html, db_path=db) is None

    def test_repeated_failures_forget_the_selector(self):
        db = self._tmp_db()
        sc.record_success("https://example.com/a", ".old-selector", db_path=db)
        sc.record_failure("https://example.com/a", db_path=db)
        sc.record_failure("https://example.com/a", db_path=db)
        sc.record_failure("https://example.com/a", db_path=db)
        assert sc.get_selector("https://example.com/a", db_path=db) is None

    def test_forget_domain(self):
        db = self._tmp_db()
        sc.record_success("https://example.com/a", ".sel", db_path=db)
        assert sc.forget_domain("https://example.com/a", db_path=db) is True
        assert sc.get_selector("https://example.com/a", db_path=db) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
