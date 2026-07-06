#!/usr/bin/env python3
"""
📄 OUTPUT FORMATTING — JSON line-length safety, .data-scout/ paths, Markdown export
======================================================================================

Three responsibilities, used by every CLI command:

1. **Line-length-safe JSON** (`write_json_output`): long string values (a
   13KB+ single-line "main_content" blob, for example) are broken into an
   array of <=500-char chunks at word boundaries, so no single line in the
   output *file* is unreasonably long — while staying 100% standard, valid
   JSON the whole time (a JSON array simply serializes one element per
   line under ``indent=2``; nothing here touches escaping rules the way the
   old, broken word-wrap-then-blind-replace approach did). Diff `patch`
   text is deliberately left alone here since `github-commit`/`github-pr`
   already provide a proper structured `patch_lines` breakdown instead.

2. **Output path resolution** (`resolve_output_path`): honors ``--out`` /
   ``--markdown`` together, enforces that they don't contradict each other
   (``--markdown`` with an explicit ``--out ....json`` is an error), and
   defaults bare filenames to live under ``.data-scout/`` instead of the
   current directory.

3. **Markdown rendering** (`render_markdown`): a generic (works for any
   command's output shape), reasonably good renderer — tables for lists of
   uniform flat dicts, fenced code blocks for diff/code/file content,
   headers for nested sections.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_OUTPUT_DIR = ".data-scout"
MAX_LINE_CHARS = 500


def parse_size_string(size_str: Optional[str]) -> Optional[int]:
    """Parse a size string like '100kb', '1mb', '2gb' into bytes. Returns
    None if *size_str* is falsy or doesn't match a recognized unit."""
    if not size_str:
        return None
    size_str = size_str.strip().lower()
    units = {'b': 1, 'kb': 1024, 'mb': 1024 ** 2, 'gb': 1024 ** 3}
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


def validate_max_chars_max_size(max_chars: Optional[int], max_size: Optional[str]) -> Optional[str]:
    """Shared validation for the --max-chars / --max-size pair used by
    fetch-url, github-repo (--file-tree), and github-folder: at most one may
    be given. Returns an error message, or None if valid."""
    if max_chars is not None and max_size is not None:
        return (
            "Cannot use both --max-chars and --max-size together. Use only ONE:\n"
            "   • --max-chars N   (limit by character count)\n"
            "   • --max-size 5mb  (limit by size, e.g. 500kb / 5mb / 1gb)\n"
            "   Omit both to get the full, untruncated content."
        )
    return None

# Keys whose string content should NOT be mechanically chunked at 500 chars,
# either because they already have a better structured representation
# (patch -> patch_lines) or because chunking would break something meant to
# be copy-pasted/parsed as a single unit (URLs, hashes, raw_html).
_NO_CHUNK_KEYS = {"patch", "raw_html", "url", "final_url", "href", "download_url", "raw_url", "html_url"}

# Keys that should render as fenced code blocks in Markdown.
_CODE_LIKE_KEYS = {"patch", "content", "raw_html"}


# ---------------------------------------------------------------------------
# 1. Line-length-safe JSON
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_len: int = MAX_LINE_CHARS) -> List[str]:
    """Break long text into <=max_len chunks at word/paragraph boundaries.
    Existing newlines become chunk boundaries too, so paragraph structure
    survives (each chunk is still just a JSON array element — no data is
    lost, it's purely a presentation split)."""
    if len(text) <= max_len:
        return [text]

    chunks: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            chunks.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            # A single "word" longer than max_len (e.g. a giant URL/hash) gets hard-split.
            while len(word) > max_len:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(word[:max_len])
                word = word[max_len:]
            candidate = f"{current} {word}" if current else word
            if len(candidate) > max_len:
                if current:
                    chunks.append(current)
                current = word
            else:
                current = candidate
        chunks.append(current)
    return chunks


