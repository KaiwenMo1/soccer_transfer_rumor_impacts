from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isnan
from pathlib import Path
from statistics import mean, median
from typing import Any

from .config import Club
from .io import ensure_parent, read_csv, write_csv
from .market_features import (
    abnormal_return,
    align_market_points,
    fit_market_model,
)
from .stock import load_price_bars


def import_backtest_dependencies() -> tuple[Any, Any]:
    try:
        import pandas as pd
        import vectorbt as vbt
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Stage 7 backtesting requires pandas and vectorbt. Install them with: pip install -e '.[market_research]'"
        ) from exc
    return pd, vbt


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def safe_round(value: float | None, digits: int = 6) -> float | str:
    if value is None:
        return ""
    if isinstance(value, float) and isnan(value):
        return ""
    return round(float(value), digits)


def stage_is_strong(stage: str) -> bool:
    return stage in {"advanced", "agreed", "medical", "official"}


def predicted_prob(row: dict[str, str], label: str) -> float:
    return parse_float(row.get(f"prob_{label}"), 0.0)


def direction_sign(direction: str) -> float:
    if direction == "in":
        return 1.0
    if direction == "out":
        return -1.0
    return 0.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def blended_signal_score(row: dict[str, str]) -> float:
    model_edge = predicted_prob(row, "positive") - predicted_prob(row, "negative")
    transfer_edge = direction_sign(row.get("direction", "")) * parse_float(row.get("transfer_indicator"), 0.0)
    credibility_edge = (parse_float(row.get("credibility_score"), 0.5) - 0.5) * 2.0
    stage_edge = (parse_float(row.get("rumor_stage_score"), 0.5) - 0.5) * 2.0
    stock_edge = (parse_float(row.get("stock_context_indicator"), 0.5) - 0.5) * 2.0
    raw = (
        0.45 * model_edge
        + 0.20 * transfer_edge
        + 0.15 * credibility_edge
        + 0.10 * stage_edge
        + 0.10 * stock_edge
    )
    return round(clamp(raw, -1.0, 1.0) * 100.0, 2)


def blended_signal_label(row: dict[str, str], threshold: float = 12.0) -> str:
    score = blended_signal_score(row)
    if score >= threshold:
        return "positive"
    if score <= -threshold:
        return "negative"
    return "neutral"


def blended_signal_confidence(row: dict[str, str]) -> float:
    score = abs(blended_signal_score(row)) / 100.0
    credibility = parse_float(row.get("credibility_score"), 0.0)
    return round(clamp(0.30 + 0.45 * score + 0.25 * credibility, 0.0, 1.0), 4)


def club_lookup(clubs: dict[str, Club]) -> dict[str, Club]:
    lookup: dict[str, Club] = {}
    for club in clubs.values():
        lookup[club.name.lower()] = club
        lookup[club.key.lower()] = club
        for alias in club.aliases:
            lookup[alias.lower()] = club
    return lookup


@dataclass(frozen=True)
class SignalCandidate:
    strategy: str
    club: str
    player: str
    side: str
    signal_date: date
    score: float
    reason: str
    row: dict[str, str]


