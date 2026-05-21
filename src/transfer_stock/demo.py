from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .backtesting import blended_signal_confidence, blended_signal_label, blended_signal_score
from .config import Club, DATA_DIR, load_clubs
from .io import ensure_parent, read_csv
from .market_features import compute_market_features_for_event, load_bars
from .targets import direct_target_rows
from .transfers import load_transfers


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
    return datetime(1970, 1, 1, tzinfo=UTC)


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
    sources = sorted({row.get("source", "") for row in ordered if row.get("source")})
    journalists = sorted({row.get("journalist", "") for row in ordered if row.get("journalist")})
    actual_values = [row.get("actual_label", "") for row in ordered if row.get("actual_label")]
    return {
        "group_key": f"{latest.get('club', '')}::{latest.get('player', '')}",
        "club": latest.get("club", ""),
        "player": latest.get("player", ""),
        "season": latest.get("season", ""),
        "direction": latest.get("direction", ""),
        "position": latest.get("position", ""),
        "age": parse_float(latest.get("age"), 0.0),
        "market_value_eur": parse_float(latest.get("market_value_eur"), 0.0),
        "transfer_fee_eur": parse_float(latest.get("transfer_fee_eur"), 0.0),
        "transfer_type": latest.get("transfer_type", ""),
        "latest_published_at": latest.get("published_at", ""),
        "latest_source": latest.get("source", ""),
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
    }


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


def article_cluster_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("target_club") or row.get("club", ""),
        row.get("player", ""),
        row.get("target_role", ""),
    )


def cluster_current_rows(
    rows: list[dict[str, str]],
    *,
    gap_days: int = 5,
) -> list[list[dict[str, str]]]:
    direct_rows = [row for row in rows if row.get("prediction_scope") == "direct" and row.get("published_at")]
    buckets: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in direct_rows:
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
                clusters.append(current_cluster)
                current_cluster = [row]
            previous_dt = current_dt
        if current_cluster:
            clusters.append(current_cluster)
    clusters.sort(key=lambda rows: parse_timestamp(str(rows[0].get("published_at", ""))), reverse=True)
    return clusters


def summarize_watchlist_cluster(rows: list[dict[str, str]]) -> dict[str, Any]:
    ordered = sorted(rows, key=lambda row: parse_timestamp(str(row.get("published_at", ""))), reverse=True)
    latest = ordered[0]
    credibility_scores = [parse_float(row.get("credibility_score"), 0.0) for row in ordered]
    blended_scores = [blended_signal_score(row) for row in ordered]
    stage_scores = [parse_float(row.get("rumor_stage_score"), 0.0) for row in ordered]
    return {
        "group_key": f"{latest.get('target_club') or latest.get('club','')}::{latest.get('player','')}",
        "cluster_key": f"{latest.get('target_club') or latest.get('club','')}::{latest.get('player','')}::{latest.get('published_date') or latest.get('date','')}",
        "published_at": latest.get("published_at", ""),
        "first_published_at": ordered[-1].get("published_at", ""),
        "cluster_span_days": max(0, (parse_timestamp(str(ordered[0].get("published_at", ""))) - parse_timestamp(str(ordered[-1].get("published_at", "")))).days),
        "article_count": len(ordered),
        "source_count": len({row.get("source", "") for row in ordered if row.get("source")}),
        "club": latest.get("club", ""),
        "player": latest.get("player", ""),
        "target_club": latest.get("target_club", ""),
        "target_role": latest.get("target_role", ""),
        "journalist": latest.get("journalist", ""),
        "source": latest.get("source", ""),
        "rumor_stage": latest.get("rumor_stage", ""),
        "credibility_score": round(max(credibility_scores) if credibility_scores else 0.0, 4),
        "transfer_indicator": round(parse_float(latest.get("transfer_indicator"), 0.0), 4),
        "stock_context_indicator": round(parse_float(latest.get("stock_context_indicator"), 0.0), 4),
        "predicted_label": latest.get("predicted_label", ""),
        "prediction_confidence": round(parse_float(latest.get("prediction_confidence"), 0.0), 4),
        "blended_label": blended_signal_label(latest),
        "blended_score": round(max(blended_scores) if blended_scores else 0.0, 2),
        "target_ticker": latest.get("target_ticker", ""),
        "max_stage_score": round(max(stage_scores) if stage_scores else 0.0, 4),
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
    latest_dt = parse_timestamp(str(clusters[0].get("published_at", "")))
    fresh_threshold = now - timedelta(days=recent_days)
    recent_clusters = [row for row in clusters if parse_timestamp(str(row.get("published_at", ""))) >= fresh_threshold]
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
        "latest_published_at": clusters[0].get("published_at", ""),
        "days_stale": days_stale,
        "window_days": recent_days,
        "is_stale": days_stale > recent_days,
        "recent_cluster_count": len(recent_clusters),
    }


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
    ranked = []
    for row in historical_rows:
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
            row["similar_examples"] = similar_examples(row, comparison_pool, limit=3)
        signal_rows.sort(key=lambda row: (abs(row["blended_score"]), row["latest_published_at"]), reverse=True)
        signals_by_season[season] = signal_rows
        season_summaries[season] = season_summary(season, signal_rows)

    transfer_rows = transfer_history_rows(clubs, transfers_path or (DATA_DIR / "processed" / "transfers_exact_dates.csv"))
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

    return {
        "generated_at": generated_at.isoformat(),
        "latest_season": latest_season,
        "available_seasons": available_seasons,
        "overview": {
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
        },
        "season_summaries": season_summaries,
        "signals_by_season": signals_by_season,
        "transfer_season_summaries": transfer_season_summaries,
        "transfers_by_season": transfers_by_season,
        "current_signals": signal_rows,
        "live_watchlist": watchlist,
        "live_watchlist_meta": watchlist_meta,
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
