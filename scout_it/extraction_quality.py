#!/usr/bin/env python3
"""
Extraction Quality Validation & Automatic Escalation

This module provides intelligent quality validation for extracted content
and automatic escalation to Playwright when requests extraction is insufficient.

Key Features:
- Content quality scoring (word count, paragraph count, structure)
- Automatic Playwright escalation for low-quality extractions
- Domain-level learning and optimization
- Paywall/block detection
"""

import logging
import re
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class ExtractionQuality:
    """Extraction quality assessment"""
    word_count: int
    paragraph_count: int
    has_title: bool
    title_similarity: float
    is_blocked: bool
    is_paywall: bool
    quality_score: float
    should_escalate: bool
    reason: str = ""


# Quality thresholds
MIN_WORDS_THRESHOLD = 150  # Lowered from 200
MIN_PARAGRAPHS_THRESHOLD = 2  # Lowered from 3
MIN_QUALITY_SCORE = 0.50  # Raised from 0.4 for better quality

# Immediate escalation triggers (bypass scoring)
IMMEDIATE_ESCALATION_WORD_LIMIT = 150
IMMEDIATE_ESCALATION_TITLE_SIMILARITY = 0.30

# Blocked page indicators
BLOCKED_INDICATORS = [
    "enable javascript",
    "javascript is disabled",
    "please enable javascript",
    "cloudflare",
    "just a moment",
    "checking your browser",
    "access denied",
    "403 forbidden",
    "are you a robot",
    "captcha",
    "security check",
    "ray id",
    "ddos protection",
]

# Paywall indicators
PAYWALL_INDICATORS = [
    "subscribe to read",
    "subscription required",
    "members only",
    "premium content",
    "sign in to continue",
    "create a free account",
    "this article is for subscribers",
    "paywall",
    "become a member",
]


def calculate_title_similarity(title: str, content: str) -> float:
    """Calculate similarity between title and content.
    
    Returns 0.0-1.0 score. Low scores indicate content may not match title.
    """
    if not title or not content:
        return 0.0
    
    # Normalize and tokenize
    title_words = set(re.findall(r'\b\w+\b', title.lower()))
    content_lower = content.lower()
    
    # Count how many title words appear in content
    matches = sum(1 for word in title_words if word in content_lower)
    
    if not title_words:
        return 0.0
    
    return matches / len(title_words)


def detect_blocked_page(content: str, html: Optional[str] = None) -> bool:
    """Detect if the page is blocked by anti-bot protection.
    
    Args:
        content: Extracted text content
        html: Raw HTML (optional, for additional checks)
    
    Returns:
        True if page appears to be blocked
    """
    if not content:
        return False
    
    content_lower = content.lower()
    
    # Check for blocked indicators
    for indicator in BLOCKED_INDICATORS:
        if indicator in content_lower:
            return True
    
    # Check HTML for Cloudflare/bot detection scripts
    if html:
        html_lower = html.lower()
        if any(marker in html_lower for marker in [
            'cf-browser-verification',
            'cf-challenge-form',
            'data-ray-id',
            'challenge-form',
        ]):
            return True
    
    return False


def detect_paywall(content: str) -> bool:
    """Detect if the page is behind a paywall.
    
    Args:
        content: Extracted text content
    
    Returns:
        True if page appears to be paywalled
    """
    if not content:
        return False
    
    content_lower = content.lower()
    
    # Check for paywall indicators
    for indicator in PAYWALL_INDICATORS:
        if indicator in content_lower:
            return True
    
    return False


def count_paragraphs(content: str) -> int:
    """Count meaningful paragraphs in content.
    
    A paragraph is considered meaningful if it has at least 20 words.
    """
    if not content:
        return 0
    
    # Split by double newlines or sentence endings
    paragraphs = re.split(r'\n\s*\n', content)
    
    # Filter out short paragraphs (< 20 words)
    meaningful_paragraphs = [
        p for p in paragraphs
        if len(p.split()) >= 20
    ]
    
    return len(meaningful_paragraphs)


