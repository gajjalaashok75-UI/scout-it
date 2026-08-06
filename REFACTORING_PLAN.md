# CLI.PY REFACTORING PLAN

## Objective
Reduce complexity of cli.py (currently 4113 lines) by extracting web-search and news-search functionality into separate modules.

## Current Structure
```
scout_it/
├── cli.py (4113 lines) - Contains everything
├── web-search/ (empty folder created)
└── news-search/ (empty folder created)
```

## Target Structure
```
scout_it/
├── cli.py (reduced - only CLI parsing and command routing)
├── web-search/
│   ├── __init__.py
│   └── web_search.py (web_search function + helpers)
└── news-search/
    ├── __init__.py
    ├── news_search.py (news_search function)
    └── helpers.py (_extract_news_content, _extract_meta_description)
```

## Files to Create

### 1. scout_it/web-search/web_search.py ✅ DONE
- Extracted web_search() function (lines 281-786 from cli.py)
- Imports from parent package (..extraction, ..cleaner, etc.)
- All helper functions inline

### 2. scout_it/news-search/news_search.py 🔄 IN PROGRESS
- Extract news_search() function (lines 909-1500 from cli.py)
- Import _extract_news_content from .helpers
- Import _extract_meta_description from .helpers

### 3. scout_it/news-search/helpers.py 🔄 IN PROGRESS
- Extract _extract_news_content() (lines 1806-2100 from cli.py)
- Extract _extract_meta_description() (lines 2418-2435 from cli.py)
- Extract _ERROR_PAGE_PHRASES constant

### 4. Update scout_it/cli.py ⏳ PENDING
- Import from scout_it.web-search import web_search
- Import from scout_it.news-search import news_search
- Remove old function definitions
- Keep CLI argument parsing and command routing

## Implementation Steps

1. ✅ Create scout_it/web-search/__init__.py
2. ✅ Create scout_it/web-search/web_search.py with full implementation
3. ⏳ Create scout_it/news-search/__init__.py
4. ⏳ Create scout_it/news-search/helpers.py
5. ⏳ Create scout_it/news-search/news_search.py
6. ⏳ Update cli.py to import and use new modules
7. ⏳ Test all commands to ensure no breakage
8. ⏳ Commit changes

## Testing Checklist
- [ ] scout-it web-search -q "test" (basic)
- [ ] scout-it web-search -q "test" --category ai (with RSS)
- [ ] scout-it web-search -q "test" --sources wikimedia
- [ ] scout-it web-search -q "test" --snippets
- [ ] scout-it news-search -q "test" (basic)
- [ ] scout-it news-search -q "test" --category ai
- [ ] scout-it news-search -q "test" --sources google-news
- [ ] scout-it news-search -q "test" --snippets

## Notes
- All imports from cli.py modules use relative imports (from ..module)
- Folder names with hyphens (web-search, news-search) require special import syntax
- No breaking changes to API or command-line interface
- Only code organization changes
