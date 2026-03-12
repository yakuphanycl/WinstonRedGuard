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


def to_match_signal(parsed: dict, url: str | None) -> MatchSignal:
    confidence, missing_fields = compute_confidence(parsed)
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
    )
