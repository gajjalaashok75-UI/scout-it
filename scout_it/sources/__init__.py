"""Source plugin system — unified search across academic, dataset, and knowledge sources.

Phase 2 of scout-it's semantic search evolution. Every source plugin emits the
same ``SearchResult`` schema, making them interchangeable in the semantic
pipeline (BM25F → vector → RRF → cross-encoder → facets).

Quick start::

    from scout_it.sources import source_search

    # Search across all enabled sources, gather all results, then semantic-rank.
    results = source_search("transformer attention mechanism",
                             sources=["openalex", "arxiv", "semantic_scholar"])

Each source plugin lives in its own module and registers itself via the
``SourcePlugin`` base class. Sources with free APIs need no key; sources with
API keys read them from the scout-it config (``scout-it config``).

Available sources (all free or free-tier):
    Academic:      openalex, semantic_scholar, arxiv, crossref, unpaywall, core, europe_pmc
    Datasets:      huggingface, zenodo, data_gov
    Knowledge:     wikidata
    Books:         open_library, gutenberg
    Events:        gdelt
    Media:         internet_archive
    Podcasts:      listennotes
    Geo:           openstreetmap
"""

from .base import SourcePlugin, SourceConfig, make_result
from .base import SearchResult  # type: SearchResult is a type alias for Dict
from .registry import (
    get_plugin,
    list_plugins,
    list_available,
    search_source,
    search_all,
    source_search,
)
from .source_config import (
    SOURCE_CREDENTIALS,
    get_source_config,
    set_source_config,
    enable_source,
    disable_source,
    is_source_enabled,
    load_sources_config,
)
from .orchestrator import augment_search_with_sources, merge_and_rank
from .source_bandit import (
    classify_query,
    choose_sources,
    record_source_outcome,
    record_source_outcomes,
    get_source_stats,
    reset_bandit,
)

__all__ = [
    "SearchResult",
    "SourcePlugin",
    "SourceConfig",
    "get_plugin",
    "list_plugins",
    "list_available",
    "search_source",
    "search_all",
    "source_search",
    "SOURCE_CREDENTIALS",
    "get_source_config",
    "set_source_config",
    "enable_source",
    "disable_source",
    "is_source_enabled",
    "load_sources_config",
    "augment_search_with_sources",
    "merge_and_rank",
    "classify_query",
    "choose_sources",
    "record_source_outcome",
    "record_source_outcomes",
    "get_source_stats",
    "reset_bandit",
]
