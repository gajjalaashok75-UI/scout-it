#!/usr/bin/env python3
"""
Unit tests for gakr_ddgs.cleaner functions — content extraction, heading
detection, section parsing, nav filtering, and paragraph quality scoring.

Every test exercises REGRESSION GUARDS: the assertions document the
behaviour we expect today, so future changes that break generic
extraction will be caught here.
"""

import re
import sys
from typing import Dict, List, Optional

import pytest

from gakr_ddgs.cleaner import (
    _is_nav_paragraph,
    _is_content_section,
    extract_content_sections,
    paragraphs,
    top_keywords,
    _best_first_paragraph,
    _looks_like_heading,
    _score_paragraph_quality,
    _group_single_newline_paragraphs,
)


# =============================================================================
# _is_nav_paragraph
# =============================================================================

class TestIsNavParagraph:
    def test_short_lines_are_nav(self):
        assert _is_nav_paragraph("") is True
        assert _is_nav_paragraph("Hi") is True
        assert _is_nav_paragraph("Hello world") is True

    def test_language_link_bars(self):
        assert _is_nav_paragraph(
            "Afrikaans | Alemannisch | Amharic | Arabic | Armenian | "
            "Azerbaijani | Basque | Belarusian"
        ) is True

    def test_breadcrumb_nav(self):
        assert _is_nav_paragraph("Home > Products > Category > Item") is True
        assert _is_nav_paragraph("You are here: Home > Blog > Post") is True

    def test_cookie_banners(self):
        assert _is_nav_paragraph(
            "This site uses cookies to improve your experience."
        ) is True
        assert _is_nav_paragraph(
            "Accept all cookies  |  Reject non-essential"
        ) is True

    def test_camelcase_infobox_noise(self):
        # Wikipedia infobox pattern
        para = (
            "PythonParadigmMulti-paradigm: object-oriented,[1] "
            "procedural,[2] functional,[3] structured,[4] "
            "reflectiveDesignedbyGuido van RossumDeveloperPython "
            "Software Foundation"
        )
        assert _is_nav_paragraph(para) is True

    def test_real_article_text_is_not_nav(self):
        para = (
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation. Python is dynamically typed and "
            "garbage-collected."
        )
        assert _is_nav_paragraph(para) is False

    def test_real_paragraph_with_sentence_endings(self):
        para = (
            "The quick brown fox jumps over the lazy dog. This sentence "
            "contains every letter of the alphabet. It is often used for "
            "testing fonts and keyboard layouts."
        )
        assert _is_nav_paragraph(para) is False

    def test_pipe_separated_list(self):
        assert _is_nav_paragraph("Item1 | Item2 | Item3 | Item4") is True

    def test_high_proper_noun_ratio_no_sentences(self):
        para = "John Smith Jane Doe Bob Wilson Alice Brown"
        assert _is_nav_paragraph(para) is True

    def test_mixed_content_with_sentences(self):
        para = (
            "John Smith was born in 1980. Jane Doe moved to the city "
            "in 2005. Bob Wilson studied computer science."
        )
        assert _is_nav_paragraph(para) is False

    def test_list_phrases_no_punctuation(self):
        para = (
            "List of countries by population List of languages by speakers "
            "List of largest cities"
        )
        assert _is_nav_paragraph(para) is True

    def test_real_paragraph_camelcase_exception(self):
        """Real content may contain camelCase naturally; nav check must not
        flag it when sentence structure is present."""
        para = (
            "The NASA rover Perseverance landed on Mars in February 2021. "
            "It carries the Ingenuity helicopter as a technology "
            "demonstration. NASA's Jet Propulsion Laboratory manages the "
            "mission."
        )
        assert _is_nav_paragraph(para) is False

    def test_nav_keyword_only_line(self):
        assert _is_nav_paragraph("Home About Contact Privacy Terms") is True
        assert _is_nav_paragraph("Search Navigation Menu") is True

    def test_short_line_no_sentence_endings(self):
        """Lines under 200 chars with camelCase and no sentence punctuation"""
        assert _is_nav_paragraph(
            "ReadEditView history"
        ) is True