def candidate_for_strategy(
    row: dict[str, str],
    strategy: str,
    positive_threshold: float,
    negative_threshold: float,
    credibility_threshold: float,
) -> SignalCandidate | None:
    if row.get("split") != "test":
        return None
    signal_date = parse_date(row.get("event_trading_date") or row.get("published_date") or row.get("date", ""))
    if signal_date is None:
        return None
    club = row.get("club", "")
    player = row.get("player", "")
    stage = row.get("rumor_stage", "")
    direction = row.get("direction", "")
    credibility = parse_float(row.get("credibility_score"), 0.0)
    transfer_indicator = parse_float(row.get("transfer_indicator"), 0.0)
    journalist_rep = parse_float(row.get("journalist_reputation_score"), 0.0)
    historical_conv = parse_float(row.get("historical_conversion_score"), 0.0)
    stage_score = parse_float(row.get("rumor_stage_score"), 0.0)

    if strategy == "blended_long_short":
        score = blended_signal_score(row)
        if credibility < 0.55:
            return None
        if score >= 12.0:
            return SignalCandidate(strategy, club, player, "long", signal_date, score / 100.0, "blended_positive", row)
        if score <= -12.0:
            return SignalCandidate(strategy, club, player, "short", signal_date, abs(score) / 100.0, "blended_negative", row)
        return None
    if strategy == "model_long_positive":
        score = predicted_prob(row, "positive")
        if row.get("predicted_label") == "positive" and score >= positive_threshold:
            return SignalCandidate(strategy, club, player, "long", signal_date, score, "model_positive", row)
        return None
    if strategy == "model_short_negative":
        score = predicted_prob(row, "negative")
        if row.get("predicted_label") == "negative" and score >= negative_threshold:
            return SignalCandidate(strategy, club, player, "short", signal_date, score, "model_negative", row)
        return None
    if strategy == "model_long_short":
        positive = predicted_prob(row, "positive")
        negative = predicted_prob(row, "negative")
        if row.get("predicted_label") == "positive" and positive >= positive_threshold:
            return SignalCandidate(strategy, club, player, "long", signal_date, positive, "model_positive", row)
        if row.get("predicted_label") == "negative" and negative >= negative_threshold:
            return SignalCandidate(strategy, club, player, "short", signal_date, negative, "model_negative", row)
        return None
    if strategy == "model_long_short_strong_stage":
        if not stage_is_strong(stage):
            return None
        positive = predicted_prob(row, "positive")
        negative = predicted_prob(row, "negative")
        if row.get("predicted_label") == "positive" and positive >= positive_threshold:
            return SignalCandidate(strategy, club, player, "long", signal_date, positive, "model_positive_strong_stage", row)
        if row.get("predicted_label") == "negative" and negative >= negative_threshold:
            return SignalCandidate(strategy, club, player, "short", signal_date, negative, "model_negative_strong_stage", row)
        return None
    if strategy == "heuristic_long_short":
        if credibility < credibility_threshold or not stage_is_strong(stage):
            return None
        score = 0.55 * credibility + 0.30 * transfer_indicator + 0.15 * stage_score
        if direction == "in":
            return SignalCandidate(strategy, club, player, "long", signal_date, score, "heuristic_incoming", row)
        if direction == "out":
            return SignalCandidate(strategy, club, player, "short", signal_date, score, "heuristic_outgoing", row)
        return None
    if strategy == "journalist_long_short":
        score = 0.45 * credibility + 0.30 * journalist_rep + 0.25 * historical_conv
        if score < credibility_threshold or not stage_is_strong(stage):
            return None
        if direction == "in":
            return SignalCandidate(strategy, club, player, "long", signal_date, score, "journalist_incoming", row)
        if direction == "out":
            return SignalCandidate(strategy, club, player, "short", signal_date, score, "journalist_outgoing", row)
        return None
    raise ValueError(f"Unknown backtest strategy: {strategy}")


def dedupe_candidates(candidates: list[SignalCandidate]) -> list[SignalCandidate]:
    best: dict[tuple[str, str, str], SignalCandidate] = {}
    for candidate in candidates:
        key = (candidate.strategy, candidate.club.lower(), candidate.signal_date.isoformat())
        current = best.get(key)
        if current is None or candidate.score > current.score:
            best[key] = candidate
    return sorted(best.values(), key=lambda item: (item.strategy, item.signal_date, item.club, item.player))


def available_strategies() -> list[str]:
    return [
        "blended_long_short",
        "model_long_positive",
        "model_short_negative",
        "model_long_short",
        "model_long_short_strong_stage",
        "heuristic_long_short",
        "journalist_long_short",
    ]


def load_aligned_points_for_club(club: Club, stocks_dir: Path) -> list[Any]:
    stock_path = stocks_dir / f"{club.key}.csv"
    market_path = stocks_dir / f"{club.key}_market.csv"
    if not stock_path.exists() or not market_path.exists():
        return []
    return align_market_points(load_price_bars(stock_path), load_price_bars(market_path))


def next_trading_index(points: list[Any], signal_date: date) -> int | None:
    for index, point in enumerate(points):
        if point.date > signal_date:
            return index
    return None


