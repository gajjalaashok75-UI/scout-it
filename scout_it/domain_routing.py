#!/usr/bin/env python3
"""
Domain Learning System for Smart Extraction Strategy Selection

Automatically learns which domains work best with requests vs Playwright
and routes accordingly. Persists learned strategies to disk.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger(__name__)


# Permanently banned domains that never return valid content
BANNED_DOMAINS = {
    "msn.com",
}


def normalize_domain(domain: str) -> str:
    """Normalize domain by removing www. prefix and lowercasing."""
    domain = domain.lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


class DomainLearningSystem:
    """Smart domain learning with automatic strategy selection."""
    
    def __init__(self, stats_file: Optional[Path] = None):
        """Initialize domain learning system."""
        if stats_file is None:
            stats_file = Path.home() / ".scout-it" / "domain_learning.json"
        
        self.stats_file = stats_file
        self.domains: Dict[str, Dict] = {}
        self._load_stats()
    
    def _load_stats(self):
        """Load domain statistics from disk."""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                
                # Normalize and merge any www. duplicates
                normalized = {}
                for domain, stats in data.items():
                    norm_domain = normalize_domain(domain)
                    
                    if norm_domain in normalized:
                        # Merge statistics
                        existing = normalized[norm_domain]
                        existing['requests_attempts'] += stats.get('requests_attempts', 0)
                        existing['requests_successes'] += stats.get('requests_successes', stats.get('requests_success', 0))
                        existing['playwright_attempts'] += stats.get('playwright_attempts', 0)
                        existing['playwright_successes'] += stats.get('playwright_successes', stats.get('playwright_success', 0))
                        existing['total_extractions'] += stats.get('total_extractions', 0)
                        existing['total_words_requests'] += stats.get('total_words_requests', 0)
                        existing['total_words_playwright'] += stats.get('total_words_playwright', 0)
                    else:
                        # Normalize schema
                        normalized[norm_domain] = {
                            'requests_attempts': stats.get('requests_attempts', 0),
                            'requests_successes': stats.get('requests_successes', stats.get('requests_success', 0)),
                            'playwright_attempts': stats.get('playwright_attempts', 0),
                            'playwright_successes': stats.get('playwright_successes', stats.get('playwright_success', 0)),
                            'total_extractions': stats.get('total_extractions', 0),
                            'total_words_requests': stats.get('total_words_requests', 0),
                            'total_words_playwright': stats.get('total_words_playwright', 0),
                            'last_updated': stats.get('last_updated'),
                            'strategy': stats.get('strategy', 'unknown'),
                            'confidence': stats.get('confidence', 0.0),
                        }
                
                self.domains = normalized
                self._recalculate_all_strategies()
                logger.info(f"Loaded domain learning data for {len(self.domains)} domains")
        except Exception as e:
            logger.warning(f"Failed to load domain learning data: {e}")
            self.domains = {}
    
    def _save_stats(self):
        """Save domain statistics to disk."""
        try:
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.stats_file, 'w') as f:
                json.dump(self.domains, f, indent=2)
            logger.debug(f"Saved domain learning data for {len(self.domains)} domains")
        except Exception as e:
            logger.warning(f"Failed to save domain learning data: {e}")
    
    def get_domain(self, url: str) -> str:
        """Extract and normalize domain from URL."""
        try:
            parsed = urlparse(url)
            domain = normalize_domain(parsed.netloc)
            return domain
        except Exception:
            return ""
    
    def _calculate_strategy(self, stats: Dict) -> Tuple[str, float]:
        """Calculate extraction strategy based on statistics.
        
        Returns: (strategy, confidence)
        """
        req_attempts = stats['requests_attempts']
        req_successes = stats['requests_successes']
        pw_attempts = stats['playwright_attempts']
        pw_successes = stats['playwright_successes']
        
        # Calculate success rates
        req_rate = req_successes / req_attempts if req_attempts > 0 else 0.0
        pw_rate = pw_successes / pw_attempts if pw_attempts > 0 else 0.0
        
        # Banned: Playwright tried but never works
        if pw_attempts >= 5 and pw_successes == 0:
            return ("banned", 1.0)
        
        # Playwright strategy: requests consistently fails, playwright works
        if (pw_attempts >= 5 and pw_rate >= 0.80 and 
            req_attempts >= 3 and req_rate <= 0.20):
            return ("playwright", pw_rate)
        
        # Requests strategy: requests works well
        if req_attempts >= 5 and req_rate >= 0.80:
            return ("requests", req_rate)
        
        # Not enough data
        return ("unknown", 0.0)
    
    def _recalculate_all_strategies(self):
        """Recalculate strategies for all domains."""
        for domain, stats in self.domains.items():
            strategy, confidence = self._calculate_strategy(stats)
            stats['strategy'] = strategy
            stats['confidence'] = confidence
    
    def get_strategy(self, url: str) -> Tuple[str, float]:
        """Get extraction strategy for URL.
        
        Returns: (strategy, confidence)
        - strategy: "banned", "playwright", "requests", "unknown"
        - confidence: 0.0-1.0
        """
        domain = self.get_domain(url)
        if not domain:
            return ("unknown", 0.0)
        
        # Check banned list
        if domain in BANNED_DOMAINS:
            return ("banned", 1.0)
        
        # Check learned strategy
        if domain in self.domains:
            stats = self.domains[domain]
            return (stats['strategy'], stats['confidence'])
        
        # No data yet
        return ("unknown", 0.0)
    
    def record_extraction(
        self,
        url: str,
        tier: str,
        success: bool,
        word_count: int = 0,
    ):
        """Record extraction outcome for domain learning.
        
        Args:
            url: The URL that was extracted
            tier: 'requests', 'playwright', or other tier name
            success: Whether extraction was successful (word_count >= 200)
            word_count: Number of words extracted
        """
        domain = self.get_domain(url)
        if not domain or domain in BANNED_DOMAINS:
            return
        
        # Initialize domain stats if not exists
        if domain not in self.domains:
            self.domains[domain] = {
                'requests_attempts': 0,
                'requests_successes': 0,
                'playwright_attempts': 0,
                'playwright_successes': 0,
                'total_extractions': 0,
                'total_words_requests': 0,
                'total_words_playwright': 0,
                'last_updated': None,
                'strategy': 'unknown',
                'confidence': 0.0,
            }
        
        stats = self.domains[domain]
        
        # Update attempts and successes
        if tier == 'requests':
            stats['requests_attempts'] += 1
            if success:
                stats['requests_successes'] += 1
            stats['total_words_requests'] += word_count
        elif tier == 'playwright':
            stats['playwright_attempts'] += 1
            if success:
                stats['playwright_successes'] += 1
            stats['total_words_playwright'] += word_count
        
        # Update totals
        stats['total_extractions'] += 1
        stats['last_updated'] = datetime.now().isoformat()
        
        # Recalculate strategy
        strategy, confidence = self._calculate_strategy(stats)
        stats['strategy'] = strategy
        stats['confidence'] = confidence
        
        # Save periodically
        if stats['total_extractions'] % 5 == 0:
            self._save_stats()
    
    def force_save(self):
        """Force save current statistics to disk."""
        self._save_stats()
    
    def get_stats_summary(self) -> Dict:
        """Get summary of domain learning statistics."""
        playwright_domains = []
        requests_domains = []
        banned_domains = []
        unknown_domains = []
        
        for domain, stats in self.domains.items():
            if stats['strategy'] == 'playwright':
                playwright_domains.append(domain)
            elif stats['strategy'] == 'requests':
                requests_domains.append(domain)
            elif stats['strategy'] == 'banned':
                banned_domains.append(domain)
            else:
                unknown_domains.append(domain)
        
        return {
            'total_domains': len(self.domains),
            'playwright_domains': len(playwright_domains),
            'requests_domains': len(requests_domains),
            'banned_domains': len(banned_domains),
            'unknown_domains': len(unknown_domains),
            'top_playwright': playwright_domains[:10],
            'top_requests': requests_domains[:10],
            'banned_list': banned_domains,
        }


# Global singleton instance
_learning_instance = None

def get_domain_learning() -> DomainLearningSystem:
    """Get global domain learning instance."""
    global _learning_instance
    if _learning_instance is None:
        _learning_instance = DomainLearningSystem()
    return _learning_instance