# =============================================================================
# _looks_like_heading
# =============================================================================

class TestLooksLikeHeading:
    def test_markdown_heading_not_matched_here(self):
        """_looks_like_heading is only called after the markdown regex
        check — but if fed a markdown heading it should still reject it
        because of the '#' character (or return None since # is not matched
        by title-case patterns)."""
        lines = ["# Introduction", "Some content here"]
        assert _looks_like_heading("# Introduction", lines, 0) is None

    def test_real_content_heading(self):
        lines = [
            "History",
            "Python was invented in the late 1980s by Guido van Rossum. "
            "The language has undergone significant evolution since then."
        ]
        result = _looks_like_heading("History", lines, 0)
        assert result is not None
        assert "History" in result

    def test_nav_label_is_rejected(self):
        lines = ["Toggle the table of contents", "Article Talk  Read  Edit"]
        assert _looks_like_heading("Toggle the table of contents", lines, 0) is None

    def test_nav_label_tools(self):
        lines = ["Tools", "What links here  Related changes"]
        assert _looks_like_heading("Tools", lines, 0) is None

    def test_short_action_word(self):
        lines = ["Edit", "Some content here"]
        assert _looks_like_heading("Edit", lines, 0) is None

    def test_no_content_following(self):
        """Heading with nothing substantial following should be rejected."""
        lines = ["Some Heading", "", "", "", ""]
        assert _looks_like_heading("Some Heading", lines, 0) is None

    def test_repeated_line_is_rejected(self):
        lines = [
            "Navigation",
            "Home About Contact",
            "Navigation",
            "More links here",
            "Navigation",
        ]
        assert _looks_like_heading("Navigation", lines, 0) is None

    def test_sentence_fragment_rejected(self):
        """Lines where most non-starting words start lowercase (sentence)."""
        lines = [
            "it is also important to note that",
            "Because this is clearly a sentence, not a heading.",
        ]
        assert _looks_like_heading("it is also important to note that", lines, 0) is None

    def test_long_line_rejected(self):
        line = "A" * 100
        lines = [line, "content"]
        assert _looks_like_heading(line, lines, 0) is None

    def test_too_many_words_rejected(self):
        line = "A B C D E F G H I J K L M N"
        lines = [line, "content"]
        assert _looks_like_heading(line, lines, 0) is None

    def test_lowercase_start_rejected(self):
        lines = ["lowercase heading", "content"]
        assert _looks_like_heading("lowercase heading", lines, 0) is None

    def test_ends_with_period_rejected(self):
        lines = ["This is a sentence.", "content"]
        assert _looks_like_heading("This is a sentence.", lines, 0) is None

    def test_all_caps_heading_passed_through(self):
        """ALL-CAPS lines are handled separately by extract_content_sections.
        But if _looks_like_heading gets one, it should still process it."""
        lines = [
            "INTRODUCTION",
            "This is the introduction paragraph. It has multiple sentences. "
            "And provides a good overview."
        ]
        result = _looks_like_heading("INTRODUCTION", lines, 0)
        assert result is not None

    def test_heading_with_content_following(self):
        lines = [
            "History",
            "The language was first released in 1991. It was created by "
            "Guido van Rossum as a successor to the ABC language. "
            "Python 2.0 was released in 2000."
        ]
        result = _looks_like_heading("History", lines, 0)
        assert result is not None

    def test_heading_with_short_following_line(self):
        """Short following lines reduce content score but don't immediately
        disqualify the heading if there's other content."""
        lines = [
            "Features",
            "Clean syntax",
            "Dynamic typing",
            "Python supports multiple programming paradigms, including "
            "structured, object-oriented, and functional programming."
        ]
        result = _looks_like_heading("Features", lines, 0)
        # The heading has content following (even if first line is short)
        # The 4th line has sentence punctuation and length
        assert result is not None

    def test_generic_heading_like_appearance(self):
        """'Appearance' is a Wikipedia UI element, not content heading."""
        lines = ["Appearance", ""]
        assert _looks_like_heading("Appearance", lines, 0) is None


