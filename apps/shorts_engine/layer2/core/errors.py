from __future__ import annotations

from typing import Literal

ErrorType = Literal[
    "validation_error",
    "io_error",
    "render_error",
    "unknown_error",
]


def classify_exception(e: BaseException) -> ErrorType:
    # Keep this simple in v0.5; grow later.
    name = type(e).__name__.lower()

    if "validation" in name:
        return "validation_error"
    if isinstance(e, (FileNotFoundError, PermissionError, OSError)):
        return "io_error"

    # subprocess / ffmpeg failures often end up as CalledProcessError
    try:
        import subprocess
        if isinstance(e, subprocess.CalledProcessError):
            return "render_error"
    except Exception:
        pass

    return "unknown_error"
