from __future__ import annotations

import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .config import ROOT


DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"

ANSWER_SOURCE_PATHS = {
    "dashboard_payload": "app/static/data/dashboard_data.json",
}


def load_dashboard_payload(path: str | Path = DEFAULT_PAYLOAD) -> dict[str, Any]:
    payload_path = Path(path)
    if not payload_path.exists():
        raise FileNotFoundError(f"Dashboard payload not found: {payload_path}")
    return json.loads(payload_path.read_text(encoding="utf-8"))


def normalize_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def fmt_number(value: Any, digits: int = 3) -> str:
    if value in {"", None}:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_pct(value: Any, digits: int = 1) -> str:
    if value in {"", None}:
        return "-"
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "-"


def answer(
    question: str,
    intent: str,
    short_answer: str,
    *,
    evidence_cards: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
    confidence: float = 0.5,
    source_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "question": question,
        "intent": intent,
        "short_answer": short_answer,
        "evidence_cards": evidence_cards or [],
        "tables": tables or [],
        "warnings": warnings or [],
        "confidence": round(max(0.0, min(1.0, confidence)), 4),
        "source_paths": source_paths or dict(ANSWER_SOURCE_PATHS),
    }


def all_signal_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for season_rows in payload.get("signals_by_season", {}).values():
        rows.extend(season_rows or [])
    rows.extend(payload.get("live_watchlist", []) or [])
    details = payload.get("watchlist_details", {}) or {}
    rows.extend(details.values())
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.get("group_key") or row.get("claim_ids") or (row.get("club"), row.get("player"), row.get("latest_published_at")))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def all_transfer_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for season_rows in payload.get("transfers_by_season", {}).values():
        rows.extend(season_rows or [])
    return rows


def candidate_names(payload: dict[str, Any], kind: str) -> list[str]:
    if kind == "club":
        names = set(payload.get("club_dossiers", {}).keys())
        names.update(payload.get("club_media", {}).keys())
        return sorted(name for name in names if name)
    if kind == "reporter":
        names = set(payload.get("reporter_profiles", {}).keys())
        names.update(row.get("journalist", "") for row in payload.get("leaderboards", {}).get("journalists", []))
        return sorted(name for name in names if name)
    if kind == "player":
        names = set()
        for row in all_signal_rows(payload):
            if row.get("player"):
                names.add(str(row.get("player")))
        for row in all_transfer_rows(payload):
            if row.get("player"):
                names.add(str(row.get("player")))
        return sorted(name for name in names if name)
    return []


def match_name(query: str, names: list[str]) -> str:
    normalized_query = f" {normalize_text(query)} "
    best = ""
    best_score = 0
    for name in names:
        normalized_name = normalize_text(name)
        if not normalized_name:
            continue
        tokens = [token for token in normalized_name.split() if len(token) > 2]
        score = 0
        if f" {normalized_name} " in normalized_query:
            score = 100 + len(normalized_name)
        elif tokens and all(f" {token} " in normalized_query for token in tokens):
            score = 70 + len(tokens)
        elif tokens and any(f" {token} " in normalized_query for token in tokens):
            score = len([token for token in tokens if f" {token} " in normalized_query])
        if score > best_score:
            best = name
            best_score = score
    return best


def match_clubs(query: str, payload: dict[str, Any]) -> list[str]:
    names = candidate_names(payload, "club")
    normalized_query = f" {normalize_text(query)} "
    matches: list[tuple[int, str]] = []
    for name in names:
        normalized_name = normalize_text(name)
        tokens = [token for token in normalized_name.split() if len(token) > 2]
        index = normalized_query.find(f" {normalized_name} ")
        if index < 0 and tokens and all(f" {token} " in normalized_query for token in tokens):
            token_indexes = [normalized_query.find(f" {token} ") for token in tokens]
            index = min(item for item in token_indexes if item >= 0)
        if index >= 0:
            matches.append((index, name))
    if len(matches) >= 2:
        return [name for _, name in sorted(matches, key=lambda item: item[0])]
    best = match_name(query, names)
    return [best] if best else []


def extract_season(query: str, payload: dict[str, Any]) -> str:
    match = re.search(r"\b(20\d{2}-\d{2})\b", query)
    if match:
        return match.group(1)
    return str(payload.get("latest_season", ""))