# =============================================================================
# _score_paragraph_quality
# =============================================================================

class TestScoreParagraphQuality:
    def test_empty_returns_zero(self):
        assert _score_paragraph_quality("") == 0.0
        assert _score_paragraph_quality(None) == 0.0  # type: ignore
        assert _score_paragraph_quality("short") == 0.0

    def test_long_content_scores_high(self):
        para = (
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation. Python is dynamically typed and "
            "garbage-collected. It supports multiple programming paradigms, "
            "including structured, object-oriented, and functional "
            "programming. It is often described as a batteries-included "
            "language due to its comprehensive standard library."
        )
        score = _score_paragraph_quality(para)
        assert score > 2.0

    def test_infobox_text_scores_low(self):
        para = (
            "PythonParadigmMulti-paradigm: object-oriented, procedural, "
            "functional, structuredDesignedbyGuido van RossumDeveloperPython"
        )
        score = _score_paragraph_quality(para)
        assert score < 2.0

    def test_short_nav_like_text_scores_low(self):
        para = "Home About Contact Privacy Policy Terms of Service Sitemap"
        score = _score_paragraph_quality(para)
        assert score < 2.0

    def test_quality_text_outranks_infobox(self):
        quality = (
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation. Python is dynamically typed and "
            "garbage-collected. It supports multiple programming paradigms."
        )
        infobox = (
            "PythonParadigmMulti-paradigm: object-oriented, procedural, "
            "functionalDesignedbyGuido van Rossum"
        )
        assert _score_paragraph_quality(quality) > _score_paragraph_quality(infobox)


# =============================================================================
# _best_first_paragraph
# =============================================================================

class TestBestFirstParagraph:
    def test_empty_fallback(self):
        result = _best_first_paragraph([], "")
        assert result == ""

    def test_returns_non_nav_paragraph(self):
        paras = [
            "Home About Contact",
            (
                "Python is a high-level, general-purpose programming "
                "language. Its design philosophy emphasizes code "
                "readability with the use of significant indentation."
            ),
            (
                "Python was conceived in the late 1980s by Guido van "
                "Rossum. The language has undergone significant changes."
            ),
        ]
        result = _best_first_paragraph(paras, "")
        assert "Python is a high-level" in result
        assert "Home About" not in result

    def test_skips_camelcase_infobox_prefix(self):
        """Strategy 1 should skip paragraphs whose first 200 chars have
        camelCase concatenation without sentence punctuation."""
        paras = [
            "PythonParadigmMulti-paradigm: object-oriented, procedural, "
            "functionalDesignedbyGuido van RossumDeveloperPythonSoftware "
            "Foundation",

            (
                "Python is a high-level, general-purpose programming "
                "language. Its design philosophy emphasizes code "
                "readability."
            ),
        ]
        result = _best_first_paragraph(paras, "")
        assert "high-level" in result
        assert "Paradigm" not in result

    def test_fallback_to_best_scored(self):
        """When no clean prefix candidates exist, use scoring."""
        paras = [
            "Short nav text",
            "More nav links here",
            (
                "This is a longer paragraph with multiple sentences. It "
                "talks about substantive content. There are technical "
                "words and real information here."
            ),
        ]
        result = _best_first_paragraph(paras, "")
        # Should pick the third paragraph (highest score)
        assert result == paras[2]
        assert result != paras[0]

    def test_fallback_raw_line_scan(self):
        """When no paragraphs pass, fall back to raw line scan."""
        result = _best_first_paragraph([], (
            "SkipThisCamelCase\nSkipShort\n\n"
            "FindThisRealContent please because it has enough length "
            "and content quality markers to be selected."
        ))
        assert result and "FindThisRealContent" in result


