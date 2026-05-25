from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .backtesting import blended_signal_confidence, blended_signal_label, blended_signal_score
from .config import Club, DATA_DIR, load_clubs
from .io import ensure_parent, read_csv, read_jsonl
from .market_features import compute_market_features_for_event, load_bars
from .targets import direct_target_rows
from .transfers import load_transfers


COMMON_HEADLINE_TOKENS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "for",
    "of",
    "on",
    "in",
    "with",
    "news",
    "rumor",
    "rumors",
    "rumour",
    "rumours",
    "transfer",
    "transfers",
    "deal",
    "deals",
    "move",
    "moves",
    "sign",
    "signs",
    "signing",
    "bid",
    "bids",
    "update",
    "updates",
    "report",
    "reports",
    "star",
    "latest",
    "live",
}

AGGREGATOR_SOURCE_PREFIXES = (
    "google news",
)

STAGE_SEQUENCE = [
    "linked",
    "talks",
    "bid",
    "advanced",
    "agreed",
    "medical",
    "official",
]
STAGE_RANK = {stage: index for index, stage in enumerate(STAGE_SEQUENCE)}


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def optional_float(value: Any) -> float | str:
    if value in {"", None}:
        return ""
    try:
        return float(value)
    except (TypeError, ValueError):
        return ""


def season_start(season: str) -> int:
    left = (season or "").split("-", 1)[0]
    return int(left) if left.isdigit() else 0


