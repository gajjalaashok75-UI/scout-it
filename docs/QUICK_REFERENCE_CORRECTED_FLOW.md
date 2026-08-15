# News Search - Quick Reference (Corrected Flow)

## TL;DR

✅ **Fixed:** Discovery → Rank → Extract (smart, fast)  
❌ **Before:** Limited collection → Extract ALL → Rank (slow, wasteful)

**Speed:** 87% faster (154s → 15-20s)

---

## How It Works Now

```
1. Discover (Lightweight)
   DDGS: 20 snippets
   RSS:  ALL entries (no limit)
   Time: <5s
   ↓
2. Rank (Fast)
   All candidates by relevance
   Select top N (N = --max)
   Time: <1s
   ↓
3. Extract (Only Top N)
   Full content for top N only
   Time: ~1-2s per article
   ↓
4. Output
   Final results
```

---

## Quick Commands

```bash
# Basic (20 DDGS → rank → extract top 10)
scout-it news-search -q "openai updates"

# More results (extract top 20)
scout-it news-search -q "openai updates" -m 20

# With category (DDGS + TechCrunch RSS → rank → extract top 10)
scout-it news-search -q "AI news" --category ai

# Multiple sources (DDGS + Google News + TechCrunch → rank → extract top 15)
scout-it news-search -q "tech" --category ai --source google-news -m 15

# All sources (DDGS + Google + TechCrunch + ToI → rank → extract top 20)
scout-it news-search -q "startup" --category startups --source google-news --location india -m 20
```

---

## What Changed

| Before | After |
|--------|-------|
| Each provider: 10 candidates | DDGS: 20, RSS: ALL |
| Extract ALL candidates | Rank first, extract top N only |
| 154s for 11 candidates | ~15s for 10 results |

---

## Discovery Limits

```
DDGS:           20 snippets
Google News:    ALL entries (up to 500)
TechCrunch:     ALL entries (up to 500)
ToI:            ALL entries (up to 500)

Total candidates: 20 + ALL RSS (could be 100-150+)
```

---

## Extraction Control

`-m` / `--max` controls how many results to extract:

```bash
-m 5     # Extract top 5 (fastest)
-m 10    # Extract top 10 (default)
-m 20    # Extract top 20
-m 50    # Extract top 50 (comprehensive)
```

**Performance:** Extraction time = N × ~1-2s

---

## Query Operators

```bash
# Required term (must contain)
scout-it news-search -q "+openai updates" --category ai

# Exclude term (must NOT contain)
scout-it news-search -q "AI -microsoft" --category ai

# Exact phrase
scout-it news-search -q '"AI agents"' --category ai

# Combined
scout-it news-search -q '+openai -microsoft "GPT-4"' --category ai
```

---

## Performance by Config

| Command | Time | Candidates | Extracted |
|---------|------|------------|-----------|
| Basic | ~15s | ~20 | 10 |
| + Category | ~18s | ~60-80 | 10 |
| + Google News | ~18s | ~40-60 | 10 |
| All sources | ~20s | ~100-150 | 10 |
| All + -m 30 | ~40s | ~100-150 | 30 |

---

## Console Output Example

```
Phase 1: Lightweight Discovery
  • Total candidates: 85
  • Collection time: 3.2s
  • Ready for ranking (NO content extracted yet)

Phase 2: Ranking Candidates
  ✓ Ranked in 45ms
  ✓ Selected top 10 for extraction

Phase 3: Content Extraction
  ✓ Extracted in 12.5s

✓ News search complete!
  • Total execution time: 16.2s
  • Final results: 10
```

---

## Tips

1. **Start with defaults** - They're optimized for speed and quality
2. **Use categories** - More focused, better results
3. **Adjust -m as needed** - Smaller = faster, larger = comprehensive
4. **Use operators** - `+required -excluded "phrase"` for precision
5. **Combine sources** - More coverage, still fast

---

## Troubleshooting

**Slow?** → Reduce `-m` or disable `--no-js-fallback`  
**Too few results?** → Increase `-m` or add sources/categories  
**Missing articles?** → Use search operators or broaden query

---

## Compare

### Before (Incorrect)
```
scout-it news-search -q "anthropic" --category ai -m 10
→ 11 candidates collected (limited)
→ Extract ALL 11 (89s wasted)
→ Total: 154s
```

### After (Correct)
```
scout-it news-search -q "anthropic" --category ai -m 10
→ 85 candidates collected (comprehensive)
→ Rank ALL (45ms)
→ Extract top 10 only (12s)
→ Total: 16s (87% faster!)
```

---

**Ready to use!** 🚀

```bash
scout-it news-search -q "your query" --category ai -m 10
```
