#!/usr/bin/env python3
"""
Enhanced main-content cleaning and structuring tool with filtering and advanced cleaning.
Reads search results, filters by extraction_status == "success",
cleans content, and writes a structured JSON.

Usage (CLI):
  python main_content_cleaner.py enterprise_search_20260207_152026.json --out struct_format_results.json

Usage (Programmatic):
  from main_content_cleaner import process_results
  structured, stats = process_results(results_list)
"""
import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Navigation / boilerplate paragraph detection helpers
# ---------------------------------------------------------------------------

_LANG_LINK_RE = re.compile(
    # "Afrikaans | Alemannisch | Amharic | ..."  – language link bars
    r'^(?:\w+(?:\s*\|\s*)){3,}$'
)
_PIPE_SEPARATED_LINE_RE = re.compile(
    # Lines consisting mainly of "word | word | word" sequences
    r'^(?:\S+(?:\s*\|\s*\S+)){2,}$'
)
_CAMEL_CASE_RE = re.compile(r'[a-z]+[A-Z][a-z]+')


_NAV_KEYWORDS = frozenset({
    'home', 'about', 'contact', 'sitemap', 'privacy', 'terms',
    'cookie', 'cookies', 'disclaimer', 'accessibility', 'copyright',
    'donate', 'help', 'search', 'navigation', 'menu', 'main menu',
    'skip to content', 'skip to main', 'table of contents',
    'toggle', 'tools', 'languages', 'personal tools', 'contents',
    'what links here', 'related changes', 'special pages',
    'permanent link', 'page information', 'cite this page',
    'download pdf', 'printable version',
    'in other projects',
})

_ENGLISH_FUNCTION_WORDS = frozenset({
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
    'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'between', 'under', 'again',
    'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most',
    'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
    'so', 'than', 'too', 'very', 'just', 'because', 'but', 'and', 'or',
    'if', 'while', 'although', 'this', 'that', 'these', 'those',
    'which', 'who', 'whom', 'what', 'it', 'its', 'they', 'them',
    'their', 'we', 'us', 'our', 'you', 'your', 'he', 'him', 'his',
    'she', 'her', 'hers',
})


def _is_nav_paragraph(para: str) -> bool:
    """Return True if *para* looks like navigation / boilerplate noise."""
    if not para or len(para) < 20:
        return True

    stripped = para.strip()
    lower = stripped.lower()

    # Language-link bars: "Afrikaans | Alemannisch | Amharic | ..."
    if _LANG_LINK_RE.match(stripped):
        return True
    if _PIPE_SEPARATED_LINE_RE.match(stripped):
        return True

    # Lines that are mostly short tokens separated by •·/* (breadcrumb style)
    breadcrumb_sep = sum(1 for ch in stripped if ch in '|•·>»/')
    if breadcrumb_sep >= 2 and len(stripped) < 200:
        return True

    # Lines whose only content is known nav keywords (≥2 distinct matches)
    words_lower = re.findall(r'[a-z]+', lower)
    nav_hits = sum(1 for w in words_lower if w in _NAV_KEYWORDS)
    if nav_hits >= 2 and len(words_lower) <= 8:
        return True

    # Cookie / consent banners (short, detect 'cookie', 'consent', 'gdpr')
    if any(t in lower for t in ('cookie', 'consent', 'gdpr', 'ccpa')):
        if len(words_lower) <= 12:
            return True

    # Pure symbol / separator lines (only 1-2 distinct alphabetic words)
    if sum(1 for c in stripped if c.isalpha()) < 10:
        return True

    # Pre-compute frequently-used values
    words = stripped.split()
    has_sentence_end = any(c in stripped for c in '.!?')
    camel_matches = _CAMEL_CASE_RE.findall(stripped)

    # High proper-noun density (≥50% of words start uppercase)
    # Catches Wikipedia language-link bars, nav toolbars, and sidebar
    # link collections that mix uppercase and lowercase words without
    # any sentence structure (e.g. "Appearance Read Edit View history
    # Personal tools What links here Permanent link Page information")
    if len(words) >= 5:
        caps_count = sum(1 for w in words if w and w[0].isupper())
        caps_ratio = caps_count / len(words)
        if caps_ratio >= 0.5 and not has_sentence_end:
            return True

    # Very short lines (<50 chars) with camelCase and no sentences are nav
    if len(stripped) < 50 and not has_sentence_end and camel_matches:
        return True

    # CamelCase concatenations (e.g. ReadEditView, changesUpload, filePermanent)
    # These are characteristic of nav/infobox content where template variables
    # get concatenated without spaces.

    # 3+ camelCase matches with no sentence structure → infobox / sidebar noise
    if len(camel_matches) >= 3 and not has_sentence_end:
        return True

    # "List of X ... List of Y ..." on a single line is list/archive navigation
    list_phrases = stripped.count('List of ')
    if list_phrases >= 2 and not has_sentence_end:
        return True

    # CamelCase word transitions (e.g. "hereRelated", "changesUpload"):
    # 3+ lowercase→uppercase transitions without spaces is a strong nav signal.
    camel_transitions = len(re.findall(r'[a-z][A-Z]', stripped))
    if camel_transitions >= 3:
        # Don't flag long lines with sentence punctuation — the camelCase
        # could be a single technical term within real English content
        if len(stripped) < 80 or not has_sentence_end:
            return True

    # Dense nav keyword hits (≥3 distinct nav words in a short line) → nav
    if nav_hits >= 3 and len(words) <= 12:
        return True
    # Lines that start with a known single-word nav action → nav
    first_word = lower.split()[0] if words_lower else ''
    if first_word in ('read', 'edit', 'view', 'download', 'printable', 'subscribe', 'follow'):
        if len(words) <= 10:
            return True

    # Article title lines like "Python (programming language)" — short lines with
    # a parenthetical category, no sentence-ending punctuation
    if len(stripped) < 80 and '(' in stripped and stripped.rstrip().endswith(')'):
        # Must start with a capital letter and have no sentence-ending punctuation
        if stripped[0].isupper() and not any(c in stripped.rstrip() for c in '.!?'):
            return True

    # Mixed-script / multi-language noise: paragraph mixes 3+ scripts
    # with almost no English sentence structure
    if _has_multi_script_noise(stripped):
        return True

    # Q&A nav listing: a short header followed only by questions (e.g.
    # "Related questions\nHow to sort a list?\nWhat is a tuple?")
    lines_in_para = stripped.split('\n')
    if len(lines_in_para) >= 3:
        first_line = lines_in_para[0].strip()
        rest_lines = lines_in_para[1:]
        if len(first_line) < 50 and len(first_line.split()) <= 5:
            q_rest = sum(1 for l in rest_lines if l.strip().endswith('?'))
            if q_rest == len(rest_lines):
                return True

    return False


