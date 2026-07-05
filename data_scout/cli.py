#!/usr/bin/env python3
"""
Complete search pipeline wrapper.
Runs extraction.py → cleaner.py
Outputs: structured JSON with filtered results

Usage (CLI):
  data-scout web-search --query "today hot news" --max 50 --workers 6 --out results.json
  data-scout image-search --query "sunset" --max 20 --out images.json

This imports `EnterpriseSearchEngine`, `ImageSearchEngine` from `extraction.py` 
and `process_results` from `cleaner.py`
"""
import argparse
import sys

# Ensure Unicode output works on Windows terminals
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass  # Fallback: ignore if not supported
import json
import random
import re
import time
from dataclasses import asdict
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:
    from .cleaner import process_results
    from .extraction import (
        DDGS,
        EnterpriseSearchEngine,
        ExtractionEngine,
        ImageSearchEngine,
        _compact_options,
        _ddgs_list_search,
        _ddgs_list_search_with_retry,
        fetch_resilient,
    )
    from . import github_extract as gh
    from . import engines as search_engines
    from . import social
    from . import config as ds_config
except Exception as e:
    raise ImportError("Could not import from data_scout modules: " + str(e))


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _write_output(out_path: Path, data: Any) -> None:
    """Write *data* as clean, valid, standard JSON to *out_path*.

    Previous versions tried to "pretty print" long strings (diff patches,
    commit messages, article bodies) by word-wrapping them and then
    blindly replacing every escaped ``\\n`` in the whole serialized JSON
    with a raw newline character. That corrupted the file two ways: (1)
    word-wrapping collapsed real embedded newlines (e.g. every line of a
    diff patch) into single spaces before re-wrapping at an arbitrary
    character width, destroying the original line structure; (2) the
    blind replace injected raw, unescaped control characters into JSON
    string literals, which is invalid per the JSON spec (RFC 8259) and
    broke ``json.load`` downstream with "Invalid control character"
    errors. Multi-line text is still fully preserved and human-readable
    here — ``json.dumps`` properly escapes real newlines as the standard
    ``\\n`` sequence, which every JSON parser/viewer renders as a line
    break; this file just no longer *lies* about being valid JSON.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    out_path.write_text(json_str, encoding="utf-8")


def web_search(
    query: str,
    max_results: int = 100,
    workers: int = 8,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: Optional[str] = None,
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    backend: str = 'auto',
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
):
    """
    Execute web search pipeline: search → extract → clean → filter.
    
    Args:
        query: Search query string
        max_results: Max results to fetch
        workers: Parallel workers
        max_fetch_retries: Retry attempts per fetch tier (requests, then
            Playwright) when fetching each result page.
        enable_js_fallback: Whether to automatically fall back to Playwright
            when a plain requests fetch fails or looks blocked.
    
    Returns:
        (structured_results, stats) tuple with cleaned and structured content
    """
    # Phase 1: Search and extract
    engine = EnterpriseSearchEngine(
        max_workers=workers,
        max_fetch_retries=max_fetch_retries,
        enable_js_fallback=enable_js_fallback,
    )
    search_options = _compact_options({
        'region': region,
        'safesearch': safesearch,
        'timelimit': timelimit,
        'backend': backend,
    })

    raw_results = engine.execute_search(
        query,
        max_results,
        search_options=search_options,
        retry_on_zero_success=retry_on_zero_success,
        max_zero_success_retries=retry_attempts,
        retry_backoff_seconds=retry_backoff,
    )
    
    # Convert dataclass results to plain dicts
    results_dicts = [asdict(r) for r in raw_results]
    
    # Phase 2: Clean and filter by extraction_status == "success"
    structured_results, cleaner_stats = process_results(results_dicts)
    
    # Combine stats
    combined_stats = {
        'search_engine': engine.stats,
        'cleaner': cleaner_stats
    }
    return structured_results, combined_stats


def multi_search(
    query: str,
    engines: Optional[List[str]] = None,
    max_results: int = 10,
    workers: int = 8,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
    dedupe: bool = True,
    **engine_kwargs,
):
    """Query multiple search engines in parallel, merge/dedupe the results,
    then run them through the same content-extraction + cleaning pipeline as
    ``web_search``.

    See ``data_scout.engines`` for what each engine needs (DuckDuckGo works
    out of the box; Brave/Bing/Google/SerpAPI each need an API key set as an
    environment variable). Unconfigured engines are skipped, not errored —
    check the returned ``stats['discovery']['skipped']`` list to see why.
    """
    engines = engines or ['duckduckgo']

    discovery = search_engines.multi_engine_search(
        query, engines=engines, max_results=max_results, max_workers=min(workers, 5), **engine_kwargs
    )

    if not discovery['merged_results']:
        return [], {
            'discovery': discovery['stats'],
            'search_engine': {'total': 0, 'success': 0, 'execution_time': discovery['stats']['execution_time']},
            'cleaner': {'total_input': 0, 'successful': 0, 'failed': 0, 'processed': 0},
        }

    engine = EnterpriseSearchEngine(
        max_workers=workers,
        max_fetch_retries=max_fetch_retries,
        enable_js_fallback=enable_js_fallback,
    )
    raw_results = engine.execute_search_from_urls(discovery['merged_results'][:max_results])

    results_dicts = [asdict(r) for r in raw_results]
    structured_results, cleaner_stats = process_results(results_dicts)

    combined_stats = {
        'discovery': discovery['stats'],
        'search_engine': engine.stats,
        'cleaner': cleaner_stats,
    }
    return structured_results, combined_stats


def image_search(
    query: str,
    max_results: int = 50,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    type_image: Optional[str] = None,
    layout: Optional[str] = None,
    license_image: Optional[str] = None,
    min_width: Optional[int] = None,
    max_width: Optional[int] = None,
    min_height: Optional[int] = None,
    max_height: Optional[int] = None,
): 
    """
    Execute image search pipeline: search → extract metadata.

    Args:
        query: Search query string
        max_results: Max images to fetch

    Returns:
        (image_results, stats) tuple with image metadata
    """
    engine = ImageSearchEngine()
    image_options = _compact_options({
        'region': region,
        'safesearch': safesearch,
        'timelimit': timelimit,
        'size': size,
        'color': color,
        'type_image': type_image,
        'layout': layout,
        'license_image': license_image,
    })

    raw_results = engine.execute_image_search(
        query,
        max_results,
        search_options=image_options,
        retry_on_zero_success=retry_on_zero_success,
        max_zero_success_retries=retry_attempts,
        retry_backoff_seconds=retry_backoff,
        min_width=min_width,
        max_width=max_width,
        min_height=min_height,
        max_height=max_height,
    ) 
    
    # Convert to dicts for JSON serialization
    results_dicts = [asdict(r) for r in raw_results]
    
    stats = {
        'search_engine': engine.stats
    }
    
    print(f"📈 Found {len(raw_results)} images for query: {query}")
    return results_dicts, stats


def news_search(
    query: str,
    max_results: int = 50,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    workers: int = 3,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
):
    """DuckDuckGo news search with full content extraction and cleaning.

    Returns structured results matching the web-search output format:
    each result goes through ``ExtractionEngine`` → ``process_results()``
    to produce cleaned content with quality signals and readability metrics.
    """
    # Phase 1: Get raw DDGS news results (retried on zero results, relaxing
    # filters on each subsequent attempt).
    raw_results, search_stats = _ddgs_list_search_with_retry(
        'news',
        query=query,
        max_results=max_results,
        options={
            'region': region,
            'safesearch': safesearch,
            'timelimit': timelimit,
        },
        retry_on_zero_success=retry_on_zero_success,
        max_zero_success_retries=retry_attempts,
        retry_backoff_seconds=retry_backoff,
    )

    if not raw_results:
        return [], {'search_engine': search_stats, 'cleaner': {'total_input': 0, 'successful': 0, 'failed': 0, 'processed': 0}}

    # Phase 2: Fetch and extract full article content in parallel, using the
    # requests -> Playwright -> basic-fallback resilient fetch chain.
    enriched_results = _extract_news_content(
        raw_results,
        max_workers=workers,
        max_fetch_retries=max_fetch_retries,
        enable_js_fallback=enable_js_fallback,
    )

    # Phase 3: Clean and structure via process_results
    structured_results, cleaner_stats = process_results(enriched_results)

    # Combine stats
    combined_stats = {
        'search_engine': search_stats,
        'cleaner': cleaner_stats,
    }
    return structured_results, combined_stats


def video_search(
    query: str,
    max_results: int = 50,
    region: str = 'us-en',
    safesearch: str = 'moderate',
    timelimit: Optional[str] = None,
    resolution: Optional[str] = None,
    duration: Optional[str] = None,
    license_videos: Optional[str] = None,
    retry_on_zero_success: bool = True,
    retry_attempts: int = 2,
    retry_backoff: float = 1.0,
):
    """DuckDuckGo video search wrapper (retried on zero results)."""
    results, stats = _ddgs_list_search_with_retry(
        'videos',
        query=query,
        max_results=max_results,
        options={
            'region': region,
            'safesearch': safesearch,
            'timelimit': timelimit,
            'resolution': resolution,
            'duration': duration,
            'license_videos': license_videos,
        },
        retry_on_zero_success=retry_on_zero_success,
        max_zero_success_retries=retry_attempts,
        retry_backoff_seconds=retry_backoff,
    )
    return results, {'search_engine': stats}


# ---------------------------------------------------------------------------
# Result enhancement: full descriptions/bodies from source URLs
# ---------------------------------------------------------------------------

def _enhance_video_descriptions(results: List[Dict[str, Any]], max_workers: int = 5) -> List[Dict[str, Any]]:
    """Enhance video results with full descriptions from YouTube.

    DuckDuckGo ``videos()`` returns descriptions truncated at ~200-300
    characters (noticeable by trailing ``...``).  For YouTube videos this
    fetches the full description from the YouTube page and replaces the
    truncated one *in-place*.
    """
    if not results:
        return results
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_one(r):
        url = r.get("content", "") or r.get("url", "")
        match = _YOUTUBE_RE.search(url)
        if not match:
            return r
        try:
            # _fetch_youtube_metadata expects a bare video ID, not the full URL.
            meta = _fetch_youtube_metadata(match.group(1))
            if meta and "error" not in meta and meta.get("description"):
                r["description"] = meta["description"]
        except Exception:
            pass
        return r

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pool.map(_fetch_one, results)
    return results


def _extract_news_content(
    results: List[Dict[str, Any]],
    max_workers: int = 3,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch and extract full article content for news results in parallel.

    Takes raw DDGS news result dicts, fetches each URL through the shared
    ``fetch_resilient`` fallback chain (requests-retries -> Playwright
    JS-render -> last-resort basic request), runs the HTML through
    ``ExtractionEngine``, and returns enriched dicts compatible with
    ``process_results()`` (i.e. containing ``main_content``,
    ``extraction_status``, ``confidence_score``, etc.).
    """
    if not results:
        return results
    from concurrent.futures import ThreadPoolExecutor, as_completed

    shared_engine = ExtractionEngine()

    def _extract_one(r):
        url = r.get("url", "")
        if not url:
            r["extraction_status"] = "failed"
            r["main_content"] = ""
            return r
        try:
            outcome = fetch_resilient(
                url,
                session=shared_engine.session,
                timeout=15,
                max_retries=max_fetch_retries,
                enable_js_fallback=enable_js_fallback,
            )
            if outcome["status"] != "success":
                r["extraction_status"] = "failed"
                r["main_content"] = ""
                r["errors"] = outcome["errors"][-3:]
                return r
            content, method, confidence = shared_engine.extract_content(url, outcome["html"])
            r["main_content"] = content
            r["extraction_method"] = f"{method} ({outcome['tier']})"
            r["confidence_score"] = confidence
            r["extraction_status"] = "success" if content.strip() else "failed"
            r["content_word_count"] = len(content.split())
        except Exception as exc:
            r["extraction_status"] = "failed"
            r["main_content"] = ""
            r["errors"] = [str(exc)]
        return r

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_extract_one, r): idx for idx, r in enumerate(results)}
        enriched = [None] * len(results)
        for future in as_completed(futures):
            idx = futures[future]
            enriched[idx] = future.result()
    return enriched


