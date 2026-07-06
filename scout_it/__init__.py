"""
scout-it: Enterprise-grade DuckDuckGo search toolkit with content extraction, cleaning, and structured JSON output.

Version: 1.0.0
Author: Ashok-gakr
License: MIT

Quick Start:
    from scout_it import web_search, image_search, news_search, video_search

    # Web search with content extraction
    results, stats = web_search("python automation", max_results=10)

    # Image search
    images, stats = image_search("sunset landscapes", max_results=20)

    # News search
    news, stats = news_search("technology news", max_results=10)

    # Video search
    videos, stats = video_search("python tutorial", max_results=10)
"""

from .cleaner import advanced_clean_text, process_results
from .extraction import (
    DDGS,
    EnterpriseResult,
    EnterpriseSearchEngine,
    ExtractionEngine,
    ImageSearchEngine,
    ImageSearchResult,
    fetch_resilient,
)
from .cli import (
    fetch_url,
    image_search,
    multi_search,
    news_search,
    video_extract,
    video_search,
    web_search,
)
from .engines import list_engines, multi_engine_search
from .github_extract import (
    github_commit,
    github_commits,
    github_discussions,
    github_file_content,
    github_folder,
    github_issue,
    github_issues,
    github_prs,
    github_pull_request,
    github_rate_limit,
    github_repo,
    github_search_code,
    github_search_repos,
)
from .social import discord_channel_messages, reddit_search, telegram_channel, telegram_search
from .config import (
    clear_all_credentials,
    clear_credential,
    credential_status,
    run_config_wizard,
)
from .output import render_markdown, resolve_output_path, write_json_output

__version__ = "1.4.0"
__author__ = "Ashok-gakr"
__license__ = "MIT"

__all__ = [
    "EnterpriseSearchEngine",
    "EnterpriseResult",
    "ExtractionEngine",
    "ImageSearchEngine",
    "ImageSearchResult",
    "DDGS",
    "process_results",
    "advanced_clean_text",
    "fetch_resilient",
    "web_search",
    "image_search",
    "news_search",
    "video_search",
    "video_extract",
    "fetch_url",
    "multi_search",
    "list_engines",
    "multi_engine_search",
    "github_repo",
    "github_commits",
    "github_commit",
    "github_pull_request",
    "github_prs",
    "github_issues",
    "github_issue",
    "github_file_content",
    "github_folder",
    "github_search_code",
    "github_search_repos",
    "github_discussions",
    "github_rate_limit",
    "telegram_channel",
    "telegram_search",
    "discord_channel_messages",
    "reddit_search",
    "credential_status",
    "run_config_wizard",
    "clear_credential",
    "clear_all_credentials",
    "render_markdown",
    "resolve_output_path",
    "write_json_output",
]