def _has_multi_script_noise(text: str) -> bool:
    """Return True if text mixes 3+ scripts but has no English sentence structure."""
    scripts = set()
    for ch in text:
        if '\u0370' <= ch <= '\u03FF':   scripts.add('greek')
        elif '\u0400' <= ch <= '\u04FF': scripts.add('cyrillic')
        elif '\u0600' <= ch <= '\u06FF': scripts.add('arabic')
        elif '\u0900' <= ch <= '\u097F': scripts.add('devanagari')
        elif '\u0E00' <= ch <= '\u0E7F': scripts.add('thai')
        elif '\u4E00' <= ch <= '\u9FFF': scripts.add('cjk')
        elif '\uAC00' <= ch <= '\uD7AF': scripts.add('hangul')
        elif '\u3040' <= ch <= '\u309F': scripts.add('hiragana')
        elif '\u30A0' <= ch <= '\u30FF': scripts.add('katakana')
        elif '\u1780' <= ch <= '\u17FF': scripts.add('khmer')
        elif '\u0F00' <= ch <= '\u0FFF': scripts.add('tibetan')
        elif '\u1000' <= ch <= '\u109F': scripts.add('myanmar')
        elif '\u1200' <= ch <= '\u137F': scripts.add('ethiopic')
        elif '\u0590' <= ch <= '\u05FF': scripts.add('hebrew')
    if len(scripts) >= 3:
        # Check for English structure — if very few function words, it's noise
        eng_words = sum(1 for w in re.findall(r"[a-z']+", text.lower())
                        if w in _ENGLISH_FUNCTION_WORDS)
        return eng_words < 5
    return False


def _alpha_ratio(text: str) -> float:
    """Return the ratio of alphabetic characters in *text* (0.0 if empty)."""
    return sum(1 for c in text if c.isalpha()) / len(text) if text else 0.0


def _is_content_section(title: str, items: List[str]) -> bool:
    """
    Determine whether a section contains real content vs nav/UI elements.

    Uses content-quality signals (sentence structure, paragraph length,
    content markers) instead of a title blocklist. This generalizes to
    all websites — not just Wikipedia.
    """
    if not items:
        return False

    # Count items that look like real content
    real_count = 0
    for item in items:
        item = item.strip()
        if not item:
            continue
        # A real paragraph has sentence-ending punctuation
        if re.search(r'[.!?](\s|$)', item):
            real_count += 1
        # A substantial paragraph (>80 chars) is likely content
        elif len(item) > 80:
            real_count += 1
        # Contains common English content markers with meaningful length
        elif len(item) > 40 and any(
            phrase in item.lower() for phrase in ('the ', 'is ', 'are ', 'was ')
        ):
            real_count += 1

    # At least 2 real items → content section
    if real_count >= 2:
        return True

    # A single substantial paragraph can be valid (e.g., short "History" section)
    if len(items) == 1:
        item = items[0].strip()
        if len(item) > 150:
            return True
        if len(item) >= 40 and re.search(r'[.!?](\s|$)', item):
            return True

    # Sections with varied item lengths (some short, some long) are likely content
    if len(items) >= 3:
        lengths = [len(i) for i in items]
        max_len = max(lengths)
        min_len = min(lengths)
        if max_len > 100 and max_len / max(min_len, 1) > 3:
            return True

    return False


