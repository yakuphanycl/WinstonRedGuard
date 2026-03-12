from pathlib import Path

from forebet_helper.parser import parse_match_page


FIXTURE = Path(__file__).parent / "fixtures" / "sample_match_page.html"
SNAPSHOT = Path(__file__).parent.parent / "Lille vs Aston Villa Prediction, Stats, H2H - 12 Mar 2026.html"


def test_parse_match_page_extracts_core_fields() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    parsed = parse_match_page(html)

    assert parsed["home_team"] == "APIA Tigers"
    assert parsed["away_team"] == "Sydney United"
    assert parsed["league"] == "Australia NSW"
    assert parsed["prediction_1x2"] == "1"
    assert parsed["correct_score"] == "2-1"
    assert parsed["btts"] == "yes"
    assert parsed["over_under_2_5"] == "over"
    assert parsed["ht_ft"] == "1/1"
    assert parsed["prob_home"] == 0.52
    assert parsed["prob_draw"] == 0.27
    assert parsed["prob_away"] == 0.21
    assert parsed["kickoff"] is not None


def test_parse_match_page_extracts_forebet_prediction_tables() -> None:
    html = SNAPSHOT.read_text(encoding="utf-8")
    parsed = parse_match_page(html)

    assert parsed["home_team"] == "Lille"
    assert parsed["away_team"] == "Aston Villa"
    assert parsed["kickoff"] is not None
    assert parsed["prediction_1x2"] == "1"
    assert parsed["prob_home"] == 0.36
    assert parsed["prob_draw"] == 0.33
    assert parsed["prob_away"] == 0.31
    assert parsed["correct_score"] == "1-0"
    assert parsed["btts"] == "no"
    assert parsed["over_under_2_5"] == "under"
    assert parsed["ht_ft"] == "X/1"
