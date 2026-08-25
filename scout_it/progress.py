"""
Lightweight progress reporting for search pipelines.

Provides:
  - make_console(): shared rich Console (falls back to a stub if rich is absent)
  - get_reporter(): singleton reporter with .phase(name) and .item_done(done, total)
"""
import sys
import threading
from typing import Optional

try:
    from rich.console import Console
except ImportError:  # pragma: no cover - rich is a hard dep, defensive only
    Console = None

_lock = threading.Lock()
_console: Optional["Console"] = None
_reporter: Optional["ProgressReporter"] = None


def make_console():
    """Return the shared rich Console instance."""
    global _console
    if _console is None:
        if Console is not None:
            _console = Console()
        else:
            _console = _FallbackConsole()
    return _console


class _FallbackConsole:
    """Minimal stand-in for rich.Console when rich is unavailable."""

    def print(self, *args, **kwargs):
        print(*args, file=sys.stderr)


class ProgressReporter:
    """Phase + item progress reporter. Safe to call from worker threads."""

    def __init__(self, console=None):
        self._console = console if console is not None else make_console()
        self._lock = threading.Lock()
        self._phase: Optional[str] = None

    def phase(self, name: str) -> None:
        """Announce a pipeline phase (e.g. discovery, ranking, extraction)."""
        with self._lock:
            self._phase = name
            self._console.print(f"[cyan]▸ {name}[/cyan]" if Console else f"» {name}")

    def item_done(self, done: int, total: int) -> None:
        """Report per-item completion within the current phase."""
        with self._lock:
            label = self._phase or "processing"
            self._console.print(f"  {label}: {done}/{total}")


def get_reporter() -> ProgressReporter:
    """Return the process-wide singleton ProgressReporter."""
    global _reporter
    with _lock:
        if _reporter is None:
            _reporter = ProgressReporter()
        return _reporter