_GENERIC_NAV_LABELS = frozenset({
    # Universal UI / navigation labels found across ALL websites
    'toggle', 'navigation', 'tools', 'search', 'menu', 'footer',
    'header', 'sidebar', 'actions', 'settings', 'options',
    'preferences', 'languages', 'language', 'share', 'print',
    'download', 'export', 'import', 'help', 'about', 'contact',
    'privacy', 'terms', 'cookie', 'cookies', 'disclaimer',
    'license', 'licence', 'copyright', 'accessibility',
    'skip to content', 'table of contents', 'on this page',
    'in this article', 'related pages', 'see also',
    'external links', 'further reading', 'bibliography',
    'notes', 'citations', 'sources', 'references',
    'download pdf', 'printable version', 'appearance',
    'donate', 'upload file',
    'contribute', 'edit this page',
    'create account', 'log in',
})


_DEFAULT_SECTION = "Main Content"


def _looks_like_heading(line: str, all_lines: List[str], line_idx: int,
                         line_counts: Optional[Counter] = None) -> Optional[str]:
    """
    Determine if a line at a given position looks like a content heading.

    Uses generic, domain-agnostic heuristics that work for ALL websites:
    not a blocklist of site-specific titles, but content-quality signals
    about the line itself and the lines that follow it.

    Args:
        line: The individual line to evaluate.
        all_lines: Full list of lines from the document.
        line_idx: Index of *line* within *all_lines*.
        line_counts: Optional pre-computed Counter of all_lines for O(1) lookups.
                     If not provided, falls back to O(n) .count().

    Returns:
        Cleaned section title string, or None if the line should not
        be treated as a heading.
    """
    stripped = line.strip()
    if not stripped:
        return None

    words = stripped.split()
    num_words = len(words)

    # --- Basic shape checks ---
    # A real heading is 1-12 words, under 80 chars, starts with uppercase
    if num_words < 1 or num_words > 12 or len(stripped) > 80:
        return None
    if not stripped[0].isupper():
        return None
    # Headings do not end with sentence punctuation
    if stripped.rstrip()[-1:] in ('.', '!', '?'):
        return None
    # A line ending in colon is a label, not a heading
    if stripped.rstrip()[-1:] == ':':
        return None

    lower_line = stripped.lower()
    first_word = words[0].lower()

    # --- Generic nav/UI label exclusion ---
    # These are universal UI elements, not content section headings
    if lower_line in _GENERIC_NAV_LABELS:
        return None
    if first_word in _GENERIC_NAV_LABELS and num_words <= 3:
        return None

    # Single short action words with ≤3 total words are nav, not headings
    _SINGLE_ACTION_NAV = frozenset({
        'edit', 'view', 'read', 'share', 'print', 'download',
        'search', 'toggle', 'donate', 'upload', 'help', 'tools',
        'login', 'logout', 'signup', 'register', 'subscribe',
    })
    if num_words <= 3 and any(w.lower() in _SINGLE_ACTION_NAV for w in words):
        return None

    # --- Content-density lookahead ---
    # A real heading must be followed by content, not empty space or more nav
    content_score = 0
    empty_count = 0
    max_lookahead = min(5, len(all_lines) - line_idx - 1)

    for j in range(1, max_lookahead + 1):
        nxt = all_lines[line_idx + j].strip() if (line_idx + j) < len(all_lines) else ''
        if not nxt:
            empty_count += 1
            continue
        # Strong content signal: sentence punctuation + substantial length
        if re.search(r'[.!?]\s', nxt) and len(nxt) > 50:
            content_score += 2
        # Moderate content signal: long line
        elif len(nxt) > 80:
            content_score += 1
        # Very short lines suggest a list/nav, not a content section
        elif len(nxt) < 25:
            content_score -= 0.5
        # Does this next line look like *another* heading? ⇒ not real content
        if re.match(r'^[A-Z][A-Za-z\s]{3,50}:?$', nxt) and len(nxt.split()) < 10:
            content_score -= 0.5

    # If most following lines are empty, this isn't a content heading
    if content_score <= 0 and empty_count >= 2:
        return None

    # --- Repetition heuristic ---
    # The same line appearing 3+ times is a UI element, not a heading
    count = line_counts.get(stripped, 0) if line_counts is not None else all_lines.count(stripped)
    if count >= 3:
        return None

    # --- Sentence-fragment check ---
    # If most non-starting words begin with lowercase, this is a sentence
    trailing_words = words[1:]
    if trailing_words:
        lc_starts = sum(1 for w in trailing_words if w[0].islower())
        if lc_starts / len(trailing_words) > 0.5:
            return None

    # Clean artifacts and return
    title = re.sub(r'[#*_`]', '', stripped)
    return title.strip()


