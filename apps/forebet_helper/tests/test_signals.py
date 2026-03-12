from forebet_helper.signals import compute_confidence


def test_compute_confidence_high_when_most_core_fields_present() -> None:
    parsed = {
        "home_team": "A",
        "away_team": "B",
        "prediction_1x2": "1",
        "correct_score": "2-1",
        "btts": "yes",
        "over_under_2_5": "over",
        "ht_ft": "1/1",
    }
    confidence, missing = compute_confidence(parsed)
    assert confidence == "high"
    assert missing == []


def test_compute_confidence_low_when_many_fields_missing() -> None:
    parsed = {
        "home_team": "A",
        "away_team": "B",
        "prediction_1x2": None,
        "correct_score": None,
        "btts": None,
        "over_under_2_5": None,
        "ht_ft": None,
    }
    confidence, missing = compute_confidence(parsed)
    assert confidence == "low"
    assert len(missing) == 5
