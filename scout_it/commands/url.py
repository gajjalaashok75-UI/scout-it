"""URL fetching command module."""

import re
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..extraction import ExtractionEngine, fetch_resilient
from ..cleaner import process_results
from .. import output as output_mod


def _extract_html_title(html_text: str) -> str:
    """Extract page title from HTML text."""
    if not html_text:
        return ""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    from html import unescape
    title = re.sub(r"<[^>]+>", " ", match.group(1))
    return unescape(re.sub(r"\s+", " ", title)).strip()


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
    enable_alternate_source: bool = False,
    enable_persistent_profile: bool = False,
    browser_profile_name: str = 'default',
) -> Dict[str, Any]:
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
        (``pip install scout-it[js-render]`` + ``playwright install chromium``).
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
            enable_alternate_source=enable_alternate_source,
            enable_persistent_profile=enable_persistent_profile,
            browser_profile_name=browser_profile_name,
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
        max_size_bytes = output_mod.parse_size_string(max_size)
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

        # Fallback: when HTML-based extraction yields very little (< 50 words),
        # use Playwright's document.body.innerText which captures JS-rendered
        # text that the HTML-based extractors may miss (anti-bot shells, SPAs).
        if len(main_content.strip().split()) < 50:
            rendered = outcome.get("rendered_text", "") or ""
            if len(rendered.strip().split()) > len(main_content.strip().split()):
                main_content = rendered
                method = f"rendered-text ({fetch_tier})"

        # Apply max_chars constraint if specified
        if max_chars and main_content and len(main_content) > max_chars:
            main_content = main_content[:max_chars]

        elapsed = time.time() - start_time

        if raw_html:
            # Return raw HTML — skip extraction and cleaner pipeline entirely
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


def fatchurl(url: str, timeout: int = 25) -> Dict[str, Any]:
    """Deprecated: Use fetch_url() instead.
    
    This function is kept for backward compatibility but will be removed in a future version.
    """
    warnings.warn(
        "fatchurl() is deprecated (typo). Use fetch_url() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return fetch_url(url, timeout)