def advanced_clean_text(text: str, url: Optional[str] = None) -> str:
    """
    Advanced cleaning focused on NOISE removal, not content alteration.
    Preserves all function words, natural syntax, and content structure.
    
    Args:
        text: Raw text to clean
        url: Optional URL for domain-specific cleaning rules
    
    Returns:
        Cleaned text with noise removed but all content preserved
    """
    if not text:
        return ''
    
    # 1. DECODE & NORMALIZE (content-preserving)
    text = html.unescape(text)
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', text)
    
    # 2. REMOVE VISUAL/LAYOUT ARTIFACTS (not content)
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        
        # Skip visual separators (lines of symbols)
        if re.match(r'^[=*\-_~]{3,}$', line):
            continue
            
        # Skip page numbers/headers
        if re.match(r'^\s*\d+\s*$|^Page\s+\d+', line):
            continue
            
        # Skip breadcrumbs (navigation paths)
        if re.match(r'^[A-Za-z]+\s*>\s*[A-Za-z]+(?:\s*>\s*[A-Za-z]+)*$', line):
            continue
            
        lines.append(line)
    
    text = '\n'.join(lines)
    
    # 3. REMOVE REPETITIVE NAVIGATION (not content)
    nav_phrases = [
        r'home\s*\|.*',
        r'about\s*us.*',
        r'contact\s*us.*',
        r'sitemap.*',
        r'privacy\s*policy.*',
        r'terms\s*of\s*use.*',
        r'cookie\s*policy.*',
        r'accessibility\s*statement.*',
        r'legal\s*notice.*',
        r'copyright\s*©.*',
        r'all\s*rights\s*reserved.*',
    ]
    
    for pattern in nav_phrases:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # 4. REMOVE SOCIAL/ADVERTISEMENT NOISE
    social_patterns = [
        r'follow\s*us\s*on.*',
        r'like\s*us\s*on.*',
        r'share\s*this\s*page.*',
        r'tweet\s*this.*',
        r'sponsored\s*content.*',
        r'advertisement.*',
        r'promoted\s*by.*',
        r'partner\s*content.*',
    ]
    
    for pattern in social_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # 5. SMART DEDUPLICATION (preserve meaningful repetition)
    # Only deduplicate very short lines that look like headers
    lines = text.split('\n')
    if len(lines) > 10:
        short_lines = [line for line in lines if len(line) < 80]
        line_counts = Counter(short_lines)
        
        # Remove only if appears > 3 times AND is very short
        repeated_headers = {
            line for line, count in line_counts.items() 
            if count > 3 and len(line.split()) < 5
        }
        
        if repeated_headers:
            seen = set()
            deduped = []
            for line in lines:
                if line in repeated_headers and line in seen:
                    continue
                seen.add(line)
                deduped.append(line)
            text = '\n'.join(deduped)
    
    # 6. FINAL CLEANUP (preserve whitespace for readability)
    text = re.sub(r'\n{3,}', '\n\n', text)  # Keep paragraph breaks
    text = re.sub(r'[ \t]{2,}', ' ', text)  # Normalize spaces
    text = text.strip()
    
    return text


def clean_text(text: str) -> str:
    """Legacy function for backward compatibility"""
    return advanced_clean_text(text)


def extract_content_quality_signals(text: str) -> Dict[str, any]:
    """
    Extract signals about content quality WITHOUT altering content.
    Used for filtering and sorting, not for content modification.
    
    Args:
        text: Cleaned text to analyze
        
    Returns:
        Dictionary with quality signals
    """
    signals = {
        'has_natural_language': False,
        'has_technical_terms': False,
        'has_code_examples': False,
        'has_references': False,
        'has_structure': False,
        'content_density': 0.0,
    }
    
    if not text:
        return signals
    
    # 1. Check for natural language patterns
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    if len(words) > 100:
        signals['has_natural_language'] = True
    
    # 2. Check for technical content (programming terms, etc.)
    technical_terms = {
        'function', 'class', 'method', 'variable', 'import', 
        'def', 'return', 'if', 'else', 'for', 'while', 'try',
        'except', 'database', 'api', 'server', 'client', 'json',
        'xml', 'html', 'css', 'javascript', 'python', 'java',
    }
    found_tech = sum(1 for word in words if word in technical_terms)
    signals['has_technical_terms'] = found_tech > 5
    
    # 3. Check for code examples
    code_patterns = [
        r'def\s+\w+\(.*\):',
        r'class\s+\w+:',
        r'import\s+\w+',
        r'print\(.*\)',
        r'console\.log\(.*\)',
        r'System\.out\.println\(.*\)',
        r'<[a-zA-Z][^>]*>',
    ]
    for pattern in code_patterns:
        if re.search(pattern, text):
            signals['has_code_examples'] = True
            break
    
    # 4. Check for references/citations
    if re.search(r'\[\d+\]|\(\d{4}\)|et al\.|pp\.', text):
        signals['has_references'] = True
    
    # 5. Check for structure (headings, lists)
    heading_count = len(re.findall(r'^\s*(#+|\*+|\-+|\d+\.)\s+', text, re.MULTILINE))
    signals['has_structure'] = heading_count > 2
    
    # 6. Calculate content density (non-noise ratio)
    total_chars = len(text)
    alpha_chars = sum(1 for c in text if c.isalpha())
    if total_chars > 0:
        signals['content_density'] = alpha_chars / total_chars
    
    return signals


