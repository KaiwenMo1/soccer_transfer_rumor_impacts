from __future__ import annotations

from .features import clamp


def impact_label(score: float) -> str:
    if score <= -0.02:
        return "negative"
    if score >= 0.02:
        return "positive"
    return "neutral"


def heuristic_market_impact(
    rumor_strength: float,
    transfer_quality: float = 0.5,
    direction: str = "in",
    liquidity_penalty: float = 0.0,
) -> dict[str, object]:
    direction_sign = 1.0 if direction == "in" else 0.65
    raw = (rumor_strength - 0.5) * 0.05 + (transfer_quality - 0.5) * 0.06 * direction_sign
    adjusted = raw - liquidity_penalty
    adjusted = max(-0.08, min(0.08, adjusted))
    confidence = clamp(0.35 + 0.45 * rumor_strength - 0.20 * liquidity_penalty)
    return {
        "predicted_car": round(adjusted, 4),
        "label": impact_label(adjusted),
        "confidence": round(confidence, 4),
    }