# =============================================================================
# _is_content_section
# =============================================================================

class TestIsContentSection:
    def test_empty_items_not_content(self):
        assert _is_content_section("Main Content", []) is False

    def test_short_items_not_content(self):
        assert _is_content_section("Test", ["short"]) is False

    def test_single_short_item_not_content(self):
        assert _is_content_section("Test Section", ["A single short line"]) is False

    def test_real_section_with_content(self):
        items = [
            "Python is a high-level, general-purpose programming language.",
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation.",
            "Python is dynamically typed and garbage-collected.",
        ]
        assert _is_content_section("History", items) is True

    def test_section_with_sentence_endings(self):
        items = [
            "One sentence here. Another sentence follows.",
            "Third sentence concludes the thought.",
            "Fourth sentence adds more detail to the paragraph.",
        ]
        assert _is_content_section("Details", items) is True

    def test_nav_section_rejected(self):
        items = [
            "What links here  Related changes  Upload file",
            "Special pages  Permanent link  Page information",
            "Cite this page  Wikidata item",
        ]
        assert _is_content_section("Tools", items) is False

    def test_mixed_content_accepted_with_enough_quality(self):
        items = [
            "What links here",
            "Related changes",
            "Python is a high-level programming language. It supports "
            "multiple paradigms and has a comprehensive standard library.",
            "The language was created by Guido van Rossum in 1991.",
        ]
        assert _is_content_section("History", items) is True


# =============================================================================
# extract_content_sections
# =============================================================================

class TestExtractContentSections:
    def test_empty_text(self):
        assert extract_content_sections("") == {}

    def test_simple_content_no_headings(self):
        text = (
            "Python is a high-level, general-purpose programming language. "
            "Its design philosophy emphasizes code readability with the use "
            "of significant indentation. Python is dynamically typed and "
            "garbage-collected."
        )
        result = extract_content_sections(text)
        assert "Main Content" in result
        assert len(result["Main Content"]) >= 1

    def test_headings_detected(self):
        text = (
            "History\n"
            "Python was invented in the late 1980s by Guido van Rossum. "
            "The language was released in 1991.\n\n"
            "Features\n"
            "Python features dynamic typing and automatic memory "
            "management. It supports multiple programming paradigms."
        )
        result = extract_content_sections(text)
        assert "History" in result or "Features" in result

    def test_nav_sections_filtered(self):
        """Nav/UI 'headings' should not create sections."""
        text = (
            "Toggle the table of contents\n"
            "Article Talk  Read  Edit  View history\n"
            "Tools\n"
            "What links here  Related changes\n\n"
            "History\n"
            "Python was invented by Guido van Rossum in the late 1980s. "
            "It was released in 1991."
        )
        result = extract_content_sections(text)
        # "Toggle the table of contents" or "Tools" should NOT be section keys
        section_keys = set(result.keys())
        assert "Toggle the table of contents" not in section_keys
        assert "Tools" not in section_keys
        # "History" should be a section key
        assert "History" in section_keys or "Main Content" in section_keys

    def test_markdown_headings_detected(self):
        text = (
            "## History\n"
            "Python was invented by Guido van Rossum.\n\n"
            "## Features\n"
            "Dynamic typing and automatic memory management."
        )
        result = extract_content_sections(text)
        assert "History" in result
        assert "Features" in result

    def test_wikipedia_nav_noise_filtered(self):
        """Simulated Wikipedia content — nav elements should be excluded."""
        text = (
            "Appearance\n"
            "Read  Edit  View history\n"
            "Personal tools\n"
            "What links here  Permanent link  Page information\n"
            "Cite this page  Wikidata item\n\n"
            "History\n"
            "Python was conceived in the late 1980s by Guido van Rossum "
            "at Centrum Wiskunde & Informatica (CWI) in the Netherlands "
            "as a successor to the ABC programming language."
        )
        result = extract_content_sections(text)
        keys = set(result.keys())
        assert "Appearance" not in keys
        assert "Personal tools" not in keys
        # Real heading should be picked up
        assert "History" in keys or "Main Content" in keys


