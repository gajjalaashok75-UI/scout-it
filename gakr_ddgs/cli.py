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
    )
except Exception as e:
    raise ImportError("Could not import from gakr_ddgs modules: " + str(e))


# ---------------------------------------------------------------------------
# Output helpers — ensure no single JSON line exceeds 400 characters
# ---------------------------------------------------------------------------

def _word_wrap_string(value: str, max_line: int = 360) -> str:
    """Word-wrap a string at word boundaries so no line exceeds *max_line* chars."""
    if len(value) <= max_line:
        return value
    words = value.split()
    lines: List[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) > max_line:
            lines.append(current)
            current = word
        else:
            current += " " + word
    if current:
        lines.append(current)
    return "\n".join(lines)


def _wrap_long_strings(data: Any, max_line: int = 360, skip_keys: Optional[set] = None) -> Any:
    """Recursively word-wrap long string values in a JSON-serialisable structure.

    String values under keys listed in *skip_keys* are returned verbatim
    (useful for preserving HTML, long descriptions, or other structured text).
    """
    if isinstance(data, str):
        return _word_wrap_string(data, max_line)
    if isinstance(data, dict):
        skip_keys = skip_keys or set()
        return {
            k: v if k in skip_keys else _wrap_long_strings(v, max_line, skip_keys)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_wrap_long_strings(item, max_line, skip_keys) for item in data]
    return data


_MAX_LINE = 400