def extract_content_sections(text: str) -> Dict[str, List[str]]:
    """
    Extract structured sections from content based on headings.

    Uses content-quality heuristics (sentence structure, paragraph length,
    follow-up content density) — NOT site-specific title lists — so it
    generalises to ALL websites.

    Args:
        text: Cleaned text content

    Returns:
        Dictionary with section titles as keys and paragraph lists as values
    """
    sections: Dict[str, List[str]] = {}
    current_section = _DEFAULT_SECTION
    sections[current_section] = []

    lines = text.split('\n')
    line_counts = Counter(lines)  # O(n) once, enables O(1) repetition checks

    # Quick single-pass: find real content headings using
    # _looks_like_heading(), which checks the line AND its neighbours.
    for i, raw_line in enumerate(lines):
        line_stripped = raw_line.strip()
        if not line_stripped:
            continue

        # --- Markdown headings (always authoritative) ---
        md_match = re.match(r'^#{1,6}\s+(.*)$', line_stripped)
        if md_match:
            section_title = md_match.group(1).strip()
            section_title = re.sub(r'[#*_`]', '', section_title)
            if section_title and section_title != current_section:
                current_section = section_title
                sections[current_section] = []
            continue

        # --- ALL-CAPS lines (common heading style on many sites) ---
        caps_match = re.match(r'^[A-Z\s]{5,30}$', line_stripped)
        if caps_match:
            title = line_stripped.strip()
            if title and title != current_section:
                current_section = title
                sections[current_section] = []
            continue

        # --- Generic content heading (heuristically determined) ---
        title = _looks_like_heading(line_stripped, lines, i, line_counts)
        if title:
            if title != current_section:
                current_section = title
                sections[current_section] = []
            continue

        # Regular content line — only keep if it has substance
        if len(line_stripped) > 10 and not _is_nav_paragraph(line_stripped):
            sections[current_section].append(line_stripped)
    
    # Filter out empty sections
    sections = {k: v for k, v in sections.items() if v}

    # Content-quality based section filtering: keep real content sections,
    # merge nav/UI sections into "Main Content" (never lose text).
    real_sections = {}
    for title, items in sections.items():
        if title == _DEFAULT_SECTION or _is_content_section(title, items):
            real_sections[title] = items
        else:
            real_sections.setdefault(_DEFAULT_SECTION, [])
            real_sections[_DEFAULT_SECTION].extend(items)
    sections = real_sections

    return sections


def paragraphs(text: str) -> List[str]:
    """Extract meaningful paragraphs from text.

    Uses content-quality signals (sentence punctuation, paragraph length,
    alpha ratio) — not site-specific rules — to produce clean paragraph
    breaks that work for ALL websites.
    """
    if not text:
        return []

    # Split on double newlines
    raw_paras = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

    # Filter paragraphs by quality
    quality_paras = []
    for para in raw_paras:
        if len(para) < 40:
            continue
        alpha_ratio = _alpha_ratio(para)
        if alpha_ratio < 0.4:
            continue
        if _is_nav_paragraph(para):
            continue
        quality_paras.append(para)

    # If double-newline split produced too few paragraphs, try a smarter
    # single-newline grouping that respects heading boundaries and avoids
    # lumping nav lines together with real content.
    if len(quality_paras) <= 1:
        quality_paras = _group_single_newline_paragraphs(text)

    return quality_paras


