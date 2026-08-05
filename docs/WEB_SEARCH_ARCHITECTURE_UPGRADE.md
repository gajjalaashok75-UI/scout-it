# Web Search Architecture Upgrade Plan

**Status:** 📋 Planning Phase  
**Goal:** Upgrade `web-search` to use the same advanced staged architecture as `news-search`

## Current State Analysis

### News Search Architecture (Advanced ✅)

```
Query
  ↓
Multi-Source Discovery (lightweight, snippets only)
  • DDGS: 20 snippets
  • RSS feeds: ALL entries (100-500)
  • NO content extraction yet
  ↓
Wrapper/Banned URL Filtering
  • Drop MSN, Yahoo, AOL
  • Attempt resolution first
  ↓
Metadata-Only Ranking (fast, ~10ms)
  • Query match (title, snippet)
  • Domain quality scores
  • Freshness signals
  • Source authority
  ↓
Top N Selection (e.g., 10)
  ↓
Content Extraction (only top N)
  • requests → quality check → Playwright fallback
  • Browser pool reuse
  • Domain learning
  ↓
Cleaning & Structuring
  ↓
Final Results (10 fully extracted)
```

**Benefits:**
- 168 candidates → rank all → extract top 10 only
- Fast discovery (12s for 168 snippets)
- Intelligent ranking before extraction
- 62% less extraction work
- Total time: <10s for most queries

### Web Search Architecture (Current - Old Pattern ❌)

```
Query
  ↓
Search Engine (DDGS/Google/Bing)
  ↓
Extract EVERY result immediately
  • requests → Playwright fallback
  • Extract first 100 results
  • NO pre-ranking
  • Wasteful extraction
  ↓
Clean & Filter
  ↓
Return Results
```

**Problems:**
- Extracts content for ALL results before ranking
- No wrapper filtering until after extraction
- No domain quality signals
- No metadata-based ranking
- Wastes bandwidth and time
- Triggers more CAPTCHAs

## Proposed Architecture

### Phase 1: Lightweight Discovery

**Collect snippets only (NO extraction)**

```python
def _discover_web_results(query, max_results=100):
    """Phase 1: Collect lightweight snippets from search providers."""
    
    candidates = []
    
    # Source 1: DDGS Text Search (primary)
    ddgs_snippets = _ddgs_text_search_snippets_only(
        query, 
        max_results=max_results,
        region=region,
        timelimit=timelimit
    )
    # Returns: {title, url, snippet, source: 'ddgs'}
    
    # Source 2: Additional providers (if enabled)
    if source == 'google':
        google_snippets = _google_search_snippets()
    
    if source == 'brave':
        brave_snippets = _brave_search_snippets()
    
    # Store lightweight metadata
    for snippet in ddgs_snippets:
        candidates.append({
            'title': snippet.title,
            'url': snippet.url,
            'snippet': snippet.body,
            'source': 'ddgs',
            'position': snippet.position,
            # NO 'content' field yet!
        })
    
    return candidates
```

**Output Example:**
```
[cyan]Phase 1: Lightweight Discovery[/cyan]
  • Total candidates: 100
  • Collection time: 2.5s
  • Ready for ranking (NO content extracted yet)
```

### Phase 1.5: Wrapper/Banned URL Filtering

**Reuse existing resolver from news-search**

```python
def _filter_wrappers_and_banned(candidates):
    """Phase 1.5: Drop MSN/Yahoo/AOL wrappers, banned domains."""
    
    from .source_resolvers import (
        is_wrapper_url,
        resolve_wrapper_url,
        is_banned_domain
    )
    
    filtered = []
    dropped_counts = {'msn': 0, 'yahoo': 0, 'aol': 0, 'banned': 0}
    
    for candidate in candidates:
        url = candidate['url']
        
        # Check banned domains first
        if is_banned_domain(url):
            dropped_counts['banned'] += 1
            continue
        
        # Check wrapper URLs
        if is_wrapper_url(url):
            # Attempt resolution
            resolved = resolve_wrapper_url(url)
            if resolved and resolved != url:
                candidate['url'] = resolved
                candidate['original_wrapper'] = url
                filtered.append(candidate)
            else:
                # Drop if can't resolve
                domain = urlparse(url).netloc
                if 'msn' in domain:
                    dropped_counts['msn'] += 1
                elif 'yahoo' in domain:
                    dropped_counts['yahoo'] += 1
                elif 'aol' in domain:
                    dropped_counts['aol'] += 1
        else:
            filtered.append(candidate)
    
    return filtered, dropped_counts
```

**Output Example:**
```
  • Wrapper resolution: 3 resolved, 7 dropped (5ms)
    └─ MSN: 5, Yahoo: 1, AOL: 1
```

### Phase 2: Metadata-Only Ranking

**Rank ALL candidates before extraction**

