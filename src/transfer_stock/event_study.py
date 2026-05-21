from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import mean

from .stock import PriceBar, load_price_bars


@dataclass(frozen=True)
class ReturnPoint:
    date: date
    value: float


def daily_returns(bars: list[PriceBar]) -> list[ReturnPoint]:
    ordered = sorted(bars, key=lambda bar: bar.date)
    returns: list[ReturnPoint] = []
    for previous, current in zip(ordered, ordered[1:]):
        if previous.close <= 0:
            continue
        returns.append(ReturnPoint(current.date, current.close / previous.close - 1.0))
    return returns


def align_returns(stock: list[ReturnPoint], market: list[ReturnPoint]) -> list[tuple[date, float, float]]:
    market_by_date = {point.date: point.value for point in market}
    aligned: list[tuple[date, float, float]] = []
    for point in stock:
        if point.date in market_by_date:
            aligned.append((point.date, point.value, market_by_date[point.date]))
    return aligned


def ols_alpha_beta(points: list[tuple[date, float, float]]) -> tuple[float, float]:
    if len(points) < 2:
        return 0.0, 1.0
    y = [stock_return for _, stock_return, _ in points]
    x = [market_return for _, _, market_return in points]
    x_mean = mean(x)
    y_mean = mean(y)
    denominator = sum((item - x_mean) ** 2 for item in x)
    if denominator == 0:
        return y_mean, 0.0
    beta = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y)) / denominator
    alpha = y_mean - beta * x_mean
    return alpha, beta


def nearest_trading_index(points: list[tuple[date, float, float]], event_date: date) -> int | None:
    for index, (point_date, _, _) in enumerate(points):
        if point_date >= event_date:
            return index
    return None


def cumulative_abnormal_return(
    stock_bars: list[PriceBar],
    market_bars: list[PriceBar],
    event_date: date,
    estimation_days: int = 120,
    window_start: int = -1,
    window_end: int = 1,
) -> float | None:
    aligned = align_returns(daily_returns(stock_bars), daily_returns(market_bars))
    event_index = nearest_trading_index(aligned, event_date)
    if event_index is None:
        return None

    estimation_start = max(0, event_index - estimation_days - 10)
    estimation_end = max(0, event_index - 10)
    estimation_points = aligned[estimation_start:estimation_end]
    if len(estimation_points) < 20:
        return None

    alpha, beta = ols_alpha_beta(estimation_points)
    start = max(0, event_index + window_start)
    end = min(len(aligned) - 1, event_index + window_end)
    car = 0.0
    for _, stock_return, market_return in aligned[start : end + 1]:
        expected = alpha + beta * market_return
        car += stock_return - expected
    return round(car, 6)


def load_bars_if_exists(path: Path) -> list[PriceBar]:
    if not path.exists():
        return []
    return load_price_bars(path)

