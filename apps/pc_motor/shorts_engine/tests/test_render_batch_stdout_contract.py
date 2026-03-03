from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class BatchRun:
    returncode: int
    stdout: str
    stderr: str


def _run_render_batch_capture_stdout() -> BatchRun:
    # Adjust flags/args to match your CLI. Keep stdout capture.
    cmd = [
        sys.executable,
        "-m",
        "layer2.cli.render_batch",
        "--batch",
        "layer2/examples/batches/smoke_batch_001.json",
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return BatchRun(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def _extract_last_json_object(text: str) -> dict:
    """
    Robust-ish fallback extractor:
    - Scans from the end for a '{' candidate and tries json.loads from there.
    - Ignores trailing non-json noise (e.g., progress/log lines).
    - Returns the first successfully parsed JSON object found from the end.
    """
    s = (text or "").strip()
    if not s:
        raise AssertionError("empty stdout")

    # Fast path: last line is JSON
    last_line = s.splitlines()[-1].strip()
    if last_line.startswith("{") and last_line.endswith("}"):
        try:
            obj = json.loads(last_line)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # Fallback: scan backwards for '{' and try parse
    for i in range(len(s) - 1, -1, -1):
        if s[i] != "{":
            continue
        chunk = s[i:]
        try:
            obj = json.loads(chunk)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    raise AssertionError("no JSON object found in stdout")


def test_render_batch_stdout_contract_minimal():
    r = _run_render_batch_capture_stdout()

    # Crash policy: 1 is crash, 0/2 are acceptable.
    assert r.returncode in (0, 2), f"unexpected exit={r.returncode}\nSTDERR:\n{r.stderr}"
    assert r.stdout.strip(), f"empty stdout\nSTDERR:\n{r.stderr}"

    payload = _extract_last_json_object(r.stdout)

    assert "items" in payload, "stdout payload must include top-level 'items'"
    assert isinstance(payload["items"], list), "'items' must be a list"

    if "runs" in payload:
        assert isinstance(payload["runs"], list), "'runs' must be a list when present"

    for it in payload["items"]:
        assert isinstance(it, dict), "each item must be an object"
        assert ("job_path" in it) or ("job" in it), "item must reference its job"
        assert "status" in it, "item must include status"
        assert it.get("status") in ("ok", "fail", "skipped"), "unexpected item.status"

