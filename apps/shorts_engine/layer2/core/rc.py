from __future__ import annotations

from .errors import ErrorType

RC_OK = 0
RC_RENDER_FAIL = 1
RC_VALIDATION_FAIL = 2
RC_IO_FAIL = 3


def rc_for_error_type(error_type: ErrorType | None) -> int:
    if error_type is None:
        return RC_RENDER_FAIL

    if error_type == "validation_error":
        return RC_VALIDATION_FAIL
    if error_type == "io_error":
        return RC_IO_FAIL
    if error_type == "render_error":
        return RC_RENDER_FAIL
    if error_type == "unknown_error":
        return RC_RENDER_FAIL

    # Defensive fallback
    return RC_RENDER_FAIL
