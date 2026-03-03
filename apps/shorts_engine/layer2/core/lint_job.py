from __future__ import annotations

import re
from typing import Any

from .presets import load_preset, PresetError


DEFAULT_MAX_LINES = 2
DEFAULT_MAX_CHARS = 26
DEFAULT_MIN_DURATION = 3.0
DEFAULT_MAX_DURATION = 90.0
DEFAULT_MAX_CPS_WARN = 22.0


def _finding(
    severity: str,
    code: str,
    message: str,
    path: str,
    value: Any = None,
) -> dict[str, Any]:
    out = {
        "severity": severity,
        "code": code,
        "message": message,
        "path": path,
    }
    if value is not None:
        out["value"] = value
    return out


def _iter_subtitle_items(job: dict[str, Any]) -> list[dict[str, Any]]:
    subs = job.get("subtitles")
    if not isinstance(subs, dict):
        return []
    items = subs.get("items")
    if not isinstance(items, list):
        return []
    return [it for it in items if isinstance(it, dict)]


def _contains_invalid_control_chars(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if o < 32 and ch not in ("\n", "\t", "\r"):
            return True
    return False


def _simulate_wrap(text: str, max_chars: int) -> tuple[list[str], bool]:
    paragraphs = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines: list[str] = []
    long_word = False
    for p in paragraphs:
        p = " ".join(p.split())
        if not p:
            continue
        words = p.split(" ")
        cur = ""
        for w in words:
            if len(w) > max_chars:
                long_word = True
            if not cur:
                cur = w
                continue
            cand = cur + " " + w
            if len(cand) <= max_chars:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    if not lines:
        lines = [""]
    return lines, long_word


def _resolve_constraints(job: dict[str, Any], preset: dict[str, Any] | None) -> tuple[int, int, str | None]:
    preset_name: str | None = None
    p = preset
    if p is None:
        pv = job.get("preset")
        if isinstance(pv, str) and pv.strip():
            try:
                p = load_preset(pv.strip())
                preset_name = pv.strip()
            except PresetError:
                p = None
                preset_name = pv.strip()
    else:
        pn = p.get("name")
        if isinstance(pn, str) and pn.strip():
            preset_name = pn.strip()

    max_lines = DEFAULT_MAX_LINES
    max_chars = DEFAULT_MAX_CHARS
    if isinstance(p, dict):
        subs = p.get("subtitles")
        if isinstance(subs, dict):
            ml = subs.get("max_lines")
            mc = subs.get("max_chars_per_line")
            if isinstance(ml, int) and ml >= 1:
                max_lines = ml
            if isinstance(mc, int) and mc >= 8:
                max_chars = mc
    return max_lines, max_chars, preset_name


def lint_job(job: dict[str, Any], preset: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    info: list[dict[str, Any]] = []

    if not isinstance(job, dict):
        errors.append(_finding("error", "JOB_TYPE_INVALID", "job must be object", "$"))
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "summary": {"error_count": len(errors), "warn_count": len(warnings), "info_count": len(info)},
        }

    max_lines, max_chars, preset_name = _resolve_constraints(job, preset)
    info.append(
        _finding(
            "info",
            "LINT_CONSTRAINTS",
            "derived subtitle constraints",
            "$.subtitles",
            {"max_lines": max_lines, "max_chars_per_line": max_chars, "preset": preset_name},
        )
    )

    out = job.get("output")
    out_path = out.get("path") if isinstance(out, dict) else None
    if not isinstance(out_path, str) or not out_path.strip():
        errors.append(_finding("error", "OUTPUT_PATH_MISSING", "output.path is required", "$.output.path"))
    elif not out_path.lower().endswith(".mp4"):
        errors.append(_finding("error", "OUTPUT_PATH_EXT_INVALID", "output.path must end with .mp4", "$.output.path", out_path))

    video = job.get("video") if isinstance(job.get("video"), dict) else {}
    duration = video.get("duration_sec")
    duration_f: float | None = None
    if isinstance(duration, (int, float)):
        duration_f = float(duration)
        if duration_f < DEFAULT_MIN_DURATION or duration_f > DEFAULT_MAX_DURATION:
            errors.append(
                _finding(
                    "error",
                    "DURATION_OUT_OF_RANGE",
                    f"video.duration_sec must be between {DEFAULT_MIN_DURATION:g} and {DEFAULT_MAX_DURATION:g}",
                    "$.video.duration_sec",
                    duration_f,
                )
            )

    items = _iter_subtitle_items(job)
    if len(items) == 0:
        errors.append(_finding("error", "SUBTITLES_EMPTY", "subtitles.items must include at least one item", "$.subtitles.items"))

    total_chars = 0
    normalized_texts: list[str] = []
    for i, it in enumerate(items):
        tx = it.get("text")
        p = f"$.subtitles.items[{i}].text"
        if not isinstance(tx, str) or not tx.strip():
            errors.append(_finding("error", "SUBTITLE_TEXT_EMPTY", "subtitle text must be non-empty", p))
            continue
        t = tx.strip()
        if _contains_invalid_control_chars(t):
            errors.append(_finding("error", "TEXT_CONTROL_CHAR", "text contains invalid unicode control character", p))

        wrapped, long_word = _simulate_wrap(t, max_chars)
        if long_word:
            errors.append(
                _finding(
                    "error",
                    "SUBTITLE_WORD_TOO_LONG",
                    f"single word exceeds max_chars_per_line={max_chars}",
                    p,
                )
            )
        for line in wrapped:
            if len(line) > max_chars:
                errors.append(
                    _finding(
                        "error",
                        "SUBTITLE_LINE_TOO_LONG",
                        f"line exceeds max_chars_per_line={max_chars}",
                        p,
                        line,
                    )
                )
        if len(wrapped) > max_lines:
            errors.append(
                _finding(
                    "error",
                    "SUBTITLE_MAX_LINES_EXCEEDED",
                    f"wrapped lines exceed max_lines={max_lines}",
                    p,
                    len(wrapped),
                )
            )
        total_chars += len(re.sub(r"\s+", "", t))
        normalized_texts.append(" ".join(t.lower().split()))

    for field in ("hook", "body", "ending"):
        if field in job:
            v = job.get(field)
            if not isinstance(v, str) or not v.strip():
                errors.append(_finding("error", f"{field.upper()}_EMPTY", f"{field} must be non-empty when provided", f"$.{field}"))

    hook = job.get("hook")
    if isinstance(hook, str) and len(hook.strip()) > 80:
        warnings.append(_finding("warn", "HOOK_TOO_LONG", "hook length exceeds 80 chars", "$.hook", len(hook.strip())))

    if len(items) > 12:
        warnings.append(_finding("warn", "SUBTITLE_ITEMS_HIGH", "subtitle item count is high (>12)", "$.subtitles.items", len(items)))

    if duration_f and duration_f > 0:
        cps = float(total_chars) / duration_f
        wpm = (float(total_chars) / 5.0) / (duration_f / 60.0)
        info.append(_finding("info", "EST_CPS", "estimated chars per second", "$", round(cps, 2)))
        info.append(_finding("info", "EST_WPM", "estimated words per minute", "$", round(wpm, 2)))
        if cps > DEFAULT_MAX_CPS_WARN:
            warnings.append(
                _finding(
                    "warn",
                    "TEXT_DENSITY_HIGH",
                    f"text density is high (cps>{DEFAULT_MAX_CPS_WARN:g})",
                    "$.subtitles",
                    round(cps, 2),
                )
            )

    if normalized_texts:
        seen: dict[str, int] = {}
        rep = 0
        for t in normalized_texts:
            seen[t] = seen.get(t, 0) + 1
        for _, c in seen.items():
            if c > 1:
                rep += c - 1
        if rep > 0:
            warnings.append(_finding("warn", "REPEATED_PHRASES", "repeated subtitle phrases detected", "$.subtitles.items", rep))

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "summary": {
            "error_count": len(errors),
            "warn_count": len(warnings),
            "info_count": len(info),
        },
    }

