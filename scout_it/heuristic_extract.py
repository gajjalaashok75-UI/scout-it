#!/usr/bin/env python3
"""
🧮 HEURISTIC EXTRACT — text-density DOM scoring (no LLM, fully deterministic)
==================================================================================

A rule-based fallback tier below trafilatura/justext/boilerpy3: scores every
candidate DOM node by text-density (ratio of text length to tag count, link
density, paragraph count) and picks the highest-scoring container. This is
the same core idea readability-style libraries use — entirely deterministic,
zero API calls, no model dependency of any kind.

Used as an *additional* fallback inside ``ExtractionEngine``, tried after
the existing engines rather than replacing any of them.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

# Tags whose text should never count toward a candidate's content score.
_NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form",
               "button", "iframe", "noscript", "svg", "figure"}

# Class/id substrings strongly associated with non-content chrome. Checked
# case-insensitively as a substring match against the node's class+id.
_NOISE_HINTS = (
    "nav", "menu", "sidebar", "footer", "header", "advert", "banner",
    "cookie", "popup", "modal", "share", "social", "comment", "related",
    "widget", "breadcrumb", "pagination", "newsletter", "subscribe",
)

_CONTENT_HINTS = ("article", "content", "post", "story", "entry", "main", "body-text")


def _node_hint_score(tag: Tag) -> float:
    """Bonus/penalty based on class/id naming conventions."""
    attrs_text = " ".join([
        " ".join(tag.get("class", []) or []),
        tag.get("id", "") or "",
    ]).lower()
    score = 0.0
    for hint in _CONTENT_HINTS:
        if hint in attrs_text:
            score += 15
    for hint in _NOISE_HINTS:
        if hint in attrs_text:
            score -= 20
    if tag.name == "article":
        score += 25
    if tag.name == "main":
        score += 20
    return score


def _text_density_score(tag: Tag) -> float:
    """Core text-density heuristic: reward nodes with lots of real text
    relative to markup/link noise; penalize link-heavy (nav-like) blocks."""
    text = tag.get_text(" ", strip=True)
    text_len = len(text)
    if text_len < 40:
        return -1e9  # too small to be a main-content container

    all_tags = tag.find_all(True)
    tag_count = max(len(all_tags), 1)

    link_text_len = sum(len(a.get_text(" ", strip=True)) for a in tag.find_all("a"))
    link_density = link_text_len / text_len if text_len else 1.0

    paragraphs = tag.find_all("p")
    paragraph_bonus = min(len(paragraphs) * 3, 60)

    density = text_len / tag_count
    score = density + paragraph_bonus - (link_density * 100)
    score += _node_hint_score(tag)
    return score


def extract(html: str, min_score: float = 10.0) -> Tuple[str, float]:
    """Score every plausible container and return the best one's text.

    Returns ``(text, confidence)`` where confidence is a 0.0-1.0 heuristic
    derived from how much the winner beat the runner-up by (a clear winner
    is more trustworthy than a narrow one) and its absolute text length.
    Returns ``("", 0.0)`` if nothing scored above *min_score*.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return "", 0.0

    for tag in soup.find_all(list(_NOISE_TAGS)):
        tag.decompose()

    candidates = soup.find_all(["div", "article", "main", "section", "td"])
    if not candidates:
        return "", 0.0

    scored: List[Tuple[float, Tag]] = []
    for tag in candidates:
        # Skip nodes that are themselves ancestors of a later, more specific
        # candidate to avoid trivially "winning" via a huge wrapper div --
        # we still let them compete, but the density formula already
        # penalizes markup-heavy wrappers relative to their text.
        try:
            score = _text_density_score(tag)
        except Exception:
            continue
        if score > -1e9:
            scored.append((score, tag))

    if not scored:
        return "", 0.0

    scored.sort(key=lambda pair: pair[0], reverse=True)
    best_score, best_tag = scored[0]
    if best_score < min_score:
        return "", 0.0

    text = best_tag.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)

    runner_up_score = scored[1][0] if len(scored) > 1 else 0.0
    margin = best_score - runner_up_score
    margin_confidence = min(margin / 200.0, 0.4)
    length_confidence = min(len(text) / 3000.0, 0.4)
    confidence = round(0.2 + margin_confidence + length_confidence, 3)
    confidence = max(0.0, min(confidence, 0.95))  # never claim higher than the "real" engines' best case

    return text, confidence
