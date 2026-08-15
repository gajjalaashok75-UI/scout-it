# Documentation

This folder contains comprehensive documentation for the scout-it package.

The authoritative command/flag reference is the CLI itself — run `scout-it <command> --help` for any command. The files below mirror that truth.

## Files

### INSTALL.md
Complete installation guide: local development setup, installation methods (pip, GitHub, PyPI), CLI usage examples, programmatic API usage, and testing instructions.

### search/ (Directory)
Detailed reference for each CLI search command:
- [websearch.md](search/websearch.md) - web-search & news-search (unified extraction pipeline)
- [fetch.md](search/fetch.md) - fetch-url (single-URL extraction + fetch tiers)
- [imagesearch.md](search/imagesearch.md) - image-search (dimension/color/license/RSS filters)
- [newssearch.md](search/newssearch.md) - news-search quick reference (full flags in websearch.md)
- [videosearch.md](search/videosearch.md) - video-search & video-extract
- [wikipedia.md](search/wikipedia.md) - wikipedia-search, sources, index, semantic-search

### Feature guides
- [NETWORK_RESILIENCE_FEATURE.md](NETWORK_RESILIENCE_FEATURE.md) - Multi-tier fetch chain, DoH, proxy pool, strategy cache
- [PRODUCTION_HARDENING_GUIDE.md](PRODUCTION_HARDENING_GUIDE.md) - Browser pool, staged ranking, quality escalation, domain learning
- [RSS_INTEGRATION_GUIDE.md](RSS_INTEGRATION_GUIDE.md) - RSS feed integration (categories, sources, locations)
- [RSS_FEEDS_EXPANSION.md](RSS_FEEDS_EXPANSION.md) - Expanded RSS feed inventory
- [STAGED_RANKING_IMPLEMENTATION.md](STAGED_RANKING_IMPLEMENTATION.md) - Discovery-first ranking design
- [QUICK_START_STAGED_RANKING.md](QUICK_START_STAGED_RANKING.md) - Quick start for staged ranking
- [QUICK_REFERENCE_CORRECTED_FLOW.md](QUICK_REFERENCE_CORRECTED_FLOW.md) - Corrected pipeline flow reference
- [QUICK_REFERENCE_ENHANCEMENTS.md](QUICK_REFERENCE_ENHANCEMENTS.md) - Enhancements quick reference
- [WEB_SEARCH_ARCHITECTURE_UPGRADE.md](WEB_SEARCH_ARCHITECTURE_UPGRADE.md) - Web search architecture upgrade

### Publication / conversion history
- [PACKAGE_CONVERSION_SUMMARY.md](PACKAGE_CONVERSION_SUMMARY.md) - Technical summary of the package conversion
- [PACKAGE_READY_FOR_PUBLICATION.md](PACKAGE_READY_FOR_PUBLICATION.md) - Publication checklist

---

**Note:** For quick start, see [INSTALL.md](INSTALL.md). The top-level [README.md](../README.md) has the full CLI reference across all 30 subcommands.