# ---------------------------------------------------------------------------
# YouTube video extraction (video-extract command)
# ---------------------------------------------------------------------------
_YOUTUBE_RE = re.compile(
    r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|m\.youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})'
)


def _fetch_youtube_metadata(video_id: str, max_fetch_retries: int = 3, enable_js_fallback: bool = True) -> Dict[str, Any]:
    """Fetch video metadata (title, description, channel, etc.) from YouTube page."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        outcome = fetch_resilient(
            url,
            timeout=15,
            max_retries=max_fetch_retries,
            enable_js_fallback=enable_js_fallback,
        )
        if outcome["status"] != "success":
            joined_errors = "; ".join(outcome["errors"][-3:])
            if "404" in joined_errors:
                return {"error": "video_not_found", "error_message": "Video not found or has been removed.", "video_id": video_id}
            return {
                "error": "network_error",
                "error_message": f"Failed to fetch YouTube page after {outcome['attempts']} attempts across all fetch tiers: {joined_errors}",
                "video_id": video_id,
            }
        html = outcome["html"]

        metadata: Dict[str, Any] = {}

        # Try to parse embedded JSON for richer data
        player_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.*?});', html, re.DOTALL)
        player_data = json.loads(player_match.group(1)) if player_match else {}

        # Title — prefer JSON source (more reliable)
        json_title = None
        if player_data:
            try:
                json_title = player_data['videoDetails']['title']
            except (KeyError, TypeError):
                pass
        if json_title:
            metadata['title'] = json_title
        else:
            title_match = re.search(r'<meta\s+name="title"\s+content="([^"]+)"', html)
            if not title_match:
                title_match = re.search(r'<title>([^<]+)</title>', html)
            metadata['title'] = (unescape(title_match.group(1).strip()).replace(' - YouTube', '') if title_match else "")

        # Description — full text from JSON, not truncated meta tag
        json_desc = None
        if player_data:
            try:
                json_desc = player_data['videoDetails']['shortDescription']
            except (KeyError, TypeError):
                pass
        if json_desc:
            metadata['description'] = json_desc
        else:
            desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            metadata['description'] = unescape(desc_match.group(1)) if desc_match else ""

        # Channel name
        json_channel = None
        if player_data:
            try:
                json_channel = player_data['videoDetails']['author']
            except (KeyError, TypeError):
                pass
        if json_channel:
            metadata['channel'] = json_channel
        else:
            channel_match = re.search(r'"ownerChannelName"\s*:\s*"([^"]+)"', html)
            metadata['channel'] = unescape(channel_match.group(1)) if channel_match else ""

        # Channel URL
        ch_url = ""
        if player_data:
            try:
                ch_url = player_data.get('microformat', {}).get('playerMicroformatRenderer', {}).get('ownerProfileUrl', '')
            except (KeyError, TypeError):
                pass
        if not ch_url:
            channel_url_match = re.search(r'"ownerChannelUrl"\s*:\s*"([^"]+)"', html)
            ch_url = channel_url_match.group(1) if channel_url_match else ""
        metadata['channel_url'] = "https://www.youtube.com" + ch_url if ch_url.startswith('/') else ch_url

        # View count
        json_views = None
        if player_data:
            try:
                json_views = player_data['videoDetails']['viewCount']
            except (KeyError, TypeError):
                pass
        if json_views:
            metadata['view_count'] = int(json_views)
        else:
            views_match = re.search(r'"viewCount"\s*:\s*"(\d+)"', html)
            metadata['view_count'] = int(views_match.group(1)) if views_match else 0

        # Duration in seconds
        json_dur = None
        if player_data:
            try:
                json_dur = player_data.get('videoDetails', {}).get('lengthSeconds', None)
            except (KeyError, TypeError):
                pass
        if json_dur is not None:
            metadata['duration_seconds'] = int(json_dur)
        else:
            duration_match = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', html)
            metadata['duration_seconds'] = int(duration_match.group(1)) if duration_match else 0

        # Thumbnail
        metadata['thumbnail_url'] = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

        # Core identifiers
        metadata['url'] = f"https://www.youtube.com/watch?v={video_id}"
        metadata['video_id'] = video_id

        return metadata
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return {"error": "video_not_found", "error_message": "Video not found or has been removed.", "video_id": video_id}
        return {"error": "http_error", "error_message": f"HTTP {exc.response.status_code if exc.response is not None else 'unknown'}: {str(exc)}", "video_id": video_id}
    except requests.exceptions.ConnectionError:
        return {"error": "network_error", "error_message": "Failed to connect to YouTube. Check your internet connection.", "video_id": video_id}
    except requests.exceptions.Timeout:
        return {"error": "timeout", "error_message": "Request to YouTube timed out.", "video_id": video_id}
    except Exception as exc:
        return {"error": "unknown", "error_message": f"Failed to fetch metadata: {str(exc)}", "video_id": video_id}


def _fetch_youtube_subtitles(
    video_id: str,
    language_code: str = "en",
    include_segments: bool = False,
) -> Optional[Dict[str, Any]]:
    """Fetch YouTube subtitles/transcript for a video in a specific language.

    Uses ``youtube-transcript-api`` to list available transcripts, validates
    that *language_code* is available, fetches it, and returns structured
    data.  When the requested language is not available the error dict
    includes an ``available_languages`` list so the caller can show the user
    what *is* available.

    Returns ``None`` for generic/unexpected failures so the caller treats it
    as "subtitles not found (unknown reason)".
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled

        api = YouTubeTranscriptApi()

        # List available transcripts upfront so we can validate the language
        try:
            transcript_list = api.list(video_id)
        except TranscriptsDisabled:
            return {
                "error": "transcripts_disabled",
                "error_message": "Subtitles are disabled for this video.",
                "video_id": video_id,
            }
        except Exception:
            return None

        # Build a list of available languages for error reporting
        available = [
            {
                "code": t.language_code,
                "name": t.language,
                "generated": t.is_generated,
            }
            for t in transcript_list
        ]

        # Try to find the requested language
        try:
            transcript = transcript_list.find_transcript([language_code])
        except NoTranscriptFound:
            return {
                "error": "subtitle_lang_not_available",
                "error_message": (
                    f"Requested subtitle language '{language_code}' is not "
                    f"available for this video."
                ),
                "requested_language": language_code,
                "available_languages": available,
                "video_id": video_id,
            }

        # Fetch the transcript data
        try:
            fetched = transcript.fetch()
        except Exception:
            return None

        if not fetched or not fetched.snippets:
            return None

        segments = []
        for snippet in fetched.snippets:
            segments.append({
                "text": snippet.text,
                "start": snippet.start,
                "duration": snippet.duration,
            })

        full_text = " ".join(s["text"] for s in segments)

        result: Dict[str, Any] = {
            "full_text": full_text,
            "language": fetched.language,
            "language_code": fetched.language_code,
            "is_generated": fetched.is_generated,
        }
        if include_segments:
            result["segments"] = segments
        return result

    except ImportError:
        return {
            "error": "missing_dependency",
            "error_message": (
                "youtube-transcript-api not installed. "
                "Run: pip install youtube-transcript-api"
            ),
        }
    except Exception:
        return None