def trade_rows_for_strategy(
    strategy: str,
    candidates: list[SignalCandidate],
    clubs: dict[str, Club],
    holding_days: int,
    stocks_dir: Path,
) -> tuple[list[dict[str, object]], dict[date, list[float]]]:
    club_map = club_lookup(clubs)
    aligned_cache: dict[str, list[Any]] = {}
    trades: list[dict[str, object]] = []
    portfolio_returns: dict[date, list[float]] = {}

    for candidate in candidates:
        club = club_map.get(candidate.club.lower())
        if club is None:
            continue
        points = aligned_cache.setdefault(club.key, load_aligned_points_for_club(club, stocks_dir))
        if not points:
            continue
        entry_idx = next_trading_index(points, candidate.signal_date)
        if entry_idx is None:
            continue
        exit_idx = entry_idx + holding_days - 1
        if exit_idx >= len(points):
            continue
        entry_point = points[entry_idx]
        exit_point = points[exit_idx]
        side_sign = 1.0 if candidate.side == "long" else -1.0
        fit = fit_market_model(points, entry_idx, estimation_days=120, gap_days=0)
        if fit is None:
            alpha = 0.0
            beta = 1.0
            abnormal_backend = "market_adjusted_fallback"
        else:
            alpha, beta, _ = fit
            abnormal_backend = "ols_market_model"
        stock_return = 1.0
        market_return = 1.0
        for point in points[entry_idx : exit_idx + 1]:
            stock_return *= 1.0 + float(point.stock_return)
            market_return *= 1.0 + float(point.market_return)
            expected = alpha + beta * point.market_return
            day_return = side_sign * float(point.stock_return)
            portfolio_returns.setdefault(point.date, []).append(day_return)
        stock_return -= 1.0
        market_return -= 1.0
        abnormal = abnormal_return(points, entry_idx, exit_idx, alpha, beta)
        trades.append(
            {
                "strategy": strategy,
                "club": candidate.club,
                "player": candidate.player,
                "side": candidate.side,
                "reason": candidate.reason,
                "signal_date": candidate.signal_date.isoformat(),
                "entry_date": entry_point.date.isoformat(),
                "exit_date": exit_point.date.isoformat(),
                "holding_days": holding_days,
                "signal_score": round(candidate.score, 4),
                "prediction_confidence": parse_float(candidate.row.get("prediction_confidence"), 0.0),
                "predicted_label": candidate.row.get("predicted_label", ""),
                "actual_label": candidate.row.get("actual_label", ""),
                "credibility_score": parse_float(candidate.row.get("credibility_score"), 0.0),
                "journalist": candidate.row.get("journalist", ""),
                "source": candidate.row.get("source", ""),
                "rumor_stage": candidate.row.get("rumor_stage", ""),
                "direction": candidate.row.get("direction", ""),
                "transfer_indicator": parse_float(candidate.row.get("transfer_indicator"), 0.0),
                "raw_stock_return": safe_round(stock_return),
                "raw_market_return": safe_round(market_return),
                "trade_return": safe_round(side_sign * stock_return),
                "abnormal_return": safe_round(side_sign * abnormal),
                "abnormal_backend": abnormal_backend,
            }
        )
    return trades, portfolio_returns


def portfolio_metrics(
    strategy: str,
    trades: list[dict[str, object]],
    portfolio_returns: dict[date, list[float]],
    pd: Any,
) -> dict[str, object]:
    if not trades:
        return {
            "strategy": strategy,
            "n_trades": 0,
            "status": "no_trades",
        }
    daily_index = sorted(portfolio_returns)
    daily_returns = [mean(portfolio_returns[day]) if portfolio_returns[day] else 0.0 for day in daily_index]
    returns_series = pd.Series(daily_returns, index=pd.DatetimeIndex([datetime.combine(day, datetime.min.time()) for day in daily_index]))
    returns_accessor = returns_series.vbt.returns(freq="1D")
    trade_returns = [parse_float(row.get("trade_return"), 0.0) for row in trades]
    abnormal_returns = [parse_float(row.get("abnormal_return"), 0.0) for row in trades]
    wins = sum(1 for value in trade_returns if value > 0)
    long_trades = sum(1 for row in trades if row.get("side") == "long")
    short_trades = sum(1 for row in trades if row.get("side") == "short")
    unique_clubs = len({str(row.get("club", "")) for row in trades})
    turnover = len(trades) / len(daily_returns) if daily_returns else 0.0
    return {
        "strategy": strategy,
        "status": "ok",
        "n_trades": len(trades),
        "long_trades": long_trades,
        "short_trades": short_trades,
        "clubs_covered": unique_clubs,
        "win_rate": safe_round(wins / len(trade_returns) if trade_returns else 0.0, 4),
        "avg_trade_return": safe_round(mean(trade_returns), 6),
        "median_trade_return": safe_round(median(trade_returns), 6),
        "avg_abnormal_return": safe_round(mean(abnormal_returns), 6),
        "portfolio_total_return": safe_round(float(returns_accessor.total()), 6),
        "sharpe_like": safe_round(float(returns_accessor.sharpe_ratio()), 6),
        "max_drawdown": safe_round(float(returns_accessor.max_drawdown()), 6),
        "turnover": safe_round(turnover, 6),
        "annualized_turnover": safe_round(turnover * 252.0, 4),
        "start_date": daily_index[0].isoformat(),
        "end_date": daily_index[-1].isoformat(),
    }


