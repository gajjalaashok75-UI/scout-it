"""Tests for scout_it.output: JSON line-length safety, --out/--markdown
path resolution, and Markdown rendering."""
import json
from pathlib import Path

import pytest

from scout_it import output as om


class TestChunkText:
    def test_short_text_unchanged(self):
        assert om._chunk_text("hello world", 500) == ["hello world"]

    def test_long_text_chunked_under_limit(self):
        text = " ".join(["word"] * 300)
        chunks = om._chunk_text(text, 500)
        assert all(len(c) <= 500 for c in chunks)
        assert " ".join(chunks) == text

    def test_preserves_paragraph_breaks_when_wrapping_kicks_in(self):
        # Chunking is length-triggered; pad past the 500-char threshold so
        # per-paragraph splitting actually runs, then check the paragraph
        # boundary survives as its own chunk.
        text = ("word " * 150) + "\n\n" + ("word " * 150)
        chunks = om._chunk_text(text, 500)
        assert "" in chunks

    def test_single_giant_word_hard_split(self):
        text = "x" * 1200
        chunks = om._chunk_text(text, 500)
        assert all(len(c) <= 500 for c in chunks)
        assert "".join(chunks) == text


class TestApplyLineLimit:
    def test_long_string_becomes_array(self):
        data = {"body": " ".join(["word"] * 300)}
        result = om._apply_line_limit(data, 500, om._NO_CHUNK_KEYS)
        assert isinstance(result["body"], list)

    def test_skip_keys_untouched(self):
        long_url = "https://example.com/" + ("a" * 600)
        data = {"url": long_url}
        result = om._apply_line_limit(data, 500, om._NO_CHUNK_KEYS)
        assert result["url"] == long_url

    def test_short_string_untouched(self):
        data = {"title": "short"}
        result = om._apply_line_limit(data, 500, om._NO_CHUNK_KEYS)
        assert result["title"] == "short"

    def test_recurses_into_nested_lists_and_dicts(self):
        data = {"results": [{"body": " ".join(["word"] * 300)}]}
        result = om._apply_line_limit(data, 500, om._NO_CHUNK_KEYS)
        assert isinstance(result["results"][0]["body"], list)


class TestWriteJsonOutput:
    def _tmp(self):
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)
        return Path(path)

    def test_produces_valid_json_with_chunked_long_field(self):
        out = self._tmp()
        try:
            long_text = " ".join(["word"] * 300)
            om.write_json_output(out, {"body": long_text})
            loaded = json.loads(out.read_text(encoding="utf-8"))
            assert isinstance(loaded["body"], list)
            assert " ".join(loaded["body"]) == long_text
        finally:
            out.unlink(missing_ok=True)

    def test_no_line_in_file_exceeds_reasonable_bound(self):
        out = self._tmp()
        try:
            long_text = " ".join(["word"] * 1000)
            om.write_json_output(out, {"body": long_text})
            text = out.read_text(encoding="utf-8")
            for line in text.split("\n"):
                # JSON quoting/escaping adds a little overhead beyond the raw 500-char limit
                assert len(line) <= 520, f"line too long: {len(line)} chars"
        finally:
            out.unlink(missing_ok=True)


class TestResolveOutputPath:
    def test_default_no_markdown(self):
        r = om.resolve_output_path(".data-scout/web_search_results.json", False, "web_search_results")
        assert r["format"] == "json"
        assert r["path"] == Path(".data-scout/web_search_results.json")

    def test_default_with_markdown_flag(self):
        r = om.resolve_output_path(".data-scout/web_search_results.json", True, "web_search_results")
        assert r["format"] == "markdown"
        assert r["path"] == Path(".data-scout/web_search_results.md")

    def test_explicit_json_out_with_markdown_flag_errors(self):
        r = om.resolve_output_path("custom.json", True, "web_search_results")
        assert "error" in r

    def test_explicit_md_out_without_markdown_flag(self):
        r = om.resolve_output_path("custom.md", False, "web_search_results")
        assert r["format"] == "markdown"
        assert r["path"] == Path("custom.md")

    def test_bare_filename_lands_under_scout_it_dir(self):
        r = om.resolve_output_path("myfile.json", False, "web_search_results")
        assert r["path"] == Path(".data-scout/myfile.json")

    def test_path_with_directory_honored_as_is(self):
        r = om.resolve_output_path("output/custom.json", False, "web_search_results")
        assert r["path"] == Path("output/custom.json")

    def test_markdown_flag_with_custom_non_json_out_forces_md_extension(self):
        r = om.resolve_output_path("custom.txt", True, "web_search_results")
        assert r["format"] == "markdown"
        assert r["path"].suffix == ".md"


class TestRenderMarkdown:
    def test_simple_dict(self):
        md = om.render_markdown({"title": "hello", "count": 5}, "Test")
        assert "# Test" in md
        assert "hello" in md
        assert "5" in md

    def test_table_for_uniform_list_of_dicts(self):
        data = {"results": [{"name": "a", "value": 1}, {"name": "b", "value": 2}]}
        md = om.render_markdown(data, "Test")
        assert "| Name | Value |" in md
        assert "| a | 1 |" in md

    def test_patch_lines_rendered_with_line_numbers(self):
        data = {"patch_lines": [
            {"type": "hunk_header", "text": "@@ -1 +1 @@", "old_line": None, "new_line": None},
            {"type": "removed", "text": "old", "old_line": 5, "new_line": None},
            {"type": "added", "text": "new", "old_line": None, "new_line": 5},
        ]}
        md = om.render_markdown(data, "Commit")
        assert "Old #" in md and "New #" in md
        assert "| 5 |" in md
        assert "`old`" in md and "`new`" in md

    def test_code_like_key_renders_as_fenced_block(self):
        md = om.render_markdown({"content": "print('hello')"}, "File")
        assert "```" in md
        assert "print('hello')" in md

    def test_empty_list_as_top_level_document(self):
        md = om.render_markdown([], "Test")
        assert "(none)" in md

    def test_empty_list_as_dict_value_renders_bracket_notation(self):
        md = om.render_markdown({"items": []}, "Test")
        assert "[]" in md


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
