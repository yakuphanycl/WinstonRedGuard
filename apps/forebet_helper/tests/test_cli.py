from pathlib import Path

from forebet_helper.cli import main


FIXTURE = Path(__file__).parent / "fixtures" / "sample_match_page.html"


def test_cli_writes_json_output(tmp_path: Path) -> None:
    out_path = tmp_path / "out.json"
    rc = main(["--html-file", str(FIXTURE), "--out", str(out_path)])
    assert rc == 0
    payload = out_path.read_text(encoding="utf-8")
    assert "APIA Tigers" in payload
    assert '"prediction_1x2": "1"' in payload