def _apply_line_limit(data: Any, max_len: int, skip_keys: set, _key: Optional[str] = None) -> Any:
    if isinstance(data, str):
        if _key in skip_keys or len(data) <= max_len:
            return data
        return _chunk_text(data, max_len)
    if isinstance(data, dict):
        return {k: _apply_line_limit(v, max_len, skip_keys, k) for k, v in data.items()}
    if isinstance(data, list):
        return [_apply_line_limit(item, max_len, skip_keys, _key) for item in data]
    return data


def write_json_output(out_path: Path, data: Any, max_line: int = MAX_LINE_CHARS) -> None:
    """Write *data* as clean, valid, standard, line-length-safe JSON.

    Every string field longer than *max_line* characters becomes an array
    of <=max_line chunks instead of one giant single-line value (except a
    small set of fields where chunking would be actively unhelpful, e.g.
    URLs or ``patch`` which already has a structured ``patch_lines``
    counterpart). This never produces invalid JSON — see the module
    docstring and the ``_write_output`` history in CHANGELOG.md for why
    that matters.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    limited = _apply_line_limit(data, max_line, _NO_CHUNK_KEYS)
    json_str = json.dumps(limited, indent=2, ensure_ascii=False)
    out_path.write_text(json_str, encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. Output path resolution (--out / --markdown)
# ---------------------------------------------------------------------------

def resolve_output_path(out_arg: str, markdown_flag: bool, default_stub: str) -> Dict[str, Any]:
    """Resolve final output path + format from --out/--markdown.

    *out_arg* is whatever ``--out`` resolved to (including its own default,
    e.g. ``.data-scout/web_search_results.json``). *default_stub* is the
    command's base name (e.g. ``"web_search_results"``), used to rebuild a
    sensible default path if ``--markdown`` forces a different extension
    than the default suggests.

    Returns ``{"path": Path, "format": "json"|"markdown"}`` or
    ``{"error": "..."}``.
    """
    out_path = Path(out_arg)
    ext = out_path.suffix.lower()
    is_default_path = (out_arg == f"{DEFAULT_OUTPUT_DIR}/{default_stub}.json")

    if markdown_flag and ext == ".json" and not is_default_path:
        return {
            "error": (
                f"--markdown conflicts with --out '{out_arg}' (ends in .json). "
                f"Either drop --markdown, or point --out at a .md file "
                f"(e.g. --out {out_path.with_suffix('.md')}), or omit --out entirely "
                f"to get the default Markdown path."
            )
        }

    if markdown_flag:
        final_path = Path(DEFAULT_OUTPUT_DIR) / f"{default_stub}.md" if is_default_path else out_path.with_suffix(".md")
        return {"path": final_path, "format": "markdown"}

    if ext == ".md":
        return {"path": out_path, "format": "markdown"}

    # Bare filename with no directory component still lands under .data-scout/
    if not out_path.is_absolute() and out_path.parent == Path("."):
        out_path = Path(DEFAULT_OUTPUT_DIR) / out_path.name

    return {"path": out_path, "format": "json"}


# ---------------------------------------------------------------------------
# 3. Markdown rendering
# ---------------------------------------------------------------------------

def _titleize(key: str) -> str:
    return key.replace("_", " ").strip().capitalize()


def _is_flat_table_row(item: Any) -> bool:
    return isinstance(item, dict) and all(not isinstance(v, (dict, list)) for v in item.values())


def _format_scalar(value: Any) -> str:
    if value is None:
        return "_(none)_"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value.replace("\n", " ").replace("|", "\\|") if len(value) < 300 else value[:297].replace("\n", " ") + "..."
    return str(value)


def _render_table(items: List[Dict[str, Any]]) -> str:
    keys: List[str] = []
    for item in items:
        for k in item.keys():
            if k not in keys:
                keys.append(k)
    keys = keys[:8]  # keep tables readable; extra fields still show via nested rendering elsewhere
    header = "| " + " | ".join(_titleize(k) for k in keys) + " |"
    sep = "|" + "|".join(["---"] * len(keys)) + "|"
    rows = []
    for item in items:
        rows.append("| " + " | ".join(_format_scalar(item.get(k)) for k in keys) + " |")
    return "\n".join([header, sep] + rows)


def _render_patch_lines(patch_lines: List[Dict[str, Any]]) -> str:
    out = []
    for line in patch_lines:
        t = line.get("type")
        text = line.get("text", "")
        old_ln = line.get("old_line")
        new_ln = line.get("new_line")
        if t == "added":
            out.append(f"+{text}")
        elif t == "removed":
            out.append(f"-{text}")
        elif t == "hunk_header":
            out.append(text)
        else:
            out.append(f" {text}")
    return "```diff\n" + "\n".join(out) + "\n```"


def _render_patch_lines_with_line_numbers(patch_lines: List[Dict[str, Any]]) -> str:
    """A second, table-style rendering alongside the diff block, since a
    fenced ```diff block can't show line-number gutters without breaking
    the leading +/-/space character syntax highlighters rely on."""
    rows = ["| Old # | New # | | Line |", "|---|---|---|---|"]
    for line in patch_lines:
        t = line.get("type")
        text = _format_scalar(line.get("text", ""))
        old_ln = line.get("old_line") or ""
        new_ln = line.get("new_line") or ""
        marker = {"added": "+", "removed": "-", "hunk_header": "", "context": " "}.get(t, " ")
        if t == "hunk_header":
            rows.append(f"| | | | `{text}` |")
        else:
            rows.append(f"| {old_ln} | {new_ln} | {marker} | `{text}` |")
    return "\n".join(rows)


def _render_value(value: Any, key: Optional[str], level: int) -> str:
    heading = "#" * min(level, 6)

    if key == "patch_lines" and isinstance(value, list) and value:
        return _render_patch_lines_with_line_numbers(value)

    if isinstance(value, dict):
        if not value:
            return "_(empty)_"
        parts = []
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                parts.append(f"{heading} {_titleize(k)}\n\n{_render_value(v, k, level + 1)}")
            elif k in _CODE_LIKE_KEYS and isinstance(v, str) and v:
                lang = "diff" if k == "patch" else ""
                parts.append(f"**{_titleize(k)}:**\n\n```{lang}\n{v}\n```")
            else:
                parts.append(f"- **{_titleize(k)}:** {_format_scalar(v)}")
        return "\n\n".join(parts)

    if isinstance(value, list):
        if not value:
            return "_(none)_"
        if all(_is_flat_table_row(item) for item in value):
            return _render_table(value)
        parts = []
        for i, item in enumerate(value, 1):
            if isinstance(item, (dict, list)):
                label = item.get("title") or item.get("name") or item.get("filename") or item.get("path") if isinstance(item, dict) else None
                parts.append(f"{heading} {i}. {label or ''}\n\n{_render_value(item, key, level + 1)}")
            else:
                parts.append(f"- {_format_scalar(item)}")
        return "\n\n".join(parts)

    if key in _CODE_LIKE_KEYS and isinstance(value, str) and value:
        return f"```\n{value}\n```"

    return _format_scalar(value)


def render_markdown(data: Any, title: str) -> str:
    """Render any command's result dict as a Markdown document."""
    body = _render_value(data, None, level=2)
    return f"# {title}\n\n{body}\n"


# ---------------------------------------------------------------------------
# Unified entry point used by every CLI dispatch block
# ---------------------------------------------------------------------------

def finalize_and_write(args: Any, data: Any, default_stub: str, title: str) -> Optional[str]:
    """Resolve --out/--markdown, write the file, and return an error message
    (or None on success). On success, ``args._resolved_out_path`` is set so
    callers can print where the file went."""
    resolved = resolve_output_path(args.out, getattr(args, "markdown", False), default_stub)
    if "error" in resolved:
        return resolved["error"]

    out_path: Path = resolved["path"]
    if resolved["format"] == "markdown":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(data, title), encoding="utf-8")
    else:
        write_json_output(out_path, data)

    args._resolved_out_path = out_path
    return None
