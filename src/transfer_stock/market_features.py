from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
import importlib.util

from .config import Club
from .event_study import daily_returns, ols_alpha_beta
from .io import read_csv, write_csv
from .model import impact_label
from .stock import PriceBar, load_price_bars


MARKET_FEATURE_EXTRA_FIELDS = [
    "market_feature_backend",
    "market_feature_status",
    "market_feature_notes",
    "event_date_used",
    "event_trading_date",
    "event_trading_offset_days",
    "estimation_points",
    "market_model_alpha",
    "market_model_beta",
    "pre_window_ok_30d",
    "post_window_ok_10d",
    "pre_raw_return_m1",
    "pre_raw_return_m3",
    "pre_raw_return_m5",
    "pre_raw_return_m10",
    "pre_raw_return_m20",
    "pre_raw_return_m30",
    "pre_market_return_m1",
    "pre_market_return_m3",
    "pre_market_return_m5",
    "pre_market_return_m10",
    "pre_market_return_m20",
    "pre_market_return_m30",
    "pre_abnormal_return_m1",
    "pre_abnormal_return_m3",
    "pre_abnormal_return_m5",
    "pre_abnormal_return_m10",
    "raw_return_0_p1",
    "raw_return_0_p3",
    "raw_return_0_p5",
    "raw_return_0_p10",
    "market_return_0_p1",
    "market_return_0_p3",
    "market_return_0_p5",
    "market_return_0_p10",
    "abnormal_return_0_p1",
    "abnormal_return_0_p3",
    "abnormal_return_0_p5",
    "abnormal_return_0_p10",
    "pre_volatility_20d",
    "post_volatility_20d",
    "volatility_shift_20d",
    "pre_close_zscore_20d",
    "event_close_zscore_20d",
    "pre_volume_zscore_20d",
    "event_volume_zscore_20d",
    "relative_volume_20d",
    "target_abnormal_return_p3",
    "target_label_p3",
]


@dataclass(frozen=True)
class AlignedMarketPoint:
    date: date
    stock_close: float
    stock_volume: int
    market_close: float
    market_volume: int
    stock_return: float
    market_return: float


def vectorbt_available() -> bool:
    return importlib.util.find_spec("vectorbt") is not None


def market_backend_label() -> str:
    return "vectorbt" if vectorbt_available() else "python_fallback"


