# 🤖 AGENTS.md - Instructions for AI Coding Agents

**Project:** data-scout v1.0.0  
**Author:** Ashok-gakr  
**Date:** June 12, 2026  
**Status:** Production Ready

This file is a guide for AI coding agents (GitHub Copilot, Cursor, Claude, etc.) on how to work with this project. Read this before making any changes.

---

## 📌 TABLE OF CONTENTS

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Setup Commands](#setup-commands)
4. [Build Commands](#build-commands)
5. [Test Commands](#test-commands)
6. [Coding Standards](#coding-standards)
7. [Security Rules](#security-rules)
8. [Repository Structure](#repository-structure)
9. [Agent Behavior Rules](#agent-behavior-rules)
10. [Commit Guidelines](#commit-guidelines)

---

## Project Overview

**data-scout** is a production-ready Python package for AI-powered web search, image search, and content extraction.

### What it does:
- Searches the web via DuckDuckGo and Google APIs
- Extracts article content using 5-layer fallback strategy
- Cleans and structures extracted content
- Scores confidence levels for results
- Provides CLI and Python API

### Key Features:
- ✅ Multi-source search (web, images, news, video)
- ✅ Parallel extraction with ThreadPoolExecutor
- ✅ 5-layer content extraction fallback
- ✅ Confidence scoring algorithm
- ✅ Sentiment analysis and quality metrics
- ✅ Full CLI with JSON output
- ✅ Comprehensive error handling

### Package Info:
- **Version:** 1.0.0
- **License:** MIT
- **Python:** >=3.8
- **Status:** Ready for PyPI publishing

---

## Architecture

### System Design

```
CLI Layer (gakr_ddgs/cli.py)
    ↓
    ├─→ EnterpriseSearchEngine (web/news search)
    ├─→ ImageSearchEngine (image search)
    └─→ ExtractionEngine (content extraction)
        ↓
        └─→ Content Cleaner (text processing)
            ↓
            Output (JSON/structured results)
```

### Core Agents

| Agent | File | Purpose |
|-------|------|---------|
| **EnterpriseSearchEngine** | extraction.py | Web search + content extraction |
| **ImageSearchEngine** | extraction.py | Image search with filtering |
| **ExtractionEngine** | extraction.py | Multi-strategy content extraction |
| **ContentCleaner** | cleaner.py | Text cleaning & structuring |
| **CLI** | cli.py | Command-line interface |

### 5-Layer Extraction Fallback

```
1. Trafilatura (confidence: 1.0) - Best for news/articles
2. Justext (confidence: 0.95)    - Good for general content
3. BoilerPy3 (confidence: 0.90)  - Robust fallback
4. Readability (confidence: 0.85) - Alternative extractor
5. BeautifulSoup (confidence: 0.70) - Ultimate HTML fallback
```

### File Organization

```
data-scout/
├── gakr_ddgs/
│   ├── __init__.py          (Public API exports)
│   ├── extraction.py        (Search & extraction engines)
│   ├── cleaner.py           (Content cleaning)
│   └── cli.py               (Command-line interface)
├── tests/
│   ├── __init__.py
│   └── test_cli.py          (38 comprehensive tests)
├── docs/                    (User documentation - DO NOT EDIT)
├── references/              (Legacy code - DO NOT EDIT)
├── pyproject.toml           (PEP 517/518 build config)
├── setup.py                 (Legacy Python setup)
├── README.md                (Main documentation)
├── AGENTS.md                (This file - for AI agents)
└── LICENSE                  (MIT License)

---

## Setup Commands

### 1. Clone Repository
```bash
git clone https://github.com/Ashok-gakr/data-scout.git
cd data-scout
```

### 2. Create Virtual Environment
```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n data-scout python=3.11
conda activate data-scout
```

### 3. Install Package in Development Mode
```bash
pip install -e ".[dev]"
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Verify Installation
```bash
# Check CLI
data-scout --help

# Run tests
pytest tests/ -v
```

---

## Build Commands

### Build Distribution Packages
```bash
# Install build tools
pip install build twine

# Build wheel and source distributions
python -m build

# Output:
# dist/gakr_ddgs-1.0.0-py3-none-any.whl (29.2 KB)
# dist/gakr_ddgs-1.0.0.tar.gz (42.3 KB)
```

### Verify Build
```bash
# Check with twine
twine check dist/*

# Expected: ✅ PASSED
```

### Local Installation Test
```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate

# Install from wheel
pip install dist/gakr_ddgs-1.0.0-py3-none-any.whl

# Test CLI
data-scout web-search --query "test" --max-results 2
```

---

## Test Commands

### Run All Tests
```bash
pytest tests/ -v --tb=short
```

### Run Specific Test File
```bash
pytest tests/test_cli.py -v
```

### Run Tests with Coverage
```bash
pytest tests/ --cov=gakr_ddgs --cov-report=html
```

### Run Tests with Markers
```bash
# Fast tests only
pytest tests/ -v -m "not slow"

# CLI tests
pytest tests/test_cli.py::test_web_search -v
```

### Coverage Requirements
- **Minimum:** 80% coverage
- **Current:** 38+ test cases covering all search types
- **Target:** Maintain or exceed 80%

### Test Locations
- Unit tests: `tests/test_cli.py`
- Test data: Mocked API responses
- Fixtures: pytest fixtures for search results

---

## Coding Standards

### Python Version
- **Minimum:** Python 3.8
- **Tested:** Python 3.11.9
- **Target:** Use f-strings, type hints, and modern Python patterns

### Code Style

**Use these tools:**
```bash
# Format with black
black gakr_ddgs/ tests/ --line-length=100

# Sort imports with isort
isort gakr_ddgs/ tests/ --profile black

# Lint with flake8
flake8 gakr_ddgs/ tests/ --max-line-length=100

# Type check with mypy
mypy gakr_ddgs/ --strict
```

**Standards:**
- ✅ Black formatter (line length: 100)
- ✅ isort for import sorting (black profile)
- ✅ Type hints on all functions
- ✅ Docstrings for all classes/functions
- ✅ No magic numbers - use constants
- ✅ PEP 8 compliance

### Naming Conventions
```python
# Classes: PascalCase
class EnterpriseSearchEngine:
    pass

# Functions: snake_case
def extract_content(url):
    pass

# Constants: UPPER_SNAKE_CASE
MAX_WORKERS = 4
TIMEOUT_SECONDS = 5

# Private: _leading_underscore
def _internal_helper():
    pass
```

### File Organization
- **Max lines per file:** 800 (target: 200-400)
- **Max lines per function:** 50
- **Max nesting:** 4 levels
- **One class per file:** For large classes

### Import Order
```python
# 1. Standard library
import json
import logging
from dataclasses import dataclass
from typing import Dict, List

# 2. Third-party
import requests
from bs4 import BeautifulSoup

# 3. Local imports
from .extraction import EnterpriseSearchEngine
from .cleaner import process_results
```

### Error Handling
```python
# ✅ DO: Handle errors explicitly
try:
    content = extract(url)
except TimeoutError:
    logging.error(f"Timeout extracting {url}")
    content = ""

# ❌ DON'T: Silently swallow exceptions
try:
    content = extract(url)
except:
    pass
```

### Type Hints
```python
# ✅ DO: Use type hints
def search(query: str, max_results: int = 10) -> List[EnterpriseResult]:
    pass

# ❌ DON'T: Skip type hints
def search(query, max_results=10):
    pass
```

---

## Security Rules

### ✅ MUST DO

- [ ] **No hardcoded secrets** - Use environment variables or config files
- [ ] **Validate all inputs** - Check user input before processing
- [ ] **Sanitize output** - Clean data before displaying
- [ ] **Log safely** - Never log sensitive data
- [ ] **Use timeouts** - Prevent hanging requests (default: 5 seconds)
- [ ] **Handle errors gracefully** - Don't leak stack traces to users

### ❌ NEVER DO

- ❌ Hardcode API keys, tokens, or passwords
- ❌ Log user credentials or sensitive data
- ❌ Disable SSL/TLS verification
- ❌ Execute user-supplied commands directly
- ❌ Store passwords in plain text
- ❌ Use unsafe deserialization (pickle, eval)

### Security Checklist for PRs

Before committing:
```bash
# Check for secrets
grep -r "password\|api_key\|token" gakr_ddgs/ | grep -v ".pyc"

# Check for hardcoded URLs (should use config)
grep -r "http://" gakr_ddgs/ | grep -v "test\|example"

# Check for dangerous functions
grep -r "eval\|exec\|pickle" gakr_ddgs/ | grep -v "test"
```

### Environment Variables

**Required for production:**
```bash
# Optional: Custom User-Agent
export USER_AGENT="YourBot/1.0"

# Optional: Request timeout
export REQUEST_TIMEOUT="10"

# Optional: Max workers for threading
export MAX_WORKERS="8"
```

---

## Repository Structure

### DO NOT MODIFY:
- ❌ `dist/` - Build artifacts (regenerated each build)
- ❌ `__pycache__/` - Python cache (regenerated)
- ❌ `.mypy_cache/` - Type checker cache (regenerated)
- ❌ `gakr_ddgs.egg-info/` - Package metadata (regenerated)
- ❌ `docs/` - User documentation (contact maintainer to update)
- ❌ `references/` - Legacy code archive (historical reference only)
- ❌ `LICENSE` - MIT license (do not modify)
- ❌ `setup.py` - Only update if changing dependencies

### CAN MODIFY:
- ✅ `gakr_ddgs/` - Source code (main development area)
- ✅ `tests/` - Test suite (add tests for new features)
- ✅ `README.md` - Main documentation (user-facing docs)
- ✅ `AGENTS.md` - This file (agent instructions)
- ✅ `pyproject.toml` - Build config (if adding dependencies)
- ✅ `.gitignore` - Git rules (if needed)

### Package Layout

```
gakr_ddgs/                          # Main package
├── __init__.py                     # Public API
├── extraction.py                   # Search engines (570+ lines)
├── cleaner.py                      # Content cleaning (350+ lines)
└── cli.py                          # Command-line interface (850+ lines)

tests/                              # Test suite
├── __init__.py
└── test_cli.py                     # 38 test cases

docs/                               # Documentation (read-only)
├── README.md
├── INSTALL.md
├── PACKAGE_CONVERSION_SUMMARY.md
└── PACKAGE_READY_FOR_PUBLICATION.md

references/                         # Legacy code (read-only)
├── quick_scrape.py
├── main_content_cleaner.py
├── search.py
├── test_search.py
└── [helper scripts]
```

---

## Agent Behavior Rules

### 1. Before Making Changes

- [ ] **Read this file first** - Understand project structure
- [ ] **Check .gitignore** - Don't modify ignored files
- [ ] **Review existing code** - Understand patterns before writing new code
- [ ] **Run tests** - Ensure nothing is broken

### 2. When Implementing Features

```bash
# 1. Create branch
git checkout -b feature/my-feature

# 2. Implement with tests
# - Write test first (TDD)
# - Implement feature
# - Run tests: pytest tests/ -v

# 3. Format code
black gakr_ddgs/ && isort gakr_ddgs/

# 4. Type check
mypy gakr_ddgs/ --strict

# 5. Lint
flake8 gakr_ddgs/

# 6. Commit
git add .
git commit -m "feat: description"
```

### 3. Import Handling

**Always use relative imports within package:**
```python
# ✅ Correct (within gakr_ddgs/)
from .extraction import EnterpriseSearchEngine
from .cleaner import process_results

# ❌ Wrong
from gakr_ddgs.extraction import EnterpriseSearchEngine
```

### 4. Dependency Management

- **No new dependencies without discussion** - Keep package lightweight
- **Update requirements.txt** - If adding any dependency
- **Update pyproject.toml** - For new dev dependencies
- **Pin versions** - For reproducibility

### 5. Testing Requirements

- **Minimum 80% coverage** - Required for PRs
- **Test new features** - Add tests for every new function
- **Mock external APIs** - Don't make real API calls in tests
- **Use pytest** - Standard test framework

### 6. Documentation

- **Update docstrings** - For all new functions/classes
- **Add type hints** - Always include return types
- **Document parameters** - Use Google-style docstrings
- **Update README** - If changing user-facing functionality

### 7. Commit Messages

**Use Conventional Commits:**
```
feat: Add new feature description
fix: Fix bug description
refactor: Refactor code description
test: Add test cases
docs: Update documentation
chore: Update dependencies

# Examples:
feat: Add video search support
fix: Handle timeout in extraction
refactor: Simplify extraction fallback logic
test: Add image search tests
```

### 8. Python Best Practices

- ✅ Use type hints
- ✅ Use dataclasses for data structures
- ✅ Handle exceptions explicitly
- ✅ Use f-strings for formatting
- ✅ Use pathlib for file paths
- ✅ Use logging instead of print
- ✅ Validate inputs early
- ✅ Use context managers (with statements)

### 9. Performance Considerations

- **Timeout:** Default 5 seconds per URL (configurable)
- **Parallelism:** ThreadPoolExecutor with CPU count × 2 workers
- **Memory:** Stream large result sets, don't load all at once
- **Caching:** Consider memoization for repeated queries

### 10. What NOT to Do

- ❌ Never modify `dist/` or cache directories
- ❌ Never commit dependencies directly (use requirements.txt)
- ❌ Never hardcode configuration values
- ❌ Never leave debug print statements
- ❌ Never skip type checking or linting
- ❌ Never make breaking API changes without discussion
- ❌ Never leave TODO comments without explanation
- ❌ Never commit credentials or secrets

---

## Commit Guidelines

### Branch Naming
```
feature/my-new-feature          # New features
fix/bug-description             # Bug fixes
refactor/module-name            # Refactoring
test/test-description           # Test additions
docs/documentation-update       # Documentation
chore/dependency-update         # Dependency updates
```

### Commit Format
```
<type>: <description>

<optional body>
<optional footer>

# Types: feat, fix, refactor, test, docs, chore, perf
# Example:
feat: Add support for custom extraction timeout

- Add extraction_timeout parameter to EnterpriseSearchEngine
- Update CLI to accept --timeout flag
- Add tests for timeout configuration
- Update README with timeout documentation

Closes #123
```

### Pre-Commit Checklist
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Code formatted: `black gakr_ddgs/`
- [ ] Imports sorted: `isort gakr_ddgs/`
- [ ] Linting passes: `flake8 gakr_ddgs/`
- [ ] Type checking passes: `mypy gakr_ddgs/`
- [ ] No hardcoded secrets
- [ ] Docstrings added/updated
- [ ] Commit message follows convention

### Push to GitHub
```bash
git push origin feature/my-feature
# Create PR on GitHub
# Wait for CI/CD to pass
# Request review
```

---

## Quick Reference

### Essential Commands
| Task | Command |
|------|---------|
| Install development | `pip install -e ".[dev]"` |
| Run tests | `pytest tests/ -v` |
| Format code | `black gakr_ddgs/` |
| Sort imports | `isort gakr_ddgs/` |
| Lint | `flake8 gakr_ddgs/` |
| Type check | `mypy gakr_ddgs/` |
| Build package | `python -m build` |
| CLI help | `data-scout --help` |
| Web search | `data-scout web-search --query "test"` |

### File Purposes
| File | Purpose | Modify? |
|------|---------|---------|
| `gakr_ddgs/__init__.py` | Public API | ✅ Yes |
| `gakr_ddgs/extraction.py` | Search engines | ✅ Yes |
| `gakr_ddgs/cleaner.py` | Content cleaning | ✅ Yes |
| `gakr_ddgs/cli.py` | CLI interface | ✅ Yes |
| `tests/test_cli.py` | Test suite | ✅ Yes |
| `pyproject.toml` | Build config | ✅ (Carefully) |
| `setup.py` | Legacy setup | ✅ (Only if needed) |
| `README.md` | Main docs | ✅ Yes |
| `docs/*` | User docs | ❌ No (contact maintainer) |
| `references/*` | Legacy code | ❌ No (historical archive) |
| `.gitignore` | Git rules | ✅ (If needed) |

---

## Status

- ✅ **Production Ready** - Version 1.0.0
- ✅ **All tests passing** - 38+ test cases
- ✅ **Ready for PyPI** - Distribution packages built
- ✅ **Ready for GitHub** - Repository initialized
- ✅ **Agent-friendly** - This AGENTS.md provides all context

---

**Last Updated:** June 12, 2026  
**License:** MIT  
**Author:** Ashok-gakr  

**For detailed usage, see [README.md](./README.md)**  
**For architecture details, see [docs/PACKAGE_CONVERSION_SUMMARY.md](./docs/PACKAGE_CONVERSION_SUMMARY.md)**