def _group_single_newline_paragraphs(text: str) -> List[str]:
    """Group lines into paragraphs using content-quality boundaries.

    Handles readability-extracted content where double-newlines may
    have been collapsed into single newlines.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return []

    grouped: List[List[str]] = []
    current: List[str] = []
    line_counts = Counter(lines)  # O(n) once for O(1) repetition checks

    for i, line in enumerate(lines):
        # Skip nav lines (they add noise, not content)
        if _is_nav_paragraph(line):
            # Flush current group before skipping nav so the nav line
            # doesn't swallow the previous content.
            if current and _group_looks_complete(current):
                grouped.append(current)
                current = []
            continue

        # Check for real content headings — split on these.
        heading = _looks_like_heading(line, lines, i, line_counts)
        if heading:
            if current:
                grouped.append(current)
            # Start a new group with this heading as its own element
            # (it will be re-processed upstream as a section title)
            current = [line]
            continue

        # Check if this line should start a new paragraph
        if current and _is_line_start_of_paragraph(line, current):
            if _group_looks_complete(current):
                grouped.append(current)
                current = [line]
            else:
                current.append(line)
        else:
            current.append(line)

    if current:
        grouped.append(current)

    # Join each group into a paragraph string
    result = []
    for group in grouped:
        para = " ".join(group).strip()
        if len(para) < 40:
            continue
        # Must have sentence punctuation or substantive length
        if len(para) >= 200 or re.search(r'[.!?]\s', para):
            result.append(para)
        # Also keep paragraphs that are clearly informational
        # (longer than 100 chars with good alpha ratio)
        elif len(para) >= 100:
            alpha_ratio = _alpha_ratio(para)
            if alpha_ratio > 0.5:
                result.append(para)

    return result


def _group_looks_complete(group: List[str]) -> bool:
    """Check if a paragraph group looks like a complete thought/block."""
    if len(group) >= 4:
        # 4+ lines is almost certainly complete
        return True
    joined = " ".join(group)
    # Ends with sentence punctuation = complete thought
    if joined.rstrip()[-1:] in ('.', '!', '"', ')'):
        return True
    return False


def _is_line_start_of_paragraph(line: str, current_group: List[str]) -> bool:
    """Check if a line looks like the start of a new paragraph.

    Uses bounded heuristics to avoid oversplitting nav/UI elements
    while still creating clean paragraph breaks at topic transitions.
    """
    # Only split when we have enough context (3+ lines in current group)
    if len(current_group) < 3:
        return False

    # A long line starting with a capital after 3+ lines is a strong signal
    if len(line) > 10 and line[0].isupper():
        # Check that the LAST line of current group was a complete sentence
        last = " ".join(current_group[-2:]) if len(current_group) >= 2 else current_group[-1]
        ends_with_sentence = last.rstrip()[-1:] in ('.', '!', '"', ')')
        return ends_with_sentence

    return False


def sentences(text: str) -> List[str]:
    """Extract sentences from text with improved detection"""
    if not text:
        return []
    
    # Better sentence splitting that handles abbreviations
    # Split on sentence endings, but be careful with abbreviations
    sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])'
    
    # Replace common abbreviations to avoid false splits
    replacements = [
        (r'Dr\.', 'Dr#'),
        (r'Mr\.', 'Mr#'),
        (r'Mrs\.', 'Mrs#'),
        (r'Ms\.', 'Ms#'),
        (r'Prof\.', 'Prof#'),
        (r'etc\.', 'etc#'),
        (r'e\.g\.', 'e#g#'),
        (r'i\.e\.', 'i#e#'),
        (r'vs\.', 'vs#'),
        (r'U\.S\.', 'U#S#'),
        (r'U\.K\.', 'U#K#'),
        (r'Jan\.', 'Jan#'),
        (r'Feb\.', 'Feb#'),
        (r'Aug\.', 'Aug#'),
        (r'Sept\.', 'Sept#'),
        (r'Oct\.', 'Oct#'),
        (r'Nov\.', 'Nov#'),
        (r'Dec\.', 'Dec#'),
    ]
    
    text_clean = text
    for pattern, replacement in replacements:
        text_clean = re.sub(pattern, replacement, text_clean)
    
    # Split sentences
    raw_sentences = re.split(sentence_endings, text_clean)
    
    # Restore abbreviations
    restored_sentences = []
    for sent in raw_sentences:
        sent_restored = sent
        for pattern, replacement in replacements:
            sent_restored = sent_restored.replace(replacement, pattern.replace(r'\.', '.'))
        restored_sentences.append(sent_restored.strip())
    
    # Filter out empty sentences and very short ones
    return [s for s in restored_sentences if len(s) > 15 and not s.isspace()]


def top_keywords(text: str, n: int = 15, min_word_length: int = 4) -> List[str]:
    """
    Extract top keywords with improved filtering.
    
    Args:
        text: Text to analyze
        n: Number of keywords to return
        min_word_length: Minimum word length to consider
        
    Returns:
        List of top keywords
    """
    if not text:
        return []
    
    # Convert to lowercase
    text_lower = text.lower()
    
    # Extract words (allow hyphens and apostrophes in words)
    words = re.findall(r"\b[a-zA-Z'][a-zA-Z'-]{%d,}\b" % (min_word_length-1), text_lower)
    
    # Filter by word length only (no stopwords removal)
    filtered_words = [w for w in words if len(w) >= min_word_length]
    
    # Count frequencies
    word_counts = Counter(filtered_words)
    
    # Return top N keywords
    return [word for word, count in word_counts.most_common(n)]


def calculate_readability_metrics(text: str) -> Dict[str, float]:
    """
    Calculate basic readability metrics for the text.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary with readability metrics
    """
    if not text:
        return {}
    
    # Count sentences
    sents = sentences(text)
    num_sentences = len(sents)
    
    # Count words
    words = re.findall(r'\b\w+\b', text)
    num_words = len(words)
    
    # Count syllables (approximate)
    vowels = 'aeiouy'
    num_syllables = 0
    for word in words:
        word_lower = word.lower()
        if len(word_lower) <= 3:
            num_syllables += 1
            continue
            
        # Count vowel groups
        num_syllables += len(re.findall(r'[aeiouy]+', word_lower))
    
    # Calculate metrics
    if num_sentences > 0 and num_words > 0:
        avg_sentence_length = num_words / num_sentences
        avg_word_length = sum(len(w) for w in words) / num_words
        
        # Flesch Reading Ease (approximate)
        flesch_score = 206.835 - 1.015 * (num_words / num_sentences) - 84.6 * (num_syllables / num_words)
        
        return {
            'word_count': num_words,
            'sentence_count': num_sentences,
            'avg_sentence_length': round(avg_sentence_length, 1),
            'avg_word_length': round(avg_word_length, 1),
            'flesch_reading_ease': round(flesch_score, 1) if flesch_score > 0 else 0,
            'syllable_count': num_syllables,
        }
    
    return {}


def _best_first_paragraph(paras: List[str], cleaned: str) -> str:
    """
    Score paragraphs and return the best candidate for *first_paragraph*.

    Instead of grabbing the first non-nav match (which on sites like
    Wikipedia picks infobox garbage before the real article text), we:

    1. Try the traditional "first non-nav paragraph whose first 200 chars
       pass a light camelCase / infobox sniff test".
    2. Fall back to the paragraph with the highest content-quality score
       (sentence count, length, technical-term density).
    3. As a last resort, scan raw lines for anything ≥40 chars that isn't
       nav noise.
    """
    if not paras:
        return _fallback_first_paragraph(cleaned)

    # --- Strategy 1: first paragraph that passes a light prefix sniff ---
    for p in paras:
        if _is_nav_paragraph(p):
            continue
        # Drop known infobox prefixes (camelCase concatenations with no
        # sentence structure within the first 200 chars)
        head = p[:200]
        camel_matches = _CAMEL_CASE_RE.findall(head)
        if camel_matches and not any(c in head for c in '.!?'):
            continue
        return p

    # --- Strategy 2: score every paragraph, return the best ---
    scored = [(p, _score_paragraph_quality(p)) for p in paras]
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored and scored[0][1] > 1.0:
        return scored[0][0]

    # --- Strategy 3: raw-line scan ---
    return _fallback_first_paragraph(cleaned)


def _score_paragraph_quality(para: str) -> float:
    """Score a paragraph for how much it looks like real, informative content."""
    if not para or len(para) < 40:
        return 0.0

    score = 0.0
    para_len = len(para)

    # Length bonus (longer paragraphs carry real exposition)
    score += min(para_len / 1500, 1.0) * 2.0

    # Sentence-ending punctuation ⇒ this is prose, not a label list
    sentence_endings = len(re.findall(r'[.!?](\s|$)', para))
    score += min(sentence_endings / 4, 1.0) * 2.0

    # Medium-length words (5-10 chars) suggest technical/scholarly content
    words = re.findall(r'\b\w+\b', para)
    if words:
        medium = sum(1 for w in words if 5 <= len(w) <= 10)
        score += min(medium / max(len(words), 1) * 3, 1.0) * 1.0

    # Penalty for excessive camelCase (infobox/noise signal)
    camel = len(_CAMEL_CASE_RE.findall(para))
    if camel > 3:
        score -= min(camel * 0.3, 2.0)

    # Penalty for very short line density (list-like content)
    lines = para.split('\n')
    short_lines = sum(1 for l in lines if len(l.strip()) < 30)
    if lines and short_lines / len(lines) > 0.4:
        score -= 1.0

    return max(score, 0.0)


def _fallback_first_paragraph(cleaned: str) -> str:
    """Last-resort scan of raw lines for a decent opening paragraph."""
    for line in cleaned.split('\n'):
        stripped = line.strip()
        if len(stripped) >= 40 and not _is_nav_paragraph(stripped):
            return stripped
    return ''


def process_record(rec: dict) -> dict:
    """
    Process a single record with advanced cleaning.
    Preserves all content while removing only noise.
    
    Args:
        rec: Input record dictionary
        
    Returns:
        Processed record dictionary with natural language preserved
    """
    raw = rec.get('main_content') or ''
    url = rec.get('url') or rec.get('final_url')
    
    # Clean ONLY noise, preserve all content words
    cleaned = advanced_clean_text(raw, url)
    
    # Extract quality signals (for filtering/sorting, not content modification)
    quality_signals = extract_content_quality_signals(cleaned)
    
    # Extract paragraphs with natural language preserved
    paras = paragraphs(cleaned)

    # Score-based first_paragraph selection: pick the best candidate,
    # not just the first non-nav match (which is often infobox garbage
    # on Wikipedia, Wiktionary, Wikibooks, etc.).
    first_para = _best_first_paragraph(paras, cleaned)

    # Trim leading non-sentence prefixes (e.g., "Python Programming (Wikibook)vte")
    if first_para and len(first_para) > 100:
        # Look for "Word is/are/was" not at position 0, indicating a prefix
        m = re.search(r'\b([A-Z][a-z]+) (is|are|was|were) ', first_para[1:150])
        if m:
            cut_pos = m.start() + 1  # +1 because we searched from index 1
            prefix = first_para[:cut_pos].strip()
            if prefix and len(prefix) < 100 and not prefix.rstrip().endswith(('.', '!', '?')):
                first_word = prefix.split()[0].lower() if prefix.split() else ''
                if first_word not in ('the', 'this', 'that', 'these', 'those', 'some', 'many', 'each', 'every', 'both', 'no', 'an', 'a'):
                    first_para = first_para[cut_pos:].strip()
    # Extract sentences with natural syntax
    sens = sentences(cleaned)
    
    # Extract keywords (stopwords removed only here)
    kw = top_keywords(cleaned, n=15)
    
    # Extract content sections
    sections = extract_content_sections(cleaned)
    
    # Calculate readability metrics
    readability = calculate_readability_metrics(cleaned)
    
    # Get content type based on URL and content
    content_type = "unknown"
    if url:
        url_lower = url.lower()
        if any(domain in url_lower for domain in ['wikipedia.org', 'wiki.']):
            content_type = "encyclopedia"
        elif any(domain in url_lower for domain in ['docs.python.org', 'documentation']):
            content_type = "official_docs"
        elif any(domain in url_lower for domain in ['tutorial', 'course', 'learn']):
            content_type = "tutorial"
        elif any(domain in url_lower for domain in ['blog', 'medium.com', 'dev.to']):
            content_type = "blog"
        elif any(domain in url_lower for domain in ['stackoverflow.com', 'stackexchange.com']):
            content_type = "qna"
        elif any(domain in url_lower for domain in ['github.com', 'gitlab.com']):
            content_type = "code_repository"
        elif any(domain in url_lower for domain in ['research', 'arxiv.org', 'academic']):
            content_type = "research_paper"
        elif any(domain in url_lower for domain in ['news', 'article', 'press']):
            content_type = "news_article"
    
    # Create structured result - full natural language preserved
    result = {
        'position': rec.get('position'),
        'title': rec.get('title'),
        'url': rec.get('url'),
        'final_url': rec.get('final_url'),
        'publish_date': rec.get('publish_date'),
        'author': rec.get('author'),
        'fetch_time': rec.get('fetch_time'),
        'extraction_status': rec.get('extraction_status'),
        'confidence_score': rec.get('confidence_score'),
        'content_word_count': rec.get('content_word_count'),
        'content_type': content_type,
        'cleaned_content': cleaned,  # ✅ Full natural language preserved
        'first_paragraph': first_para,
        'content_sections': sections,
        'sentences_count': len(sens),
        'sample_sentences': sens[:5],  # ✅ Natural sentences with proper syntax
        'top_keywords': kw,  # ✅ Keywords extracted separately (stopwords removed only here)
        'readability_metrics': readability,
        'quality_signals': quality_signals,  # ✅ Quality metrics without content alteration
    }
    
    # Add content quality score
    quality_score = 0.0
    if cleaned:
        # Base score on extraction confidence
        quality_score += rec.get('confidence_score', 0.0) * 0.3
        
        # Score based on content length
        word_count = len(cleaned.split())
        if word_count > 1000:
            quality_score += 0.4
        elif word_count > 500:
            quality_score += 0.3
        elif word_count > 200:
            quality_score += 0.2
        elif word_count > 50:
            quality_score += 0.1
        
        # Score based on structure
        if len(sections) > 1:
            quality_score += 0.2
        if len(paras) > 5:
            quality_score += 0.1
        
        # Bonus for natural language signals
        if quality_signals.get('has_natural_language'):
            quality_score += 0.1
        
        # Cap at 1.0
        quality_score = min(quality_score, 1.0)
    
    result['content_quality_score'] = round(quality_score, 2)
    
    return result


def process_results(results: list) -> tuple:
    """
    Process search results: filter by success, clean content.
    
    Args:
        results: List of result dicts (from quick_scrape.py)
    
    Returns:
        (structured_results, stats) where stats has filtering info
    """
    # Filter: only "success" extraction status
    successful_results = [r for r in results if r.get('extraction_status') == 'success']
    
    structured_results = []
    
    for rec in successful_results:
        # Process and clean
        structured_rec = process_record(rec)
        structured_results.append(structured_rec)
    
    # Sort by quality score (descending) then position (ascending)
    structured_results.sort(key=lambda x: (-x.get('content_quality_score', 0), x.get('position', 0)))
    
    stats = {
        'total_input': len(results),
        'successful': len(successful_results),
        'failed': len(results) - len(successful_results),
        'processed': len(structured_results)
    }

    return structured_results, stats


def main():
    parser = argparse.ArgumentParser(
        description='Advanced clean and structure main_content from enterprise JSON'
    )
    parser.add_argument('input', help='Input enterprise JSON file')
    parser.add_argument('--out', '-o', default='struct_format_results.json', 
                       help='Output structured JSON path')
    parser.add_argument('--min-quality', type=float, default=0.3,
                       help='Minimum content quality score to include (0.0-1.0)')
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f'Input not found: {in_path}')
        return

    data = json.loads(in_path.read_text(encoding='utf-8'))
    results = data.get('results', [])

    # Process results: filter, clean
    structured_results, stats = process_results(results)
    
    # Filter by quality score if specified
    if args.min_quality > 0:
        original_count = len(structured_results)
        structured_results = [
            r for r in structured_results 
            if r.get('content_quality_score', 0) >= args.min_quality
        ]
        stats['quality_filtered'] = original_count - len(structured_results)

    # Build output structure
    structured = {
        'metadata': data.get('metadata', {}),
        'processing_stats': stats,
        'processing_notes': {
            'cleaning_method': 'advanced_clean_text',
            'min_quality_score': args.min_quality,
            'stopwords_filtering': False,
            'version': '2.0'
        },
        'structured_results': structured_results
    }

    # Save structured JSON
    out_path = Path(args.out)
    out_path.write_text(
        json.dumps(structured, indent=2, ensure_ascii=False), 
        encoding='utf-8'
    )
    
    print(f'\n✅ Advanced processing complete!')
    print(f'   📄 Structured JSON: {out_path}')
    print(f'   📊 Total input: {stats["total_input"]}')
    print(f'   ✅ Successful: {stats["successful"]}')
    print(f'   ❌ Failed (ignored): {stats["failed"]}')
    if 'quality_filtered' in stats:
        print(f'   ⚠️  Quality filtered: {stats["quality_filtered"]}')
    
    # Show top results summary
    if structured_results:
        print(f'\n🏆 Top {min(3, len(structured_results))} results by quality:')
        for i, result in enumerate(structured_results[:3], 1):
            print(f'   {i}. {result.get("title", "No title")[:60]}...')
            print(f'      URL: {result.get("url", "No URL")[:80]}...')
            print(f'      Quality: {result.get("content_quality_score", 0):.2f}')
            print(f'      Words: {len(result.get("cleaned_content", "").split())}')
            print(f'      Type: {result.get("content_type", "unknown")}')
            print()


if __name__ == '__main__':
    main()