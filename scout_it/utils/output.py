"""Output utility functions for CLI commands."""

import time
from pathlib import Path
from typing import Any
from .. import output as output_mod


def _log_phase(label: str, phase: str, **details: Any) -> None:
    """Consistent one-line phase status for commands that don't already have
    a Rich-powered progress UI (web-search/image-search do, via
    EnterpriseSearchEngine/ImageSearchEngine). Prints e.g.:

        🔄 github-commit: fetching psf/requests@abc123...
        ✅ github-commit: done in 0.8s (3 files changed)
    """
    icon = {"started": "🔄", "completed": "✅", "failed": "❌"}.get(phase, "•")
    extra = " (" + ", ".join(f"{k}={v}" for k, v in details.items()) + ")" if details else ""
    print(f"{icon} {label}{extra}")


class _PhaseTimer:
    """Context manager pairing a 'started' log line with a timed
    'completed'/'failed' one, for the simpler (non-Rich-UI) commands."""

    def __init__(self, label: str, **start_details: Any):
        self.label = label
        self.start_details = start_details
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        _log_phase(self.label, "started", **self.start_details)
        return self

    def done(self, **details: Any) -> None:
        elapsed = time.time() - self.start_time
        _log_phase(self.label, "completed", seconds=f"{elapsed:.2f}", **details)

    def failed(self, **details: Any) -> None:
        elapsed = time.time() - self.start_time
        _log_phase(self.label, "failed", seconds=f"{elapsed:.2f}", **details)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def _write_output(out_path: Path, data: Any) -> None:
    """Write *data* to *out_path* as either line-length-safe JSON (default)
    or Markdown, based on the resolved extension. Path/format resolution
    itself (honoring --out/--markdown together, defaulting bare filenames
    under .scout-it/) happens once, centrally, right after argument
    parsing in main() -- see COMMAND_OUTPUT_STUBS and its use below.
    """
    if out_path.suffix.lower() == ".md":
        out_path.parent.mkdir(parents=True, exist_ok=True)
        title = out_path.stem.replace("_", " ").replace("-", " ").title()
        out_path.write_text(output_mod.render_markdown(data, title), encoding="utf-8")
    else:
        output_mod.write_json_output(out_path, data)