def build_report_markdown(summary_rows: list[dict[str, object]], trades: list[dict[str, object]], holding_days: int) -> str:
    lines = [
        "# Backtest Report",
        "",
        "Trade convention:",
        f"- Signal observed on rumor/event date.",
        f"- Entry occurs on the next available trading day close.",
        f"- Position holds for {holding_days} trading days.",
        "- Portfolio daily return is the equal-weight average of active trade returns across clubs.",
        "",
        "## Strategy Summary",
        "",
        "| Strategy | Trades | Win Rate | Avg Trade | Avg Abnormal | Total Return | Sharpe | Max DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        if row.get("status") != "ok":
            lines.append(f"| {row['strategy']} | 0 |  |  |  |  |  |  |")
            continue
        lines.append(
            "| {strategy} | {n_trades} | {win_rate} | {avg_trade_return} | {avg_abnormal_return} | {portfolio_total_return} | {sharpe_like} | {max_drawdown} |".format(
                **row
            )
        )

    top_trades = sorted(trades, key=lambda row: abs(parse_float(row.get("trade_return"), 0.0)), reverse=True)[:10]
    lines.extend(
        [
            "",
            "## Biggest Trades",
            "",
            "| Strategy | Club | Player | Side | Entry | Exit | Return | Abnormal | Reason |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in top_trades:
        lines.append(
            "| {strategy} | {club} | {player} | {side} | {entry_date} | {exit_date} | {trade_return} | {abnormal_return} | {reason} |".format(
                **row
            )
        )
    return "\n".join(lines) + "\n"


def run_backtests(
    predictions_path: Path,
    output_dir: Path,
    clubs: dict[str, Club],
    holding_days: int = 3,
    positive_threshold: float = 0.55,
    negative_threshold: float = 0.55,
    credibility_threshold: float = 0.65,
    stocks_dir: Path | None = None,
) -> dict[str, Path]:
    pd, _ = import_backtest_dependencies()
    rows = read_csv(predictions_path)
    stocks_root = stocks_dir or predictions_path.parents[2] / "raw" / "stocks"
    strategy_summary_rows: list[dict[str, object]] = []
    all_trades: list[dict[str, object]] = []
    all_daily_rows: list[dict[str, object]] = []

    for strategy in available_strategies():
        raw_candidates = [
            candidate
            for row in rows
            if (candidate := candidate_for_strategy(row, strategy, positive_threshold, negative_threshold, credibility_threshold))
            is not None
        ]
        candidates = dedupe_candidates(raw_candidates)
        trades, portfolio_returns = trade_rows_for_strategy(strategy, candidates, clubs, holding_days, stocks_root)
        summary = portfolio_metrics(strategy, trades, portfolio_returns, pd)
        summary["raw_signal_rows"] = len(raw_candidates)
        summary["deduped_signal_rows"] = len(candidates)
        strategy_summary_rows.append(summary)
        all_trades.extend(trades)
        for day in sorted(portfolio_returns):
            all_daily_rows.append(
                {
                    "strategy": strategy,
                    "date": day.isoformat(),
                    "active_trades": len(portfolio_returns[day]),
                    "portfolio_return": safe_round(mean(portfolio_returns[day]) if portfolio_returns[day] else 0.0),
                }
            )

    strategy_summary_rows.sort(key=lambda row: parse_float(row.get("portfolio_total_return"), -999.0), reverse=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "backtest_summary.csv"
    trades_path = output_dir / "backtest_trades.csv"
    daily_path = output_dir / "backtest_daily_returns.csv"
    report_path = output_dir / "backtest_report.md"
    write_csv(summary_path, strategy_summary_rows, list(strategy_summary_rows[0].keys()) if strategy_summary_rows else ["strategy", "status"])
    write_csv(trades_path, all_trades, list(all_trades[0].keys()) if all_trades else ["strategy", "club", "player", "side"])
    write_csv(daily_path, all_daily_rows, list(all_daily_rows[0].keys()) if all_daily_rows else ["strategy", "date", "active_trades", "portfolio_return"])
    ensure_parent(report_path)
    report_path.write_text(build_report_markdown(strategy_summary_rows, all_trades, holding_days), encoding="utf-8")
    return {
        "summary": summary_path,
        "trades": trades_path,
        "daily_returns": daily_path,
        "report": report_path,
    }


def backtest_stats(path: Path) -> dict[str, object]:
    rows = read_csv(path)
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    return {
        "rows": len(rows),
        "ok_rows": len(ok_rows),
        "best_strategy": "" if not ok_rows else max(ok_rows, key=lambda row: parse_float(row.get("portfolio_total_return"), -999.0)).get("strategy", ""),
    }