def video_extract(
    url: str,
    subtitle_lang: str = "en",
    include_segments: bool = False,
    max_fetch_retries: int = 3,
    enable_js_fallback: bool = True,
) -> Dict[str, Any]:
    """Extract full details from a video URL.

    Supports YouTube URLs. Non-YouTube URLs receive a friendly notice.

    :param url: The video URL to extract.
    :param subtitle_lang: Preferred subtitle language code (default ``"en"``).
    :param include_segments: If True, include subtitle segment timestamps in output.
    :param max_fetch_retries: Retry attempts per fetch tier when fetching the
        YouTube page (requests, then Playwright).
    :param enable_js_fallback: Whether to fall back to Playwright if requests fails.
    """
    url = str(url or "").strip()
    if not url:
        return {"error": "invalid_url", "error_message": "No URL provided. Use --url to specify a video URL.", "hint": "Example: data-scout video-extract --url \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\""}

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"error": "invalid_url", "error_message": "Invalid URL. Provide a valid http/https URL."}

    # Check if YouTube URL
    match = _YOUTUBE_RE.search(url)
    if not match:
        return {
            "error": "unsupported_platform",
            "error_message": "Only YouTube is supported at this time. Other video platforms coming soon.",
            "url": url,
            "supported_platforms": ["youtube"],
        }

    video_id = match.group(1)

    # Fetch metadata
    meta = _fetch_youtube_metadata(video_id, max_fetch_retries=max_fetch_retries, enable_js_fallback=enable_js_fallback)
    if "error" in meta:
        return meta  # error dict already has proper error classification

    # Fetch subtitles in the requested language
    subs = _fetch_youtube_subtitles(video_id, language_code=subtitle_lang, include_segments=include_segments)

    if subs and subs.get("error") == "subtitle_lang_not_available":
        avail = subs.get("available_languages", [])
        meta["available_subtitle_languages"] = avail
        meta["requested_subtitle_language"] = subs.get("requested_language")
        subs = None

        if not avail:
            meta["subtitles_error"] = "No subtitles available for this video."
        elif subtitle_lang != "en":
            # Retry with default language
            subs = _fetch_youtube_subtitles(video_id, language_code="en", include_segments=include_segments)
            if subs and "error" in subs:
                meta["subtitles_error"] = (
                    f"Requested subtitle language '{subtitle_lang}' not available. "
                    f"Default 'en' also not available."
                )
                subs = None
            else:
                meta["subtitles_error"] = (
                    f"Requested subtitle language '{subtitle_lang}' not available, "
                    f"falling back to default 'en'."
                )
        else:
            meta["subtitles_error"] = (
                f"Requested subtitle language '{subtitle_lang}' not available "
                f"for this video."
            )
    elif subs and "error" in subs:
        meta["subtitles_error"] = subs["error_message"]
        subs = None

    meta["subtitles"] = subs

    return {
        "url": meta["url"],
        "video_id": video_id,
        "platform": "youtube",
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "channel": meta.get("channel", ""),
        "channel_url": meta.get("channel_url", ""),
        "view_count": meta.get("view_count", 0),
        "duration_seconds": meta.get("duration_seconds", 0),
        "thumbnail_url": meta.get("thumbnail_url", ""),
        "subtitles": meta.get("subtitles"),
        "subtitles_error": meta.get("subtitles_error"),
        "requested_subtitle_language": meta.get("requested_subtitle_language"),
        "available_subtitle_languages": meta.get("available_subtitle_languages"),
    }


# ---------------------------------------------------------------------------


def _extract_html_title(html_text: str) -> str:
    """Extract page title from HTML text."""
    if not html_text:
        return ""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    return unescape(re.sub(r"\s+", " ", title)).strip()


def _parse_size_string(size_str: Optional[str]) -> Optional[int]:
    """Parse size string like '100kb', '1mb' to bytes. Returns None if invalid."""
    if not size_str:
        return None
    
    size_str = size_str.strip().lower()
    
    # Mapping of units to bytes
    units = {
        'b': 1,
        'kb': 1024,
        'mb': 1024 ** 2,
        'gb': 1024 ** 3,
    }
    
    # Try to parse the string
    match = re.match(r'^([0-9.]+)\s*([a-z]+)$', size_str)
    if not match:
        return None
    
    try:
        value = float(match.group(1))
        unit = match.group(2)
        
        if unit not in units:
            return None
        
        return int(value * units[unit])
    except (ValueError, TypeError):
        return None


def _check_max_size_warning(max_size: Optional[str], main_content: Any) -> Optional[str]:
    """Check if max_size truncation produced suspiciously short content."""
    if max_size and main_content:
        words = len(str(main_content).split())
        if words < 50:
            return f"Content very short ({words} words) after --max-size {max_size} truncation. Consider a larger limit."
    return None


