from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from io import StringIO
from pathlib import Path
from urllib.parse import quote

from .http import get_json, get_text
from .io import write_csv


STOOQ_URL = "https://stooq.com/q/d/l/"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


@dataclass(frozen=True)
class PriceBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def fetch_stooq_daily(symbol: str, start: date, end: date, api_key: str | None = None) -> list[PriceBar]:
    params = {
        "s": symbol.lower(),
        "i": "d",
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
    }
    if api_key:
        params["apikey"] = api_key
    text = get_text(STOOQ_URL, params=params)
    if text.lower().startswith("get your apikey"):
        return []
    rows = list(csv.DictReader(StringIO(text)))
    bars: list[PriceBar] = []
    for row in rows:
        if not row.get("Date") or row.get("Close") in {"", "N/D", None}:
            continue
        bars.append(
            PriceBar(
                date=date.fromisoformat(row["Date"]),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(float(row.get("Volume") or 0)),
            )
        )
    return bars


def unix_seconds(day: date) -> int:
    return int(datetime.combine(day, time.min, tzinfo=UTC).timestamp())


def fetch_yahoo_daily(symbol: str, start: date, end: date) -> list[PriceBar]:
    # Yahoo's period2 is exclusive, so move it one day forward.
    params = {
        "period1": unix_seconds(start),
        "period2": unix_seconds(end + timedelta(days=1)),
        "interval": "1d",
        "events": "history",
    }
    data = get_json(YAHOO_CHART_URL.format(symbol=quote(symbol, safe="^.")), params=params)
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        return []
    timestamps = result.get("timestamp") or []
    quote_data = (result.get("indicators", {}).get("quote") or [{}])[0]
    bars: list[PriceBar] = []
    for index, timestamp in enumerate(timestamps):
        close_values = quote_data.get("close") or []
        close = close_values[index] if index < len(close_values) else None
        if close is None:
            continue
        bars.append(
            PriceBar(
                date=datetime.fromtimestamp(timestamp, tz=UTC).date(),
                open=float((quote_data.get("open") or [close])[index] or close),
                high=float((quote_data.get("high") or [close])[index] or close),
                low=float((quote_data.get("low") or [close])[index] or close),
                close=float(close),
                volume=int((quote_data.get("volume") or [0])[index] or 0),
            )
        )
    return bars


def fetch_daily(
    symbol: str,
    start: date,
    end: date,
    source: str = "yahoo",
    stooq_api_key: str | None = None,
) -> list[PriceBar]:
    if source == "yahoo":
        return fetch_yahoo_daily(symbol, start, end)
    if source == "stooq":
        return fetch_stooq_daily(symbol, start, end, api_key=stooq_api_key)
    raise ValueError(f"Unsupported stock source: {source}")


def save_price_bars(path: Path, bars: list[PriceBar]) -> None:
    write_csv(
        path,
        [
            {
                "date": bar.date.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ],
        ["date", "open", "high", "low", "close", "volume"],
    )


def load_price_bars(path: Path) -> list[PriceBar]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        return [
            PriceBar(
                date=date.fromisoformat(row["date"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(float(row["volume"])),
            )
            for row in rows
        ]
