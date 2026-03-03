"""
workspace_inspector.cli

Public CLI facade.

Tests import this module and monkeypatch attributes like:
- cli.scan
- cli.datetime
- cli.main()

So cli.main() must route execution through the real implementation while
honoring monkeypatching done on this facade module.
"""

from __future__ import annotations

from . import main as _impl

# Expose patchable symbols on the facade.
scan = _impl.scan
format_size_binary = _impl.format_size_binary

# datetime is used for timestamps in JSON output (tests monkeypatch this).
datetime = _impl.datetime


def main() -> int:
    """
    Facade entrypoint.

    Before delegating to the implementation, sync patchable symbols so that
    monkeypatching `workspace_inspector.cli.scan/datetime` affects the code
    that runs inside the implementation module.
    """
    _impl.scan = scan
    _impl.datetime = datetime
    return _impl.main()


__all__ = [
    "main",
    "scan",
    "datetime",
    "format_size_binary",
]