```python
def _rank_web_candidates(candidates, query):
    """Phase 2: Rank candidates using metadata only."""
    
    from .staged_ranker import rank_candidates_initial
    from .domain_learning import get_domain_quality_score
    
    for candidate in candidates:
        score = 0.0
        
        # 1. Query Match (title + snippet)
        title_match = fuzzy_match(query, candidate['title'])
        snippet_match = fuzzy_match(query, candidate['snippet'])
        
        score += title_match * 10.0  # Title weight
        score += snippet_match * 5.0  # Snippet weight
        
        # Exact phrase boost
        if query.lower() in candidate['title'].lower():
            score += 50.0
        
        # 2. Domain Quality
        domain = urlparse(candidate['url']).netloc
        domain_score = get_domain_quality_score(domain)
        score += domain_score * 2.0
        
        # 3. Authority Signals
        if is_official_docs(domain):
            score += 20.0  # docs.python.org, docs.github.com
        
        if is_company_site(domain):
            score += 15.0  # openai.com, microsoft.com
        
        if is_github_repo(candidate['url']):
            score += 18.0  # github.com/user/repo
        
        # 4. Domain Penalties
        if is_low_quality_domain(domain):
            score -= 30.0  # pinterest, quora, msn
        
        # 5. Position Bonus (earlier results slightly favored)
        position_bonus = max(0, 10 - candidate.get('position', 10))
        score += position_bonus
        
        candidate['rank_score'] = score
    
    # Sort by rank_score descending
    ranked = sorted(candidates, key=lambda x: x['rank_score'], reverse=True)
    
    return ranked
```

**Output Example:**
```
[cyan]Phase 2: Ranking Candidates[/cyan]
  • Ranking 93 candidates by relevance
  • Using: title, snippet, domain quality, authority
  • Selecting top 10 for content extraction
  ✓ Ranked in 15ms
  ✓ Selected top 10 for extraction
```

### Phase 3: Top N Selection

```python
# Simply take top N after ranking
top_n = ranked_candidates[:max_results]

print(f"[cyan]Phase 3: Content Extraction[/cyan]")
print(f"  • Extracting full page content for {len(top_n)} URLs")
print(f"  • Using: requests → Playwright fallback")
```

### Phase 4: Content Extraction

**Reuse existing ExtractionEngine**

```python
def _extract_top_candidates(candidates, workers=5):
    """Phase 4: Extract full content for top N only."""
    
    from .extraction import ExtractionEngine, fetch_resilient
    
    engine = ExtractionEngine(
        max_workers=workers,
        max_fetch_retries=3,
        enable_js_fallback=True
    )
    
    # Extract only the top candidates
    extracted = engine.extract_multiple(candidates)
    
    return extracted
```

**Output Example:**
```
[cyan]Extraction Breakdown:[/cyan]
  ✓ URL  1 (docs.python.org) [green]requests [/green] 2341 words
  ✓ URL  2 (github.com     ) [green]requests [/green] 1823 words
  ✓ URL  3 (openai.com     ) [green]Playwright[/green] 1456 words
  ...
  
[cyan]Extraction Stats:[/cyan]
  • Requests tier: 8/10
  • Playwright tier: 2/10
  • Failed/Low quality: 0/10
  • Total time: 12.3s
  • Average per URL: 1.23s
  ✓ Extracted in 12.3s
```

### Phase 5: Cleaning & Structuring

**Reuse existing cleaner**

```python
structured_results, cleaner_stats = process_results(extracted)
```

## Implementation Checklist

### Step 1: Add Snippet-Only Discovery ✅

- [ ] Create `_ddgs_text_search_snippets_only()` function
- [ ] Modify DDGS integration to return lightweight metadata
- [ ] NO extraction in discovery phase

### Step 2: Integrate Wrapper Filtering ✅

- [ ] Import `source_resolvers` module
- [ ] Add wrapper detection and resolution
- [ ] Drop unresolvable wrappers
- [ ] Log dropped counts

### Step 3: Add Metadata Ranking ✅

- [ ] Create `_rank_web_candidates()` function
- [ ] Implement query matching (title, snippet)
- [ ] Add domain quality scoring
- [ ] Add authority signals (docs, github, company sites)
- [ ] Add domain penalties (pinterest, quora, low-quality)
- [ ] Sort by relevance score

### Step 4: Top N Selection ✅

- [ ] Select top `max_results` after ranking
- [ ] Pass only top N to extraction

### Step 5: Reuse Extraction Engine ✅

- [ ] Use existing `ExtractionEngine`
- [ ] Apply requests → Playwright fallback
- [ ] Use browser pool
- [ ] Apply domain learning

### Step 6: Update Output Format ✅

- [ ] Match news-search output structure
- [ ] Add phase timing breakdowns
- [ ] Add candidate counts at each stage
- [ ] Add ranking metadata

### Step 7: Testing ✅

- [ ] Test with 100 candidates → extract 10
- [ ] Verify ranking quality
- [ ] Verify extraction only happens for top N
- [ ] Compare old vs new performance
- [ ] Verify no breaking changes to CLI

## Shared Components to Reuse

### From news-search

