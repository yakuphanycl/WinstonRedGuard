from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal


Confidence = Literal["low", "medium", "high"]


@dataclass
class MatchSignal:
    match_id: str
    source: Literal["forebet"]
    url: str | None
    kickoff: datetime | None
    league: str | None
    home_team: str | None
    away_team: str | None
    prediction_1x2: str | None
    prob_home: float | None
    prob_draw: float | None
    prob_away: float | None
    correct_score: str | None
    btts: str | None
    over_under_2_5: str | None
    ht_ft: str | None
    confidence: Confidence
    parser_version: str
    fetched_at: datetime
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
