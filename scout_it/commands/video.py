"""Video search and extraction command module — unified discovery -> rank -> output.

Mirrors the web-search/news-search unified flow: discover candidate videos
from multiple sources (DuckDuckGo Videos + video RSS category feeds, e.g.
YouTube channel feeds), rank them with the shared ``rank_candidates_initial``
scorer, and return the top results.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

from ..extraction import (
    ExtractionEngine,
    _ddgs_list_search_with_retry,
    fetch_resilient,
)
from ..staged_ranker import rank_candidates_initial
from .video_category_providers import fetch_video_category_feeds

logger = logging.getLogger(__name__)

# YouTube URL pattern - matches youtube.com/watch?v=VIDEO_ID or youtu.be/VIDEO_ID
_YOUTUBE_RE = re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})')


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
    categories: Optional[Sequence[str]] = None,
    include_rss: bool = False,
    top_k: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Execute the unified video search pipeline: discover -> rank -> output.

    Discovery sources (merged before ranking):
      1. DuckDuckGo Videos (always).
      2. Video RSS category feeds (YouTube channel feeds) when ``categories``
         is given or ``include_rss=True``.

    Ranking uses the shared ``rank_candidates_initial`` scorer (title/body
    relevance, source quality, recency) - the same one used by
    web-search/news-search.

    Args:
        query: Search query string.
        max_results: Max videos to fetch from DuckDuckGo.
        categories: Video RSS categories to include (e.g. ``["technology","science"]``).
        include_rss: Force RSS discovery even without ``categories``.
        top_k: Number of ranked results to return (defaults to ``max_results``).

    Returns:
        ``(video_results, stats)`` tuple with ranked video metadata.
    """
    ddgs_results, ddgs_stats = _ddgs_list_search_with_retry(
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

    # Normalize DDGS video results into ranking candidate shape.
    candidates: List[Dict[str, Any]] = []
    for r in ddgs_results:
        url = r.get("content") or r.get("url") or ""
        candidates.append({
            "title": r.get("title", ""),
            "content": url,
            "url": url,
            "description": r.get("description", ""),
            "body": r.get("description", "") or r.get("title", ""),
            "snippet": r.get("description", ""),
            "thumbnail": r.get("image") or r.get("thumbnail", ""),
            "image": r.get("image") or r.get("thumbnail", ""),
            "source": "DuckDuckGo",
            "publish_date": r.get("date", "") or r.get("published", ""),
        })

    rss_count = 0
    rss_categories = list(categories) if categories else []
    if rss_categories:
        rss_entries = fetch_video_category_feeds(rss_categories, query, max_results=max_results)
        candidates.extend(rss_entries)
        rss_count += len(rss_entries)
    elif include_rss:
        # No categories given: pull a small default set of popular channels.
        from .video_category_providers import VIDEO_CATEGORY_PROVIDERS
        default_cats = list(VIDEO_CATEGORY_PROVIDERS.keys())[:3]
        if default_cats:
            rss_entries = fetch_video_category_feeds(default_cats, query, max_results=max_results)
            candidates.extend(rss_entries)
            rss_count += len(rss_entries)

    # ---- Rank (shared scorer) ----
    limit = int(top_k) if top_k is not None else int(max_results)
    ranked = rank_candidates_initial(candidates, query, top_k=max(limit, len(candidates)))

    # Dedupe by video URL and emit ranked output.
    seen: set = set()
    output: List[Dict[str, Any]] = []
    for entry in ranked:
        url = entry.get("url") or entry.get("content") or ""
        # Keep URL-less entries too (e.g. stub DDGS results in tests) by
        # falling back to a title-based key so they are not silently dropped.
        key = url or f"title:{entry.get('title', '')}"
        if not key or key in seen:
            continue
        seen.add(key)
        output.append({
            "position": len(output) + 1,
            "title": entry.get("title", ""),
            "content": url,
            "url": url,
            "description": entry.get("description", ""),
            "body": entry.get("body", ""),
            "snippet": entry.get("snippet", ""),
            "image": entry.get("image") or entry.get("thumbnail", ""),
            "thumbnail": entry.get("thumbnail") or entry.get("image", ""),
            "source": entry.get("source", "DuckDuckGo"),
            "publish_date": entry.get("publish_date", ""),
            "initial_rank_score": entry.get("initial_rank_score", 0.0),
            "rank_breakdown": entry.get("rank_breakdown", {}),
        })
        if len(output) >= limit:
            break

    stats = {
        'search_engine': ddgs_stats,
        'pipeline': 'unified',
        'ddgs_candidates': len(ddgs_results),
        'rss_candidates': rss_count,
        'total_candidates': len(candidates),
        'ranked_output': len(output),
        'rss_categories': rss_categories,
    }

    print(f"🎥 Found {len(output)} ranked videos for query: {query} "
          f"(DDGS: {len(ddgs_results)}, RSS: {rss_count})")
    return output, stats


def _enhance_video_descriptions(results: List[Dict[str, Any]], max_workers: int = 5) -> List[Dict[str, Any]]:
    """Enhance video results with full descriptions from YouTube.

    DuckDuckGo ``videos()`` returns descriptions truncated at ~200-300
    characters (noticeable by trailing ``...``).  For YouTube videos this
    fetches the full description from the YouTube page and replaces the
    truncated one *in-place*.
    """
    if not results:
        return results

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
        list(pool.map(_fetch_one, results))
    return results


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
        return {"error": "invalid_url", "error_message": "No URL provided. Use --url to specify a video URL.", "hint": "Example: scout-it video-extract --url \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\""}

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
