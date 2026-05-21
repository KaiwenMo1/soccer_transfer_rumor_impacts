from __future__ import annotations

import math
from typing import Any

from .transfers import Transfer


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def transfer_quality_score(transfer: Transfer) -> float:
    """Transparent starter score until enough labeled data exists."""
    market = transfer.market_value_eur or 0.0
    fee = transfer.transfer_fee_eur or 0.0
    wage = transfer.wage_eur_annual or 0.0
    age = transfer.age or 27.0

    value_gap = 0.0
    if market > 0:
        if transfer.direction == "in":
            value_gap = (market - fee) / market
        else:
            value_gap = (fee - market) / market
    value_component = clamp(0.5 + value_gap / 2.0)

    wage_burden = clamp(wage / 25_000_000.0)
    wage_component = 1.0 - 0.35 * wage_burden

    if transfer.direction == "in":
        age_component = clamp(1.0 - abs(age - 24.0) / 12.0)
    else:
        age_component = clamp(0.65 + max(age - 27.0, 0.0) / 12.0)

    return round(clamp(0.45 * value_component + 0.30 * age_component + 0.25 * wage_component), 4)


def credibility_score(text: str, source: str, credibility_config: dict[str, Any]) -> float:
    base = float(credibility_config.get("default_source_score", 0.5))
    for name, score in credibility_config.get("sources", {}).items():
        if name.lower() in source.lower() or name.lower() in text.lower():
            base = max(base, float(score))

    lowered = text.lower()
    adjustment = 0.0
    for keyword, score in credibility_config.get("keywords", {}).items():
        if keyword.lower() in lowered:
            adjustment += float(score)
    return round(clamp(base + adjustment), 4)


def article_features(article: dict[str, object], credibility_config: dict[str, Any]) -> dict[str, object]:
    text = f"{article.get('title', '')} {article.get('snippet', '')}"
    score = credibility_score(text, str(article.get("source", "")), credibility_config)
    urgency = 1.0 if any(word in text.lower() for word in ["medical", "agreement", "signed"]) else 0.4
    return {
        **article,
        "credibility_score": score,
        "rumor_strength": round(clamp(0.65 * score + 0.35 * urgency), 4),
    }


def log_money(value: float | None) -> float:
    if not value or value <= 0:
        return 0.0
    return math.log1p(value)