def detect_intent(question: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_text(question)
    clubs = match_clubs(question, payload)
    reporter = match_name(question, candidate_names(payload, "reporter"))
    player = match_name(question, candidate_names(payload, "player"))
    has_compare = any(token in normalized for token in ("compare", " versus ", " vs ", " v "))
    if not has_compare and len(clubs) >= 2 and " and " in f" {normalized} ":
        has_compare = True
    if has_compare and len(clubs) >= 2:
        return {"intent": "compare_clubs", "clubs": clubs[:2]}
    if reporter:
        return {"intent": "reporter_profile", "reporter": reporter}
    if clubs and any(token in normalized for token in ("reporter", "journalist", "source", "credibility")):
        return {"intent": "club_reporters", "club": clubs[0]}
    if player and "similar" in normalized:
        return {"intent": "similar_historical_cases", "player": player}
    if player:
        return {"intent": "explain_rumor", "player": player}
    if clubs and any(token in normalized for token in ("match", "result", "stock path", "stock", "price")):
        return {"intent": "match_stock_context", "club": clubs[0]}
    if clubs and any(token in normalized for token in ("confirmed", "transfer", "transfers", "past", "history")):
        return {"intent": "confirmed_transfers", "club": clubs[0], "season": extract_season(question, payload)}
    if clubs:
        return {"intent": "current_signals_for_club", "club": clubs[0]}
    return {"intent": "unknown"}


def row_club(row: dict[str, Any]) -> str:
    return str(row.get("target_club") or row.get("club") or "").strip()


def row_date(row: dict[str, Any]) -> str:
    value = str(row.get("published_at") or row.get("latest_published_at") or row.get("date") or "").strip()
    if not value:
        return ""
    if len(value) >= 10 and re.match(r"\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return value[:10]


def club_current_signals(payload: dict[str, Any], club: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = [
        row for row in payload.get("live_watchlist", []) or []
        if row_club(row) == club or row.get("club") == club
    ]
    if rows:
        return rows[:limit]
    latest = payload.get("latest_season", "")
    season_rows = payload.get("signals_by_season", {}).get(latest, [])
    return [row for row in season_rows if row_club(row) == club or row.get("club") == club][:limit]


def signal_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "title": "Signals",
        "columns": ["date", "club", "player", "stage", "credibility", "model", "blend"],
        "rows": [
            {
                "date": row_date(row),
                "club": row_club(row),
                "player": row.get("player", ""),
                "stage": row.get("rumor_stage") or row.get("latest_rumor_stage", ""),
                "credibility": fmt_number(row.get("credibility_score"), 3),
                "model": row.get("predicted_label", ""),
                "blend": row.get("blended_label", ""),
            }
            for row in rows
        ],
    }


def answer_current_signals(question: str, payload: dict[str, Any], club: str) -> dict[str, Any]:
    dossier = payload.get("club_dossiers", {}).get(club, {})
    rows = club_current_signals(payload, club)
    cards = [
        {"title": "Live events", "value": dossier.get("live_signal_count", 0), "detail": "Current watchlist events for this club."},
        {"title": "Avg live credibility", "value": fmt_number(dossier.get("avg_live_credibility"), 3), "detail": "Mean credibility score in live events."},
        {"title": "Avg transfer index", "value": fmt_number(dossier.get("avg_transfer_index"), 3), "detail": "Recent confirmed transfer quality index."},
        {"title": "Avg realized CAR t+3", "value": fmt_number(dossier.get("avg_realized_car_p3"), 4), "detail": "Historical transfer-window abnormal return average."},
    ]
    if not rows:
        return answer(
            question,
            "current_signals_for_club",
            f"No current direct-target signals are available for {club} in the local payload.",
            evidence_cards=cards,
            tables=[],
            warnings=["This answer is based only on the current dashboard payload. Refresh live data if it looks stale."],
            confidence=0.75,
        )
    top = rows[0]
    short = (
        f"{club} has {len(rows)} visible signal(s). The top row is {top.get('player', '-')} "
        f"at stage {top.get('rumor_stage') or top.get('latest_rumor_stage') or '-'} with "
        f"credibility {fmt_number(top.get('credibility_score'), 3)} and blend {top.get('blended_label', '-')}.")
    return answer(
        question,
        "current_signals_for_club",
        short,
        evidence_cards=cards,
        tables=[signal_table(rows)],
        warnings=["This ranks signals for research triage, not as trading advice."],
        confidence=0.86,
    )


def answer_compare_clubs(question: str, payload: dict[str, Any], club_a: str, club_b: str) -> dict[str, Any]:
    dossiers = payload.get("club_dossiers", {})
    a = dossiers.get(club_a, {})
    b = dossiers.get(club_b, {})
    stock_paths = payload.get("club_stock_paths", {})
    a_markers = len((stock_paths.get(club_a, {}) or {}).get("markers", []) or [])
    b_markers = len((stock_paths.get(club_b, {}) or {}).get("markers", []) or [])
    rows = [
        {
            "metric": "live_signal_count",
            club_a: a.get("live_signal_count", 0),
            club_b: b.get("live_signal_count", 0),
        },
        {
            "metric": "avg_live_credibility",
            club_a: fmt_number(a.get("avg_live_credibility"), 3),
            club_b: fmt_number(b.get("avg_live_credibility"), 3),
        },
        {
            "metric": "avg_transfer_index",
            club_a: fmt_number(a.get("avg_transfer_index"), 3),
            club_b: fmt_number(b.get("avg_transfer_index"), 3),
        },
        {
            "metric": "avg_realized_car_p3",
            club_a: fmt_number(a.get("avg_realized_car_p3"), 4),
            club_b: fmt_number(b.get("avg_realized_car_p3"), 4),
        },
        {
            "metric": "realized_positive_share",
            club_a: fmt_pct(a.get("realized_positive_share"), 1),
            club_b: fmt_pct(b.get("realized_positive_share"), 1),
        },
        {
            "metric": "match_markers",
            club_a: a_markers,
            club_b: b_markers,
        },
    ]
    if parse_float(a.get("live_signal_count"), 0.0) > parse_float(b.get("live_signal_count"), 0.0):
        lead = f"{club_a} has more live rumor coverage in this payload."
    elif parse_float(b.get("live_signal_count"), 0.0) > parse_float(a.get("live_signal_count"), 0.0):
        lead = f"{club_b} has more live rumor coverage in this payload."
    else:
        lead = f"{club_a} and {club_b} have similar live rumor volume in this payload."
    return answer(
        question,
        "compare_clubs",
        f"{lead} Compare transfer quality, realized CAR, and match markers before reading stock impact as signal.",
        evidence_cards=[
            {"title": club_a, "value": a.get("top_confidence_tier", "-"), "detail": f"{a.get('recent_transfer_count', 0)} recent transfers tracked."},
            {"title": club_b, "value": b.get("top_confidence_tier", "-"), "detail": f"{b.get('recent_transfer_count', 0)} recent transfers tracked."},
        ],
        tables=[{"title": "Club comparison", "columns": ["metric", club_a, club_b], "rows": rows}],
        warnings=["Club stocks can also move on match results, ownership news, liquidity, and broad markets."],
        confidence=0.9,
    )


def answer_reporter_profile(question: str, payload: dict[str, Any], reporter: str) -> dict[str, Any]:
    profile = payload.get("reporter_profiles", {}).get(reporter, {})
    if not profile:
        return answer(
            question,
            "reporter_profile",
            f"No reporter profile is available for {reporter}.",
            warnings=["Reporter profiles require journalist stats in the dashboard payload."],
            confidence=0.55,
        )
    cards = [
        {"title": "Claims", "value": profile.get("n_claims", 0), "detail": "Historical rows tied to this reporter."},
        {"title": "Smoothed hit rate", "value": fmt_number(profile.get("smoothed_rate"), 3), "detail": "Credibility stat from matched history."},
        {"title": "Avg match score", "value": fmt_number(profile.get("avg_match_score"), 3), "detail": "Entity-resolution confidence for matched claims."},
        {"title": "Avg realized CAR t+3", "value": fmt_number(profile.get("avg_realized_car_p3"), 4), "detail": "Average realized market label context where available."},
    ]
    club_rows = profile.get("clubs", []) or []
    source_rows = profile.get("sources", []) or []
    claim_rows = profile.get("latest_claims", []) or []
    return answer(
        question,
        "reporter_profile",
        f"{reporter} has {profile.get('n_claims', 0)} tracked claims with smoothed rate {fmt_number(profile.get('smoothed_rate'), 3)}.",
        evidence_cards=cards,
        tables=[
            {"title": "Club coverage", "columns": ["club", "count"], "rows": club_rows},
            {"title": "Source mix", "columns": ["source", "count"], "rows": source_rows},
            {
                "title": "Recent claims",
                "columns": ["date", "club", "player", "stage", "model"],
                "rows": [
                    {
                        "date": row_date(row),
                        "club": row.get("club", ""),
                        "player": row.get("player", ""),
                        "stage": row.get("rumor_stage", ""),
                        "model": row.get("predicted_label", ""),
                    }
                    for row in claim_rows[:6]
                ],
            },
        ],
        warnings=["Reporter scores reflect the local historical sample and can be biased by sparse coverage."],
        confidence=0.88,
    )


def answer_club_reporters(question: str, payload: dict[str, Any], club: str) -> dict[str, Any]:
    rows = [
        row for row in payload.get("leaderboards", {}).get("club_journalists", [])
        if row.get("club") == club
    ]
    rows = rows[:8]
    if not rows:
        rows = payload.get("club_dossiers", {}).get(club, {}).get("reporters", [])[:8]
    return answer(
        question,
        "club_reporters",
        f"{club} has {len(rows)} club-specific reporter row(s) in the local credibility table.",
        tables=[
            {
                "title": f"{club} reporters",
                "columns": ["journalist", "n_claims", "smoothed_rate", "avg_match_score"],
                "rows": [
                    {
                        "journalist": row.get("journalist", ""),
                        "n_claims": row.get("n_claims", 0),
                        "smoothed_rate": fmt_number(row.get("smoothed_rate"), 3),
                        "avg_match_score": fmt_number(row.get("avg_match_score"), 3),
                    }
                    for row in rows
                ],
            }
        ],
        warnings=["Sparse club-reporter rows should be read as leads, not proof of reliability."],
        confidence=0.8 if rows else 0.55,
    )


def find_signal_for_player(payload: dict[str, Any], player: str) -> dict[str, Any] | None:
    normalized_player = normalize_text(player)
    rows = all_signal_rows(payload)
    ranked = []
    for row in rows:
        if normalize_text(row.get("player")) != normalized_player:
            continue
        date_value = row.get("latest_published_at") or row.get("published_at") or row.get("date") or ""
        ranked.append((str(date_value), row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked else None


def answer_explain_rumor(question: str, payload: dict[str, Any], player: str) -> dict[str, Any]:
    row = find_signal_for_player(payload, player)
    if not row:
        return answer(
            question,
            "explain_rumor",
            f"No rumor signal for {player} is available in the local dashboard payload.",
            warnings=["Try a player that appears in current signals, live watchlist, or historical rows."],
            confidence=0.55,
        )
    links = row.get("confirmed_transfer_links", []) or []
    short = (
        f"{player} maps to {row_club(row) or '-'} as {row.get('target_role', '-')}. "
        f"The signal is {row.get('blended_label', '-')} with model label {row.get('predicted_label', '-')} "
        f"and confidence {fmt_pct(row.get('prediction_confidence'), 1)}.")
    tables = [signal_table([row])]
    if links:
        tables.append(
            {
                "title": "Closest confirmed transfer links",
                "columns": ["date", "player", "club", "role", "actual_label", "car_p3"],
                "rows": [
                    {
                        "date": item.get("date", ""),
                        "player": item.get("player", ""),
                        "club": item.get("club", ""),
                        "role": item.get("target_role", ""),
                        "actual_label": item.get("actual_label", ""),
                        "car_p3": fmt_number(item.get("actual_abnormal_return_p3"), 4),
                    }
                    for item in links[:5]
                ],
            }
        )
    return answer(
        question,
        "explain_rumor",
        short,
        evidence_cards=[
            {"title": "Credibility", "value": fmt_number(row.get("credibility_score"), 3), "detail": str(row.get("latest_source") or row.get("source") or "")},
            {"title": "Transfer index", "value": fmt_number(row.get("transfer_indicator"), 3), "detail": f"Stage {row.get('latest_rumor_stage') or row.get('rumor_stage') or '-'}"},
            {"title": "Scope", "value": row.get("prediction_scope", "-"), "detail": "Direct only when mapped to a public listed-club target."},
        ],
        tables=tables,
        warnings=["This is a model-assisted research summary, not a trade recommendation."],
        confidence=0.86,
    )


def answer_similar_cases(question: str, payload: dict[str, Any], player: str) -> dict[str, Any]:
    row = find_signal_for_player(payload, player)
    examples = (row or {}).get("similar_examples", []) or []
    return answer(
        question,
        "similar_historical_cases",
        f"Found {len(examples)} similar historical case(s) for {player}." if examples else f"No similar examples are attached for {player}.",
        tables=[
            {
                "title": "Similar historical cases",
                "columns": ["similarity", "date", "club", "player", "actual_label", "car_p3"],
                "rows": [
                    {
                        "similarity": fmt_number(item.get("similarity"), 3),
                        "date": item.get("date", ""),
                        "club": item.get("club", ""),
                        "player": item.get("player", ""),
                        "actual_label": item.get("actual_label", ""),
                        "car_p3": fmt_number(item.get("target_abnormal_return_p3"), 4),
                    }
                    for item in examples
                ],
            }
        ],
        warnings=["Similar cases are nearest-neighbor context, not proof of the same market reaction."],
        confidence=0.82 if examples else 0.55,
    )


def answer_match_stock_context(question: str, payload: dict[str, Any], club: str) -> dict[str, Any]:
    path = payload.get("club_stock_paths", {}).get(club, {}) or {}
    markers = path.get("markers", []) or []
    latest_markers = list(reversed(markers[-6:]))
    short = (
        f"{club} has {len(markers)} match-result marker(s) on its local stock path. "
        f"The chart spans {path.get('dates', ['-'])[0] if path.get('dates') else '-'} to {path.get('latest_date', '-')}.")
    return answer(
        question,
        "match_stock_context",
        short,
        evidence_cards=[
            {"title": "Ticker", "value": path.get("ticker", "-"), "detail": "Configured public equity symbol."},
            {"title": "Latest change", "value": fmt_pct(path.get("latest_change"), 1), "detail": "Change over the loaded chart window."},
            {"title": "Match markers", "value": len(markers), "detail": "Wins/losses/draws mapped to next trading date."},
        ],
        tables=[
            {
                "title": "Recent match markers",
                "columns": ["match_date", "trading_date", "opponent", "result", "score"],
                "rows": [
                    {
                        "match_date": row.get("match_date", ""),
                        "trading_date": row.get("trading_date", ""),
                        "opponent": row.get("opponent", ""),
                        "result": row.get("result", ""),
                        "score": row.get("score", ""),
                    }
                    for row in latest_markers
                ],
            }
        ],
        warnings=["Match markers show timing context only; they do not isolate causality from other market events."],
        confidence=0.86 if path else 0.55,
    )


def answer_confirmed_transfers(question: str, payload: dict[str, Any], club: str, season: str) -> dict[str, Any]:
    rows = [
        row for row in payload.get("transfers_by_season", {}).get(season, []) or []
        if row.get("club") == club or row.get("subject_club") == club
    ][:10]
    return answer(
        question,
        "confirmed_transfers",
        f"{club} has {len(rows)} confirmed public-target transfer row(s) in {season}.",
        tables=[
            {
                "title": f"{club} confirmed transfers",
                "columns": ["date", "player", "role", "seller", "buyer", "transfer_index", "actual_label"],
                "rows": [
                    {
                        "date": row.get("date", ""),
                        "player": row.get("player", ""),
                        "role": row.get("target_role", ""),
                        "seller": row.get("seller_club", ""),
                        "buyer": row.get("buyer_club", ""),
                        "transfer_index": fmt_number(row.get("transfer_indicator"), 3),
                        "actual_label": row.get("actual_label", ""),
                    }
                    for row in rows
                ],
            }
        ],
        warnings=["Confirmed transfer dates may be later than initial rumor dates, so market reaction may already be priced in."],
        confidence=0.82 if rows else 0.6,
    )


def ask_analyst(
    question: str,
    payload: dict[str, Any] | None = None,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    *,
    include_evidence: bool = False,
    evidence_index_path: str | Path | None = None,
    evidence_top_k: int = 5,
) -> dict[str, Any]:
    data = payload if payload is not None else load_dashboard_payload(payload_path)
    detected = detect_intent(question, data)
    intent = detected.get("intent", "unknown")
    if intent == "compare_clubs":
        result = answer_compare_clubs(question, data, detected["clubs"][0], detected["clubs"][1])
    elif intent == "reporter_profile":
        result = answer_reporter_profile(question, data, detected["reporter"])
    elif intent == "club_reporters":
        result = answer_club_reporters(question, data, detected["club"])
    elif intent == "similar_historical_cases":
        result = answer_similar_cases(question, data, detected["player"])
    elif intent == "explain_rumor":
        result = answer_explain_rumor(question, data, detected["player"])
    elif intent == "match_stock_context":
        result = answer_match_stock_context(question, data, detected["club"])
    elif intent == "confirmed_transfers":
        result = answer_confirmed_transfers(question, data, detected["club"], detected["season"])
    elif intent == "current_signals_for_club":
        result = answer_current_signals(question, data, detected["club"])
    else:
        result = answer(
            question,
            "unknown",
            "I could not map this question to a club, reporter, player, comparison, or transfer-history query in the local payload.",
            warnings=[
                "Try naming a configured club, player, or reporter.",
                "Examples: 'Compare Manchester United and Juventus', 'Explain Casemiro', or 'Show Fabrizio Romano profile'.",
            ],
            confidence=0.25,
        )
    if include_evidence:
        from .evidence_rag import attach_evidence_to_answer

        return attach_evidence_to_answer(
            result,
            question,
            payload=data,
            payload_path=payload_path,
            index_path=evidence_index_path,
            top_k=evidence_top_k,
        )
    return result
