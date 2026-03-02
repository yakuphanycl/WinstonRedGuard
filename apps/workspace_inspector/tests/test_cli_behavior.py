import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import workspace_inspector.cli as cli
from workspace_inspector import __version__


def _strip_volatile_fields(obj: dict) -> dict:
    """
    Remove fields that are expected to vary between runs.
    Keep the rest deterministic for snapshot-style comparisons.
    """
    obj = dict(obj)  # shallow copy
    obj.pop("generated_at", None)
    obj.pop("run_id", None)
    obj.pop("duration_ms", None)

    meta = obj.get("meta")
    if isinstance(meta, dict):
        meta = dict(meta)
        meta.pop("generated_at", None)
        meta.pop("run_id", None)
        meta.pop("duration_ms", None)
        obj["meta"] = meta
    return obj


def assert_metadata(payload: dict):
    assert payload["schema_version"] == "1"
    assert payload["tool"] == "workspace-inspector"
    assert payload["tool_version"] == __version__
    assert "generated_at" in payload
    # Accept trailing Z in UTC timestamps.
    datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))


def test_json_dash_writes_valid_json_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "scan",
        lambda folder, ignore_names: (
            {"audio": 1, "video": 2, "image": 3, "other": 4},
            1024,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["workspace-inspector", ".", "--json", "-"],
    )

    rc = cli.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["folder"] == str(Path(".").resolve())
    assert "counts" in payload
    assert "total_files" in payload
    assert "total_size_bytes" in payload
    assert "ignore_names" in payload
    assert_metadata(payload)
    assert "JSON report written:" not in captured.out
    assert "Total files:" not in captured.out


def test_json_without_value_defaults_to_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "scan",
        lambda folder, ignore_names: (
            {"audio": 0, "video": 1, "image": 0, "other": 0},
            10,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["workspace-inspector", ".", "--json"],
    )

    rc = cli.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["folder"] == str(Path(".").resolve())
    assert payload["counts"]["video"] == 1
    assert_metadata(payload)
    assert "Total files:" not in captured.out


def test_quiet_suppresses_human_summary(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "scan",
        lambda folder, ignore_names: (
            {"audio": 0, "video": 0, "image": 0, "other": 1},
            5,
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["workspace-inspector", ".", "--quiet"],
    )

    rc = cli.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_with_json_file_writes_file_only(monkeypatch, capsys):
    written: dict[str, str] = {}

    def fake_write_text(self, text, encoding=None):
        written[str(self)] = text
        return len(text)

    monkeypatch.setattr(
        cli,
        "scan",
        lambda folder, ignore_names: (
            {"audio": 1, "video": 0, "image": 0, "other": 0},
            7,
        ),
    )
    monkeypatch.setattr(Path, "write_text", fake_write_text)
    monkeypatch.setattr(
        sys,
        "argv",
        ["workspace-inspector", ".", "--json", "report.json", "--quiet"],
    )

    rc = cli.main()
    captured = capsys.readouterr()
    payload = json.loads(written["report.json"])

    assert rc == 0
    assert captured.out == ""
    assert captured.err == ""
    assert payload["folder"] == str(Path(".").resolve())
    assert_metadata(payload)


def test_quiet_with_json_file_write_error_goes_to_stderr(monkeypatch, capsys):
    def fake_write_text(self, text, encoding=None):
        raise OSError("disk is full")

    monkeypatch.setattr(
        cli,
        "scan",
        lambda folder, ignore_names: (
            {"audio": 1, "video": 0, "image": 0, "other": 0},
            7,
        ),
    )
    monkeypatch.setattr(Path, "write_text", fake_write_text)
    monkeypatch.setattr(
        sys,
        "argv",
        ["workspace-inspector", ".", "--json", "report.json", "--quiet"],
    )

    rc = cli.main()
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "Error: cannot write JSON report:" in captured.err


def test_version_prints_and_exits(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workspace-inspector", "--version"])

    rc = cli.main()
    captured = capsys.readouterr()

    assert rc == 0
    assert captured.out.strip() == f"workspace-inspector {__version__}"
    assert captured.err == ""


def test_cli_json_is_deterministic_except_timestamp(monkeypatch, capsys):
    class FakeDateTime:
        tick = 0

        @classmethod
        def now(cls, tz=None):
            cls.tick += 1
            return datetime(2026, 1, 1, 0, 0, cls.tick, tzinfo=timezone.utc)

    monkeypatch.setattr(
        cli,
        "scan",
        lambda folder, ignore_names: (
            {"audio": 1, "video": 2, "image": 3, "other": 4},
            1024,
        ),
    )
    monkeypatch.setattr(cli, "datetime", FakeDateTime)

    monkeypatch.setattr(sys, "argv", ["workspace-inspector", ".", "--json"])
    rc1 = cli.main()
    out1 = capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["workspace-inspector", ".", "--json"])
    rc2 = cli.main()
    out2 = capsys.readouterr().out

    assert rc1 == 0
    assert rc2 == 0
    payload1 = json.loads(out1)
    payload2 = json.loads(out2)
    assert "generated_at" in payload1
    assert payload1["generated_at"].endswith("Z")
    assert payload1["generated_at"] != payload2["generated_at"]
    assert _strip_volatile_fields(payload1) == _strip_volatile_fields(payload2)