def _write_output(out_path: Path, data: Any) -> None:
    """Write JSON to *out_path*, wrapping lines so no line exceeds 400 chars.

    Long string values are word-wrapped *before* serialisation so the
    resulting JSON file stays readable and no single line exceeds 400
    characters.

    The following fields are preserved verbatim (not word-wrapped):
    - ``raw_html``  (prettified HTML — wrapping would break tag structure)
    - ``description``  (video descriptions / metadata — can be very long)
    - ``body``         (news article body — long-form text)
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    skip_keys = {"raw_html", "description", "body"}
    wrapped = _wrap_long_strings(data, _MAX_LINE - 60, skip_keys)
    json_str = json.dumps(wrapped, indent=2, ensure_ascii=False)
    # Turn escaped newlines (inserted by _wrap_long_strings) into real newlines
    json_str = json_str.replace("\\n", "\n")
    out_path.write_text(json_str, encoding="utf-8")


def _ddgs_list_search(
    method_name: str,
    query: str,
    max_results: int,
    options: Optional[Dict[str, Any]] = None,
    timeout: int = 25,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Run DDGS method with compatibility fallbacks across package versions."""
    start_time = time.time()
    params = _compact_options(options or {})
    params['max_results'] = max_results

    try:
        with DDGS(timeout=timeout) as ddgs:
            method = getattr(ddgs, method_name, None)
            if not callable(method):
                return [], {
                    'total': 0,
                    'success': 0,
                    'execution_time': time.time() - start_time,
                    'error': f"DDGS method '{method_name}' is unavailable in this installed version",
                }

            call_patterns = [
                lambda: list(method(keywords=query, **params)),
                lambda: list(method(query, **params)),
                lambda: list(method(query, max_results=max_results)),
                lambda: list(method(keywords=query, max_results=max_results)),
                lambda: list(method(query, max_results)),
                lambda: list(method(query))[:max_results],
            ]

            for call in call_patterns:
                try:
                    results = call()
                    return results, {
                        'total': len(results),
                        'success': len(results),
                        'execution_time': time.time() - start_time,
                    }
                except TypeError:
                    continue

            return [], {
                'total': 0,
                'success': 0,
                'execution_time': time.time() - start_time,
                'error': f"No compatible DDGS call signature worked for '{method_name}'",
            }
    except Exception as exc:
        return [], {
            'total': 0,
            'success': 0,
            'execution_time': time.time() - start_time,
            'error': 'DuckDuckGo request failed',
        }


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
):
    """
    Execute web search pipeline: search → extract → clean → filter.
    
    Args:
        query: Search query string
        max_results: Max results to fetch
        workers: Parallel workers
    
    Returns:
        (structured_results, stats) tuple with cleaned and structured content
    """
    # Phase 1: Search and extract
    engine = EnterpriseSearchEngine(max_workers=workers)
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
):
    """DuckDuckGo news search with full content extraction and cleaning.

    Returns structured results matching the web-search output format:
    each result goes through ``ExtractionEngine`` → ``process_results()``
    to produce cleaned content with quality signals and readability metrics.
    """
    # Phase 1: Get raw DDGS news results
    raw_results, search_stats = _ddgs_list_search(
        'news',
        query=query,
        max_results=max_results,
        options={
            'region': region,
            'safesearch': safesearch,
            'timelimit': timelimit,
        },
    )

    if not raw_results:
        return [], {'search_engine': search_stats, 'cleaner': {'total_input': 0, 'successful': 0, 'failed': 0, 'processed': 0}}

    # Phase 2: Fetch and extract full article content in parallel
    enriched_results = _extract_news_content(raw_results, max_workers=workers)

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
):
    """DuckDuckGo video search wrapper."""
    results, stats = _ddgs_list_search(
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
        if not _YOUTUBE_RE.search(url):
            return r
        try:
            meta = _fetch_youtube_metadata(url)
            if meta and "error" not in meta and meta.get("description"):
                r["description"] = meta["description"]
        except Exception:
            pass
        return r

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pool.map(_fetch_one, results)
    return results


def _extract_news_content(results: List[Dict[str, Any]], max_workers: int = 3) -> List[Dict[str, Any]]:
    """Fetch and extract full article content for news results in parallel.

    Takes raw DDGS news result dicts, fetches each URL, runs through
    ``ExtractionEngine``, and returns enriched dicts compatible with
    ``process_results()`` (i.e. containing ``main_content``,
    ``extraction_status``, ``confidence_score``, etc.).
    """
    if not results:
        return results
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _extract_one(r):
        url = r.get("url", "")
        if not url:
            r["extraction_status"] = "failed"
            r["main_content"] = ""
            return r
        try:
            resp = requests.get(
                url, timeout=10,
                headers={"User-Agent": random.choice(ExtractionEngine.USER_AGENTS)},
            )
            if resp.status_code != 200:
                r["extraction_status"] = "failed"
                r["main_content"] = ""
                return r
            engine = ExtractionEngine()
            content, method, confidence = engine.extract_content(url, resp.text)
            r["main_content"] = content
            r["extraction_method"] = method
            r["confidence_score"] = confidence
            r["extraction_status"] = "success" if content.strip() else "failed"
            r["content_word_count"] = len(content.split())
        except Exception:
            r["extraction_status"] = "failed"
            r["main_content"] = ""
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


def _fetch_youtube_metadata(video_id: str) -> Dict[str, Any]:
    """Fetch video metadata (title, description, channel, etc.) from YouTube page."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text

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


def video_extract(url: str, subtitle_lang: str = "en", include_segments: bool = False) -> Dict[str, Any]:
    """Extract full details from a video URL.

    Supports YouTube URLs. Non-YouTube URLs receive a friendly notice.

    :param url: The video URL to extract.
    :param subtitle_lang: Preferred subtitle language code (default ``"en"``).
    :param include_segments: If True, include subtitle segment timestamps in output.
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
    meta = _fetch_youtube_metadata(video_id)
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
):
    """
    Fetch a single URL and extract/clean its content.
    
    Enhanced version of fatchurl with better naming.

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
        headers = {
            "User-Agent": random.choice(ExtractionEngine.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        response.raise_for_status()
        final_url = str(response.url)

        # Truncate HTML response if max_size is specified
        response_text = response.text
        max_size_bytes = _parse_size_string(max_size)
        if max_size_bytes and len(response.content) > max_size_bytes:
            # Truncate HTML content to max_size bytes
            response_text = response.content[:max_size_bytes].decode('utf-8', errors='ignore')

        extractor = ExtractionEngine()
        main_content, method, confidence = extractor.extract_content(
            final_url,
            response_text,
            timeout=timeout,
        )

        # Apply max_chars constraint if specified
        if max_chars and main_content and len(main_content) > max_chars:
            main_content = main_content[:max_chars]

        elapsed = time.time() - start_time
        title = _extract_html_title(response_text) or final_url

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
    url_parser.add_argument('--timeout', type=int, default=5, help='Extraction timeout in seconds')
    url_parser.add_argument('--max-chars', type=int, default=None, help='Maximum characters to extract (e.g., 10000)')
    url_parser.add_argument('--max-size', type=str, default=None, help='Maximum response size (e.g., 100kb, 1mb, 500mb)')
    url_parser.add_argument('--out', '-o', default='url_fetch_result.json', help='Output file')
    url_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')
    url_parser.add_argument('--raw-html', action='store_true', help='Return raw HTML (prettified) instead of extracted/cleaned content')

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
            'Examples:\\n'
            '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"\\n'
            '  data-scout video-extract --url "https://youtu.be/dQw4w9WgXcQ"\\n'
            '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --subtitle-lang fr\\n'
            '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --segments\\n'
        '  data-scout video-extract --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    video_extract_parser.add_argument('--url', required=True, help='Video URL to extract (e.g., https://www.youtube.com/watch?v=VIDEO_ID)')
    video_extract_parser.add_argument('--subtitle-lang', default='en', help='Preferred subtitle language code (default: en)')
    video_extract_parser.add_argument('--segments', action='store_true', help='Include subtitle segments with timestamps (default: off)')
    video_extract_parser.add_argument('--out', '-o', default='video_extract_results.json', help='Output file (default: video_extract_results.json)')
    video_extract_parser.add_argument('--json', action='store_true', help='Output raw JSON to stdout')

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
        result = video_extract(args.url, subtitle_lang=lang, include_segments=include_segments)

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
            wrapped = _wrap_long_strings(output, _MAX_LINE - 60, skip_keys={"description"})
            print(json.dumps(wrapped, indent=2, ensure_ascii=False).replace('\\n', '\n'))

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
        )

        output = {
            'url': args.url,
            'search_type': 'fetch',
            'parameters': {
                'timeout': args.timeout,
                'max_chars': args.max_chars,
                'max_size': args.max_size,
                'raw_html': args.raw_html,
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


if __name__ == '__main__':
    main()