def calculate_quality_score(
    word_count: int,
    paragraph_count: int,
    has_title: bool,
    title_similarity: float,
    is_blocked: bool,
    is_paywall: bool,
    content_density: float = 0.5,
) -> float:
    """Calculate overall quality score (0.0 - 1.0) with improved weighting.
    
    Scoring factors (revised for better balance):
    - Title similarity: 25% weight (HIGHEST - content must match title)
    - Word count: 20% weight (sufficient length)
    - Structure (paragraphs): 20% weight (proper formatting)
    - Content density: 15% weight (actual content vs boilerplate)
    - Readability: 10% weight (proper sentences)
    - Metadata: 10% weight (title presence)
    - Blocked/paywall: immediate failure
    
    Quality interpretation:
    - 0.80-1.00 = Excellent
    - 0.65-0.79 = Good
    - 0.50-0.64 = Acceptable
    - 0.30-0.49 = Escalate
    - 0.00-0.29 = Escalate
    """
    if is_blocked or is_paywall:
        return 0.0
    
    score = 0.0
    
    # 1. Title similarity (25% weight) - MOST IMPORTANT
    score += 0.25 * title_similarity
    
    # 2. Word count score (20% weight) - Supporting factor
    if word_count >= 800:
        score += 0.20
    elif word_count >= MIN_WORDS_THRESHOLD:
        score += 0.20 * (word_count / 800)
    else:
        score += 0.20 * (word_count / MIN_WORDS_THRESHOLD) * 0.4
    
    # 3. Structure/Paragraph count (20% weight)
    if paragraph_count >= 4:
        score += 0.20
    elif paragraph_count >= MIN_PARAGRAPHS_THRESHOLD:
        score += 0.20 * (paragraph_count / 4)
    else:
        score += 0.20 * (paragraph_count / MIN_PARAGRAPHS_THRESHOLD) * 0.4
    
    # 4. Content density (15% weight) - Real content vs boilerplate
    # Higher density = more actual content, less navigation/ads
    score += 0.15 * min(content_density, 1.0)
    
    # 5. Readability (10% weight) - Proper sentence structure
    # Estimated by checking if content has punctuation and capitalization
    readability = 0.5  # Default medium
    if word_count > 50:
        # Simple heuristic: proper sentences have periods and capitals
        # This would need the actual content, so we use a default
        readability = 0.7
    score += 0.10 * readability
    
    # 6. Metadata/Title presence (10% weight)
    if has_title:
        score += 0.10
    
    return min(score, 1.0)


def assess_extraction_quality(
    content: str,
    title: Optional[str] = None,
    html: Optional[str] = None,
    expected_title: Optional[str] = None,
    content_density: float = 0.5,
) -> ExtractionQuality:
    """Assess the quality of extracted content.
    
    Args:
        content: Extracted text content
        title: Extracted title (optional)
        html: Raw HTML (optional, for additional checks)
        expected_title: Expected title from search result (optional)
        content_density: Ratio of actual content to total page size (0.0-1.0)
    
    Returns:
        ExtractionQuality assessment with escalation recommendation
    """
    # Basic metrics
    word_count = len(content.split()) if content else 0
    paragraph_count = count_paragraphs(content)
    has_title = bool(title and len(title.strip()) > 0)
    
    # Detection checks
    is_blocked = detect_blocked_page(content, html)
    is_paywall = detect_paywall(content)
    
    # Title similarity
    title_similarity = 0.0
    if expected_title and content:
        title_similarity = calculate_title_similarity(expected_title, content)
    elif title and content:
        title_similarity = calculate_title_similarity(title, content)
    
    # Calculate quality score
    quality_score = calculate_quality_score(
        word_count=word_count,
        paragraph_count=paragraph_count,
        has_title=has_title,
        title_similarity=title_similarity,
        is_blocked=is_blocked,
        is_paywall=is_paywall,
        content_density=content_density,
    )
    
    # Determine if escalation is needed
    # IMMEDIATE escalation triggers (bypass quality score)
    should_escalate = False
    reason = ""
    
    if is_blocked:
        should_escalate = True
        reason = "blocked_page_detected"
    elif is_paywall:
        should_escalate = False  # Playwright won't help with paywalls
        reason = "paywall_detected"
    elif word_count < IMMEDIATE_ESCALATION_WORD_LIMIT:
        should_escalate = True
        reason = f"insufficient_words ({word_count} < {IMMEDIATE_ESCALATION_WORD_LIMIT})"
    elif title_similarity < IMMEDIATE_ESCALATION_TITLE_SIMILARITY:
        should_escalate = True
        reason = f"poor_title_match ({title_similarity:.2f} < {IMMEDIATE_ESCALATION_TITLE_SIMILARITY})"
    elif paragraph_count < MIN_PARAGRAPHS_THRESHOLD:
        should_escalate = True
        reason = f"insufficient_paragraphs ({paragraph_count} < {MIN_PARAGRAPHS_THRESHOLD})"
    elif quality_score < MIN_QUALITY_SCORE:
        should_escalate = True
        reason = f"low_quality_score ({quality_score:.2f} < {MIN_QUALITY_SCORE})"
    else:
        reason = "quality_acceptable"
    
    return ExtractionQuality(
        word_count=word_count,
        paragraph_count=paragraph_count,
        has_title=has_title,
        title_similarity=title_similarity,
        is_blocked=is_blocked,
        is_paywall=is_paywall,
        quality_score=quality_score,
        should_escalate=should_escalate,
        reason=reason,
    )


def should_escalate_to_playwright(
    content: str,
    title: Optional[str] = None,
    html: Optional[str] = None,
    expected_title: Optional[str] = None,
    extraction_tier: str = "requests",
) -> Tuple[bool, str]:
    """Determine if extraction should be escalated to Playwright.
    
    Args:
        content: Extracted text content
        title: Extracted title (optional)
        html: Raw HTML (optional)
        expected_title: Expected title from search result (optional)
        extraction_tier: Current extraction tier (requests/playwright/etc)
    
    Returns:
        (should_escalate, reason) tuple
    """
    # Don't escalate if already using Playwright
    if extraction_tier == "playwright":
        return False, "already_using_playwright"
    
    # Assess quality
    quality = assess_extraction_quality(
        content=content,
        title=title,
        html=html,
        expected_title=expected_title,
    )
    
    return quality.should_escalate, quality.reason


