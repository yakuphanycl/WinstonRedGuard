from __future__ import annotations

from datetime import datetime

from .models import MatchSignal
from .normalizer import build_match_id


IMPORTANT_FIELDS = [
    "home_team",
    "away_team",
    "prediction_1x2",
    "correct_score",
    "btts",
    "over_under_2_5",
    "ht_ft",
]


def compute_confidence(parsed: dict) -> tuple[str, list[str]]:
    missing = [field for field in IMPORTANT_FIELDS if parsed.get(field) in (None, "")]
    present_count = len(IMPORTANT_FIELDS) - len(missing)
    if present_count >= 6:
        confidence = "high"
    elif present_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"
    return confidence, missing


def derive_interpretation(parsed: dict) -> dict[str, str | None]:
    home = parsed.get("prob_home")
    draw = parsed.get("prob_draw")
    away = parsed.get("prob_away")
    prediction = parsed.get("prediction_1x2")

    if home is None or draw is None or away is None:
        return {
            "edge_strength": None,
            "match_profile": None,
            "signal_summary": None,
            "risk_note": None,
        }

    outcomes = [("home", home), ("draw", draw), ("away", away)]
    ordered = sorted(outcomes, key=lambda item: item[1], reverse=True)
    top_label, top_prob = ordered[0]
    second_prob = ordered[1][1]
    gap = top_prob - second_prob

    if gap < 0.05:
        edge_strength = "weak"
    elif gap < 0.12:
        edge_strength = "medium"
    else:
        edge_strength = "strong"

    if top_label == "home" and gap >= 0.05:
        match_profile = "home_lean"
    elif top_label == "away" and gap >= 0.05:
        match_profile = "away_lean"
    else:
        match_profile = "balanced"

    prediction_text = prediction.upper() if isinstance(prediction, str) and prediction.upper() in {"1", "X", "2"} else None
    if match_profile == "balanced":
        signal_summary = f"Balanced outlook with a {edge_strength} 1X2 edge."
    else:
        lean_text = "Home lean" if match_profile == "home_lean" else "Away lean"
        if prediction_text is not None:
            signal_summary = f"{lean_text} with a {edge_strength} {prediction_text} signal."
        else:
            signal_summary = f"{lean_text} with a {edge_strength} probability edge."

    risk_note = None
    if gap < 0.05:
        risk_note = "Probabilities are tightly clustered; treat the edge as fragile."
    elif abs(home - away) < 0.06 and draw >= min(home, away) - 0.02:
        risk_note = "Home and away probabilities are close, with draw still in play."

    return {
        "edge_strength": edge_strength,
        "match_profile": match_profile,
        "signal_summary": signal_summary,
        "risk_note": risk_note,
    }


def to_match_signal(parsed: dict, url: str | None) -> MatchSignal:
    confidence, missing_fields = compute_confidence(parsed)
    interpretation = derive_interpretation(parsed)
    kickoff = parsed.get("kickoff")
    home = parsed.get("home_team")
    away = parsed.get("away_team")

    return MatchSignal(
        match_id=build_match_id(home, away, kickoff),
        source="forebet",
        url=url,
        kickoff=kickoff,
        league=parsed.get("league"),
        home_team=home,
        away_team=away,
        prediction_1x2=parsed.get("prediction_1x2"),
        prob_home=parsed.get("prob_home"),
        prob_draw=parsed.get("prob_draw"),
        prob_away=parsed.get("prob_away"),
        correct_score=parsed.get("correct_score"),
        btts=parsed.get("btts"),
        over_under_2_5=parsed.get("over_under_2_5"),
        ht_ft=parsed.get("ht_ft"),
        confidence=confidence,
        parser_version=parsed.get("parser_version", "0.1.0"),
        fetched_at=datetime.now().astimezone(),
        missing_fields=missing_fields,
        edge_strength=interpretation["edge_strength"],
        match_profile=interpretation["match_profile"],
        signal_summary=interpretation["signal_summary"],
        risk_note=interpretation["risk_note"],
    )