def parse_timestamp(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        return datetime(1970, 1, 1, tzinfo=UTC)
    if text.endswith("Z") and "-" in text:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    if text.endswith("Z") and "T" in text:
        try:
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        return parsedate_to_datetime(text).astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        pass
    return datetime(1970, 1, 1, tzinfo=UTC)


def format_short_date(value: str) -> str:
    dt = parse_timestamp(value)
    if dt.year <= 1970:
        return ""
    return dt.date().isoformat()


def title_base(title: str) -> str:
    text = (title or "").strip()
    if not text:
        return ""
    if " - " in text:
        text = text.rsplit(" - ", 1)[0]
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def title_suffix_source(title: str) -> str:
    text = (title or "").strip()
    if " - " not in text:
        return ""
    suffix = text.rsplit(" - ", 1)[-1].strip()
    if not suffix or len(suffix) > 80:
        return ""
    return suffix


def snippet_source(snippet: str) -> str:
    text = (snippet or "").strip()
    if not text:
        return ""
    match = re.search(r"<font[^>]*>([^<]+)</font>", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def publisher_label(row: dict[str, Any]) -> str:
    source = str(row.get("source", "")).strip()
    normalized = source.split(" / ", 1)[0].strip()
    if normalized and normalized.lower().startswith(AGGREGATOR_SOURCE_PREFIXES):
        return (
            title_suffix_source(str(row.get("title", "")))
            or snippet_source(str(row.get("snippet", "")))
            or normalized
        )
    return normalized or title_suffix_source(str(row.get("title", ""))) or "Unknown"


def headline_fingerprint(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", title_base(title).lower())
    tokens = [token for token in normalized.split() if token and token not in COMMON_HEADLINE_TOKENS]
    if not tokens:
        return normalized.strip()
    return " ".join(tokens[:10])


def probability_breakdown(row: dict[str, str]) -> dict[str, float]:
    return {
        "negative": round(parse_float(row.get("prob_negative"), 0.0), 4),
        "neutral": round(parse_float(row.get("prob_neutral"), 0.0), 4),
        "positive": round(parse_float(row.get("prob_positive"), 0.0), 4),
    }


def summarize_group(rows: list[dict[str, str]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: parse_timestamp(row.get("published_at", "")), reverse=True)
    latest = ordered[0]
    scores = [blended_signal_score(row) for row in ordered]
    predicted_counts = Counter(row.get("predicted_label", "") for row in ordered)
    sources = sorted({publisher_label(row) for row in ordered if publisher_label(row)})
    journalists = sorted({row.get("journalist", "") for row in ordered if row.get("journalist")})
    actual_values = [row.get("actual_label", "") for row in ordered if row.get("actual_label")]
    claim_ids = [row.get("claim_id", "") for row in ordered if row.get("claim_id")]
    return {
        "group_key": f"{latest.get('club', '')}::{latest.get('player', '')}",
        "club": latest.get("club", ""),
        "player": latest.get("player", ""),
        "title": latest.get("title", ""),
        "season": latest.get("season", ""),
        "direction": latest.get("direction", ""),
        "buyer_club": latest.get("buyer_club", ""),
        "seller_club": latest.get("seller_club", ""),
        "position": latest.get("position", ""),
        "age": parse_float(latest.get("age"), 0.0),
        "market_value_eur": parse_float(latest.get("market_value_eur"), 0.0),
        "transfer_fee_eur": parse_float(latest.get("transfer_fee_eur"), 0.0),
        "transfer_type": latest.get("transfer_type", ""),
        "latest_published_at": latest.get("published_at", ""),
        "latest_source": publisher_label(latest),
        "latest_journalist": latest.get("journalist", ""),
        "latest_rumor_stage": latest.get("rumor_stage", ""),
        "article_count": len(rows),
        "source_count": len(sources),
        "sources": sources,
        "journalists": journalists,
        "credibility_score": round(parse_float(latest.get("credibility_score"), 0.0), 4),
        "transfer_indicator": round(parse_float(latest.get("transfer_indicator"), 0.0), 4),
        "rumor_indicator": round(parse_float(latest.get("rumor_indicator"), 0.0), 4),
        "stock_context_indicator": round(parse_float(latest.get("stock_context_indicator"), 0.0), 4),
        "rumor_stage_score": round(parse_float(latest.get("rumor_stage_score"), 0.0), 4),
        "prediction_confidence": round(parse_float(latest.get("prediction_confidence"), 0.0), 4),
        "predicted_label": latest.get("predicted_label", ""),
        "predicted_probabilities": probability_breakdown(latest),
        "target_club": latest.get("target_club", ""),
        "target_ticker": latest.get("target_ticker", ""),
        "target_market_index": latest.get("target_market_symbol", latest.get("target_market_index", "")),
        "target_exchange_timezone": latest.get("target_exchange_timezone", ""),
        "target_entity_type": latest.get("target_entity_type", ""),
        "target_role": latest.get("target_role", ""),
        "prediction_scope": latest.get("prediction_scope", ""),
        "blended_score": round(blended_signal_score(latest), 2),
        "blended_label": blended_signal_label(latest),
        "blended_confidence": blended_signal_confidence(latest),
        "predicted_label_mix": dict(predicted_counts),
        "realized_label": actual_values[0] if actual_values else "",
        "target_abnormal_return_p3": (
            round(optional_float(latest.get("target_abnormal_return_p3")), 6)
            if optional_float(latest.get("target_abnormal_return_p3")) != ""
            else ""
        ),
        "pre_market_return_30d": (
            round(optional_float(latest.get("pre_market_return_30d")), 6)
            if optional_float(latest.get("pre_market_return_30d")) != ""
            else ""
        ),
        "pre_volatility_20d": (
            round(optional_float(latest.get("pre_volatility_20d")), 6)
            if optional_float(latest.get("pre_volatility_20d")) != ""
            else ""
        ),
        "match_score": round(parse_float(latest.get("match_score"), 0.0), 4),
        "entity_match_indicator": round(parse_float(latest.get("entity_match_indicator"), 0.0), 4),
        "claim_ids": claim_ids,
    }


def counterparty_club(row: dict[str, Any]) -> str:
    role = str(row.get("target_role", "")).strip()
    if role == "buyer":
        return str(row.get("seller_club", "")).strip()
    if role == "seller":
        return str(row.get("buyer_club", "")).strip()
    return ""


def deal_path_label(row: dict[str, Any]) -> str:
    seller = str(row.get("seller_club", "")).strip() or "Unknown seller"
    buyer = str(row.get("buyer_club", "")).strip() or "Unknown buyer"
    return f"{seller} -> {buyer}"


def top_similar_summary(example: dict[str, Any] | None) -> str:
    if not example:
        return ""
    club = str(example.get("club", "")).strip()
    player = str(example.get("player", "")).strip()
    actual_label = str(example.get("actual_label", "")).strip() or "unlabeled"
    car = optional_float(example.get("target_abnormal_return_p3"))
    if car == "":
        return f"{player} / {club} · {actual_label}"
    return f"{player} / {club} · {actual_label} · CAR {float(car):.4f}"


def same_player(left: Any, right: Any) -> bool:
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def row_date(value: Any) -> date | None:
    dt = parse_timestamp(str(value or ""))
    if dt.year <= 1970:
        return None
    return dt.date()


def confirmed_transfer_links(
    row: dict[str, Any],
    transfer_rows: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    player = str(row.get("player", "")).strip()
    target_club = str(row.get("target_club") or row.get("club") or "").strip()
    role = str(row.get("target_role", "")).strip()
    event_date = row_date(row.get("latest_published_at") or row.get("published_at") or row.get("date"))
    if not player or not target_club:
        return []
    scored: list[tuple[float, dict[str, Any]]] = []
    for transfer in transfer_rows:
        if not same_player(player, transfer.get("player")):
            continue
        score = 0.0
        if str(transfer.get("club", "")).strip() == target_club:
            score += 0.55
        if role and str(transfer.get("target_role", "")).strip() == role:
            score += 0.20
        if str(transfer.get("buyer_club", "")).strip() == str(row.get("buyer_club", "")).strip() and row.get("buyer_club"):
            score += 0.08
        if str(transfer.get("seller_club", "")).strip() == str(row.get("seller_club", "")).strip() and row.get("seller_club"):
            score += 0.08
        transfer_date = row_date(transfer.get("date"))
        if event_date and transfer_date:
            days = abs((transfer_date - event_date).days)
            score += max(0.0, 0.17 - min(days, 365) / 365.0 * 0.17)
        if score <= 0.0:
            continue
        scored.append((score, transfer))
    scored.sort(key=lambda item: (item[0], str(item[1].get("date", ""))), reverse=True)
    output: list[dict[str, Any]] = []
    for score, transfer in scored[:limit]:
        output.append(
            {
                "match_score": round(score, 4),
                "date": transfer.get("date", ""),
                "season": transfer.get("season", ""),
                "player": transfer.get("player", ""),
                "club": transfer.get("club", ""),
                "buyer_club": transfer.get("buyer_club", ""),
                "seller_club": transfer.get("seller_club", ""),
                "target_role": transfer.get("target_role", ""),
                "transfer_type": transfer.get("transfer_type", ""),
                "transfer_fee_eur": transfer.get("transfer_fee_eur", ""),
                "market_value_eur": transfer.get("market_value_eur", ""),
                "transfer_indicator": transfer.get("transfer_indicator", ""),
                "actual_label": transfer.get("actual_label", ""),
                "actual_abnormal_return_p3": transfer.get("actual_abnormal_return_p3", ""),
                "transfer_key": transfer.get("transfer_key", ""),
            }
        )
    return output


def signal_summary(row: dict[str, Any], top_example: dict[str, Any] | None = None) -> str:
    tier = str(row.get("confidence_tier", "thin")).replace("_", " ")
    role = str(row.get("target_role", "")).strip() or "target"
    outlets = int(parse_float(row.get("source_count"), 0.0))
    direct_articles = int(parse_float(row.get("direct_article_count"), 0.0))
    counterparty = counterparty_club(row) or "counterparty unconfirmed"
    base = f"{tier.title()} {role}-side event across {outlets} outlets with {direct_articles} direct article"
    if direct_articles != 1:
        base += "s"
    base += f"; counterparty: {counterparty}."
    similar = top_similar_summary(top_example)
    if similar:
        base += f" Closest historical comp: {similar}."
    return base


def reporter_profiles(
    rows: list[dict[str, str]],
    journalist_leaderboard: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> dict[str, dict[str, Any]]:
    by_reporter: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        journalist = str(row.get("journalist", "")).strip()
        if not journalist:
            continue
        by_reporter.setdefault(journalist, []).append(row)

    leaderboard_lookup = {
        str(row.get("journalist", "")).strip(): row
        for row in journalist_leaderboard
        if str(row.get("journalist", "")).strip()
    }
    ranked_names = [row["journalist"] for row in journalist_leaderboard if row.get("journalist")]
    for journalist in by_reporter:
        if journalist not in ranked_names:
            ranked_names.append(journalist)

    profiles: dict[str, dict[str, Any]] = {}
    for journalist in ranked_names[:limit]:
        reporter_rows = by_reporter.get(journalist, [])
        ordered = sorted(reporter_rows, key=lambda row: parse_timestamp(str(row.get("published_at", ""))), reverse=True)
        clubs = Counter(row.get("target_club") or row.get("club", "") for row in reporter_rows)
        sources = Counter(publisher_label(row) for row in reporter_rows)
        realized = [
            row for row in reporter_rows
            if row.get("actual_label") and row.get("target_abnormal_return_p3") not in {"", None}
        ]
        avg_car = (
            round(sum(parse_float(row.get("target_abnormal_return_p3"), 0.0) for row in realized) / len(realized), 6)
            if realized
            else 0.0
        )
        leaderboard_row = leaderboard_lookup.get(journalist, {})
        profiles[journalist] = {
            "journalist": journalist,
            "n_claims": int(parse_float(leaderboard_row.get("n_claims"), len(reporter_rows))),
            "smoothed_rate": round(parse_float(leaderboard_row.get("smoothed_rate"), 0.0), 4),
            "avg_match_score": round(parse_float(leaderboard_row.get("avg_match_score"), 0.0), 4),
            "clubs": [{"club": club, "count": count} for club, count in clubs.most_common(6) if club],
            "sources": [{"source": source, "count": count} for source, count in sources.most_common(6) if source],
            "avg_realized_car_p3": avg_car,
            "realized_count": len(realized),
            "latest_claims": [
                {
                    "published_at": row.get("published_at", ""),
                    "club": row.get("target_club") or row.get("club", ""),
                    "player": row.get("player", ""),
                    "source": publisher_label(row),
                    "rumor_stage": row.get("rumor_stage", ""),
                    "predicted_label": row.get("predicted_label", ""),
                    "actual_label": row.get("actual_label", ""),
                    "title": title_base(str(row.get("title", ""))),
                    "url": row.get("url", ""),
                }
                for row in ordered[:8]
            ],
        }
    return profiles


def target_role(direction: str) -> str:
    if direction == "in":
        return "buyer"
    if direction == "out":
        return "seller"
    return "unknown"


def target_metadata(club_name: str, direction: str, clubs_by_name: dict[str, Club]) -> dict[str, str]:
    club = clubs_by_name.get((club_name or "").lower())
    if club is None:
        return {
            "target_club": club_name or "",
            "target_ticker": "",
            "target_market_index": "",
            "target_exchange_timezone": "",
            "target_entity_type": "",
            "target_role": target_role(direction),
            "prediction_scope": "none",
        }
    return {
        "target_club": club.name,
        "target_ticker": club.yahoo_symbol or club.stooq_symbol,
        "target_market_index": club.yahoo_market_symbol or club.market_index_symbol,
        "target_exchange_timezone": club.exchange_timezone,
        "target_entity_type": club.entity_type,
        "target_role": target_role(direction),
        "prediction_scope": "direct",
    }


def season_summary(season: str, signal_rows: list[dict[str, Any]]) -> dict[str, Any]:
    realized_rows = [row for row in signal_rows if row.get("realized_label")]
    realized_returns = [parse_float(row.get("target_abnormal_return_p3"), 0.0) for row in realized_rows]
    realized_counts = Counter(row.get("realized_label", "") for row in realized_rows)
    direct_count = sum(1 for row in signal_rows if row.get("prediction_scope") == "direct")
    intelligence_only_count = sum(1 for row in signal_rows if row.get("prediction_scope") == "none")
    positive_share = 0.0
    if realized_rows:
        positive_share = realized_counts.get("positive", 0) / len(realized_rows)
    return {
        "season": season,
        "signal_count": len(signal_rows),
        "direct_count": direct_count,
        "intelligence_only_count": intelligence_only_count,
        "realized_count": len(realized_rows),
        "avg_realized_car_p3": round(sum(realized_returns) / len(realized_returns), 6) if realized_returns else 0.0,
        "positive_share": round(positive_share, 4),
        "realized_label_mix": dict(realized_counts),
        "latest_published_at": max((row.get("latest_published_at", "") for row in signal_rows), default=""),
    }


def transfer_history_rows(clubs: dict[str, Club], transfers_path: Path) -> list[dict[str, Any]]:
    stock_cache: dict[str, tuple[list[Any], list[Any]]] = {}
    rows: list[dict[str, Any]] = []
    today = datetime.now(tz=UTC).date()
    for transfer in load_transfers(transfers_path):
        if transfer.date > today:
            continue
        if transfer.transfer_type == "loan_return":
            continue
        base_row = {
            "club": transfer.club,
            "subject_club": transfer.club,
            "player": transfer.player,
            "season": transfer.season,
            "direction": transfer.direction,
            "subject_direction": transfer.direction,
            "transfer_type": transfer.transfer_type,
            "is_loan": int(transfer.is_loan),
            "age": transfer.age if transfer.age is not None else "",
            "position": transfer.position,
            "market_value_eur": transfer.market_value_eur if transfer.market_value_eur is not None else "",
            "transfer_fee_eur": transfer.transfer_fee_eur if transfer.transfer_fee_eur is not None else "",
            "wage_eur_annual": transfer.wage_eur_annual if transfer.wage_eur_annual is not None else "",
        }
        for target_row in direct_target_rows(base_row, transfer, clubs):
            if target_row.get("prediction_scope") != "direct":
                continue
            target_club = target_row.get("target_club", "")
            target_key = ""
            for club in clubs.values():
                names = {club.name, club.key, *club.aliases}
                if target_club in names:
                    target_key = club.key
                    break
            if target_key not in stock_cache:
                stock_cache[target_key] = (
                    load_bars(DATA_DIR / "raw" / "stocks" / f"{target_key}.csv"),
                    load_bars(DATA_DIR / "raw" / "stocks" / f"{target_key}_market.csv"),
                )
            stock_bars, market_bars = stock_cache.get(target_key, ([], []))
            market = compute_market_features_for_event(transfer.date, stock_bars, market_bars)
            rows.append(
                {
                    "transfer_key": f"{transfer.date.isoformat()}::{target_row.get('target_club','')}::{transfer.player}::{target_row.get('target_role','')}",
                    "date": transfer.date.isoformat(),
                    "season": transfer.season,
                    "player": transfer.player,
                    "club": target_row.get("target_club", ""),
                    "subject_club": transfer.club,
                    "buyer_club": target_row.get("buyer_club", ""),
                    "seller_club": target_row.get("seller_club", ""),
                    "target_role": target_row.get("target_role", ""),
                    "direction": target_row.get("direction", ""),
                    "position": transfer.position,
                    "age": transfer.age if transfer.age is not None else "",
                    "transfer_type": transfer.transfer_type,
                    "is_loan": int(transfer.is_loan),
                    "market_value_eur": transfer.market_value_eur if transfer.market_value_eur is not None else "",
                    "transfer_fee_eur": transfer.transfer_fee_eur if transfer.transfer_fee_eur is not None else "",
                    "wage_eur_annual": transfer.wage_eur_annual if transfer.wage_eur_annual is not None else "",
                    "fee_to_market": target_row.get("fee_to_market", 0.0),
                    "market_minus_fee_eur": target_row.get("market_minus_fee_eur", 0.0),
                    "transfer_quality": target_row.get("transfer_quality", 0.0),
                    "transfer_indicator": target_row.get("transfer_indicator", 0.0),
                    "target_ticker": target_row.get("target_ticker", ""),
                    "target_entity_type": target_row.get("target_entity_type", ""),
                    "prediction_scope": "direct",
                    "market_feature_status": market.get("market_feature_status", ""),
                    "actual_label": market.get("target_label_p3", ""),
                    "actual_abnormal_return_p3": market.get("target_abnormal_return_p3", ""),
                    "event_trading_date": market.get("event_trading_date", ""),
                    "event_trading_offset_days": market.get("event_trading_offset_days", ""),
                    "relative_volume_20d": market.get("relative_volume_20d", ""),
                    "pre_volatility_20d": market.get("pre_volatility_20d", ""),
                }
            )
    rows.sort(key=lambda row: (row.get("date", ""), row.get("club", ""), row.get("player", "")), reverse=True)
    return rows


def transfer_history_summary(season: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    realized_rows = [row for row in rows if row.get("actual_label")]
    realized_returns = [float(row.get("actual_abnormal_return_p3")) for row in realized_rows if row.get("actual_abnormal_return_p3") not in {"", None}]
    label_mix = Counter(row.get("actual_label", "") for row in realized_rows)
    positive_share = 0.0
    if realized_rows:
        positive_share = label_mix.get("positive", 0) / len(realized_rows)
    avg_index = sum(parse_float(row.get("transfer_indicator"), 0.0) for row in rows) / len(rows) if rows else 0.0
    return {
        "season": season,
        "transfer_count": len(rows),
        "realized_count": len(realized_rows),
        "avg_transfer_index": round(avg_index, 4),
        "avg_realized_car_p3": round(sum(realized_returns) / len(realized_returns), 6) if realized_returns else 0.0,
        "positive_share": round(positive_share, 4),
        "realized_label_mix": dict(label_mix),
    }


def market_sensitive_club(rows: list[dict[str, Any]], min_rows: int = 12) -> dict[str, Any]:
    by_club: dict[str, list[float]] = {}
    for row in rows:
        club = str(row.get("club", "")).strip()
        value = optional_float(row.get("actual_abnormal_return_p3"))
        if not club or value == "":
            continue
        by_club.setdefault(club, []).append(abs(float(value)))
    best: dict[str, Any] = {}
    for club, values in by_club.items():
        if len(values) < min_rows:
            continue
        avg_abs = sum(values) / len(values)
        if not best or avg_abs > best["avg_abs_car_p3"]:
            best = {
                "club": club,
                "avg_abs_car_p3": round(avg_abs, 4),
                "n_rows": len(values),
            }
    return best


def extreme_realized_examples(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    realized = []
    for row in rows:
        if row.get("prediction_scope") != "direct" or not row.get("actual_label"):
            continue
        value = optional_float(row.get("target_abnormal_return_p3"))
        if value == "":
            continue
        realized.append((float(value), row))
    if not realized:
        return {}
    positive_value, positive_row = max(realized, key=lambda item: item[0])
    negative_value, negative_row = min(realized, key=lambda item: item[0])
    return {
        "positive": {
            "club": positive_row.get("club", ""),
            "player": positive_row.get("player", ""),
            "season": positive_row.get("season", ""),
            "actual_label": positive_row.get("actual_label", ""),
            "target_abnormal_return_p3": round(positive_value, 4),
        },
        "negative": {
            "club": negative_row.get("club", ""),
            "player": negative_row.get("player", ""),
            "season": negative_row.get("season", ""),
            "actual_label": negative_row.get("actual_label", ""),
            "target_abnormal_return_p3": round(negative_value, 4),
        },
    }


def user_takeaways(
    signal_rows: list[dict[str, Any]],
    watchlist: list[dict[str, Any]],
    watchlist_meta: dict[str, Any],
    journalist_leaderboard: list[dict[str, Any]],
    transfer_rows: list[dict[str, Any]],
    historical_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if watchlist_meta.get("is_stale"):
        latest = format_short_date(str(watchlist_meta.get("latest_published_at", ""))) or "unknown"
        cards.append(
            {
                "title": "Live Status",
                "primary": "Needs refresh",
                "secondary": f"Latest live article in the payload is from {latest}.",
                "tone": "warning",
            }
        )
    elif watchlist:
        top_live = watchlist[0]
        cards.append(
            {
                "title": "Live Watch",
                "primary": f"{top_live.get('player', '')} -> {top_live.get('target_club', top_live.get('club', ''))}",
                "secondary": (
                    f"{top_live.get('confidence_tier', 'thin').replace('_', ' ')} · "
                    f"{top_live.get('source_count', 1)} outlets · "
                    f"{top_live.get('rumor_stage', 'unclear')} · "
                    f"{top_live.get('blended_label', '')}"
                ),
                "tone": top_live.get("blended_label", "neutral"),
            }
        )

    direct_signal_rows = [row for row in signal_rows if row.get("prediction_scope") == "direct"]
    if direct_signal_rows:
        top_signal = max(
            direct_signal_rows,
            key=lambda row: (abs(parse_float(row.get("blended_score"), 0.0)), parse_float(row.get("credibility_score"), 0.0)),
        )
        cards.append(
            {
                "title": "What To Check",
                "primary": f"{top_signal.get('player', '')} / {top_signal.get('target_club', top_signal.get('club', ''))}",
                "secondary": f"Blend {parse_float(top_signal.get('blended_score'), 0.0):.1f} · model {top_signal.get('predicted_label', '-')}",
                "tone": top_signal.get("blended_label", "neutral"),
            }
        )

    if journalist_leaderboard:
        top_journalist = journalist_leaderboard[0]
        cards.append(
            {
                "title": "Best Reporter",
                "primary": str(top_journalist.get("journalist", "")),
                "secondary": f"{top_journalist.get('n_claims', 0)} claims · smoothed {parse_float(top_journalist.get('smoothed_rate'), 0.0):.3f}",
                "tone": "info",
            }
        )

    sensitive = market_sensitive_club(transfer_rows)
    if sensitive:
        cards.append(
            {
                "title": "Most Reactive Club",
                "primary": str(sensitive.get("club", "")),
                "secondary": f"Avg abs CAR t+3 {parse_float(sensitive.get('avg_abs_car_p3'), 0.0):.4f} over {sensitive.get('n_rows', 0)} transfers",
                "tone": "info",
            }
        )

    extremes = extreme_realized_examples(historical_rows)
    if extremes.get("positive"):
        item = extremes["positive"]
        cards.append(
            {
                "title": "Best Historical Hit",
                "primary": f"{item.get('player', '')} / {item.get('club', '')}",
                "secondary": f"{item.get('season', '')} · CAR t+3 {parse_float(item.get('target_abnormal_return_p3'), 0.0):.4f}",
                "tone": "positive",
            }
        )
    return cards[:4]


CONFIDENCE_TIER_RANK = {
    "broad_consensus": 4,
    "strong": 3,
    "developing": 2,
    "thin": 1,
}


def strongest_confidence_tier(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "thin"
    return max(
        (str(row.get("confidence_tier", "thin")) for row in rows),
        key=lambda tier: CONFIDENCE_TIER_RANK.get(tier, 0),
    )


def club_peak_examples(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    realized = []
    for row in rows:
        value = optional_float(row.get("actual_abnormal_return_p3", row.get("target_abnormal_return_p3", "")))
        if value == "":
            continue
        realized.append((float(value), row))
    if not realized:
        return {}
    positive_value, positive_row = max(realized, key=lambda item: item[0])
    negative_value, negative_row = min(realized, key=lambda item: item[0])
    return {
        "best_positive": {
            "player": positive_row.get("player", ""),
            "date": positive_row.get("date", positive_row.get("published_date", "")),
            "actual_label": positive_row.get("actual_label", ""),
            "car_p3": round(positive_value, 4),
        },
        "worst_negative": {
            "player": negative_row.get("player", ""),
            "date": negative_row.get("date", negative_row.get("published_date", "")),
            "actual_label": negative_row.get("actual_label", ""),
            "car_p3": round(negative_value, 4),
        },
    }


def build_club_dossiers(
    clubs: dict[str, Club],
    *,
    latest_season: str,
    signals_by_season: dict[str, list[dict[str, Any]]],
    transfers_by_season: dict[str, list[dict[str, Any]]],
    watchlist: list[dict[str, Any]],
    club_journalist_leaderboard: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    all_transfers = [row for rows in transfers_by_season.values() for row in rows]
    current_signals = signals_by_season.get(latest_season, [])
    signal_seasons = sorted(signals_by_season.keys(), key=season_start, reverse=True)
    transfer_seasons = sorted(transfers_by_season.keys(), key=season_start, reverse=True)
    dossiers: dict[str, dict[str, Any]] = {}
    club_names = sorted({club.name for club in clubs.values()})
    for club_name in club_names:
        club_live = [row for row in watchlist if (row.get("target_club") or row.get("club")) == club_name]
        club_signals = [row for row in current_signals if row.get("club") == club_name]
        club_transfers = [row for row in all_transfers if row.get("club") == club_name]
        club_transfers.sort(key=lambda row: str(row.get("date", "")), reverse=True)
        club_reporters = [row for row in club_journalist_leaderboard if row.get("club") == club_name][:5]
        avg_live_credibility = (
            round(sum(parse_float(row.get("credibility_score"), 0.0) for row in club_live) / len(club_live), 4)
            if club_live
            else 0.0
        )
        realized_rows = [row for row in club_transfers if row.get("actual_abnormal_return_p3") not in {"", None}]
        avg_realized_car = (
            round(sum(parse_float(row.get("actual_abnormal_return_p3"), 0.0) for row in realized_rows) / len(realized_rows), 6)
            if realized_rows
            else 0.0
        )
        avg_transfer_index = (
            round(sum(parse_float(row.get("transfer_indicator"), 0.0) for row in club_transfers[:12]) / min(len(club_transfers[:12]), 12), 4)
            if club_transfers[:12]
            else 0.0
        )
        realized_positive_share = (
            round(
                sum(1 for row in realized_rows if str(row.get("actual_label", "")).strip() == "positive") / len(realized_rows),
                4,
            )
            if realized_rows
            else 0.0
        )
        rumor_season_history: list[dict[str, Any]] = []
        for season in signal_seasons:
            season_rows = [row for row in signals_by_season.get(season, []) if row.get("club") == club_name]
            if not season_rows:
                continue
            rumor_season_history.append(season_summary(season, season_rows))
        transfer_season_history: list[dict[str, Any]] = []
        for season in transfer_seasons:
            season_rows = [row for row in transfers_by_season.get(season, []) if row.get("club") == club_name]
            if not season_rows:
                continue
            transfer_season_history.append(transfer_history_summary(season, season_rows))
        dossiers[club_name] = {
            "club": club_name,
            "season": latest_season,
            "live_signal_count": len(club_live),
            "current_signal_count": len(club_signals),
            "recent_transfer_count": len(club_transfers[:12]),
            "avg_live_credibility": avg_live_credibility,
            "avg_transfer_index": avg_transfer_index,
            "avg_realized_car_p3": avg_realized_car,
            "realized_positive_share": realized_positive_share,
            "top_confidence_tier": strongest_confidence_tier(club_live or club_signals),
            "live_events": club_live[:5],
            "current_signals": club_signals[:5],
            "recent_transfers": club_transfers[:5],
            "reporters": club_reporters,
            "peak_examples": club_peak_examples(club_transfers),
            "rumor_season_history": rumor_season_history,
            "transfer_season_history": transfer_season_history,
        }
    return dossiers


def data_quality_summary(
    watchlist_meta: dict[str, Any],
    overview: dict[str, Any],
    journalist_leaderboard: list[dict[str, Any]],
) -> dict[str, Any]:
    accuracy = parse_float(overview.get("xgboost_test_accuracy"), 0.0)
    macro_f1 = parse_float(overview.get("xgboost_test_macro_f1"), 0.0)
    if accuracy >= 0.55 and macro_f1 >= 0.35:
        evidence = "moderate"
    elif accuracy >= 0.45 and macro_f1 >= 0.25:
        evidence = "early"
    else:
        evidence = "experimental"
    return {
        "live_status": "stale" if watchlist_meta.get("is_stale") else "fresh",
        "latest_live_date": format_short_date(str(watchlist_meta.get("latest_published_at", ""))),
        "recent_live_clusters": int(parse_float(watchlist_meta.get("recent_cluster_count"), 0.0)),
        "model_evidence": evidence,
        "xgboost_test_accuracy": round(accuracy, 4),
        "xgboost_test_macro_f1": round(macro_f1, 4),
        "journalist_rows": len(journalist_leaderboard),
    }


def infer_companion_claims_path(predictions_path: Path) -> Path | None:
    try:
        run_dir = predictions_path.parents[2]
    except IndexError:
        return None
    candidate = run_dir / "processed" / "claims" / "claims.jsonl"
    return candidate if candidate.exists() else None


def load_claim_lookup(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        claim_id = str(row.get("claim_id", "")).strip()
        if claim_id:
            lookup[claim_id] = row
    return lookup


def evidence_articles(
    claim_ids: list[str],
    claim_lookup: dict[str, dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for claim_id in claim_ids:
        row = claim_lookup.get(claim_id)
        if not row:
            continue
        url = str(row.get("url", "")).strip()
        title = str(row.get("title", "")).strip()
        source = publisher_label(row)
        dedupe_key = (headline_fingerprint(title) or url or claim_id, source)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(
            {
                "title": title,
                "headline_fingerprint": headline_fingerprint(title),
                "url": url,
                "source": source,
                "feed_source": str(row.get("source", "")).strip(),
                "journalist": str(row.get("journalist", "")).strip(),
                "published_at": str(row.get("published_at", "")).strip(),
                "rumor_stage": str(row.get("rumor_stage", "")).strip(),
                "is_transfer_related": int(parse_float(row.get("is_transfer_related"), 0.0)),
                "extraction_confidence": round(parse_float(row.get("extraction_confidence"), 0.0), 4),
            }
        )
        if len(items) >= limit:
            break
    return items


def leaderboard_rows(
    path: Path | None,
    *,
    label_field: str,
    limit: int = 12,
    min_claims: int = 2,
) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows = read_csv(path)
    ranked = sorted(
        rows,
        key=lambda row: (
            parse_float(row.get("smoothed_rate"), 0.0),
            parse_float(row.get("avg_match_score"), 0.0),
            parse_float(row.get("n_claims"), 0.0),
        ),
        reverse=True,
    )
    output: list[dict[str, Any]] = []
    for row in ranked:
        n_claims = int(parse_float(row.get("n_claims"), 0.0))
        if n_claims < min_claims:
            continue
        label = str(row.get(label_field, "")).strip()
        if not label:
            continue
        item = {
            label_field: label,
            "n_claims": n_claims,
            "n_matched": int(parse_float(row.get("n_matched"), 0.0)),
            "match_rate": round(parse_float(row.get("match_rate"), 0.0), 4),
            "smoothed_rate": round(parse_float(row.get("smoothed_rate"), 0.0), 4),
            "avg_match_score": round(parse_float(row.get("avg_match_score"), 0.0), 4),
        }
        if "club" in row:
            item["club"] = str(row.get("club", "")).strip()
        output.append(item)
        if len(output) >= limit:
            break
    return output


def live_source_coverage(rows: list[dict[str, str]], *, recent_days: int = 21, limit: int = 10) -> list[dict[str, Any]]:
    now = datetime.now(tz=UTC)
    threshold = now - timedelta(days=recent_days)
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("prediction_scope") != "direct":
            continue
        published_at = str(row.get("published_at", ""))
        published_dt = parse_timestamp(published_at)
        if published_dt < threshold:
            continue
        source = publisher_label(row)
        item = grouped.setdefault(
            source,
            {
                "source": source,
                "n_rows": 0,
                "n_unique_players": 0,
                "latest_published_at": "",
                "avg_credibility": 0.0,
                "players": set(),
            },
        )
        item["n_rows"] += 1
        player = str(row.get("player", "")).strip()
        if player:
            item["players"].add(player)
        latest_existing = parse_timestamp(str(item.get("latest_published_at", "")))
        if published_dt > latest_existing:
            item["latest_published_at"] = published_at
        item["avg_credibility"] += parse_float(row.get("credibility_score"), 0.0)
    output: list[dict[str, Any]] = []
    for item in grouped.values():
        n_rows = int(item["n_rows"])
        players = item.pop("players")
        output.append(
            {
                "source": item["source"],
                "n_rows": n_rows,
                "n_unique_players": len(players),
                "latest_published_at": item["latest_published_at"],
                "avg_credibility": round((item["avg_credibility"] / n_rows) if n_rows else 0.0, 4),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("n_rows", 0),
            parse_timestamp(str(row.get("latest_published_at", ""))),
        ),
        reverse=True,
    )
    return output[:limit]


def article_cluster_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("target_club") or row.get("club", ""),
        row.get("player", ""),
        "",
    )


def direction_consensus(rows: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
    counts = Counter(
        direction
        for direction in (str(row.get("direction", "")).strip() for row in rows)
        if direction
    )
    if not counts:
        return "unclear", {}
    preferred = sorted(
        counts.items(),
        key=lambda item: (
            item[1],
            1 if item[0] != "unclear" else 0,
        ),
        reverse=True,
    )[0][0]
    return preferred, dict(counts)


def stage_consensus(rows: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
    counts = Counter(
        stage
        for stage in (str(row.get("rumor_stage", "")).strip() for row in rows)
        if stage
    )
    if not counts:
        return "unclear", {}
    score_by_stage: dict[str, float] = {}
    for stage, count in counts.items():
        max_stage_score = max(
            (
                parse_float(row.get("rumor_stage_score"), 0.0)
                for row in rows
                if str(row.get("rumor_stage", "")).strip() == stage
            ),
            default=0.0,
        )
        score_by_stage[stage] = count + max_stage_score
    preferred = max(score_by_stage.items(), key=lambda item: item[1])[0]
    return preferred, dict(counts)


def headline_variants(rows: list[dict[str, str]], limit: int = 4) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        fingerprint = headline_fingerprint(str(row.get("title", ""))) or str(row.get("claim_id", ""))
        grouped.setdefault(fingerprint, []).append(row)
    variants: list[dict[str, Any]] = []
    for fingerprint, grouped_rows in grouped.items():
        ordered = sorted(grouped_rows, key=lambda row: parse_timestamp(str(row.get("published_at", ""))), reverse=True)
        representative = ordered[0]
        sources = sorted({publisher_label(row) for row in ordered if publisher_label(row)})
        variants.append(
            {
                "fingerprint": fingerprint,
                "title": title_base(str(representative.get("title", ""))),
                "article_count": len(grouped_rows),
                "source_count": len(sources),
                "sources": sources,
                "latest_published_at": str(representative.get("published_at", "")),
            }
        )
    variants.sort(
        key=lambda item: (
            item.get("article_count", 0),
            item.get("source_count", 0),
            parse_timestamp(str(item.get("latest_published_at", ""))),
        ),
        reverse=True,
    )
    return variants[:limit]


def source_breakdown(rows: list[dict[str, str]], limit: int = 6) -> list[dict[str, Any]]:
    counts = Counter(publisher_label(row) for row in rows)
    output = [
        {"source": source, "count": count}
        for source, count in counts.most_common(limit)
    ]
    return output


def event_strength(rows: list[dict[str, str]], *, unique_headline_count: int, source_count: int) -> float:
    max_cred = max((parse_float(row.get("credibility_score"), 0.0) for row in rows), default=0.0)
    max_stage = max((parse_float(row.get("rumor_stage_score"), 0.0) for row in rows), default=0.0)
    diversity = min(1.0, source_count / 4.0)
    volume = min(1.0, unique_headline_count / 4.0)
    strength = 0.45 * max_cred + 0.25 * max_stage + 0.15 * diversity + 0.15 * volume
    return round(strength, 4)


def coverage_consensus(
    rows: list[dict[str, str]],
    *,
    source_count: int,
    unique_headline_count: int,
    direction_mix: dict[str, int],
    stage_mix: dict[str, int],
    direct_article_count: int,
) -> tuple[float, str]:
    total_rows = max(len(rows), 1)
    direction_total = sum(direction_mix.values())
    direction_agreement = (max(direction_mix.values()) / direction_total) if direction_total else 0.0
    stage_total = sum(stage_mix.values())
    stage_agreement = (max(stage_mix.values()) / stage_total) if stage_total else 0.0
    direct_share = direct_article_count / total_rows
    source_breadth = min(1.0, source_count / 4.0)
    headline_uniqueness = unique_headline_count / total_rows
    score = (
        0.30 * direction_agreement
        + 0.25 * stage_agreement
        + 0.20 * source_breadth
        + 0.15 * direct_share
        + 0.10 * headline_uniqueness
    )
    rounded = round(score, 4)
    if rounded >= 0.82:
        label = "Broad alignment"
    elif rounded >= 0.68:
        label = "Aligned"
    elif rounded >= 0.52:
        label = "Developing"
    else:
        label = "Mixed"
    return rounded, label


def rumor_timeline(rows: list[dict[str, str]], active_stage: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        stage = str(row.get("rumor_stage", "")).strip().lower()
        if stage in STAGE_RANK:
            grouped.setdefault(stage, []).append(row)

    timeline: list[dict[str, Any]] = []
    for stage in STAGE_SEQUENCE:
        stage_rows = grouped.get(stage, [])
        latest = max(
            (parse_timestamp(str(row.get("published_at", ""))) for row in stage_rows),
            default=None,
        )
        timeline.append(
            {
                "stage": stage,
                "label": stage.title(),
                "seen": bool(stage_rows),
                "active": stage == active_stage,
                "date": latest.date().isoformat() if latest else "",
                "article_count": len(stage_rows),
                "source_count": len({publisher_label(row) for row in stage_rows if publisher_label(row)}),
            }
        )

    if active_stage and active_stage not in STAGE_RANK:
        stage_rows = [
            row for row in rows
            if str(row.get("rumor_stage", "")).strip().lower() == active_stage
        ]
        latest = max(
            (parse_timestamp(str(row.get("published_at", ""))) for row in stage_rows),
            default=None,
        )
        timeline.append(
            {
                "stage": active_stage,
                "label": active_stage.title(),
                "seen": bool(stage_rows),
                "active": True,
                "date": latest.date().isoformat() if latest else "",
                "article_count": len(stage_rows),
                "source_count": len({publisher_label(row) for row in stage_rows if publisher_label(row)}),
            }
        )
    return timeline


def resolve_club_key(club_name: str, clubs_by_name: dict[str, Club]) -> str:
    club = clubs_by_name.get((club_name or "").lower())
    return club.key if club else ""


def build_signal_stock_chart(
    row: dict[str, Any],
    *,
    clubs_by_name: dict[str, Club],
    stock_cache: dict[str, list[Any]],
    lookback: int = 20,
    lookahead: int = 10,
) -> dict[str, Any]:
    if str(row.get("prediction_scope", "")).strip() != "direct":
        return {}
    club_name = str(row.get("target_club", "") or row.get("club", "")).strip()
    club_key = resolve_club_key(club_name, clubs_by_name)
    if not club_key:
        return {}
    bars = stock_cache.get(club_key)
    if bars is None:
        bars = load_bars(DATA_DIR / "raw" / "stocks" / f"{club_key}.csv")
        stock_cache[club_key] = bars
    if not bars:
        return {}

    event_date = parse_timestamp(str(row.get("latest_published_at", row.get("published_at", "")))).date()
    event_idx = next((index for index, bar in enumerate(bars) if bar.date >= event_date), -1)
    if event_idx < 0:
        earlier = [index for index, bar in enumerate(bars) if bar.date <= event_date]
        if not earlier:
            return {}
        event_idx = earlier[-1]

    start_idx = max(0, event_idx - lookback)
    end_idx = min(len(bars), event_idx + lookahead + 1)
    segment = bars[start_idx:end_idx]
    if len(segment) < 2:
        return {}

    event_bar = bars[event_idx]
    event_close = event_bar.close or segment[0].close or 1.0
    if not event_close:
        return {}

    normalized_points = [round((bar.close / event_close) * 100.0, 3) for bar in segment]
    latest_change = round((segment[-1].close / event_close) - 1.0, 4)
    pre_change = round((event_close / segment[0].close) - 1.0, 4) if segment[0].close else 0.0
    post_change = round((segment[-1].close / event_close) - 1.0, 4) if len(segment) > (event_idx - start_idx + 1) else 0.0

    return {
        "dates": [bar.date.isoformat() for bar in segment],
        "points": normalized_points,
        "event_index": event_idx - start_idx,
        "latest_index": len(segment) - 1,
        "event_date": event_bar.date.isoformat(),
        "latest_date": segment[-1].date.isoformat(),
        "latest_change": latest_change,
        "pre_change": pre_change,
        "post_change": post_change,
        "point_count": len(segment),
    }


def match_result_sentiment(result: str, goals_for: Any = "", goals_against: Any = "") -> str:
    normalized = str(result or "").strip().lower()
    if normalized in {"w", "win", "won"}:
        return "positive"
    if normalized in {"l", "loss", "lost"}:
        return "negative"
    if normalized in {"d", "draw"}:
        return "neutral"
    try:
        gf = int(float(goals_for))
        ga = int(float(goals_against))
    except (TypeError, ValueError):
        return "neutral"
    if gf > ga:
        return "positive"
    if gf < ga:
        return "negative"
    return "neutral"


def load_match_results(club_key: str, match_results_dir: Path | None = None) -> list[dict[str, Any]]:
    directory = match_results_dir or (DATA_DIR / "raw" / "matches")
    path = directory / f"{club_key}.csv"
    if not path.exists():
        return []
    results: list[dict[str, Any]] = []
    for row in read_csv(path):
        match_date = str(row.get("date", "")).strip()
        if not match_date:
            continue
        parsed = parse_timestamp(match_date).date()
        if parsed.year <= 1970:
            continue
        goals_for = row.get("goals_for", row.get("gf", ""))
        goals_against = row.get("goals_against", row.get("ga", ""))
        score = str(row.get("score", "")).strip()
        if not score and goals_for not in {"", None} and goals_against not in {"", None}:
            score = f"{goals_for}-{goals_against}"
        result = str(row.get("result", "")).strip()
        results.append(
            {
                "date": parsed,
                "date_raw": match_date,
                "opponent": str(row.get("opponent", "")).strip(),
                "competition": str(row.get("competition", "")).strip(),
                "venue": str(row.get("venue", "")).strip(),
                "result": result.upper()[:1] if result else "",
                "score": score,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "source_url": str(row.get("source_url", "")).strip(),
                "sentiment": match_result_sentiment(result, goals_for, goals_against),
            }
        )
    results.sort(key=lambda row: row["date"])
    return results


def next_bar_index_on_or_after(bars: list[Any], event_date: date) -> int | None:
    for index, bar in enumerate(bars):
        if bar.date >= event_date:
            return index
    return None


def build_club_stock_path(
    club: Club,
    *,
    match_results_dir: Path | None = None,
    lookback_bars: int = 160,
) -> dict[str, Any]:
    bars = load_bars(DATA_DIR / "raw" / "stocks" / f"{club.key}.csv")
    if not bars:
        return {
            "club": club.name,
            "ticker": club.yahoo_symbol or club.stooq_symbol,
            "dates": [],
            "points": [],
            "markers": [],
            "status": "missing_stock_bars",
        }
    segment = bars[-lookback_bars:] if len(bars) > lookback_bars else bars
    start_close = segment[0].close or 1.0
    dates = [bar.date.isoformat() for bar in segment]
    points = [round((bar.close / start_close) * 100.0, 3) for bar in segment]
    match_results = load_match_results(club.key, match_results_dir=match_results_dir)
    markers: list[dict[str, Any]] = []
    for result in match_results:
        marker_idx = next_bar_index_on_or_after(segment, result["date"])
        if marker_idx is None:
            continue
        markers.append(
            {
                "kind": "match",
                "index": marker_idx,
                "match_date": result["date"].isoformat(),
                "trading_date": segment[marker_idx].date.isoformat(),
                "opponent": result["opponent"],
                "competition": result["competition"],
                "venue": result["venue"],
                "result": result["result"],
                "score": result["score"],
                "sentiment": result["sentiment"],
                "source_url": result["source_url"],
            }
        )
    return {
        "club": club.name,
        "ticker": club.yahoo_symbol or club.stooq_symbol,
        "dates": dates,
        "points": points,
        "markers": markers,
        "latest_date": dates[-1],
        "latest_change": round((segment[-1].close / start_close) - 1.0, 4) if start_close else 0.0,
        "match_marker_count": len(markers),
        "status": "ok",
        "match_results_path": str((match_results_dir or (DATA_DIR / "raw" / "matches")) / f"{club.key}.csv"),
    }


def build_club_stock_paths(clubs: dict[str, Club]) -> dict[str, dict[str, Any]]:
    return {
        club.name: build_club_stock_path(club)
        for club in clubs.values()
    }


def event_confidence_tier(
    *,
    event_strength_value: float,
    unique_headline_count: int,
    source_count: int,
    direct_article_count: int,
) -> tuple[str, str]:
    if event_strength_value >= 0.68 and source_count >= 3 and unique_headline_count >= 2 and direct_article_count >= 2:
        return "broad_consensus", "Multiple outlets, repeated headlines, and strong event quality."
    if event_strength_value >= 0.56 and source_count >= 2 and direct_article_count >= 1:
        return "strong", "More than one outlet is carrying a direct-target version of the story."
    if event_strength_value >= 0.44 and (source_count >= 2 or unique_headline_count >= 2):
        return "developing", "The rumor has early confirmation, but coverage is still forming."
    return "thin", "Coverage is light or concentrated in a narrow slice of sources."


def cluster_current_rows(
    rows: list[dict[str, str]],
    *,
    gap_days: int = 5,
) -> list[list[dict[str, str]]]:
    candidate_rows = [
        row
        for row in rows
        if row.get("published_at")
        and row.get("player")
        and (row.get("target_club") or row.get("club"))
    ]
    buckets: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in candidate_rows:
        buckets.setdefault(article_cluster_key(row), []).append(row)
    clusters: list[list[dict[str, str]]] = []
    for grouped_rows in buckets.values():
        ordered = sorted(grouped_rows, key=lambda row: parse_timestamp(str(row.get("published_at", ""))), reverse=True)
        current_cluster: list[dict[str, str]] = []
        previous_dt: datetime | None = None
        for row in ordered:
            current_dt = parse_timestamp(str(row.get("published_at", "")))
            if previous_dt is None or (previous_dt - current_dt).days <= gap_days:
                current_cluster.append(row)
            else:
                if any(item.get("prediction_scope") == "direct" for item in current_cluster):
                    clusters.append(current_cluster)
                current_cluster = [row]
            previous_dt = current_dt
        if current_cluster and any(item.get("prediction_scope") == "direct" for item in current_cluster):
            clusters.append(current_cluster)
    clusters.sort(key=lambda rows: parse_timestamp(str(rows[0].get("published_at", ""))), reverse=True)
    return clusters


def summarize_watchlist_cluster(rows: list[dict[str, str]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: parse_timestamp(str(row.get("published_at", ""))), reverse=True)
    latest = ordered[0]
    direct_rows = [row for row in ordered if row.get("prediction_scope") == "direct"]
    anchor = direct_rows[0] if direct_rows else latest
    credibility_scores = [parse_float(row.get("credibility_score"), 0.0) for row in ordered]
    blended_scores = [blended_signal_score(row) for row in direct_rows] or [blended_signal_score(row) for row in ordered]
    stage_scores = [parse_float(row.get("rumor_stage_score"), 0.0) for row in ordered]
    unique_headlines = headline_variants(ordered)
    direction_value, direction_mix = direction_consensus(ordered)
    stage_value, stage_mix = stage_consensus(ordered)
    source_mix = source_breakdown(ordered)
    unique_headline_count = len({headline_fingerprint(str(row.get("title", ""))) or str(row.get("claim_id", "")) for row in ordered})
    direct_article_count = len(direct_rows)
    supporting_article_count = max(0, len(ordered) - direct_article_count)
    event_strength_value = event_strength(ordered, unique_headline_count=unique_headline_count, source_count=len(source_mix))
    confidence_tier, confidence_reason = event_confidence_tier(
        event_strength_value=event_strength_value,
        unique_headline_count=unique_headline_count,
        source_count=len(source_mix),
        direct_article_count=direct_article_count,
    )
    consensus_score, consensus_label = coverage_consensus(
        ordered,
        source_count=len(source_mix),
        unique_headline_count=unique_headline_count,
        direction_mix=direction_mix,
        stage_mix=stage_mix,
        direct_article_count=direct_article_count,
    )
    return {
        "group_key": f"{anchor.get('target_club') or anchor.get('club','')}::{anchor.get('player','')}",
        "cluster_key": f"{anchor.get('target_club') or anchor.get('club','')}::{anchor.get('player','')}::{anchor.get('published_date') or anchor.get('date','')}",
        "published_at": latest.get("published_at", ""),
        "latest_published_at": latest.get("published_at", ""),
        "first_published_at": ordered[-1].get("published_at", ""),
        "cluster_span_days": max(0, (parse_timestamp(str(ordered[0].get("published_at", ""))) - parse_timestamp(str(ordered[-1].get("published_at", "")))).days),
        "article_count": len(ordered),
        "direct_article_count": direct_article_count,
        "supporting_article_count": supporting_article_count,
        "unique_headline_count": unique_headline_count,
        "duplicate_article_count": max(0, len(ordered) - unique_headline_count),
        "source_count": len(source_mix),
        "source_breakdown": source_mix,
        "headline_variants": unique_headlines,
        "timeline": rumor_timeline(ordered, stage_value),
        "club": anchor.get("club", ""),
        "player": anchor.get("player", ""),
        "target_club": anchor.get("target_club", ""),
        "target_role": anchor.get("target_role", ""),
        "prediction_scope": anchor.get("prediction_scope", ""),
        "journalist": anchor.get("journalist", ""),
        "source": publisher_label(anchor),
        "rumor_stage": stage_value,
        "direction": direction_value,
        "direction_mix": direction_mix,
        "stage_mix": stage_mix,
        "credibility_score": round(max(credibility_scores) if credibility_scores else 0.0, 4),
        "transfer_indicator": round(parse_float(anchor.get("transfer_indicator"), 0.0), 4),
        "stock_context_indicator": round(parse_float(anchor.get("stock_context_indicator"), 0.0), 4),
        "predicted_label": anchor.get("predicted_label", ""),
        "prediction_confidence": round(parse_float(anchor.get("prediction_confidence"), 0.0), 4),
        "blended_label": blended_signal_label(anchor),
        "blended_score": round(max(blended_scores) if blended_scores else 0.0, 2),
        "target_ticker": anchor.get("target_ticker", ""),
        "max_stage_score": round(max(stage_scores) if stage_scores else 0.0, 4),
        "event_strength": event_strength_value,
        "confidence_tier": confidence_tier,
        "confidence_reason": confidence_reason,
        "consensus_score": consensus_score,
        "consensus_label": consensus_label,
        "primary_headline": unique_headlines[0]["title"] if unique_headlines else title_base(str(latest.get("title", ""))),
    }


def live_watchlist(
    rows: list[dict[str, str]],
    *,
    now: datetime,
    recent_days: int = 21,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    clusters = [summarize_watchlist_cluster(cluster) for cluster in cluster_current_rows(rows)]
    if not clusters:
        return [], {
            "latest_published_at": "",
            "days_stale": "",
            "window_days": recent_days,
            "is_stale": True,
            "recent_cluster_count": 0,
        }
    latest_dt = parse_timestamp(str(clusters[0].get("latest_published_at", "")))
    fresh_threshold = now - timedelta(days=recent_days)
    recent_clusters = [
        row for row in clusters if parse_timestamp(str(row.get("latest_published_at", ""))) >= fresh_threshold
    ]
    candidate_rows = recent_clusters if recent_clusters else clusters
    selected: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for row in candidate_rows:
        group_key = str(row.get("group_key", ""))
        if group_key in seen_groups:
            continue
        seen_groups.add(group_key)
        selected.append(row)
        if len(selected) >= limit:
            break
    days_stale = (now.date() - latest_dt.date()).days
    return selected, {
        "latest_published_at": clusters[0].get("latest_published_at", ""),
        "days_stale": days_stale,
        "window_days": recent_days,
        "is_stale": days_stale > recent_days,
        "recent_cluster_count": len(recent_clusters),
    }


def build_watchlist_details(
    rows: list[dict[str, str]],
    *,
    now: datetime,
    claim_lookup: dict[str, dict[str, Any]],
    historical_rows: list[dict[str, str]],
    clubs_by_name: dict[str, Club],
    transfer_rows: list[dict[str, Any]],
    recent_days: int = 21,
) -> dict[str, dict[str, Any]]:
    fresh_threshold = now - timedelta(days=recent_days)
    details: dict[str, dict[str, Any]] = {}
    stock_cache: dict[str, list[Any]] = {}
    for cluster in cluster_current_rows(rows):
        latest_dt = parse_timestamp(str(cluster[0].get("published_at", "")))
        if latest_dt < fresh_threshold:
            continue
        detail = {
            **summarize_group(cluster),
            **summarize_watchlist_cluster(cluster),
        }
        detail["evidence_articles"] = evidence_articles(detail.get("claim_ids", []), claim_lookup)
        detail["similar_examples"] = similar_examples(detail, historical_rows, limit=3)
        detail["counterparty_club"] = counterparty_club(detail)
        detail["deal_path"] = deal_path_label(detail)
        detail["top_similar_example"] = detail["similar_examples"][0] if detail["similar_examples"] else {}
        detail["signal_summary"] = signal_summary(detail, detail["top_similar_example"])
        detail["confirmed_transfer_links"] = confirmed_transfer_links(detail, transfer_rows)
        detail["stock_chart"] = build_signal_stock_chart(
            detail,
            clubs_by_name=clubs_by_name,
            stock_cache=stock_cache,
        )
        details[str(detail.get("group_key", ""))] = detail
    return details


def dedupe_historical_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    best: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            row.get("season", ""),
            row.get("club", ""),
            row.get("player", ""),
            row.get("published_date", row.get("date", "")),
        )
        current = best.get(key)
        if current is None or parse_float(row.get("prediction_confidence"), 0.0) > parse_float(current.get("prediction_confidence"), 0.0):
            best[key] = row
    return list(best.values())


def similarity_score(current: dict[str, Any], historical: dict[str, str]) -> float:
    score = 0.0
    if current["club"] == historical.get("club", ""):
        score += 0.16
    if current["direction"] == historical.get("direction", ""):
        score += 0.18
    elif current.get("direction") and historical.get("direction"):
        score -= 0.08
    if str(current.get("target_role", "")).strip() == str(historical.get("target_role", "")).strip():
        score += 0.10
    if current["position"] == historical.get("position", ""):
        score += 0.12
    score += max(0.0, 0.18 - abs(current["credibility_score"] - parse_float(historical.get("credibility_score"), 0.0)) * 0.30)
    score += max(0.0, 0.16 - abs(current["transfer_indicator"] - parse_float(historical.get("transfer_indicator"), 0.0)) * 0.28)
    score += max(0.0, 0.10 - abs(current["rumor_stage_score"] - parse_float(historical.get("rumor_stage_score"), 0.0)) * 0.20)
    score += max(0.0, 0.08 - abs(current["stock_context_indicator"] - parse_float(historical.get("stock_context_indicator"), 0.0)) * 0.16)
    score += max(0.0, 0.08 - abs(current["age"] - parse_float(historical.get("age"), 0.0)) / 20.0)
    score += max(0.0, 0.12 - abs(current["market_value_eur"] - parse_float(historical.get("market_value_eur"), 0.0)) / 250_000_000.0)
    return round(score, 4)


def similar_examples(current: dict[str, Any], historical_rows: list[dict[str, str]], limit: int = 3) -> list[dict[str, Any]]:
    candidate_rows = historical_rows
    same_role_rows = [
        row for row in historical_rows
        if str(row.get("target_role", "")).strip()
        and str(row.get("target_role", "")).strip() == str(current.get("target_role", "")).strip()
    ]
    if len(same_role_rows) >= max(2, limit):
        candidate_rows = same_role_rows
    same_direction_rows = [
        row for row in candidate_rows
        if str(row.get("direction", "")).strip()
        and str(row.get("direction", "")).strip() == str(current.get("direction", "")).strip()
    ]
    if len(same_direction_rows) >= max(2, limit):
        candidate_rows = same_direction_rows

    ranked = []
    for row in candidate_rows:
        ranked.append((similarity_score(current, row), row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for score, row in ranked:
        key = (row.get("club", ""), row.get("player", ""), row.get("published_date", row.get("date", "")))
        if key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "similarity": score,
                "date": row.get("published_date", row.get("date", "")),
                "club": row.get("club", ""),
                "player": row.get("player", ""),
                "direction": row.get("direction", ""),
                "position": row.get("position", ""),
                "journalist": row.get("journalist", ""),
                "rumor_stage": row.get("rumor_stage", ""),
                "predicted_label": row.get("predicted_label", ""),
                "actual_label": row.get("actual_label", ""),
                "target_abnormal_return_p3": (
                    round(optional_float(row.get("target_abnormal_return_p3")), 6)
                    if optional_float(row.get("target_abnormal_return_p3")) != ""
                    else ""
                ),
                "credibility_score": round(parse_float(row.get("credibility_score"), 0.0), 4),
                "transfer_indicator": round(parse_float(row.get("transfer_indicator"), 0.0), 4),
            }
        )
        if len(output) >= limit:
            break
    return output


def build_demo_payload(
    predictions_path: Path,
    metrics_path: Path,
    backtest_summary_path: Path,
    backtest_trades_path: Path,
    transfers_path: Path | None = None,
    journalist_stats_path: Path | None = None,
    source_stats_path: Path | None = None,
    club_journalist_stats_path: Path | None = None,
) -> dict[str, Any]:
    rows = read_csv(predictions_path)
    claim_lookup = load_claim_lookup(infer_companion_claims_path(predictions_path))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    backtests = read_csv(backtest_summary_path)
    backtest_trades = read_csv(backtest_trades_path)
    clubs = load_clubs()
    clubs_by_name: dict[str, Club] = {}
    for club in clubs.values():
        clubs_by_name[club.name.lower()] = club
        clubs_by_name[club.key.lower()] = club
        for alias in club.aliases:
            clubs_by_name[alias.lower()] = club
    for row in rows:
        if not row.get("target_club") and row.get("prediction_scope") != "none":
            row.update(target_metadata(str(row.get("club", "")), str(row.get("direction", "")), clubs_by_name))

    latest_season = max((row.get("season", "") for row in rows), key=season_start, default="")
    all_seasons = sorted({row.get("season", "") for row in rows if row.get("season")}, key=season_start, reverse=True)
    all_historical_rows = dedupe_historical_rows(rows)
    transfer_rows = transfer_history_rows(clubs, transfers_path or (DATA_DIR / "processed" / "transfers_exact_dates.csv"))

    signals_by_season: dict[str, list[dict[str, Any]]] = {}
    season_summaries: dict[str, dict[str, Any]] = {}
    for season in all_seasons:
        season_rows = [row for row in rows if row.get("season") == season and row.get("split") in {"train", "test", "live_unlabeled", "unlabeled", "intelligence_only"}]
        grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in season_rows:
            grouped.setdefault((row.get("target_club") or row.get("club", ""), row.get("player", "")), []).append(row)

        signal_rows = [summarize_group(group_rows) for group_rows in grouped.values()]
        comparison_pool = [row for row in all_historical_rows if row.get("season") != season]
        for row in signal_rows:
            if not row.get("target_club") and row.get("prediction_scope") != "none":
                row.update(target_metadata(row.get("club", ""), row.get("direction", ""), clubs_by_name))
            row["evidence_articles"] = evidence_articles(row.get("claim_ids", []), claim_lookup)
            row["similar_examples"] = similar_examples(row, comparison_pool, limit=3)
            row["counterparty_club"] = counterparty_club(row)
            row["deal_path"] = deal_path_label(row)
            row["top_similar_example"] = row["similar_examples"][0] if row["similar_examples"] else {}
            row["signal_summary"] = signal_summary(row, row["top_similar_example"])
            row["confirmed_transfer_links"] = confirmed_transfer_links(row, transfer_rows)
        signal_rows.sort(key=lambda row: (abs(row["blended_score"]), row["latest_published_at"]), reverse=True)
        signals_by_season[season] = signal_rows
        season_summaries[season] = season_summary(season, signal_rows)

    transfers_by_season: dict[str, list[dict[str, Any]]] = {}
    transfer_season_summaries: dict[str, dict[str, Any]] = {}
    for row in transfer_rows:
        transfers_by_season.setdefault(str(row.get("season", "")), []).append(row)
    for season, season_rows in transfers_by_season.items():
        transfer_season_summaries[season] = transfer_history_summary(season, season_rows)

    available_signal_seasons = [season for season in all_seasons if season_summaries.get(season, {}).get("direct_count", 0) > 0]
    available_transfer_seasons = sorted(transfers_by_season.keys(), key=season_start, reverse=True)
    available_seasons = sorted(set(available_signal_seasons) | set(available_transfer_seasons), key=season_start, reverse=True)
    latest_season = available_seasons[0] if available_seasons else latest_season

    signal_rows = signals_by_season.get(latest_season, [])
    historical_rows = [row for row in all_historical_rows if row.get("season") != latest_season]
    generated_at = datetime.now(tz=UTC)
    watchlist, watchlist_meta = live_watchlist(rows, now=generated_at)
    watchlist_details = build_watchlist_details(
        rows,
        now=generated_at,
        claim_lookup=claim_lookup,
        historical_rows=historical_rows,
        clubs_by_name=clubs_by_name,
        transfer_rows=transfer_rows,
    )
    for row in watchlist:
        detail = watchlist_details.get(str(row.get("group_key", "")), {})
        row["counterparty_club"] = detail.get("counterparty_club", counterparty_club(row))
        row["deal_path"] = detail.get("deal_path", deal_path_label(row))
        row["top_similar_example"] = detail.get("top_similar_example", {})
        row["signal_summary"] = detail.get("signal_summary", signal_summary(row, row.get("top_similar_example", {})))
        row["stock_chart"] = detail.get("stock_chart", {})
        row["confirmed_transfer_links"] = detail.get("confirmed_transfer_links", [])
    journalist_leaderboard = leaderboard_rows(journalist_stats_path, label_field="journalist")
    source_leaderboard = leaderboard_rows(source_stats_path, label_field="source")
    club_journalist_leaderboard = leaderboard_rows(
        club_journalist_stats_path,
        label_field="journalist",
        min_claims=1,
    )

    backtests_sorted = sorted(backtests, key=lambda row: parse_float(row.get("portfolio_total_return"), -999.0), reverse=True)
    top_backtest = backtests_sorted[0] if backtests_sorted else {}
    model_metrics = metrics.get("models", {}).get("xgboost", {})
    overview = {
        "current_signal_count": len(signal_rows),
        "current_transfer_count": len(transfers_by_season.get(latest_season, [])),
        "historical_reference_count": len(historical_rows),
        "season_count": len(available_seasons),
        "test_rows": metrics.get("n_test_rows", 0),
        "xgboost_test_accuracy": model_metrics.get("test", {}).get("accuracy", 0.0),
        "xgboost_test_macro_f1": model_metrics.get("test", {}).get("macro_f1", 0.0),
        "best_backtest_strategy": top_backtest.get("strategy", ""),
        "best_backtest_total_return": parse_float(top_backtest.get("portfolio_total_return"), 0.0),
        "best_backtest_sharpe": parse_float(top_backtest.get("sharpe_like"), 0.0),
    }
    takeaways = user_takeaways(
        signal_rows,
        watchlist,
        watchlist_meta,
        journalist_leaderboard,
        transfer_rows,
        historical_rows,
    )
    quality_summary = data_quality_summary(
        watchlist_meta,
        overview,
        journalist_leaderboard,
    )
    source_coverage = live_source_coverage(rows)
    club_dossiers = build_club_dossiers(
        clubs,
        latest_season=latest_season,
        signals_by_season=signals_by_season,
        transfers_by_season=transfers_by_season,
        watchlist=watchlist,
        club_journalist_leaderboard=club_journalist_leaderboard,
    )
    club_stock_paths = build_club_stock_paths(clubs)
    reporter_profile_map = reporter_profiles(rows, journalist_leaderboard)

    return {
        "generated_at": generated_at.isoformat(),
        "latest_season": latest_season,
        "available_seasons": available_seasons,
        "club_media": {
            club.name: {
                "logo_url": club.logo_url,
                "accent_color": club.accent_color,
                "entity_type": club.entity_type,
                "ticker": club.yahoo_symbol or club.stooq_symbol,
            }
            for club in clubs.values()
        },
        "overview": overview,
        "takeaways": takeaways,
        "quality_summary": quality_summary,
        "automation": {
            "auto_refresh_ready": True,
            "recommended_cadence": "daily",
            "generated_at": generated_at.isoformat(),
        },
        "season_summaries": season_summaries,
        "signals_by_season": signals_by_season,
        "transfer_season_summaries": transfer_season_summaries,
        "transfers_by_season": transfers_by_season,
        "current_signals": signal_rows,
        "live_watchlist": watchlist,
        "watchlist_details": watchlist_details,
        "live_watchlist_meta": watchlist_meta,
        "live_source_coverage": source_coverage,
        "club_dossiers": club_dossiers,
        "club_stock_paths": club_stock_paths,
        "reporter_profiles": reporter_profile_map,
        "leaderboards": {
            "journalists": journalist_leaderboard,
            "sources": source_leaderboard,
            "club_journalists": club_journalist_leaderboard,
        },
        "backtests": backtests_sorted,
        "top_backtest_trades": sorted(
            backtest_trades,
            key=lambda row: abs(parse_float(row.get("trade_return"), 0.0)),
            reverse=True,
        )[:12],
        "model_summary": {
            "dataset_path": metrics.get("dataset_path", ""),
            "target_label_field": metrics.get("target_label_field", ""),
            "train_end_season": metrics.get("train_end_season", ""),
            "baseline_majority": metrics.get("baseline_majority", {}),
            "legacy_repo_baselines": metrics.get("legacy_repo_baselines", {}),
            "xgboost": model_metrics,
        },
        "data_flow": {
            "predictions": str(predictions_path),
            "metrics": str(metrics_path),
            "backtest_summary": str(backtest_summary_path),
            "backtest_trades": str(backtest_trades_path),
            "transfers": str(transfers_path or (DATA_DIR / "processed" / "transfers_exact_dates.csv")),
            "journalist_stats": "" if journalist_stats_path is None else str(journalist_stats_path),
            "source_stats": "" if source_stats_path is None else str(source_stats_path),
            "club_journalist_stats": "" if club_journalist_stats_path is None else str(club_journalist_stats_path),
        },
    }


def write_demo_payload(
    predictions_path: Path,
    metrics_path: Path,
    backtest_summary_path: Path,
    backtest_trades_path: Path,
    output_path: Path,
    transfers_path: Path | None = None,
    journalist_stats_path: Path | None = None,
    source_stats_path: Path | None = None,
    club_journalist_stats_path: Path | None = None,
) -> dict[str, Any]:
    payload = build_demo_payload(
        predictions_path,
        metrics_path,
        backtest_summary_path,
        backtest_trades_path,
        transfers_path=transfers_path,
        journalist_stats_path=journalist_stats_path,
        source_stats_path=source_stats_path,
        club_journalist_stats_path=club_journalist_stats_path,
    )
    ensure_parent(output_path)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def demo_payload_stats(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "signals": len(payload.get("current_signals", [])),
        "best_backtest_strategy": payload.get("overview", {}).get("best_backtest_strategy", ""),
        "latest_season": payload.get("latest_season", ""),
        "seasons": len(payload.get("available_seasons", [])),
    }