# Domain-level learning (persistent storage)
import json
from pathlib import Path

_DOMAIN_STATS_FILE = Path.home() / ".scout-it" / "domain_stats.json"
_DOMAIN_STATS: Dict[str, Dict[str, Any]] = {}


def _load_domain_stats() -> None:
    """Load domain statistics from persistent storage."""
    global _DOMAIN_STATS
    try:
        if _DOMAIN_STATS_FILE.exists():
            with open(_DOMAIN_STATS_FILE, 'r') as f:
                _DOMAIN_STATS = json.load(f)
            logger.info(f"Loaded domain stats for {len(_DOMAIN_STATS)} domains")
    except Exception as e:
        logger.warning(f"Failed to load domain stats: {e}")
        _DOMAIN_STATS = {}


def _save_domain_stats() -> None:
    """Save domain statistics to persistent storage."""
    try:
        _DOMAIN_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_DOMAIN_STATS_FILE, 'w') as f:
            json.dump(_DOMAIN_STATS, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save domain stats: {e}")


# Load stats on module import
_load_domain_stats()


def record_domain_extraction(
    url: str,
    tier: str,
    success: bool,
    word_count: int = 0,
) -> None:
    """Record extraction outcome for domain-level learning (persisted to disk).
    
    Args:
        url: Full URL
        tier: Extraction tier used (requests/playwright)
        success: Whether extraction was successful
        word_count: Number of words extracted
    """
    try:
        domain = urlparse(url).netloc
        if not domain:
            return
        
        if domain not in _DOMAIN_STATS:
            _DOMAIN_STATS[domain] = {
                "requests_attempts": 0,
                "requests_successes": 0,
                "playwright_attempts": 0,
                "playwright_successes": 0,
                "total_words_requests": 0,
                "total_words_playwright": 0,
            }
        
        stats = _DOMAIN_STATS[domain]
        
        if tier in ("requests", "basic-fallback", "tls-impersonate"):
            stats["requests_attempts"] += 1
            if success:
                stats["requests_successes"] += 1
                stats["total_words_requests"] += word_count
        elif tier == "playwright":
            stats["playwright_attempts"] += 1
            if success:
                stats["playwright_successes"] += 1
                stats["total_words_playwright"] += word_count
        
        # Save to disk after every update
        _save_domain_stats()
    
    except Exception:
        pass  # Never fail the extraction due to stats tracking


def should_skip_to_playwright(url: str) -> Tuple[bool, float]:
    """Check if domain history suggests skipping directly to Playwright.
    
    Args:
        url: Full URL
    
    Returns:
        (should_skip, confidence) tuple
    """
    try:
        domain = urlparse(url).netloc
        if not domain or domain not in _DOMAIN_STATS:
            return False, 0.0
        
        stats = _DOMAIN_STATS[domain]
        
        # Need at least 5 attempts to make a decision
        total_attempts = stats["requests_attempts"] + stats["playwright_attempts"]
        if total_attempts < 5:
            return False, 0.0
        
        # Calculate success rates
        requests_rate = (
            stats["requests_successes"] / stats["requests_attempts"]
            if stats["requests_attempts"] > 0 else 0.0
        )
        playwright_rate = (
            stats["playwright_successes"] / stats["playwright_attempts"]
            if stats["playwright_attempts"] > 0 else 0.0
        )
        
        # Skip to Playwright if it has >80% success and requests has <30% success
        if playwright_rate > 0.8 and requests_rate < 0.3 and stats["playwright_attempts"] >= 3:
            logger.info(
                f"Domain {domain}: Playwright success rate {playwright_rate:.1%} vs "
                f"requests {requests_rate:.1%} - skipping to Playwright"
            )
            return True, playwright_rate
        
        return False, 0.0
    
    except Exception:
        return False, 0.0


def get_domain_stats(url: str) -> Optional[Dict[str, Any]]:
    """Get extraction statistics for a domain.
    
    Args:
        url: Full URL
    
    Returns:
        Domain statistics dict or None
    """
    try:
        domain = urlparse(url).netloc
        if domain and domain in _DOMAIN_STATS:
            stats = _DOMAIN_STATS[domain].copy()
            
            # Add calculated rates
            if stats["requests_attempts"] > 0:
                stats["requests_success_rate"] = stats["requests_successes"] / stats["requests_attempts"]
                stats["requests_avg_words"] = stats["total_words_requests"] / stats["requests_successes"] if stats["requests_successes"] > 0 else 0
            else:
                stats["requests_success_rate"] = 0.0
                stats["requests_avg_words"] = 0
            
            if stats["playwright_attempts"] > 0:
                stats["playwright_success_rate"] = stats["playwright_successes"] / stats["playwright_attempts"]
                stats["playwright_avg_words"] = stats["total_words_playwright"] / stats["playwright_successes"] if stats["playwright_successes"] > 0 else 0
            else:
                stats["playwright_success_rate"] = 0.0
                stats["playwright_avg_words"] = 0
            
            return stats
        
        return None
    
    except Exception:
        return None
