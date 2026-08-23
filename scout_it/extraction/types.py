"""Data types for extraction module."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class EnterpriseResult:
    """Enterprise-grade result with full content extraction"""

    position: int
    title: str
    url: str
    snippet: str
    source: str = "DuckDuckGo"

    # Content extraction
    main_content: str = ""
    content_word_count: int = 0
    extraction_method: str = "pending"
    confidence_score: float = 0.0
    extraction_status: str = "pending"

    # Metadata
    publish_date: Optional[str] = None
    author: Optional[str] = None
    cleaned_html: Optional[str] = None

    # Error tracking
    errors: List[str] = field(default_factory=list)
    final_url: str = ""

    # Performance metrics
    fetch_time: float = 0.0
    content_quality_score: float = 0.0

    # API-source passthrough: the FULL content + metadata provided by an
    # ``--source`` API search provider (tavily/exa/firecrawl/linkup/langsearch/
    # serper). Preserved untruncated through ranking → extraction → cleaning
    # so the complete provider JSON is available in the final output, alongside
    # the extracted ``main_content`` (which comes from re-fetching the URL).
    api_content: str = ""
    api_metadata: dict = field(default_factory=dict)
    api_authority_score: float = 0.0
    api_timestamp: str = ""


@dataclass
class ImageSearchResult:
    """Image search result from DuckDuckGo"""

    position: int
    title: str
    image_url: str
    source_url: str
    thumbnail_url: str = ""
    width: int = 0
    height: int = 0
    image_size: str = ""
    source: str = "DuckDuckGo"
    fetch_time: float = 0.0
    errors: List[str] = field(default_factory=list)