def fetch_url(
    url: str,
    timeout: int = 25,
    max_chars: Optional[int] = None,
    max_size: Optional[str] = None,
    raw_html: bool = False,
    js_render: bool = False,
    no_js_fallback: bool = False,
    max_retries: int = 3,
):
    """
    Fetch a single URL and extract/clean its content.

    Parameters
    ----------
    url : str
        The URL to fetch.
    timeout : int
        Request / browser-navigation timeout in seconds.
    max_chars : Optional[int]
        Maximum characters to keep in extracted content.
    max_size : Optional[str]
        Maximum response size (e.g. '1mb').
    raw_html : bool
        If True, return raw prettified HTML instead of extracted content.
    js_render : bool
        If True, skip straight to Playwright (headless Chromium) rendering
        instead of trying plain ``requests`` first. Requires ``playwright``
        (``pip install data-scout[js-render]`` + ``playwright install chromium``).
    no_js_fallback : bool
        If True, disable the automatic Playwright fallback that normally
        kicks in when plain ``requests`` fails or looks blocked. Has no
        effect when ``js_render`` is already set.
    max_retries : int
        Retry attempts per tier (requests, then Playwright) before moving on
        or giving up. Default 3, matching the rest of the toolkit.

    Returns a dict containing a single structured result.
    """
    # Validation: Only one of max_chars or max_size is allowed
    if max_chars is not None and max_size is not None:
        return {
            "error": "Cannot use both --max-chars and --max-size together. Use only ONE parameter:\n"
                    "   • --max-chars 10000 (to limit extracted content by character count)\n"
                    "   • --max-size 5mb (to limit response size by file size)\n"
                    "   Use either one, not both."
        }
    
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"error": "Invalid URL. Provide a working http/https URL."}

    start_time = time.time()
    try:
        extractor = ExtractionEngine()
        outcome = fetch_resilient(
            url,
            timeout=timeout,
            max_retries=max(1, int(max_retries)),
            enable_js_fallback=(not no_js_fallback) or js_render,
            force_js=js_render,
        )

        if outcome["status"] != "success":
            joined = "; ".join(outcome["errors"][-3:])
            status_match = re.search(r'\b([45]\d{2})\b', joined)
            prefix = f"HTTP {status_match.group(1)} — " if status_match else ""
            return {
                "error": (
                    f"fetch_url failed: {prefix}all fetch tiers exhausted "
                    f"({outcome['attempts']} attempts).\n"
                    f"       URL: {url}\n"
                    "       Details: " + joined
                )
            }

        response_text = outcome["html"]
        final_url = outcome["final_url"]
        fetch_tier = outcome["tier"]

        # Truncate HTML response if max_size is specified
        max_size_bytes = _parse_size_string(max_size)
        if max_size_bytes:
            encoded = response_text.encode('utf-8', errors='ignore')
            if len(encoded) > max_size_bytes:
                response_text = encoded[:max_size_bytes].decode('utf-8', errors='ignore')

        title = _extract_html_title(response_text) or final_url

        main_content, method, confidence = extractor.extract_content(
            final_url,
            response_text,
            timeout=timeout,
        )
        method = f"{method} ({fetch_tier})"

        # Apply max_chars constraint if specified
        if max_chars and main_content and len(main_content) > max_chars:
            main_content = main_content[:max_chars]

        elapsed = time.time() - start_time

        if raw_html:
            # Return raw HTML — skip extraction and cleaner pipeline entirely
            from bs4 import BeautifulSoup
            raw_html_text = BeautifulSoup(response_text, 'html.parser').prettify()
            if max_chars:
                if len(raw_html_text) > max_chars:
                    raw_html_text = raw_html_text[:max_chars]
            structured = {
                "position": 1,
                "title": title,
                "url": str(url),
                "final_url": final_url,
                "extraction_status": "success" if raw_html_text.strip() else "failed",
                "content_word_count": len(raw_html_text.split()),
                "extraction_method": "raw-html",
                "raw_html": raw_html_text,
            }
            return {
                "result": structured,
                "stats": {
                    "fetch_time_seconds": round(elapsed, 3),
                    "raw_html_mode": True,
                    "extraction_method": "raw-html",
                    "extraction_max_size_warning": _check_max_size_warning(max_size, raw_html_text),
                },
            }

        raw_record = {
            "position": 1,
            "title": title,
            "url": str(url),
            "final_url": final_url,
            "publish_date": None,
            "author": None,
            "fetch_time": elapsed,
            "extraction_status": "success" if str(main_content).strip() else "failed",
            "confidence_score": float(confidence or 0.0),
            "content_word_count": len(str(main_content or "").split()),
            "content_type": "unknown",
            "main_content": main_content or "",
            "snippet": "",
            "extraction_method": method or "unknown",
        }

        structured_results, cleaner_stats = process_results([raw_record])
        if structured_results:
            structured = structured_results[0]
        else:
            structured = raw_record
            structured["cleaned_content"] = str(main_content or "").strip()
            structured["content_sections"] = {}
            structured["top_keywords"] = []
            structured["sentences_count"] = 0
            structured["sample_sentences"] = []

        return {
            "result": structured,
            "stats": {
                "fetch_time_seconds": round(elapsed, 3),
                "cleaner": cleaner_stats,
                "extraction_method": method,
                "confidence_score": confidence,
                "extraction_max_size_warning": _check_max_size_warning(max_size, main_content),
            },
        }
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        status_hints = {
            301: "The page has permanently moved. Try the updated URL.",
            302: "The page has temporarily moved. The final destination may be blocked.",
            403: "Access forbidden. The site may be blocking automated requests.",
            404: "Page not found. The URL may be incorrect or the page was removed.",
            410: "The page has been permanently removed from the server.",
            429: "Rate-limited by the server. Try again later with a lower request rate.",
            500: "Internal server error on the target site. Try again later.",
            502: "Bad gateway from the target server. Temporarily unavailable.",
            503: "Service unavailable. The target site may be temporarily overloaded.",
        }
        hint = status_hints.get(status_code,
                                "The server returned an unexpected status code.")
        return {
            "error": (
                f"fetch_url failed: HTTP {status_code} — {hint}\n"
                f"       URL: {url}"
            )
        }
    except requests.ConnectionError:
        return {"error": f"fetch_url failed: Connection refused — the server at {url} may be unreachable or blocking requests"}
    except requests.Timeout:
        return {"error": f"fetch_url failed: Request timed out after {timeout}s — {url} may be too slow or unresponsive"}
    except Exception as exc:
        exc_name = type(exc).__name__
        return {"error": f"fetch_url failed: [{exc_name}] {exc}"}


# Legacy function name for backward compatibility
def fatchurl(url: str, timeout: int = 25):
    """Deprecated: Use fetch_url() instead"""
    return fetch_url(url, timeout)


