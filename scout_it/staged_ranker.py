"""
Staged ranking system for news search.

Implements fast initial ranking based on lightweight metadata before
expensive content extraction, then re-ranks with full content.

Performance targets:
- Initial ranking: < 1s
- Final ranking: < 1s
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse


# ============================================================================
# Source Quality Scores
# ============================================================================

# Default fallback scores (used if source_quality.json cannot be loaded)
_DEFAULT_SOURCE_QUALITY_SCORES = {
    # Premium tech sources
    'techcrunch': 1.0,
    'techcrunch:ai': 1.0,
    'techcrunch:startups': 1.0,
    'techcrunch:security': 1.0,
    'techcrunch:cloud': 1.0,
    
    # News aggregators
    'google-news': 0.95,
    'duckduckgo': 0.90,
    
    # Regional sources
    'timesofindia': 0.85,
    'toi': 0.85,
    
    # Default
    'default': 0.80,
}

# Global cache for loaded scores
_LOADED_SOURCE_QUALITY_SCORES = None


def load_source_quality_scores(path: Optional[str] = None) -> Dict[str, float]:
    """Load source quality scores from JSON file with fallback to defaults.
    
    Args:
        path: Optional custom path to JSON file. If None, uses default location.
    
    Returns:
        Dictionary of source names to quality scores (0.0-1.0)
    """
    if path is None:
        # Default location: scout_it/data/source_quality.json
        default_path = Path(__file__).parent / "data" / "source_quality.json"
    else:
        default_path = Path(path)
    
    try:
        if default_path.exists():
            with open(default_path, 'r', encoding='utf-8') as f:
                scores = json.load(f)
                # Validate that scores are floats between 0 and 1
                for key, value in scores.items():
                    if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                        raise ValueError(f"Invalid score for '{key}': {value} (must be 0.0-1.0)")
                return scores
    except Exception as e:
        import warnings
        warnings.warn(f"Could not load source_quality.json: {e}. Using defaults.", UserWarning)
    
    return _DEFAULT_SOURCE_QUALITY_SCORES.copy()


def get_source_quality_score(source: str) -> float:
    """Get quality score for a news source.
    
    Loads scores from scout_it/data/source_quality.json on first call,
    with fallback to hardcoded defaults if the file is missing or invalid.
    
    Args:
        source: Source name (e.g., 'techcrunch', 'google-news')
    
    Returns:
        Quality score (0.0-1.0), or default score if source not found
    """
    global _LOADED_SOURCE_QUALITY_SCORES
    
    # Load scores on first call (lazy initialization)
    if _LOADED_SOURCE_QUALITY_SCORES is None:
        _LOADED_SOURCE_QUALITY_SCORES = load_source_quality_scores()
    
    source_lower = (source or '').lower()
    
    # Exact match
    if source_lower in _LOADED_SOURCE_QUALITY_SCORES:
        return _LOADED_SOURCE_QUALITY_SCORES[source_lower]
    
    # Prefix match
    for key, score in _LOADED_SOURCE_QUALITY_SCORES.items():
        if source_lower.startswith(key):
            return score
    
    return _LOADED_SOURCE_QUALITY_SCORES.get('default', 0.80)


# ============================================================================
# Text Relevance Scoring
# ============================================================================

def tokenize_query(query: str) -> tuple[List[str], List[str], List[str]]:
    """Parse query into required (+), excluded (-), and phrase ("...") terms.
    
    Returns:
        (required_terms, excluded_terms, phrase_terms)
    """
    required = []
    excluded = []
    phrases = []
    
    # Extract phrases first
    phrase_pattern = r'"([^"]+)"'
    for match in re.finditer(phrase_pattern, query):
        phrases.append(match.group(1).lower().strip())
    
    # Remove phrases from query
    query_no_phrases = re.sub(phrase_pattern, '', query)
    
    # Extract +required and -excluded terms
    tokens = query_no_phrases.split()
    normal_terms = []
    
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        
        if token.startswith('+'):
            required.append(token[1:].lower())
        elif token.startswith('-'):
            excluded.append(token[1:].lower())
        else:
            normal_terms.append(token.lower())
    
    # If no explicit +required, treat all normal terms as semi-required
    if not required and normal_terms:
        required = normal_terms
    
    return required, excluded, phrases


def score_text_relevance(text: str, query_parts: tuple) -> tuple[float, int, List[str]]:
    """Score text relevance to query.
    
    Args:
        text: Text to score
        query_parts: (required_terms, excluded_terms, phrase_terms) from tokenize_query
    
    Returns:
        (score, match_count, matched_terms)
    """
    if not text:
        return 0.0, 0, []
    
    text_lower = text.lower()
    required, excluded, phrases = query_parts
    
    # Check excluded terms (instant disqualification)
    for term in excluded:
        if term in text_lower:
            return 0.0, 0, []
    
    score = 0.0
    match_count = 0
    matched_terms = []
    
    # Score required terms
    for term in required:
        if term in text_lower:
            # Count occurrences
            occurrences = text_lower.count(term)
            score += occurrences * 10.0
            match_count += occurrences
            matched_terms.append(term)
    
    # Score phrase matches (higher weight)
    for phrase in phrases:
        if phrase in text_lower:
            occurrences = text_lower.count(phrase)
            score += occurrences * 20.0
            match_count += occurrences
            matched_terms.append(f'"{phrase}"')
    
    return score, match_count, matched_terms


def calculate_recency_score(publish_date: Optional[str]) -> float:
    """Calculate recency boost (0.0 to 1.0).
    
    - Last 24 hours: 1.0
    - Last week: 0.8
    - Last month: 0.5
    - Older: 0.2
    """
    if not publish_date:
        return 0.2
    
    try:
        # Parse various date formats
        date_formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
        ]
        
        pub_dt = None
        for fmt in date_formats:
            try:
                pub_dt = datetime.strptime(publish_date[:26], fmt)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                break
            except (ValueError, IndexError):
                continue
        
        if pub_dt is None:
            return 0.2
        
        now = datetime.now(timezone.utc)
        age_hours = (now - pub_dt).total_seconds() / 3600
        
        if age_hours < 24:
            return 1.0
        elif age_hours < 168:  # 1 week
            return 0.8
        elif age_hours < 720:  # 30 days
            return 0.5
        else:
            return 0.2
            
    except Exception:
        return 0.2


# ============================================================================
# Initial Ranking (Fast, Metadata-Only)
# ============================================================================

def rank_candidates_initial(
    candidates: Sequence[Dict[str, Any]],
    query: str,
    top_k: int = 15,
) -> List[Dict[str, Any]]:
    """Fast initial ranking using only lightweight metadata.
    
    No content extraction. No expensive operations.
    
    Scoring factors:
    - Title relevance (weight: 3.0)
    - Summary/body relevance (weight: 2.0)
    - Source quality (weight: 1.0)
    - Publication recency (weight: 1.5)
    - Provider score (if available)
    
    Args:
        candidates: List of candidate articles (with title, body, source, publish_date)
        query: Search query
        top_k: Number of top candidates to return
    
    Returns:
        Top K candidates with initial_rank_score added
    """
    start_time = time.perf_counter()
    
    query_parts = tokenize_query(query)
    scored_candidates = []
    
    for candidate in candidates:
        title = candidate.get('title', '')
        body = candidate.get('body', '') or candidate.get('summary', '')
        source = candidate.get('source', '')
        publish_date = candidate.get('publish_date', '') or candidate.get('date', '')
        provider_score = candidate.get('score', 0) or candidate.get('rank_score', 0)
        
        # Title relevance (weight: 3.0)
        title_score, title_matches, title_terms = score_text_relevance(title, query_parts)
        title_component = title_score * 3.0
        
        # Summary/body relevance (weight: 2.0)
        body_score, body_matches, body_terms = score_text_relevance(body, query_parts)
        body_component = body_score * 2.0
        
        # Source quality (weight: 1.0)
        source_quality = get_source_quality_score(source)
        source_component = source_quality * 10.0
        
        # Recency (weight: 1.5)
        recency = calculate_recency_score(publish_date)
        recency_component = recency * 15.0
        
        # Provider score (normalized to 0-10 range)
        provider_component = min(provider_score / 10.0, 10.0) if provider_score else 0.0
        
        # Total score
        total_score = (
            title_component +
            body_component +
            source_component +
            recency_component +
            provider_component
        )
        
        # Enrich candidate with ranking metadata
        enriched = candidate.copy()
        enriched['initial_rank_score'] = round(total_score, 2)
        enriched['rank_breakdown'] = {
            'title': round(title_component, 2),
            'body': round(body_component, 2),
            'source': round(source_component, 2),
            'recency': round(recency_component, 2),
            'provider': round(provider_component, 2),
        }
        enriched['matched_terms'] = list(set(title_terms + body_terms))
        enriched['match_count'] = title_matches + body_matches
        
        scored_candidates.append(enriched)
    
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x['initial_rank_score'], reverse=True)
    
    # Take top K
    top_candidates = scored_candidates[:top_k]
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    return top_candidates


# ============================================================================
# Final Ranking (With Full Content)
# ============================================================================

def rank_candidates_final(
    candidates: Sequence[Dict[str, Any]],
    query: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """Final ranking using full extracted content.
    
    Re-ranks candidates after content extraction.
    
    Scoring factors:
    - Initial rank score (weight: 1.0) - preserves metadata relevance
    - Full content relevance (weight: 3.0)
    - Content quality signals (weight: 1.0)
    - Keyword density (weight: 0.5)
    
    Args:
        candidates: List of candidates with extracted content
        query: Search query
        top_k: Number of top results to return
    
    Returns:
        Top K candidates with final_rank_score added
    """
    start_time = time.perf_counter()
    
    query_parts = tokenize_query(query)
    scored_candidates = []
    
    for candidate in candidates:
        # Get full content
        content = candidate.get('cleaned_content', '') or candidate.get('main_content', '')
        if isinstance(content, list):
            content = ' '.join(content)
        
        # Initial score (weight: 1.0)
        initial_score = candidate.get('initial_rank_score', 0.0)
        
        # Content relevance (weight: 3.0)
        content_score, content_matches, content_terms = score_text_relevance(content, query_parts)
        content_component = content_score * 3.0
        
        # Content quality signals (weight: 1.0)
        quality_signals = candidate.get('quality_signals', {})
        quality_score = 0.0
        if quality_signals.get('has_content'):
            quality_score += 5.0
        if quality_signals.get('content_length', 0) > 500:
            quality_score += 3.0
        if not quality_signals.get('is_suspicious'):
            quality_score += 2.0
        quality_component = quality_score * 1.0
        
        # Keyword density (weight: 0.5)
        word_count = candidate.get('word_count', 0) or len(content.split())
        density = (content_matches / word_count * 100) if word_count > 0 else 0
        density_component = min(density, 10.0) * 0.5
        
        # Total final score
        total_score = (
            initial_score +
            content_component +
            quality_component +
            density_component
        )
        
        # Enrich candidate
        enriched = candidate.copy()
        enriched['final_rank_score'] = round(total_score, 2)
        enriched['rank_breakdown']['content'] = round(content_component, 2)
        enriched['rank_breakdown']['quality'] = round(quality_component, 2)
        enriched['rank_breakdown']['density'] = round(density_component, 2)
        enriched['keyword_density'] = round(density, 2)
        
        # Update matched terms
        all_matched = set(enriched.get('matched_terms', [])) | set(content_terms)
        enriched['matched_terms'] = list(all_matched)
        enriched['match_count'] = enriched.get('match_count', 0) + content_matches
        
        scored_candidates.append(enriched)
    
    # Sort by final score descending
    scored_candidates.sort(key=lambda x: x['final_rank_score'], reverse=True)
    
    # Take top K
    top_candidates = scored_candidates[:top_k]
    
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    
    return top_candidates


# ============================================================================
# Convenience Functions
# ============================================================================

def staged_ranking_pipeline(
    all_candidates: List[Dict[str, Any]],
    query: str,
    extract_content_fn: Any,
    initial_top_k: int = 15,
    final_top_k: int = 10,
    **extract_kwargs,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Complete staged ranking pipeline.
    
    1. Initial ranking (fast, metadata-only)
    2. Content extraction (only top K candidates)
    3. Final ranking (with full content)
    
    Args:
        all_candidates: All candidate articles from providers
        query: Search query
        extract_content_fn: Function to extract content (e.g., _extract_news_content)
        initial_top_k: Number of candidates to extract content for
        final_top_k: Final number of results to return
        **extract_kwargs: Arguments for extract_content_fn
    
    Returns:
        (final_results, stats)
    """
    pipeline_start = time.perf_counter()
    
    # Stage 1: Initial ranking
    stage1_start = time.perf_counter()
    top_candidates = rank_candidates_initial(all_candidates, query, top_k=initial_top_k)
    stage1_time = (time.perf_counter() - stage1_start) * 1000
    
    if not top_candidates:
        return [], {
            'pipeline': 'staged_ranking',
            'stage1_initial_ranking_ms': round(stage1_time, 2),
            'stage2_content_extraction_ms': 0,
            'stage3_final_ranking_ms': 0,
            'total_pipeline_ms': round(stage1_time, 2),
            'candidates_total': len(all_candidates),
            'candidates_selected': 0,
            'results_final': 0,
        }
    
    # Stage 2: Content extraction (only top K)
    stage2_start = time.perf_counter()
    enriched_candidates = extract_content_fn(top_candidates, **extract_kwargs)
    stage2_time = (time.perf_counter() - stage2_start) * 1000
    
    # Stage 3: Final ranking
    stage3_start = time.perf_counter()
    final_results = rank_candidates_final(enriched_candidates, query, top_k=final_top_k)
    stage3_time = (time.perf_counter() - stage3_start) * 1000
    
    total_time = (time.perf_counter() - pipeline_start) * 1000
    
    stats = {
        'pipeline': 'staged_ranking',
        'stage1_initial_ranking_ms': round(stage1_time, 2),
        'stage2_content_extraction_ms': round(stage2_time, 2),
        'stage3_final_ranking_ms': round(stage3_time, 2),
        'total_pipeline_ms': round(total_time, 2),
        'candidates_total': len(all_candidates),
        'candidates_selected': len(top_candidates),
        'results_final': len(final_results),
    }
    
    return final_results, stats