# =============================================================================
# paragraphs
# =============================================================================

class TestParagraphs:
    def test_empty_input(self):
        assert paragraphs("") == []

    def test_double_newline_paragraphs(self):
        text = (
            "First paragraph with multiple sentences. It has enough "
            "content to be a real paragraph. Three sentences minimum.\n\n"
            "Second paragraph also has real content. It discusses "
            "important topics. Many interesting ideas here."
        )
        result = paragraphs(text)
        assert len(result) >= 2

    def test_single_newline_grouping(self):
        """Readability-extracted content with single newlines."""
        text = (
            "First paragraph with multiple sentences.\n"
            "It has enough content to be a real paragraph.\n"
            "Three sentences minimum.\n"
            "History\n"
            "Second paragraph discusses history.\n"
            "It has real content too.\n"
            "Many interesting ideas."
        )
        result = paragraphs(text)
        assert len(result) >= 1

    def test_short_paragraphs_filtered(self):
        text = "Short\n\n" + (
            "Real content paragraph with multiple sentences. It has "
            "enough length and quality to pass the filter. Three "
            "sentences to make it substantial."
        )
        result = paragraphs(text)
        assert all(len(p) >= 40 for p in result)

    def test_nav_paragraphs_filtered(self):
        text = (
            "Home About Contact Privacy Terms\n\n"
            "Python is a high-level programming language. It was created "
            "by Guido van Rossum in 1991. The language emphasizes code "
            "readability and simplicity."
        )
        result = paragraphs(text)
        assert not any("Home About Contact" in p for p in result)

    def test_all_caps_not_overfiltered(self):
        """ALL-CAPS lines like 'INTRODUCTION' should not break paragraphs."""
        text = (
            "INTRODUCTION\n"
            "This is the introduction paragraph. It has multiple "
            "sentences that explain the topic. The content is "
            "substantial and informative."
        )
        result = paragraphs(text)
        assert len(result) >= 1
        assert any("INTRODUCTION" in p or "introduct" in p.lower() for p in result)


# =============================================================================
# _group_single_newline_paragraphs
# =============================================================================

class TestGroupSingleNewlineParagraphs:
    def test_empty(self):
        assert _group_single_newline_paragraphs("") == []

    def test_simple_grouping(self):
        text = (
            "First line with content.\n"
            "Second line continues.\n"
            "Third line finishes."
        )
        result = _group_single_newline_paragraphs(text)
        assert len(result) >= 1

    def test_nav_lines_skipped(self):
        text = (
            "What links here\n"
            "Related changes\n"
            "Python is a high-level programming language. It supports "
            "multiple paradigms. The language is dynamically typed."
        )
        result = _group_single_newline_paragraphs(text)
        assert any("Python" in p for p in result)

    def test_heading_splits_group(self):
        text = (
            "First paragraph content. Has enough sentences. "
            "Three total here.\n"
            "History\n"
            "Second paragraph content. Also has sufficient. "
            "Many ideas discussed."
        )
        result = _group_single_newline_paragraphs(text)
        assert len(result) >= 1
        # At minimum one paragraph should survive the quality filter
        assert all(len(p) >= 40 for p in result)


# =============================================================================
# top_keywords — type consistency regression
# =============================================================================

