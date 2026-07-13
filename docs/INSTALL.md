# Installation and Build Instructions

## For Development

1. **Clone the repository:**
```bash
git clone https://github.com/gajjalaashok75-UI/scout-it.git
cd scout-it
```

2. **Create virtual environment:**
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. **Install in development mode:**
```bash
pip install -e ".[dev]"
```

4. **Run tests:**
```bash
pytest tests/ -v
```

## For Installation (End Users)

### From PyPI (Once published):
```bash
pip install scout-it
```

### From GitHub:
```bash
pip install git+https://github.com/gajjalaashok75-UI/scout-it.git
```

### From local source:
```bash
pip install .
```

## Build Distribution Packages

```bash
# Install build tools
pip install build twine

# Build distributions
python -m build

# Check the build
twine check dist/*

# Upload to PyPI (requires credentials)
twine upload dist/*
```

## Project Structure

```
scout-it/
├── scout_it/              # Main package
│   ├── __init__.py        # Package initialization
│   ├── extraction.py      # Web/image search & extraction
│   ├── cleaner.py         # Content cleaning & structuring
│   └── cli.py             # Command-line interface
├── tests/                 # Test suite
│   ├── __init__.py
│   └── test_cli.py
├── pyproject.toml         # Modern Python packaging
├── setup.py               # Legacy setup for compatibility
├── MANIFEST.in            # Package data
├── LICENSE                # MIT License
└── README.md              # Documentation
```

## CLI Commands

After installation, use:

```bash
# Check version
scout-it --version          # Shows scout-it 1.5.0
scout-it -v                 # Short flag

# Search commands
scout-it web-search --query "your query" --max 10
scout-it image-search --query "your query" --max 20
scout-it news-search --query "your query" --max 10
scout-it video-search --query "your query" --max 10
scout-it fetch-url --url "https://example.com"

# Utility commands
scout-it list-engines       # List available search engines and their status
scout-it config             # View or modify scout-it configuration
scout-it stats              # Show usage statistics
scout-it doctor             # Run diagnostics to verify your setup
```

## Programmatic Usage

```python
from scout_it import EnterpriseSearchEngine, ImageSearchEngine

# Web search
engine = EnterpriseSearchEngine(max_workers=8)
results = engine.execute_search("python automation", max_results=10)

# Image search  
img_engine = ImageSearchEngine()
images = img_engine.execute_image_search("sunset", max_results=20)
```

## Dependencies

- Python >= 3.8
- duckduckgo-search >= 3.9.0
- requests >= 2.28.0
- beautifulsoup4 >= 4.11.0
- trafilatura >= 1.6.0
- justext >= 3.0.0
- boilerpy3 >= 1.0.0
- rich >= 13.0.0
- urllib3 >= 1.26.0

Development dependencies:
- pytest >= 7.0.0
- black >= 22.0.0
- flake8 >= 5.0.0
