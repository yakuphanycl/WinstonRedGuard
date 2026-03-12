from forebet_helper.signals import compute_confidence, derive_interpretation, to_match_signal


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


def test_derive_interpretation_marks_balanced_when_probabilities_are_close() -> None:
    interpretation = derive_interpretation(
        {
            "prob_home": 0.34,
            "prob_draw": 0.33,
            "prob_away": 0.33,
            "prediction_1x2": "1",
        }
    )

    assert interpretation["edge_strength"] == "weak"
    assert interpretation["match_profile"] == "balanced"
    assert interpretation["signal_summary"] == "Balanced outlook with a weak 1X2 edge."
    assert interpretation["risk_note"] == "Probabilities are tightly clustered; treat the edge as fragile."


def test_to_match_signal_adds_interpretation_fields_for_clear_home_lean() -> None:
    signal = to_match_signal(
        {
            "home_team": "Lille",
            "away_team": "Aston Villa",
            "kickoff": None,
            "league": None,
            "prediction_1x2": "1",
            "prob_home": 0.36,
            "prob_draw": 0.33,
            "prob_away": 0.31,
            "correct_score": "1-0",
            "btts": "no",
            "over_under_2_5": "under",
            "ht_ft": "X/1",
            "parser_version": "0.1.0",
        },
        url=None,
    )

    assert signal.edge_strength == "weak"
    assert signal.match_profile == "balanced"
    assert signal.signal_summary == "Balanced outlook with a weak 1X2 edge."
    assert signal.risk_note == "Probabilities are tightly clustered; treat the edge as fragile."