class TestTopKeywords:
    def test_always_returns_list(self):
        """Regression: top_keywords must always return a list, never a dict."""
        text = (
            "Python is a high-level programming language. It was created "
            "by Guido van Rossum. Python emphasizes code readability."
        )
        result = top_keywords(text)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    def test_empty_text_returns_list(self):
        result = top_keywords("")
        assert isinstance(result, list)
        assert result == []

    def test_short_text_returns_list(self):
        result = top_keywords("short text here")
        assert isinstance(result, list)

    def test_keywords_are_strings(self):
        text = (
            "Python is a programming language. Python is used for web "
            "development. Python supports data science."
        )
        result = top_keywords(text)
        assert all(isinstance(k, str) for k in result)


# =============================================================================
# Integration: full Wikipedia-like extraction pipeline
# =============================================================================

class TestWikipediaExtractionIntegration:
    """Simulate a realistic Wikipedia article extraction scenario, ensuring
    the pipeline produces quality content despite heavy nav noise."""

    WIKI_TEXT = """Appearance
Read  Edit  View history
Personal tools
What links here  Permanent link  Page information
Cite this page  Wikidata item

Python is a high-level, general-purpose programming language. Its design
philosophy emphasizes code readability with the use of significant
indentation. Python is dynamically typed and garbage-collected. It supports
multiple programming paradigms, including structured, object-oriented, and
functional programming. It is often described as a batteries-included
language due to its comprehensive standard library.

History
Python was conceived in the late 1980s by Guido van Rossum at Centrum
Wiskunde & Informatica (CWI) in the Netherlands as a successor to the ABC
programming language. Python 2.0 was released in 2000 and Python 3.0 in
2008. Python 2.7 was discontinued in 2020.

Features
Python is dynamically typed. It uses automatic memory management and has a
large standard library. Python supports multiple programming paradigms,
including procedural, object-oriented, and functional programming. It has a
comprehensive standard library described as batteries included.

Design philosophy
Python's design philosophy emphasizes code readability. Its core philosophy
is summarized by the Zen of Python, which includes aphorisms such as
Beautiful is better than ugly, Explicit is better than implicit, and Simple
is better than complex.
"""

    def test_heading_detection_skips_nav(self):
        """Nav UI 'headings' must not appear as section keys."""
        sections = extract_content_sections(self.WIKI_TEXT)
        keys = set(sections.keys())
        for bad in ("Appearance", "Personal tools", "What links here"):
            assert bad not in keys, f"Nav UI '{bad}' leaked as section key"

    def test_real_sections_detected(self):
        """Real content headings should be detected."""
        sections = extract_content_sections(self.WIKI_TEXT)
        keys = set(sections.keys())
        # At least one real heading should be found
        real_headings = {"History", "Features", "Design philosophy", "Main Content"}
        assert keys & real_headings, f"No real headings found in {keys}"

    def test_paragraphs_have_real_content(self):
        """paragraphs() should produce quality paragraphs, not nav noise."""
        result = paragraphs(self.WIKI_TEXT)
        assert len(result) >= 2
        all_text = " ".join(result)
        assert "Python is a high-level" in all_text
        assert "Appearance" not in all_text

    def test_first_paragraph_is_real_content(self):
        """first_paragraph should pick real intro, not nav noise."""
        paras = paragraphs(self.WIKI_TEXT)
        fp = _best_first_paragraph(paras, self.WIKI_TEXT)
        assert fp and len(fp) > 50
        assert "Python is a high-level" in fp
        assert "Appearance" not in fp

    def test_whole_pipeline_quality(self):
        """Combined: sections + paragraphs + first_para all produce
        quality content for a Wikipedia-like article."""
        sections = extract_content_sections(self.WIKI_TEXT)
        paras = paragraphs(self.WIKI_TEXT)
        fp = _best_first_paragraph(paras, self.WIKI_TEXT)

        # Main Content should have real content
        main_content = sections.get("Main Content")
        if main_content:
            all_main = " ".join(main_content)
            assert len(all_main) > 100

        # Real content should be substantial
        assert fp and len(fp) > 50
        assert len(paras) >= 2