✅ **Wrapper Resolution**
- `source_resolvers.is_wrapper_url()`
- `source_resolvers.resolve_wrapper_url()`
- `source_resolvers.is_banned_domain()`

✅ **Ranking Engine**
- `staged_ranker.rank_candidates_initial()`
- Domain quality scoring
- Query matching utilities

✅ **Extraction Engine**
- `ExtractionEngine` class
- `fetch_resilient()` function
- Browser pool
- Quality validation

✅ **Domain Learning**
- `domain_learning.get_domain_quality_score()`
- Domain statistics tracking
- Strategy persistence

✅ **Content Cleaning**
- `process_results()` from cleaner
- HTML stripping
- Quality filtering

## Expected Performance Improvements

### Before (Current)

```bash
scout-it web-search -q "openai agents sdk" -m 10
```

- Discovers 100 URLs from DDGS
- **Extracts ALL 100 immediately** (wasteful)
- Requests: ~60 succeed, 40 fail
- Playwright: ~40 attempts
- Total time: **45-60s**
- Bandwidth: **~50MB**

### After (Staged)

```bash
scout-it web-search -q "openai agents sdk" -m 10
```

- Discovers 100 snippets (lightweight)
- Filters wrappers: 93 remain
- Ranks all 93 by relevance
- **Extracts only top 10** (efficient)
- Requests: ~8 succeed
- Playwright: ~2 attempts
- Total time: **8-12s** (4-5x faster)
- Bandwidth: **~5MB** (10x less)

## Migration Strategy

### Option 1: In-Place Upgrade (Recommended)

Update `web_search()` function in `cli.py`:

```python
def web_search(query, max_results=10, ...):
    """Web search with staged architecture (matches news-search)."""
    
    # Phase 1: Discovery (snippets only)
    candidates = _discover_web_results(query, max_results=100)
    
    # Phase 1.5: Filter wrappers
    candidates, wrapper_stats = _filter_wrappers_and_banned(candidates)
    
    # Phase 2: Rank
    ranked = _rank_web_candidates(candidates, query)
    
    # Phase 3: Select top N
    top_n = ranked[:max_results]
    
    # Phase 4: Extract
    extracted = _extract_top_candidates(top_n, workers=workers)
    
    # Phase 5: Clean
    structured_results, cleaner_stats = process_results(extracted)
    
    return structured_results, stats
```

### Option 2: Create BaseSearchPipeline (Future)

```python
class BaseSearchPipeline:
    """Shared pipeline for news-search and web-search."""
    
    def discover(self, query):
        raise NotImplementedError
    
    def filter(self, candidates):
        # Shared wrapper filtering
        pass
    
    def rank(self, candidates, query):
        # Shared ranking logic
        pass
    
    def extract(self, top_n):
        # Shared extraction
        pass
    
    def clean(self, extracted):
        # Shared cleaning
        pass

class WebSearchPipeline(BaseSearchPipeline):
    def discover(self, query):
        return _ddgs_text_search_snippets_only(query)

class NewsSearchPipeline(BaseSearchPipeline):
    def discover(self, query):
        # DDGS + RSS feeds
        pass
```

## CLI Compatibility

### Keep Existing Arguments

```bash
# Old behavior (still works)
scout-it web-search -q "query" -m 10

# New internal flow:
# - Discovers 100 snippets
# - Ranks all
# - Extracts top 10
```

### Add New Argument (Future)

```bash
# Snippets mode (no extraction)
scout-it web-search -q "query" --snippets

# Returns:
# - 100 ranked snippets
# - NO content extraction
# - Metadata only
```

## Success Metrics

### Performance

- ✅ **4-5x faster** for typical queries
- ✅ **10x less bandwidth** usage
- ✅ **90% fewer Playwright launches**
- ✅ **50% fewer CAPTCHAs** (less aggressive)

### Quality

- ✅ **Better ranking** (metadata + domain quality)
- ✅ **Official docs prioritized** (authority signals)
- ✅ **Low-quality sites demoted** (pinterest, quora)
- ✅ **Wrappers resolved or dropped** (cleaner results)

### Architecture

- ✅ **Consistent with news-search**
- ✅ **Reuses shared components**
- ✅ **No duplicate implementations**
- ✅ **Easier to maintain**

## Next Steps

1. **Review this plan** with stakeholders
2. **Create feature branch**: `feature/web-search-staged-architecture`
3. **Implement Phase 1**: Discovery + wrapper filtering
4. **Implement Phase 2**: Ranking
5. **Test performance** improvements
6. **Compare results** quality (old vs new)
7. **Update documentation**
8. **Merge to main**

## Related Documentation

- [News Search Architecture](RSS_INTEGRATION_GUIDE.md)
- [Staged Ranking Implementation](STAGED_RANKING_IMPLEMENTATION.md)
- [Discovery-First Flow](QUICK_REFERENCE_CORRECTED_FLOW.md)
- [Production Hardening](PRODUCTION_HARDENING_GUIDE.md)

---

**Question for review:** Should we implement this as an in-place upgrade or create a BaseSearchPipeline abstraction first?