def compact_row_fields(rows: list[dict[str, str]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row.keys():
            if field in seen:
                continue
            seen.add(field)
            ordered.append(field)
    return ordered


def parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def club_lookup(clubs: dict[str, Club]) -> dict[str, Club]:
    lookup: dict[str, Club] = {}
    for club in clubs.values():
        lookup[club.name.lower()] = club
        lookup[club.key.lower()] = club
        for alias in club.aliases:
            lookup[alias.lower()] = club
    return lookup


def load_bars(path: Path) -> list[PriceBar]:
    if not path.exists():
        return []
    return load_price_bars(path)


def align_market_points(stock_bars: list[PriceBar], market_bars: list[PriceBar]) -> list[AlignedMarketPoint]:
    stock_by_date = {bar.date: bar for bar in stock_bars}
    market_by_date = {bar.date: bar for bar in market_bars}
    stock_returns = {point.date: point.value for point in daily_returns(stock_bars)}
    market_returns = {point.date: point.value for point in daily_returns(market_bars)}
    common_dates = sorted(set(stock_returns) & set(market_returns) & set(stock_by_date) & set(market_by_date))
    points: list[AlignedMarketPoint] = []
    for day in common_dates:
        stock_bar = stock_by_date[day]
        market_bar = market_by_date[day]
        points.append(
            AlignedMarketPoint(
                date=day,
                stock_close=stock_bar.close,
                stock_volume=stock_bar.volume,
                market_close=market_bar.close,
                market_volume=market_bar.volume,
                stock_return=stock_returns[day],
                market_return=market_returns[day],
            )
        )
    return points


def event_index(points: list[AlignedMarketPoint], event_date: date) -> int | None:
    for index, point in enumerate(points):
        if point.date >= event_date:
            return index
    return None


def round_or_blank(value: float | None, digits: int = 6) -> float | str:
    if value is None:
        return ""
    return round(value, digits)


def window_bounds(event_idx: int, start_offset: int, end_offset: int, total: int) -> tuple[int, int] | None:
    start = event_idx + start_offset
    end = event_idx + end_offset
    if start < 0 or end < 0 or start >= total or end >= total or start > end:
        return None
    return start, end


def compounded_return(points: list[AlignedMarketPoint], start: int, end: int, field: str) -> float:
    product = 1.0
    for point in points[start : end + 1]:
        product *= 1.0 + float(getattr(point, field))
    return product - 1.0


def abnormal_return(points: list[AlignedMarketPoint], start: int, end: int, alpha: float, beta: float) -> float:
    total = 0.0
    for point in points[start : end + 1]:
        expected = alpha + beta * point.market_return
        total += point.stock_return - expected
    return total


def return_volatility(points: list[AlignedMarketPoint], start: int, end: int, field: str) -> float | None:
    returns = [float(getattr(point, field)) for point in points[start : end + 1]]
    if len(returns) < 2:
        return None
    return pstdev(returns)


def zscore(current: float, history: list[float]) -> float | None:
    if len(history) < 2:
        return None
    sigma = pstdev(history)
    if sigma == 0:
        return 0.0
    return (current - mean(history)) / sigma


def trailing_history(points: list[AlignedMarketPoint], current_idx: int, lookback: int, field: str) -> tuple[float, list[float]] | None:
    if current_idx < 0:
        return None
    start = current_idx - lookback
    if start < 0:
        return None
    history = [float(getattr(point, field)) for point in points[start:current_idx]]
    if len(history) < lookback:
        return None
    current = float(getattr(points[current_idx], field))
    return current, history


def trailing_zscore(points: list[AlignedMarketPoint], current_idx: int, lookback: int, field: str) -> float | None:
    values = trailing_history(points, current_idx, lookback, field)
    if values is None:
        return None
    current, history = values
    return zscore(current, history)


def relative_volume(points: list[AlignedMarketPoint], event_idx: int, lookback: int) -> float | None:
    values = trailing_history(points, event_idx, lookback, "stock_volume")
    if values is None:
        return None
    current, history = values
    baseline = mean(history)
    if baseline <= 0:
        return None
    return current / baseline


def fit_market_model(
    points: list[AlignedMarketPoint],
    event_idx: int,
    estimation_days: int = 120,
    gap_days: int = 5,
) -> tuple[float, float, int] | None:
    estimation_end = event_idx - gap_days
    if estimation_end <= 0:
        return None
    estimation_start = max(0, estimation_end - estimation_days)
    sample = points[estimation_start:estimation_end]
    if len(sample) < 20:
        return None
    alpha, beta = ols_alpha_beta([(point.date, point.stock_return, point.market_return) for point in sample])
    return alpha, beta, len(sample)


def compute_market_features_for_event(
    event_date: date,
    stock_bars: list[PriceBar],
    market_bars: list[PriceBar],
    estimation_days: int = 120,
    gap_days: int = 5,
    lookback_days: int = 20,
) -> dict[str, object]:
    backend = market_backend_label()
    notes: list[str] = []
    if not stock_bars:
        return {
            "market_feature_backend": backend,
            "market_feature_status": "missing_stock_bars",
            "market_feature_notes": "missing_stock_bars",
            "event_date_used": event_date.isoformat(),
        }
    if not market_bars:
        return {
            "market_feature_backend": backend,
            "market_feature_status": "missing_market_bars",
            "market_feature_notes": "missing_market_bars",
            "event_date_used": event_date.isoformat(),
        }

    points = align_market_points(stock_bars, market_bars)
    if not points:
        return {
            "market_feature_backend": backend,
            "market_feature_status": "no_aligned_market_points",
            "market_feature_notes": "no_aligned_market_points",
            "event_date_used": event_date.isoformat(),
        }

    idx = event_index(points, event_date)
    if idx is None:
        return {
            "market_feature_backend": backend,
            "market_feature_status": "event_after_price_history",
            "market_feature_notes": "event_after_price_history",
            "event_date_used": event_date.isoformat(),
        }

    model = fit_market_model(points, idx, estimation_days=estimation_days, gap_days=gap_days)
    if model is None:
        alpha = 0.0
        beta = 1.0
        estimation_points = 0
        notes.append("insufficient_estimation_window")
        status = "limited_history"
    else:
        alpha, beta, estimation_points = model
        status = "ok"

    result: dict[str, object] = {
        "market_feature_backend": backend,
        "market_feature_status": status,
        "market_feature_notes": "",
        "event_date_used": event_date.isoformat(),
        "event_trading_date": points[idx].date.isoformat(),
        "event_trading_offset_days": (points[idx].date - event_date).days,
        "estimation_points": estimation_points,
        "market_model_alpha": round_or_blank(alpha),
        "market_model_beta": round_or_blank(beta),
    }

    total = len(points)
    result["pre_window_ok_30d"] = int(window_bounds(idx, -30, -1, total) is not None)
    result["post_window_ok_10d"] = int(window_bounds(idx, 0, 10, total) is not None)

    for window in (1, 3, 5, 10, 20, 30):
        bounds = window_bounds(idx, -window, -1, total)
        result[f"pre_raw_return_m{window}"] = round_or_blank(
            compounded_return(points, bounds[0], bounds[1], "stock_return") if bounds else None
        )
        result[f"pre_market_return_m{window}"] = round_or_blank(
            compounded_return(points, bounds[0], bounds[1], "market_return") if bounds else None
        )
        if window in {1, 3, 5, 10}:
            result[f"pre_abnormal_return_m{window}"] = round_or_blank(
                abnormal_return(points, bounds[0], bounds[1], alpha, beta) if bounds else None
            )

    for window in (1, 3, 5, 10):
        bounds = window_bounds(idx, 0, window, total)
        result[f"raw_return_0_p{window}"] = round_or_blank(
            compounded_return(points, bounds[0], bounds[1], "stock_return") if bounds else None
        )
        result[f"market_return_0_p{window}"] = round_or_blank(
            compounded_return(points, bounds[0], bounds[1], "market_return") if bounds else None
        )
        result[f"abnormal_return_0_p{window}"] = round_or_blank(
            abnormal_return(points, bounds[0], bounds[1], alpha, beta) if bounds else None
        )

    pre_vol_bounds = window_bounds(idx, -lookback_days, -1, total)
    post_vol_bounds = window_bounds(idx, 0, lookback_days - 1, total)
    pre_vol = return_volatility(points, pre_vol_bounds[0], pre_vol_bounds[1], "stock_return") if pre_vol_bounds else None
    post_vol = return_volatility(points, post_vol_bounds[0], post_vol_bounds[1], "stock_return") if post_vol_bounds else None
    result["pre_volatility_20d"] = round_or_blank(pre_vol)
    result["post_volatility_20d"] = round_or_blank(post_vol)
    result["volatility_shift_20d"] = round_or_blank(None if pre_vol is None or post_vol is None else post_vol - pre_vol)

    result["pre_close_zscore_20d"] = round_or_blank(trailing_zscore(points, idx - 1, lookback_days, "stock_close"))
    result["event_close_zscore_20d"] = round_or_blank(trailing_zscore(points, idx, lookback_days, "stock_close"))
    result["pre_volume_zscore_20d"] = round_or_blank(trailing_zscore(points, idx - 1, lookback_days, "stock_volume"))
    result["event_volume_zscore_20d"] = round_or_blank(trailing_zscore(points, idx, lookback_days, "stock_volume"))
    result["relative_volume_20d"] = round_or_blank(relative_volume(points, idx, lookback_days))

    target = result.get("abnormal_return_0_p3")
    target_value = None if target == "" else float(target)
    result["target_abnormal_return_p3"] = "" if target_value is None else target_value
    result["target_label_p3"] = "" if target_value is None else impact_label(target_value)

    if result["event_trading_offset_days"] > 3:
        notes.append("event_date_far_from_trading_day")
    if not result["pre_window_ok_30d"]:
        notes.append("short_pre_window")
    if not result["post_window_ok_10d"]:
        notes.append("short_post_window")
    result["market_feature_notes"] = "|".join(notes)
    return result


def build_market_features(
    input_path: Path,
    output_path: Path,
    clubs: dict[str, Club],
    estimation_days: int = 120,
    gap_days: int = 5,
    lookback_days: int = 20,
) -> list[dict[str, object]]:
    input_rows = read_csv(input_path)
    clubs_by_name = club_lookup(clubs)
    cache: dict[str, tuple[list[PriceBar], list[PriceBar]]] = {}
    output_rows: list[dict[str, object]] = []

    for row in input_rows:
        prediction_scope = row.get("prediction_scope", "direct")
        club_name = row.get("target_club") or row.get("club", "")
        event_date = parse_date(row.get("published_date") or row.get("date", ""))
        if event_date is None:
            output_rows.append(
                {
                    **row,
                    "market_feature_backend": market_backend_label(),
                    "market_feature_status": "missing_event_date",
                    "market_feature_notes": "missing_event_date",
                    "event_date_used": "",
                }
            )
            continue
        if prediction_scope != "direct" or not club_name:
            output_rows.append(
                {
                    **row,
                    "market_feature_backend": market_backend_label(),
                    "market_feature_status": "no_public_target",
                    "market_feature_notes": "no_public_target",
                    "event_date_used": event_date.isoformat(),
                }
            )
            continue
        club = clubs_by_name.get(club_name.lower())
        if club is None:
            output_rows.append(
                {
                    **row,
                    "market_feature_backend": market_backend_label(),
                    "market_feature_status": "unknown_club",
                    "market_feature_notes": "unknown_club",
                    "event_date_used": event_date.isoformat(),
                }
            )
            continue
        if club.key not in cache:
            cache[club.key] = (
                load_bars(Path("data/raw/stocks") / f"{club.key}.csv"),
                load_bars(Path("data/raw/stocks") / f"{club.key}_market.csv"),
            )
        stock_bars, market_bars = cache[club.key]
        features = compute_market_features_for_event(
            event_date,
            stock_bars,
            market_bars,
            estimation_days=estimation_days,
            gap_days=gap_days,
            lookback_days=lookback_days,
        )
        output_rows.append({**row, **features})

    fieldnames = compact_row_fields(input_rows)
    for field in MARKET_FEATURE_EXTRA_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    write_csv(output_path, output_rows, fieldnames)
    return output_rows


def market_feature_stats(rows: list[dict[str, Any]]) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    target_values: list[float] = []
    for row in rows:
        status = str(row.get("market_feature_status", "") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        value = row.get("target_abnormal_return_p3")
        if value not in {"", None}:
            target_values.append(float(value))
    return {
        "n_rows": len(rows),
        "status_counts": dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0]))),
        "rows_with_target_p3": len(target_values),
        "avg_abs_target_p3": round(mean(abs(value) for value in target_values), 6) if target_values else 0.0,
    }