def main():
    ds_config.load_stored_credentials_into_env()

    parser = argparse.ArgumentParser(
        description='Complete search pipeline: web, image, news, video search + URL fetch'
    )
    
    # Subcommands for different search types
    subparsers = parser.add_subparsers(dest='command', help='Search commands')
    
    # Web search subcommand
    web_parser = subparsers.add_parser(
        'web-search',
        help='Web search',
        description='Web search with content extraction.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after retries,\n'
                    'try: (1) Using a different search query, (2) Adjusting --retry-attempts and --retry-backoff,\n'
                    '(3) Waiting and trying again later, or (4) Checking your internet connection.'
    )
    web_parser.add_argument('--query', '-q', required=True, help='Search query')
    web_parser.add_argument('--max', '-m', type=int, default=5, help='Max results (1-100)')
    web_parser.add_argument('--workers', '-w', type=int, default=8, help='Parallel workers')
    web_parser.add_argument('--out', '-o', default='struct_format_results.json', help='Output file')
    web_parser.add_argument('--region', default=None, help='DuckDuckGo region (example: us-en, wt-wt)')
    web_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    web_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    web_parser.add_argument('--backend', default='auto', choices=['auto', 'html', 'lite'], help='DDGS backend')
    web_parser.set_defaults(retry_on_zero=True)
    web_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 successful extractions')
    web_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 successful extractions')
    web_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    web_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright) when fetching each result page')
    web_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback when a page fetch fails or looks blocked')
    web_parser.set_defaults(enable_js_fallback=True)
    
    # Image search subcommand
    img_parser = subparsers.add_parser(
        'image-search',
        help='Image search',
        description='Image search with dimension and property filtering.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Using different query keywords, (2) Removing dimension filters temporarily,\n'
                    '(3) Reducing --max parameter, or (4) Trying again later.'
    )
    img_parser.add_argument('--query', '-q', required=True, help='Search query')
    img_parser.add_argument('--max', '-m', type=int, default=5, help='Max images (1-50)')
    img_parser.add_argument('--out', '-o', default='image_search_results.json', help='Output file')
    img_parser.add_argument('--download', '-d', action='store_true', help='Download images')
    img_parser.add_argument('--download-dir', default='downloaded_images', help='Download directory')
    img_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    img_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    img_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    img_parser.add_argument('--size', default=None, help='Image size filter (Small, Medium, Large, Wallpaper)')
    img_parser.add_argument('--color', default=None, help='Image color filter')
    img_parser.add_argument('--type-image', default=None, help='Image type filter (photo, clipart, gif, transparent, line)')
    img_parser.add_argument('--layout', default=None, help='Image layout filter (Square, Tall, Wide)')
    img_parser.add_argument('--license-image', default=None, help='Image license filter')
    img_parser.add_argument('--min-width', type=int, default=None, help='Minimum image width in pixels')
    img_parser.add_argument('--max-width', type=int, default=None, help='Maximum image width in pixels')
    img_parser.add_argument('--min-height', type=int, default=None, help='Minimum image height in pixels')
    img_parser.add_argument('--max-height', type=int, default=None, help='Maximum image height in pixels')
    img_parser.set_defaults(retry_on_zero=True)
    img_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 valid images are found')
    img_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 valid images are found')
    img_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')

    # News search subcommand
    news_parser = subparsers.add_parser(
        'news-search',
        help='DuckDuckGo news search with full content extraction',
        description='News search with regional and temporal filtering and full article content extraction.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Broadening your query, (2) Removing --timelimit filter,\n'
                    '(3) Changing --region, or (4) Waiting and retrying.'
    )
    news_parser.add_argument('--query', '-q', required=True, help='Search query')
    news_parser.add_argument('--max', '-m', type=int, default=5, help='Max news items (1-50)')
    news_parser.add_argument('--out', '-o', default='news_search_results.json', help='Output file')
    news_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    news_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    news_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    news_parser.add_argument('--workers', type=int, default=3, help='Parallel workers for content extraction')
    news_parser.set_defaults(retry_on_zero=True)
    news_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries on zero results')
    news_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts on zero results')
    news_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    news_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright) when fetching each article page')
    news_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback when an article fetch fails or looks blocked')
    news_parser.set_defaults(enable_js_fallback=True)

    # Video search subcommand
    video_parser = subparsers.add_parser(
        'video-search',
        help='DuckDuckGo video search',
        description='Video search with duration and resolution filtering.\n\n'
                    '⚠️  RATE LIMITING: DuckDuckGo is rate-limited. If you get zero results after searches,\n'
                    'try: (1) Using broader search terms, (2) Removing --duration filter,\n'
                    '(3) Changing --region, or (4) Trying again later.'
    )
    video_parser.add_argument('--query', '-q', required=True, help='Search query')
    video_parser.add_argument('--max', '-m', type=int, default=5, help='Max videos (1-50)')
    video_parser.add_argument('--out', '-o', default='video_search_results.json', help='Output file')
    video_parser.add_argument('--region', default='us-en', help='DuckDuckGo region (example: us-en, wt-wt)')
    video_parser.add_argument('--safesearch', default='moderate', choices=['on', 'moderate', 'off'], help='Safe search mode')
    video_parser.add_argument('--timelimit', default=None, help='DuckDuckGo time limit (d, w, m, y)')
    video_parser.add_argument('--resolution', default=None, help='Video resolution filter (high, standard)')
    video_parser.add_argument('--duration', default=None, help='Video duration filter (short, medium, long)')
    video_parser.add_argument('--license-videos', default=None, help='Video license filter')
    video_parser.set_defaults(retry_on_zero=True)
    video_parser.add_argument('--no-retry-on-zero', dest='retry_on_zero', action='store_false', help='Disable retries when 0 results are found')
    video_parser.add_argument('--retry-attempts', type=int, default=2, help='Retry attempts when 0 results are found')
    video_parser.add_argument('--retry-backoff', type=float, default=1.0, help='Backoff seconds between retries')
    
    # URL fetch subcommand
    url_parser = subparsers.add_parser(
        'fetch-url',
        help='Fetch and extract single URL',
        description='Fetch a URL and extract main content.\n\n'
                    '⚠️  NOTE: Content extraction depends on website structure. If extraction fails,\n'
                    'try: (1) Checking if the URL is valid, (2) Using --max-chars or --max-size to adjust output,\n'
                    '(3) Verifying the website is accessible, or (4) Using --timeout to increase wait time.'
    )
    url_parser.add_argument('--url', '-u', required=True, help='URL to fetch')
    url_parser.add_argument('--timeout', type=int, default=25, help='Extraction timeout in seconds (increase for JS-rendered SPAs)')
    url_parser.add_argument('--max-chars', type=int, default=None, help='Maximum characters to extract (e.g., 10000)')
    url_parser.add_argument('--max-size', type=str, default=None, help='Maximum response size (e.g., 100kb, 1mb, 500mb)')
    url_parser.add_argument('--out', '-o', default='url_fetch_result.json', help='Output file')
    url_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    url_parser.add_argument('--raw-html', action='store_true', help='Return raw HTML (prettified) instead of extracted/cleaned content')
    url_parser.add_argument('--js-render', action='store_true', help='Skip straight to Playwright rendering instead of trying requests first')
    url_parser.add_argument('--no-js-fallback', action='store_true', help='Disable automatic Playwright fallback when requests fails or looks blocked')
    url_parser.add_argument('--max-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright)')

    # ======================================================================
    # video-extract subcommand
    # ======================================================================
    video_extract_parser = subparsers.add_parser(
        'video-extract',
        help='Extract full details from a video URL (supports YouTube)',
        description=(
            'Extract full metadata, description, and subtitles from a video URL. '
            'Currently supports YouTube. Other platforms coming soon.'
        ),
        epilog=(
            'Examples:\n'
            '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"\n'
            '  data-scout video-extract --url "https://youtu.be/dQw4w9WgXcQ"\n'
            '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --subtitle-lang fr\n'
            '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments\n'
        '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    video_extract_parser.add_argument('--url', required=True, help='Video URL to extract (e.g., https://www.youtube.com/watch?v=VIDEO_ID)')
    video_extract_parser.add_argument('--subtitle-lang', default='en', help='Preferred subtitle language code (default: en)')
    video_extract_parser.add_argument('--segments', action='store_true', help='Include subtitle segments with timestamps (default: off)')
    video_extract_parser.add_argument('--out', '-o', default='video_extract_results.json', help='Output file (default: video_extract_results.json)')
    video_extract_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    video_extract_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier (requests, then Playwright) when fetching the video page')
    video_extract_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback when the page fetch fails or looks blocked')
    video_extract_parser.set_defaults(enable_js_fallback=True)

    # ======================================================================
    # multi-search subcommand — search across multiple engines in parallel
    # ======================================================================
    multi_parser = subparsers.add_parser(
        'multi-search',
        help='Search across multiple engines (DuckDuckGo + optional Brave/Bing/Google/SerpAPI) in parallel',
        description=(
            'Query several search engines in parallel, merge/dedupe the results, then run the '
            'same content-extraction pipeline as web-search. DuckDuckGo works with no setup. '
            'Brave/Bing/Google/SerpAPI each need an API key (env var) — see `data-scout list-engines`. '
            'Unconfigured engines are skipped, not treated as errors.'
        ),
        epilog=(
            'Examples:\n'
            '  data-scout multi-search --query "rust vs go" --engines duckduckgo\n'
            '  data-scout multi-search --query "rust vs go" --engines duckduckgo,brave,google --max 15\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    multi_parser.add_argument('--query', '-q', required=True, help='Search query')
    multi_parser.add_argument('--engines', default='duckduckgo', help='Comma-separated engine names (duckduckgo,brave,bing,google,serpapi)')
    multi_parser.add_argument('--max', '-m', type=int, default=10, help='Max merged results')
    multi_parser.add_argument('--workers', '-w', type=int, default=8, help='Parallel content-extraction workers')
    multi_parser.add_argument('--serpapi-engine', default='google', help='Underlying engine for SerpAPI (google/bing/yahoo/baidu/yandex/...)')
    multi_parser.add_argument('--no-dedupe', dest='dedupe', action='store_false', help='Keep duplicate URLs across engines instead of deduping')
    multi_parser.set_defaults(dedupe=True)
    multi_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier when fetching each result page')
    multi_parser.add_argument('--no-js-fallback', dest='enable_js_fallback', action='store_false', help='Disable automatic Playwright fallback')
    multi_parser.set_defaults(enable_js_fallback=True)
    multi_parser.add_argument('--out', '-o', default='multi_search_results.json', help='Output file')
    multi_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    # list-engines subcommand — show configuration status of every engine
    subparsers.add_parser('list-engines', help='List available search engines and whether each is configured')

    # config subcommand — interactive credential setup, stored at ~/.data-scout/
    config_parser = subparsers.add_parser(
        'config',
        help='Set up API keys/tokens (GitHub, Brave, Bing, Google, SerpAPI, Discord, Reddit) -- stored at ~/.data-scout/',
        description=(
            "Run with no flags for an interactive wizard that asks for each supported API key/token "
            "one at a time (Enter to skip). Values are stored at ~/.data-scout/credentials.json "
            "(owner-only file permissions) and loaded automatically on every future run -- a real "
            "environment variable always takes precedence over a stored value."
        ),
    )
    config_parser.add_argument('--show', action='store_true', help='Show configuration status for every known key (no secrets printed) instead of running the wizard')
    config_parser.add_argument('--clear', default=None, metavar='KEY', help='Remove one stored key, e.g. --clear GITHUB_TOKEN')
    config_parser.add_argument('--clear-all', action='store_true', help='Remove all stored keys')

    # ======================================================================
    # GitHub extraction subcommands
    # ======================================================================
    gh_repo_parser = subparsers.add_parser(
        'github-repo',
        help='Get comprehensive GitHub repository details (metadata + branches + commit/PR/issue counts + contributors + releases + languages + file tree)',
        description=(
            "By default this aggregates a full overview: base metadata, all branches, an "
            "approximate commit count, accurately split open-issue/open-PR counts, top "
            "contributors, latest release, per-language byte breakdown, and a file-tree "
            "preview -- everything several separate github-* commands would otherwise need. "
            "That costs ~7 API calls instead of 1; pass --quick for just the fast base metadata "
            "if you're conserving rate limit (60/hr unauthenticated, 5,000/hr with GITHUB_TOKEN)."
        ),
    )
    gh_repo_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_repo_parser.add_argument('--quick', dest='full', action='store_false', help='Fast single-call basic metadata only (skip branches/contributors/releases/tree/etc.)')
    gh_repo_parser.set_defaults(full=True)
    gh_repo_parser.add_argument('--tree-limit', type=int, default=200, help='Max file-tree entries to include in the preview')
    gh_repo_parser.add_argument('--out', '-o', default='github_repo_results.json', help='Output file')
    gh_repo_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_commits_parser = subparsers.add_parser('github-commits', help='List commits in a GitHub repo')
    gh_commits_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_commits_parser.add_argument('--branch', default=None, help='Branch/tag/SHA to list commits from (default: repo default branch)')
    gh_commits_parser.add_argument('--path', default=None, help='Only commits touching this file/path')
    gh_commits_parser.add_argument('--author', default=None, help='Filter by author username or email')
    gh_commits_parser.add_argument('--since', default=None, help='ISO8601 date — only commits after this')
    gh_commits_parser.add_argument('--until', default=None, help='ISO8601 date — only commits before this')
    gh_commits_parser.add_argument('--max', '-m', type=int, default=30, help='Max commits to list')
    gh_commits_parser.add_argument('--out', '-o', default='github_commits_results.json', help='Output file')
    gh_commits_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_commit_parser = subparsers.add_parser('github-commit', help='Full details for ONE commit: stats, changed files, and unified diff patches')
    gh_commit_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_commit_parser.add_argument('--sha', required=True, help='Commit SHA (full or short)')
    gh_commit_parser.add_argument('--no-patch', dest='include_patch', action='store_false', help="Omit each file's unified diff patch text (metadata only)")
    gh_commit_parser.set_defaults(include_patch=True)
    gh_commit_parser.add_argument('--out', '-o', default='github_commit_results.json', help='Output file')
    gh_commit_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_pr_parser = subparsers.add_parser('github-pr', help='Get a pull request, including its full diff and changed files')
    gh_pr_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_pr_parser.add_argument('--number', '-n', type=int, required=True, help='Pull request number')
    gh_pr_parser.add_argument('--no-diff', dest='include_diff', action='store_false', help='Omit the changed-files/diff list (metadata only)')
    gh_pr_parser.set_defaults(include_diff=True)
    gh_pr_parser.add_argument('--out', '-o', default='github_pr_results.json', help='Output file')
    gh_pr_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_prs_parser = subparsers.add_parser('github-prs', help='List pull requests in a GitHub repo (PR-specific fields, unlike github-issues)')
    gh_prs_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_prs_parser.add_argument('--state', default='open', choices=['open', 'closed', 'all'], help='PR state filter')
    gh_prs_parser.add_argument('--sort', default='created', choices=['created', 'updated', 'popularity', 'long-running'], help='Sort order')
    gh_prs_parser.add_argument('--max', '-m', type=int, default=30, help='Max PRs to list')
    gh_prs_parser.add_argument('--out', '-o', default='github_prs_results.json', help='Output file')
    gh_prs_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_folder_parser = subparsers.add_parser('github-folder', help="List (and optionally fetch) every file under a repo folder, e.g. 'src/'")
    gh_folder_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_folder_parser.add_argument('--path', default='', help="Folder path, e.g. 'src/' (default: repo root)")
    gh_folder_parser.add_argument('--ref', default=None, help='Branch/tag/SHA (default: repo default branch)')
    gh_folder_parser.add_argument('--no-recursive', dest='recursive', action='store_false', help='List only immediate children instead of walking the whole subtree')
    gh_folder_parser.set_defaults(recursive=True)
    gh_folder_parser.add_argument('--include-content', action='store_true', help="Also fetch each file's contents (capped by --max-files)")
    gh_folder_parser.add_argument('--max-files', type=int, default=20, help='Cap on how many files to fetch content for (only with --include-content)')
    gh_folder_parser.add_argument('--out', '-o', default='github_folder_results.json', help='Output file')
    gh_folder_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_issues_parser = subparsers.add_parser('github-issues', help='List issues in a GitHub repo')
    gh_issues_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_issues_parser.add_argument('--state', default='open', choices=['open', 'closed', 'all'], help='Issue state filter')
    gh_issues_parser.add_argument('--labels', default=None, help='Comma-separated label filter')
    gh_issues_parser.add_argument('--max', '-m', type=int, default=30, help='Max issues to list')
    gh_issues_parser.add_argument('--include-prs', dest='include_pull_requests', action='store_true', help="Include pull requests (GitHub's issues API returns PRs too by default)")
    gh_issues_parser.add_argument('--out', '-o', default='github_issues_results.json', help='Output file')
    gh_issues_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_issue_parser = subparsers.add_parser('github-issue', help='Get one issue, including its full body and comments')
    gh_issue_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_issue_parser.add_argument('--number', '-n', type=int, required=True, help='Issue number')
    gh_issue_parser.add_argument('--no-comments', dest='include_comments', action='store_false', help='Omit comments')
    gh_issue_parser.set_defaults(include_comments=True)
    gh_issue_parser.add_argument('--out', '-o', default='github_issue_results.json', help='Output file')
    gh_issue_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_file_parser = subparsers.add_parser('github-file', help='Fetch a single file\'s contents from a GitHub repo')
    gh_file_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_file_parser.add_argument('--path', required=True, help='File path within the repo, e.g. src/main.py')
    gh_file_parser.add_argument('--ref', default=None, help='Branch/tag/SHA (default: repo default branch)')
    gh_file_parser.add_argument('--out', '-o', default='github_file_results.json', help='Output file')
    gh_file_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_search_code_parser = subparsers.add_parser('github-search-code', help='Search code across GitHub (requires GITHUB_TOKEN)')
    gh_search_code_parser.add_argument('--query', '-q', required=True, help="GitHub code search query, e.g. 'fetch_resilient language:python'")
    gh_search_code_parser.add_argument('--max', '-m', type=int, default=20, help='Max results')
    gh_search_code_parser.add_argument('--out', '-o', default='github_search_code_results.json', help='Output file')
    gh_search_code_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_search_repos_parser = subparsers.add_parser('github-search-repos', help='Search GitHub repositories')
    gh_search_repos_parser.add_argument('--query', '-q', required=True, help="e.g. 'language:python topic:llm stars:>1000'")
    gh_search_repos_parser.add_argument('--sort', default='stars', choices=['stars', 'forks', 'help-wanted-issues', 'updated'], help='Sort order')
    gh_search_repos_parser.add_argument('--max', '-m', type=int, default=20, help='Max results')
    gh_search_repos_parser.add_argument('--out', '-o', default='github_search_repos_results.json', help='Output file')
    gh_search_repos_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    gh_discussions_parser = subparsers.add_parser('github-discussions', help='List GitHub Discussions for a repo (requires GITHUB_TOKEN)')
    gh_discussions_parser.add_argument('--repo', required=True, help="'owner/repo' or a github.com URL")
    gh_discussions_parser.add_argument('--max', '-m', type=int, default=20, help='Max discussions')
    gh_discussions_parser.add_argument('--out', '-o', default='github_discussions_results.json', help='Output file')
    gh_discussions_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    # ======================================================================
    # Social/platform subcommands
    # ======================================================================
    telegram_parser = subparsers.add_parser(
        'telegram-channel',
        help='Fetch posts from a PUBLIC Telegram channel, or search for channels by topic',
        description=(
            'Two modes: --channel NAME fetches posts directly from a known public channel '
            '(no auth needed). --query "..." instead searches for public channels matching a '
            'topic (via a site:t.me web search -- there is no official Telegram-wide search '
            'API for anonymous use) and returns a preview of each match.'
        ),
    )
    telegram_parser.add_argument('--channel', default=None, help="Channel username, e.g. 'durov' (or a t.me URL) -- direct mode")
    telegram_parser.add_argument('--query', '-q', default=None, help='Search for public channels matching this topic -- search mode')
    telegram_parser.add_argument('--max', '-m', type=int, default=20, help='Max posts to return (--channel mode) or max channels (--query mode)')
    telegram_parser.add_argument('--posts-per-channel', type=int, default=3, help='(--query mode) posts to preview per matched channel')
    telegram_parser.add_argument('--max-fetch-retries', type=int, default=3, help='Retry attempts per fetch tier')
    telegram_parser.add_argument('--out', '-o', default='telegram_results.json', help='Output file')
    telegram_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    discord_parser = subparsers.add_parser(
        'discord-channel',
        help='Fetch recent messages from a Discord channel (requires DISCORD_BOT_TOKEN)',
        description=(
            'Requires DISCORD_BOT_TOKEN, and the bot must already be a member of the target '
            "server with read-history permission. Unlike telegram-channel, there's no --query "
            "topic-search mode here: Discord has no anonymous/public read API of any kind "
            '(you always need a bot that has actually been invited into the specific server), '
            "so there's no server-wide or cross-server search this library could legitimately offer."
        ),
    )
    discord_parser.add_argument('--channel-id', required=True, help='Numeric Discord channel ID')
    discord_parser.add_argument('--max', '-m', type=int, default=50, help='Max messages to return')
    discord_parser.add_argument('--before', default=None, help='Only messages before this message ID (pagination)')
    discord_parser.add_argument('--out', '-o', default='discord_results.json', help='Output file')
    discord_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    reddit_parser = subparsers.add_parser(
        'reddit-search',
        help='Best-effort Reddit search (unreliable as of 2026 — see --help)',
        description=(
            'Best-effort only: Reddit blocks most anonymous requests as of 2026 and has no '
            'reliable zero-config API path. This command tries anyway and reports the real '
            'failure reason on a 403 rather than pretending to succeed. Set REDDIT_COOKIE '
            "(a logged-in session's Cookie header) to improve your odds."
        ),
    )
    reddit_parser.add_argument('--query', '-q', required=True, help='Search query')
    reddit_parser.add_argument('--subreddit', default=None, help='Restrict search to one subreddit')
    reddit_parser.add_argument('--sort', default='relevance', choices=['relevance', 'hot', 'top', 'new', 'comments'], help='Sort order')
    reddit_parser.add_argument('--max', '-m', type=int, default=20, help='Max results')
    reddit_parser.add_argument('--out', '-o', default='reddit_results.json', help='Output file')
    reddit_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    if args.command == 'image-search':
        if args.min_width is not None and args.max_width is not None and args.min_width > args.max_width:
            parser.error('--min-width cannot be greater than --max-width')
        if args.min_height is not None and args.max_height is not None and args.min_height > args.max_height:
            parser.error('--min-height cannot be greater than --max-height')
    
    # Web search
    if args.command == 'web-search':
        print(f"\n🔍 Starting web search: '{args.query}'\n")
        structured_results, stats = web_search(
            args.query,
            max_results=args.max,
            workers=args.workers,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            backend=args.backend,
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
        )
        
        output = {
            'query': args.query,
            'search_type': 'web',
            'parameters': {
                'max_results': args.max,
                'workers': args.workers,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'backend': args.backend,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
                'max_fetch_retries': args.max_fetch_retries,
                'enable_js_fallback': args.enable_js_fallback,
            },
            'stats': stats,
            'structured_results': structured_results
        }
        
        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ WEB SEARCH COMPLETE!')
        print(f'   🔍 Query: {args.query}')
        print(f'   📊 Total results from search: {stats["search_engine"]["total"]}')
        print(f'   ✅ Successfully extracted: {stats["cleaner"]["successful"]}')
        print(f'   ❌ Failed (ignored): {stats["cleaner"]["failed"]}')
        print(f'   📄 Structured JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"]["execution_time"]:.1f}s\n')
    
    # Image search
    elif args.command == 'image-search':
        print(f"\n🖼️  Starting image search: '{args.query}'\n")
        image_results, stats = image_search(
            args.query,
            max_results=args.max,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            size=args.size,
            color=args.color,
            type_image=args.type_image,
            layout=args.layout,
            license_image=args.license_image,
            min_width=args.min_width,
            max_width=args.max_width,
            min_height=args.min_height,
            max_height=args.max_height,
        )
        
        output = {
            'query': args.query,
            'search_type': 'image',
            'parameters': {
                'max_results': args.max,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'size': args.size,
                'color': args.color,
                'type_image': args.type_image,
                'layout': args.layout,
                'license_image': args.license_image,
                'min_width': args.min_width,
                'max_width': args.max_width,
                'min_height': args.min_height,
                'max_height': args.max_height,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
            },
            'stats': stats,
            'image_results': image_results
        }
        
        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ IMAGE SEARCH COMPLETE!')
        print(f'   🖼️  Query: {args.query}')
        print(f'   📊 Total images found: {stats["search_engine"]["total"]}')
        print(f'   ✅ Valid URLs: {stats["search_engine"]["success"]}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"]["execution_time"]:.2f}s')
        
        # Download images if requested
        if args.download and image_results:
            from .extraction import ImageSearchResult
            engine = ImageSearchEngine()
            engine.results = [ImageSearchResult(**r) for r in image_results]
            engine.download_images(args.download_dir, min(10, len(image_results)))
        
        print()

    # News search
    elif args.command == 'news-search':
        print(f"\n📰 Starting news search: '{args.query}'\n")
        news_results, stats = news_search(
            args.query,
            max_results=args.max,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            workers=getattr(args, 'workers', 3),
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
        )

        output = {
            'query': args.query,
            'search_type': 'news',
            'parameters': {
                'max_results': args.max,
                'workers': args.workers if hasattr(args, 'workers') else 3,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
                'max_fetch_retries': args.max_fetch_retries,
                'enable_js_fallback': args.enable_js_fallback,
            },
            'stats': stats,
            'structured_results': news_results,
        }

        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ NEWS SEARCH COMPLETE!')
        print(f'   📰 Query: {args.query}')
        print(f'   📊 Total results from search: {stats["search_engine"].get("total", 0)}')
        print(f'   ✅ Successfully extracted: {stats.get("cleaner", {}).get("successful", 0)}')
        print(f'   ❌ Failed (ignored): {stats.get("cleaner", {}).get("failed", 0)}')
        print(f'   📄 Structured JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"].get("execution_time", 0.0):.1f}s\n')

    # Video search
    elif args.command == 'video-search':
        print(f"\n🎬 Starting video search: '{args.query}'\n")
        video_results, stats = video_search(
            args.query,
            max_results=args.max,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            resolution=args.resolution,
            duration=args.duration,
            license_videos=args.license_videos,
            retry_on_zero_success=args.retry_on_zero,
            retry_attempts=args.retry_attempts,
            retry_backoff=args.retry_backoff,
        )

        # Enhance truncated DDGS descriptions with full YouTube descriptions
        video_results = _enhance_video_descriptions(video_results)

        output = {
            'query': args.query,
            'search_type': 'video',
            'parameters': {
                'max_results': args.max,
                'region': args.region,
                'safesearch': args.safesearch,
                'timelimit': args.timelimit,
                'resolution': args.resolution,
                'duration': args.duration,
                'license_videos': args.license_videos,
                'retry_on_zero_success': args.retry_on_zero,
                'retry_attempts': args.retry_attempts,
                'retry_backoff': args.retry_backoff,
            },
            'stats': stats,
            'video_results': video_results,
        }

        out_path = Path(args.out)
        _write_output(out_path, output)

        print(f'\n✅ VIDEO SEARCH COMPLETE!')
        print(f'   🎬 Query: {args.query}')
        print(f'   📊 Total videos found: {stats["search_engine"].get("total", 0)}')
        print(f'   📄 Results JSON: {out_path}')
        print(f'   📂 Results saved to: {out_path.resolve()}')
        print(f'   ⏱️  Execution time: {stats["search_engine"].get("execution_time", 0.0):.2f}s\n')

    # Video extract
    elif args.command == 'video-extract':
        print(f"\n🎥 Extracting video details: {args.url}\n")

        lang = getattr(args, 'subtitle_lang', 'en') or 'en'
        include_segments = getattr(args, 'segments', False)
        result = video_extract(
            args.url,
            subtitle_lang=lang,
            include_segments=include_segments,
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
        )

        # Handle error cases
        if "error" in result:
            err_code = result.get("error", "unknown")
            err_msg = result.get("error_message", "Unknown error")

            if err_code == "invalid_url":
                print(f'   [ERR] Invalid URL: {err_msg}')
            elif err_code == "unsupported_platform":
                print(f'   [ERR] Unsupported platform: {err_msg}')
                print(f'   [OK]  Supported platforms: {", ".join(result.get("supported_platforms", []))}')
            elif err_code in ("video_not_found", "http_error", "network_error", "timeout"):
                print(f'   [ERR] {err_msg}')
            else:
                print(f'   [ERR] {err_msg}')
            print(f'   [HINT] Provide a valid YouTube URL: data-scout video-extract --url "https://www.youtube.com/watch?v=VIDEO_ID"')
            print(f'   [HINT] Other video platforms coming soon.\n')

            # Still save error result to output for debugging
            output = result
            out_path = Path(args.out)
            _write_output(out_path, output)
        else:
            platform = result.get("platform", "unknown")
            title = result.get("title", "Unknown")
            channel = result.get("channel", "Unknown")
            views = result.get("view_count", 0)
            duration = result.get("duration_seconds", 0)
            has_subs = result.get("subtitles") is not None
            subs_error = result.get("subtitles_error")
            avail_langs = result.get("available_subtitle_languages")
            req_lang = result.get("requested_subtitle_language", "en")

            print(f'   ✅ Platform: {platform}')
            print(f'   ✅ Title: {title}')
            print(f'   📺 Channel: {channel}')
            print(f'   👁️  Views: {views:,}')
            print(f'   ⏱️  Duration: {duration}s')

            if subs_error:
                print(f'   [!]  Subtitles: {subs_error}')
                if avail_langs:
                    print(f'   [OK]  Available subtitle languages:')
                    for lang in avail_langs:
                        tag = " (auto-generated)" if lang["generated"] and "auto-generated" not in lang["name"] else ""
                        print(f'         - {lang["code"]}: {lang["name"]}{tag}')

            if has_subs:
                sub_lang = result["subtitles"].get("language_code", "?")
                print(f'   📝 Subtitles: Available ({sub_lang})')
            elif not subs_error:
                print(f'   📝 Subtitles: Not available')

            output = result

            out_path = Path(args.out)
            _write_output(out_path, output)
        if not args.json:
            if "error" in result:
                print(f'\n   [ERR] Extraction failed. Details saved to: {out_path.resolve()}\n')
            else:
                print(f'\n   ✅ VIDEO EXTRACTION COMPLETE!')
                print(f'   📄 Results saved to: {out_path.resolve()}\n')
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))

    # Fetch URL
    elif args.command == 'fetch-url':
        # Validate: Only one of --max-chars or --max-size is allowed
        if args.max_chars is not None and args.max_size is not None:
            parser.error('❌ ERROR: Cannot use both --max-chars and --max-size together. Use only ONE parameter at a time:\n'
                        '   • --max-chars 10000 (to limit extracted content by character count)\n'
                        '   • --max-size 5mb (to limit response size by file size)\n'
                        '   Use either one, not both.')
        
        print(f"\n📥 Fetching: {args.url}\n")
        result = fetch_url(
            args.url,
            timeout=args.timeout,
            max_chars=args.max_chars,
            max_size=args.max_size,
            raw_html=args.raw_html,
            js_render=args.js_render,
            no_js_fallback=args.no_js_fallback,
            max_retries=args.max_retries,
        )

        output = {
            'url': args.url,
            'search_type': 'fetch',
            'parameters': {
                'timeout': args.timeout,
                'max_chars': args.max_chars,
                'max_size': args.max_size,
                'raw_html': args.raw_html,
                'js_render': args.js_render,
                'no_js_fallback': args.no_js_fallback,
                'max_retries': args.max_retries,
            },
            'result': result
        }

        out_path = Path(args.out)
        _write_output(out_path, output)

        if "error" in result:
            print(f"❌ Error: {result['error']}\n")
        else:
            mode_tag = " RAW" if args.raw_html else ""
            print(f'✅ FETCH COMPLETE{mode_tag}!')
            print(f'   📝 Title: {result["result"]["title"]}')
            print(f'   📊 Words: {result["result"]["content_word_count"]}')
            print(f'   ✅ Status: {result["stats"]["extraction_method"]}')
            print(f'   ⏱️  Fetch time: {result["stats"]["fetch_time_seconds"]}s')
            print(f'   📄 Result JSON: {out_path}')
            if args.raw_html:
                print(f'   🔧 Mode: raw-html (cleaner pipeline skipped)')
            print(f'   📂 Results saved to: {out_path.resolve()}\n')

    # ==========================================================================
    # multi-search
    # ==========================================================================
    elif args.command == 'multi-search':
        engine_list = [e.strip() for e in args.engines.split(',') if e.strip()]
        print(f"\n🌐 Multi-engine search: '{args.query}' across {engine_list}\n")
        structured_results, stats = multi_search(
            args.query,
            engines=engine_list,
            max_results=args.max,
            workers=args.workers,
            max_fetch_retries=args.max_fetch_retries,
            enable_js_fallback=args.enable_js_fallback,
            dedupe=args.dedupe,
            serpapi_engine=args.serpapi_engine,
        )
        output = {
            'query': args.query,
            'search_type': 'multi-engine',
            'parameters': {'engines': engine_list, 'max_results': args.max, 'workers': args.workers},
            'stats': stats,
            'structured_results': structured_results,
        }
        out_path = Path(args.out)
        _write_output(out_path, output)
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            skipped = stats['discovery'].get('skipped', [])
            print(f"✅ MULTI-SEARCH COMPLETE!")
            print(f"   🔎 Engines run: {stats['discovery'].get('engines_run', [])}")
            if skipped:
                print(f"   ⏭️  Skipped: {[s['engine'] for s in skipped]} (run `data-scout list-engines` for setup hints)")
            print(f"   📊 Results: {len(structured_results)}")
            print(f'   📂 Results saved to: {out_path.resolve()}\n')

    # ==========================================================================
    # list-engines
    # ==========================================================================
    elif args.command == 'list-engines':
        print("\n🌐 SEARCH ENGINES\n")
        for info in search_engines.list_engines():
            status = "✅ configured" if info['configured'] else "⚪ not configured"
            tier_tag = "zero-config" if info['tier'] == 0 else "needs API key"
            print(f"  {info['name']:<12} [{tier_tag:<14}] {status}")
            if not info['configured']:
                print(f"      → {info['setup_hint']}")
        print(
            "\nNote: Google/Bing/Yahoo/Opera search-result *pages* can't be scraped directly "
            "(anti-bot + ToS). The engines above use each provider's official API instead — "
            "SerpAPI additionally proxies Yahoo/Baidu/Yandex/etc. via --serpapi-engine.\n"
            "Run `data-scout config` to set up API keys interactively.\n"
        )

    # ==========================================================================
    # config
    # ==========================================================================
    elif args.command == 'config':
        if args.clear_all:
            ds_config.clear_all_credentials()
            print("✅ All stored credentials cleared.\n")
        elif args.clear:
            if ds_config.clear_credential(args.clear):
                print(f"✅ Cleared stored credential: {args.clear}\n")
            else:
                print(f"⚪ No stored credential found for: {args.clear}\n")
        elif args.show:
            ds_config.print_credential_status()
        else:
            ds_config.run_config_wizard()

    # ==========================================================================
    # GitHub extraction commands
    # ==========================================================================
    elif args.command == 'github-repo':
        result = gh.github_repo(args.repo, full=args.full, tree_limit=args.tree_limit)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['full_name']} — ⭐ {result['stars']} stars, 🍴 {result['forks']} forks, lang: {result['language']}")
            if args.full:
                print(f"   {result.get('branch_count', '?')} branches, ~{result.get('commit_count_approx', '?')} commits, "
                      f"{result.get('open_issues_only', '?')} open issues, {result.get('open_pull_requests', '?')} open PRs")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-commits':
        result = gh.github_commits(
            args.repo, branch=args.branch, path=args.path, author=args.author,
            since=args.since, until=args.until, max_results=args.max,
        )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['commit_count']} commits found\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-commit':
        result = gh.github_commit(args.repo, args.sha, include_patch=args.include_patch)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            stats = result.get('stats', {})
            print(f"✅ Commit {result['short_sha']}: {result['files_changed']} files changed "
                  f"(+{stats.get('additions', 0)}/-{stats.get('deletions', 0)})")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-pr':
        result = gh.github_pull_request(args.repo, args.number, include_diff=args.include_diff)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ PR #{result['number']}: {result['title']} [{result['state']}]"
                  f"{' (merged)' if result.get('is_merged') else ''}")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-prs':
        result = gh.github_prs(args.repo, state=args.state, sort=args.sort, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['pr_count']} pull requests found\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-folder':
        result = gh.github_folder(
            args.repo, path=args.path, ref=args.ref, recursive=args.recursive,
            include_content=args.include_content, max_files=args.max_files,
        )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['entry_count']} entries under '{result['path']}'"
                  + (f", {result.get('files_fetched', 0)} files' content fetched" if args.include_content else ""))
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-issues':
        result = gh.github_issues(
            args.repo, state=args.state, labels=args.labels, max_results=args.max,
            include_pull_requests=args.include_pull_requests,
        )
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['issue_count']} issues found\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-issue':
        result = gh.github_issue(args.repo, args.number, include_comments=args.include_comments)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ Issue #{result['number']}: {result['title']} [{result['state']}], "
                  f"{len(result.get('comments', []))} comments loaded")
            print(f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-file':
        result = gh.github_file_content(args.repo, args.path, ref=args.ref)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['path']} ({result['size_bytes']} bytes)\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-search-code':
        result = gh.github_search_code(args.query, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['total_count']} total matches ({len(result['results'])} returned)\n"
                  f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-search-repos':
        result = gh.github_search_repos(args.query, sort=args.sort, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['total_count']} total matches ({len(result['results'])} returned)\n"
                  f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'github-discussions':
        result = gh.github_discussions(args.repo, max_results=args.max)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['total_count']} discussions found\n   📂 Results saved to: {out_path.resolve()}\n")

    # ==========================================================================
    # Social/platform commands
    # ==========================================================================
    elif args.command == 'telegram-channel':
        if not args.channel and not args.query:
            print("❌ Error: provide either --channel NAME (direct mode) or --query \"...\" (search mode)\n")
        elif args.query:
            result = social.telegram_search(
                args.query, max_channels=args.max, posts_per_channel=args.posts_per_channel,
                max_fetch_retries=args.max_fetch_retries,
            )
            out_path = Path(args.out)
            _write_output(out_path, result)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif "error" in result:
                print(f"❌ Error: {result['error_message']}\n")
            else:
                print(f"✅ {result['channel_count']} public channels found matching '{args.query}'\n"
                      f"   📂 Results saved to: {out_path.resolve()}\n")
        else:
            result = social.telegram_channel(args.channel, max_results=args.max, max_fetch_retries=args.max_fetch_retries)
            out_path = Path(args.out)
            _write_output(out_path, result)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif "error" in result:
                print(f"❌ Error: {result['error_message']}\n")
            else:
                print(f"✅ {result['post_count_returned']} posts from @{result['channel']}\n"
                      f"   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'discord-channel':
        result = social.discord_channel_messages(args.channel_id, max_results=args.max, before_message_id=args.before)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['message_count']} messages\n   📂 Results saved to: {out_path.resolve()}\n")

    elif args.command == 'reddit-search':
        result = social.reddit_search(args.query, subreddit=args.subreddit, max_results=args.max, sort=args.sort)
        out_path = Path(args.out)
        _write_output(out_path, result)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif "error" in result:
            print(f"❌ Error: {result['error_message']}\n")
        else:
            print(f"✅ {result['result_count']} posts found\n   📂 Results saved to: {out_path.resolve()}\n")


if __name__ == '__main__':
    main()
