from __future__ import annotations

from typing import Any

from .analyst import parse_float
from .demo import similar_examples
from .features import clamp
from .indicators import transfer_indicator
from .model import heuristic_market_impact


RUMOR_STAGE_SCORES = {
    "unclear": 0.40,
    "linked": 0.44,
    "talks": 0.52,
    "bid": 0.62,
    "advanced": 0.72,
    "agreed": 0.84,
    "medical": 0.90,
    "official": 0.96,
}


def direction_for_role(target_role: str) -> str:
    return "out" if str(target_role).lower() == "seller" else "in"


def credibility_from_payload(payload: dict[str, Any], source: str = "", journalist: str = "") -> tuple[float, list[str]]:
    warnings: list[str] = []
    source_norm = source.strip().lower()
    journalist_norm = journalist.strip().lower()
    source_score = 0.0
    journalist_score = 0.0

    for row in (payload.get("leaderboards", {}) or {}).get("sources", []) or []:
        if source_norm and source_norm == str(row.get("source", "")).strip().lower():
            source_score = parse_float(row.get("smoothed_rate"), 0.0)
            break

    for row in (payload.get("leaderboards", {}) or {}).get("journalists", []) or []:
        if journalist_norm and journalist_norm == str(row.get("journalist", "")).strip().lower():
            journalist_score = parse_float(row.get("smoothed_rate"), 0.0)
            break

    if journalist_norm and not journalist_score:
        profile = (payload.get("reporter_profiles", {}) or {}).get(journalist, {})
        journalist_score = parse_float(profile.get("smoothed_rate"), 0.0)

    if source_score and journalist_score:
        score = 0.45 * source_score + 0.55 * journalist_score
    elif journalist_score:
        score = journalist_score
    elif source_score:
        score = source_score
    else:
        score = 0.50
        warnings.append("No matching source or journalist history found; credibility defaults to neutral.")
    return round(clamp(score), 4), warnings


def historical_signal_rows(payload: dict[str, Any], latest_only: bool = False) -> list[dict[str, Any]]:
    latest = str(payload.get("latest_season", ""))
    rows: list[dict[str, Any]] = []
    for season, season_rows in (payload.get("signals_by_season", {}) or {}).items():
        if not latest_only and season == latest:
            continue
        rows.extend(season_rows or [])
    if not rows and not latest_only:
        return historical_signal_rows(payload, latest_only=True)
    return rows


def simulator_input_row(inputs: dict[str, Any], credibility: float, rumor_stage_score: float, transfer_ind: float) -> dict[str, Any]:
    role = str(inputs.get("target_role") or "buyer").lower()
    return {
        "club": str(inputs.get("target_club") or ""),
        "target_club": str(inputs.get("target_club") or ""),
        "target_role": role,
        "direction": direction_for_role(role),
        "position": str(inputs.get("position") or ""),
        "age": parse_float(inputs.get("age"), 27.0),
        "market_value_eur": parse_float(inputs.get("market_value_eur"), 0.0),
        "transfer_fee_eur": parse_float(inputs.get("transfer_fee_eur"), 0.0),
        "wage_eur_annual": parse_float(inputs.get("wage_eur_annual"), 0.0),
        "transfer_type": str(inputs.get("transfer_type") or "permanent"),
        "is_loan": 1 if "loan" in str(inputs.get("transfer_type") or "").lower() else 0,
        "credibility_score": credibility,
        "transfer_indicator": transfer_ind,
        "rumor_stage_score": rumor_stage_score,
        "stock_context_indicator": 0.0,
    }


def estimate_impact_range(midpoint: float, confidence: float) -> dict[str, Any]:
    half_width = 0.018 + (1.0 - clamp(confidence)) * 0.045
    low = max(-0.10, midpoint - half_width)
    high = min(0.10, midpoint + half_width)
    return {
        "midpoint": round(midpoint, 4),
        "low": round(low, 4),
        "high": round(high, 4),
        "label": "positive" if low > 0.005 else ("negative" if high < -0.005 else "watch"),
    }


