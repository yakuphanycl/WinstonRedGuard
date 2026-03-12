from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from .utils import normalize_team_name, parse_percentage

PARSER_VERSION = "0.1.0"


def parse_match_page(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    data: dict[str, Any] = {
        "league": None,
        "home_team": None,
        "away_team": None,
        "kickoff": None,
        "prediction_1x2": None,
        "prob_home": None,
        "prob_draw": None,
        "prob_away": None,
        "correct_score": None,
        "btts": None,
        "over_under_2_5": None,
        "ht_ft": None,
        "raw_signals_found": [],
        "parser_version": PARSER_VERSION,
    }

    _parse_title_and_meta(soup, data)
    _parse_embedded_json(soup, data)
    _parse_prediction_tables(soup, data)
    _parse_text_fallbacks(text, data)

    data["home_team"] = normalize_team_name(data["home_team"])
    data["away_team"] = normalize_team_name(data["away_team"])
    data["league"] = normalize_team_name(data["league"])
    return data


def _debug_log(label: str, value: Any) -> None:
    if os.getenv("FOREBET_HELPER_DEBUG") == "1":
        print(f"[DEBUG] {label}: {value!r}")


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\xa0", " ")
    value = re.sub(r"[\t\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalize_score(value: str | None) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None

    normalized = cleaned.replace("–", "-").replace("—", "-").replace("−", "-")
    direct = re.search(r"(?<!\d)(\d{1,2})\s*-\s*(\d{1,2})(?!\d)", normalized)
    if direct:
        left = direct.group(1)
        right = direct.group(2)
        if not (
            ("\n" in (value or "") or "\r" in (value or ""))
            and len(left) > 1
            and len(right) > 1
            and len(set(left)) == 1
            and len(set(right)) == 1
        ):
            return f"{int(left)}-{int(right)}"

    compact = "".join(ch for ch in normalized if ch.isdigit() or ch == "-")
    compact_match = re.search(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!\d)", compact)
    if compact_match:
        return f"{int(compact_match.group(1))}-{int(compact_match.group(2))}"

    if compact.count("-") == 1:
        left_digits, right_digits = compact.split("-", 1)
        if (
            left_digits
            and right_digits
            and len(left_digits) > 1
            and len(right_digits) > 1
            and len(set(left_digits)) == 1
            and len(set(right_digits)) == 1
        ):
            return f"{int(left_digits[-1])}-{int(right_digits[0])}"
    return None


def _parse_probability_value(value: str | None) -> float | None:
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    if "%" not in cleaned:
        cleaned = f"{cleaned}%"
    return parse_percentage(cleaned)


def _extract_percent_triplet(container: Any) -> tuple[float, float, float] | None:
    if container is None:
        return None
    values = []
    for span in container.select("span"):
        parsed = _parse_probability_value(span.get_text(" ", strip=True))
        if parsed is not None:
            values.append(parsed)
    if len(values) == 3:
        return values[0], values[1], values[2]
    return None


def _extract_prediction_text(node: Any) -> str | None:
    if node is None:
        return None
    text = _clean_text(node.get_text(" ", strip=True))
    return text or None


def _normalize_market_pick(value: str | None, allowed: set[str]) -> str | None:
    cleaned = _clean_text(value).lower()
    if cleaned in allowed:
        return cleaned
    return None


def _parse_prediction_tables(soup: BeautifulSoup, data: dict[str, Any]) -> None:
    m1x2_row = soup.select_one("#m1x2_table .rcnt")
    if m1x2_row:
        triplet = _extract_percent_triplet(m1x2_row.select_one(".fprc"))
        if triplet is not None:
            if data["prob_home"] is None:
                data["prob_home"] = triplet[0]
                data["raw_signals_found"].append("prob_home:dom_1x2")
            if data["prob_draw"] is None:
                data["prob_draw"] = triplet[1]
                data["raw_signals_found"].append("prob_draw:dom_1x2")
            if data["prob_away"] is None:
                data["prob_away"] = triplet[2]
                data["raw_signals_found"].append("prob_away:dom_1x2")

        if data["prediction_1x2"] is None:
            prediction = _extract_prediction_text(m1x2_row.select_one(".predict .forepr span"))
            if prediction and prediction.upper() in {"1", "2", "X"}:
                data["prediction_1x2"] = prediction.upper()
                data["raw_signals_found"].append("prediction_1x2:dom_1x2")

        if data["correct_score"] is None:
            score = _normalize_score(_extract_prediction_text(m1x2_row.select_one(".ex_sc.tabonly")))
            if score is None:
                score = _normalize_score(_extract_prediction_text(m1x2_row.select_one(".scrmobpred.ex_sc")))
            if score is not None:
                data["correct_score"] = score
                data["raw_signals_found"].append("correct_score:dom_1x2")

    uo_row = soup.select_one("#uo_table .rcnt")
    if uo_row and data["over_under_2_5"] is None:
        pick = _normalize_market_pick(_extract_prediction_text(uo_row.select_one(".predict .forepr span")), {"over", "under"})
        if pick is not None:
            data["over_under_2_5"] = pick
            data["raw_signals_found"].append("over_under_2_5:dom_uo")

    bts_row = soup.select_one("#bts_table .rcnt")
    if bts_row and data["btts"] is None:
        pick = _normalize_market_pick(_extract_prediction_text(bts_row.select_one(".predict .forepr span")), {"yes", "no"})
        if pick is not None:
            data["btts"] = pick
            data["raw_signals_found"].append("btts:dom_bts")

    htft_row = soup.select_one("#htft_table .rcnt")
    if htft_row and data["ht_ft"] is None:
        ht_pick = _extract_prediction_text(htft_row.select_one(".predict.prht .forepr span"))
        ft_pick = None
        for predict_node in htft_row.select("div.predict"):
            classes = predict_node.get("class") or []
            if "prht" in classes:
                continue
            ft_pick = _extract_prediction_text(predict_node.select_one(".forepr span"))
            if ft_pick:
                break
        if ht_pick and ft_pick and ht_pick.upper() in {"1", "2", "X"} and ft_pick.upper() in {"1", "2", "X"}:
            data["ht_ft"] = f"{ht_pick.upper()}/{ft_pick.upper()}"
            data["raw_signals_found"].append("ht_ft:dom_htft")


def _parse_title_and_meta(soup: BeautifulSoup, data: dict[str, Any]) -> None:
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta_parts = []
    for attrs in ({"property": "og:title"}, {"name": "title"}, {"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            meta_parts.append(str(tag["content"]))

    combined = "\n".join([title, *meta_parts])

    # Team extraction
    patterns = [
        r"(?P<home>.*?)\s+vs\s+(?P<away>.*?)\s+Prediction",
        r"(?P<home>.*?)\s+vs\s+(?P<away>.*?)\s+-",
        r"(?P<home>.*?)\s+v(?:s\.?)*\s+(?P<away>.*?)\s+H2H",
    ]
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            data["home_team"] = data["home_team"] or match.group("home").strip(" -|")
            data["away_team"] = data["away_team"] or match.group("away").strip(" -|")
            data["raw_signals_found"].append("teams:title_or_meta")
            break

    # League extraction
    league_match = re.search(r"(?:league|competition|tournament)\s*[:\-]\s*([A-Za-z0-9 .,'()/+-]{3,80})", combined, re.IGNORECASE)
    if league_match:
        league_value = league_match.group(1).strip()
        league_value = re.split(r"\.\s+(?:Prediction|Correct Score|BTTS|Over/Under|HT/FT)\b", league_value, maxsplit=1, flags=re.IGNORECASE)[0]
        data["league"] = league_value.strip()
        data["raw_signals_found"].append("league:title_or_meta")


def _parse_embedded_json(soup: BeautifulSoup, data: dict[str, Any]) -> None:
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text("\n", strip=True)
        if not script_text:
            continue

        if script.get("type") == "application/ld+json":
            _parse_json_ld_block(script_text, data)
            continue

        # Fallback: try to find named fields in JS blobs.
        js_patterns: list[tuple[str, str]] = [
            ("correct_score", r'"correct[_ ]?score"\s*:\s*"?(\d{1,2}\s*-\s*\d{1,2})"?'),
            ("ht_ft", r'"ht[_/ -]?ft"\s*:\s*"?([12X]\s*/\s*[12X])"?'),
            ("prediction_1x2", r'"(?:prediction|tip|pick)[_ ]?1x2"\s*:\s*"?([12X])"?'),
            ("btts", r'"btts"\s*:\s*"?(yes|no)"?'),
            ("over_under_2_5", r'"(?:over_under_2_5|ou25)"\s*:\s*"?(over|under)"?'),
        ]
        for field_name, pattern in js_patterns:
            match = re.search(pattern, script_text, re.IGNORECASE)
            if match and data.get(field_name) is None:
                value = _clean_text(match.group(1)).lower()
                if field_name == "correct_score":
                    value = _normalize_score(value)
                elif field_name == "ht_ft":
                    value = value.replace(" ", "").upper()
                if value:
                    data[field_name] = value
                    data["raw_signals_found"].append(f"{field_name}:script")

        prob_patterns: list[tuple[str, str]] = [
            ("prob_home", r'"(?:prob_home|home_prob|home_win_probability)"\s*:\s*"?([0-9.,]+%?)"?'),
            ("prob_draw", r'"(?:prob_draw|draw_prob|draw_probability)"\s*:\s*"?([0-9.,]+%?)"?'),
            ("prob_away", r'"(?:prob_away|away_prob|away_win_probability)"\s*:\s*"?([0-9.,]+%?)"?'),
        ]
        for field_name, pattern in prob_patterns:
            match = re.search(pattern, script_text, re.IGNORECASE)
            if match and data.get(field_name) is None:
                parsed = _parse_probability_value(match.group(1))
                if parsed is not None:
                    data[field_name] = parsed
                    data["raw_signals_found"].append(f"{field_name}:script")


def _parse_json_ld_block(script_text: str, data: dict[str, Any]) -> None:
    try:
        payload = json.loads(script_text)
    except json.JSONDecodeError:
        return

    candidates = payload if isinstance(payload, list) else [payload]
    for item in candidates:
        if not isinstance(item, dict):
            continue

        # Team extraction from SportsEvent-ish blocks
        home = _dig(item, ["homeTeam", "name"])
        away = _dig(item, ["awayTeam", "name"])
        if isinstance(home, str) and data["home_team"] is None:
            data["home_team"] = home
            data["raw_signals_found"].append("teams:jsonld_home")
        if isinstance(away, str) and data["away_team"] is None:
            data["away_team"] = away
            data["raw_signals_found"].append("teams:jsonld_away")

        if data["kickoff"] is None:
            kickoff_candidate = item.get("startDate") or item.get("datePublished")
            parsed = _parse_datetime(kickoff_candidate)
            if parsed is not None:
                data["kickoff"] = parsed
                data["raw_signals_found"].append("kickoff:jsonld")

        if data["league"] is None:
            league = item.get("name") if item.get("@type") in {"SportsEvent", "Event"} else None
            if isinstance(league, str) and 3 <= len(league) <= 120:
                data["league"] = league
                data["raw_signals_found"].append("league:jsonld")


def _parse_text_fallbacks(text: str, data: dict[str, Any]) -> None:
    compact_text = _clean_text(text)
    _debug_log("prediction_text", compact_text[:500])

    if data["home_team"] is None or data["away_team"] is None:
        team_match = re.search(
            r"([A-Za-z0-9 .,'()/+-]{2,60})\s+vs\s+([A-Za-z0-9 .,'()/+-]{2,60})\s+(?:Prediction|H2H|Stats)",
            compact_text,
            re.IGNORECASE,
        )
        if team_match:
            data["home_team"] = data["home_team"] or team_match.group(1).strip()
            data["away_team"] = data["away_team"] or team_match.group(2).strip()
            data["raw_signals_found"].append("teams:text")

    if data["league"] is None:
        league_match = re.search(r"League\s*[:\-]\s*([A-Za-z0-9 .,'()/+-]{3,80})", compact_text, re.IGNORECASE)
        if league_match:
            data["league"] = league_match.group(1).strip()
            data["raw_signals_found"].append("league:text")

    if data["prediction_1x2"] is None:
        for pattern, token in [
            (r"\bPrediction\s*[:\-]\s*([12X])\b", None),
            (r"\bPick(?: of the day)?\s*[:\-]\s*([12X])\b", None),
            (r"\b1X2\s*[:\-]\s*([12X])\b", None),
        ]:
            match = re.search(pattern, compact_text, re.IGNORECASE)
            if match:
                data["prediction_1x2"] = match.group(1).upper()
                data["raw_signals_found"].append("prediction_1x2:text")
                break

    if data["correct_score"] is None:
        score_match = re.search(r"\bCorrect Score\s*[:\-]\s*([0-9\s\-\r\n]+)", text, re.IGNORECASE)
        score = _normalize_score(score_match.group(1)) if score_match else None
        if score is None:
            score_match = re.search(r"\b(\d{1,2}\s*-\s*\d{1,2})\b", compact_text)
            score = _normalize_score(score_match.group(1)) if score_match else None
        if score is not None:
            data["correct_score"] = score
            data["raw_signals_found"].append("correct_score:text")

    if data["btts"] is None:
        match = re.search(r"\b(?:BTTS|Both Teams To Score)\s*[:\-]\s*(Yes|No)\b", compact_text, re.IGNORECASE)
        if match:
            data["btts"] = match.group(1).lower()
            data["raw_signals_found"].append("btts:text")

    if data["over_under_2_5"] is None:
        match = re.search(r"\b(?:Over/Under\s*2\.5|Under/Over\s*2\.5|O/U\s*2\.5)\s*[:\-]\s*(Over|Under)\b", compact_text, re.IGNORECASE)
        if match:
            data["over_under_2_5"] = match.group(1).lower()
            data["raw_signals_found"].append("over_under_2_5:text")

    if data["ht_ft"] is None:
        match = re.search(r"\bHT/FT\s*[:\-]\s*([12X]\s*/\s*[12X])\b", compact_text, re.IGNORECASE)
        if match:
            data["ht_ft"] = match.group(1).replace(" ", "").upper()
            data["raw_signals_found"].append("ht_ft:text")

    _parse_probabilities_from_text(compact_text, data)

    if data["kickoff"] is None:
        for pattern in [
            r"\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)\b",
            r"\b(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2})\b",
        ]:
            match = re.search(pattern, compact_text)
            if not match:
                continue
            parsed = _parse_datetime(match.group(1))
            if parsed is not None:
                data["kickoff"] = parsed
                data["raw_signals_found"].append("kickoff:text")
                break


def _parse_probabilities_from_text(text: str, data: dict[str, Any]) -> None:
    if data["prob_home"] is None and data["prob_draw"] is None and data["prob_away"] is None:
        for pattern in [
            r"Prob\.\s*%\s*1\s*X\s*2\s*Pred(?:.{0,200}?)(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})",
            r"1X2(?:.{0,120}?)(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})",
        ]:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            triplet = tuple(_parse_probability_value(match.group(idx)) for idx in (1, 2, 3))
            if all(value is not None for value in triplet):
                data["prob_home"], data["prob_draw"], data["prob_away"] = triplet
                data["raw_signals_found"].append("probabilities:text_triplet")
                break

    patterns: list[tuple[str, list[str]]] = [
        (
            "prob_home",
            [
                r"\bHome\s*(?:win)?\s*[:\-]?\s*([0-9.,]+%)",
                r"\b1\s*[:\-]?\s*([0-9.,]+%)",
            ],
        ),
        (
            "prob_draw",
            [
                r"\bDraw\s*[:\-]?\s*([0-9.,]+%)",
                r"\bX\s*[:\-]?\s*([0-9.,]+%)",
            ],
        ),
        (
            "prob_away",
            [
                r"\bAway\s*(?:win)?\s*[:\-]?\s*([0-9.,]+%)",
                r"\b2\s*[:\-]?\s*([0-9.,]+%)",
            ],
        ),
    ]
    for field_name, field_patterns in patterns:
        if data[field_name] is not None:
            continue
        for pattern in field_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            parsed = _parse_probability_value(match.group(1))
            if parsed is not None:
                data[field_name] = parsed
                data["raw_signals_found"].append(f"{field_name}:text")
                break


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    candidates = [value]
    if value.endswith("Z"):
        candidates.append(value.replace("Z", "+00:00"))

    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass

    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def _dig(payload: dict[str, Any], path: list[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