# =============================================================================
# Integration: blog/article page (like the blog post test case)
# =============================================================================

class TestBlogExtractionIntegration:
    """Simulate a blog-style article that triggered earlier issues."""

    BLOG_TEXT = """Navigation
Home  About  Blog  Contact  Search
Subscribe to our newsletter
Cookie settings  Privacy policy

The Future of Artificial Intelligence

Artificial intelligence is transforming industries across the globe. From
healthcare to finance, AI systems are being deployed to solve complex
problems that were previously thought to require human intelligence.

Recent breakthroughs in machine learning have led to significant advances
in natural language processing, computer vision, and reinforcement learning.
These technologies are being integrated into everyday applications.

Challenges and Opportunities

Despite the rapid progress, several challenges remain. AI systems can
perpetuate biases present in their training data. Ensuring fairness and
accountability in AI decision-making is an active area of research.

The future of AI will likely involve closer collaboration between humans
and machines, rather than full automation. Augmented intelligence, where
AI enhances human capabilities rather than replacing them, is gaining
traction.

Conclusion
Artificial intelligence continues to evolve at a rapid pace. While there
are challenges to address, the potential benefits are substantial. The
coming years will likely see even more transformative applications.
"""

    def test_nav_does_not_leak_into_content(self):
        sections = extract_content_sections(self.BLOG_TEXT)
        keys = set(sections.keys())
        for bad in ("Navigation", "Cookie settings"):
            assert bad not in keys, f"Nav UI '{bad}' leaked as section key"

    def test_blog_headings_detected(self):
        sections = extract_content_sections(self.BLOG_TEXT)
        keys = set(sections.keys())
        real = {"Challenges and Opportunities", "Conclusion", "Main Content",
                "The Future of Artificial Intelligence"}
        assert keys & real, f"No real headings found in {keys}"

    def test_paragraphs_have_blog_content(self):
        paras = paragraphs(self.BLOG_TEXT)
        assert len(paras) >= 2
        all_text = " ".join(paras)
        assert "transform" in all_text.lower()

    def test_first_paragraph_not_nav(self):
        paras = paragraphs(self.BLOG_TEXT)
        fp = _best_first_paragraph(paras, self.BLOG_TEXT)
        assert fp and len(fp) > 50
        assert "Artificial intelligence" in fp
        assert "Navigation" not in fp
        assert "Subscribe" not in fp


# =============================================================================
# Integration: short/technical content (Stack Overflow style)
# =============================================================================

class TestTechnicalContentExtraction:
    """Simulate a Q&A / technical reference page."""

    TECH_TEXT = """Related questions
How to sort a list in Python?
What is the difference between list and tuple?

Answer
You can sort a list using the built-in sorted() function or the list.sort()
method. The sorted() function returns a new sorted list, while sort()
modifies the list in place. Both accept a key parameter for custom sorting.

For example:
sorted_list = sorted(original_list)
original_list.sort()

The key parameter allows you to specify a function that returns the value
to sort by. For case-insensitive sorting:
sorted_list = sorted(list, key=str.lower)

Tags: python sorting list
Share  Edit  Follow  Improve this answer
"""

    def test_answer_content_extracted(self):
        paras = paragraphs(self.TECH_TEXT)
        assert len(paras) >= 1
        all_text = " ".join(paras).lower()
        assert "sorted()" in all_text or "sorted" in all_text
        # Nav items should not be in paragraphs
        assert "related questions" not in all_text.lower()

    def test_sections(self):
        sections = extract_content_sections(self.TECH_TEXT)
        keys = set(sections.keys())
        assert "Answer" in keys or "Main Content" in keys

    def test_first_paragraph_quality(self):
        paras = paragraphs(self.TECH_TEXT)
        fp = _best_first_paragraph(paras, self.TECH_TEXT)
        assert fp and len(fp) > 30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