def scenario_swarm_seed(inputs: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal": {
            "player": str(inputs.get("player") or "Hypothetical Player"),
            "club": str(inputs.get("target_club") or ""),
            "target_club": str(inputs.get("target_club") or ""),
            "target_role": str(inputs.get("target_role") or "buyer"),
            "rumor_stage": str(inputs.get("rumor_stage") or "linked"),
            "credibility_score": result["credibility_indicator"],
            "transfer_indicator": result["transfer_indicator"],
            "rumor_indicator": result["rumor_indicator"],
            "predicted_label": result["estimated_impact"]["label"],
            "blended_label": result["estimated_impact"]["label"],
            "prediction_confidence": result["confidence"],
            "latest_source": str(inputs.get("source") or ""),
            "latest_journalist": str(inputs.get("journalist") or ""),
            "position": str(inputs.get("position") or ""),
            "age": parse_float(inputs.get("age"), 27.0),
            "market_value_eur": parse_float(inputs.get("market_value_eur"), 0.0),
            "transfer_fee_eur": parse_float(inputs.get("transfer_fee_eur"), 0.0),
            "wage_eur_annual": parse_float(inputs.get("wage_eur_annual"), 0.0),
        },
        "note": "This seed is compatible with Scenario Swarm evidence shape but is not an article-backed rumor.",
    }


def simulate_hypothetical_transfer(payload: dict[str, Any], inputs: dict[str, Any], *, examples_limit: int = 3) -> dict[str, Any]:
    warnings = [
        "Exploratory simulator only; this is not investment advice.",
        "No future price movement is used to score the hypothetical scenario.",
    ]
    role = str(inputs.get("target_role") or "buyer").lower()
    stage = str(inputs.get("rumor_stage") or "linked").lower()
    target_club = str(inputs.get("target_club") or "")
    transfer_type = str(inputs.get("transfer_type") or "permanent").lower()
    direction = direction_for_role(role)
    credibility, credibility_warnings = credibility_from_payload(
        payload,
        source=str(inputs.get("source") or ""),
        journalist=str(inputs.get("journalist") or ""),
    )
    warnings.extend(credibility_warnings)

    transfer_row = {
        "date": "2026-01-01",
        "club": target_club,
        "player": str(inputs.get("player") or "Hypothetical Player"),
        "direction": direction,
        "age": str(parse_float(inputs.get("age"), 27.0)),
        "position": str(inputs.get("position") or ""),
        "market_value_eur": str(parse_float(inputs.get("market_value_eur"), 0.0)),
        "transfer_fee_eur": str(parse_float(inputs.get("transfer_fee_eur"), 0.0)),
        "wage_eur_annual": str(parse_float(inputs.get("wage_eur_annual"), 0.0)),
        "transfer_type": transfer_type,
        "is_loan": "1" if "loan" in transfer_type else "0",
        "source": "scenario_simulator",
        "url": "",
    }
    transfer_ind = transfer_indicator(transfer_row)
    stage_score = RUMOR_STAGE_SCORES.get(stage, RUMOR_STAGE_SCORES["unclear"])
    rumor_ind = round(clamp(0.58 * credibility + 0.32 * stage_score + 0.10 * (0.35 if "loan" in transfer_type else 0.55)), 4)
    impact = heuristic_market_impact(rumor_strength=rumor_ind, transfer_quality=transfer_ind, direction=direction)
    confidence = round(clamp(0.35 * credibility + 0.35 * stage_score + 0.30 * impact["confidence"]), 4)
    impact_range = estimate_impact_range(parse_float(impact.get("predicted_car"), 0.0), confidence)

    current = simulator_input_row(inputs, credibility, stage_score, transfer_ind)
    historical_rows = historical_signal_rows(payload)
    examples = similar_examples(current, historical_rows, limit=examples_limit) if historical_rows else []

    media = (payload.get("club_media", {}) or {}).get(target_club, {})
    if not media.get("ticker"):
        warnings.append("Target club has no configured public ticker in the dashboard payload; interpret impact as transfer intelligence only.")
    if "loan" in transfer_type:
        warnings.append("Loan scenarios are discounted because fees, wages, and obligations are often incomplete.")
    if not examples:
        warnings.append("No historical examples were available from pre-latest-season payload rows.")

    result = {
        "target_club": target_club,
        "target_role": role,
        "direction": direction,
        "transfer_indicator": transfer_ind,
        "credibility_indicator": credibility,
        "rumor_indicator": rumor_ind,
        "rumor_stage_score": round(stage_score, 4),
        "estimated_impact": impact_range,
        "model_midpoint_label": impact.get("label", ""),
        "confidence": confidence,
        "nearest_historical_examples": examples,
        "history_policy": "Nearest examples exclude the latest season when older rows exist.",
        "scenario_swarm_seed": {},
        "warnings": warnings,
    }
    result["scenario_swarm_seed"] = scenario_swarm_seed(inputs, result)
    return result
