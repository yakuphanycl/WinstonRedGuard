import json
from pathlib import Path


def test_batch_report_contract_shape():
    p = Path("layer2/examples/reports/batch_report_golden.v0.1.json")
    data = json.loads(p.read_text(encoding="utf-8"))

    for k in ["meta", "summary", "fail_by_type", "sample_failures", "items"]:
        assert k in data, f"missing key: {k}"

    s = data["summary"]
    for k in ["total", "ok", "fail", "skipped"]:
        assert k in s, f"missing summary.{k}"

    for it in data["items"]:
        assert "job_path" in it
        assert it.get("status") in ("ok", "fail", "skipped")
        assert "duration_sec" in it

        if it["status"] == "fail":
            err = it.get("error")
            assert err, "fail item must include error"
            assert err.get("type") in (
                "validation_error",
                "io_error",
                "render_error",
                "timeout",
                "internal_error",
            )
            assert isinstance(err.get("message"), str) and err["message"].strip()

