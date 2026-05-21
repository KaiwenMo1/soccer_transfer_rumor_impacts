from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from statistics import mean, pstdev

from .config import Club
from .features import clamp, transfer_quality_score
from .io import read_csv, write_csv
from .stock import PriceBar, load_price_bars
from .transfers import Transfer


ENRICHED_RUMOR_FIELDS = [
    "date",
    "published_date",
    "club",
    "player",
    "source",
    "title",
    "url",
    "credibility_score",
    "rumor_strength",
    "rumor_count",
    "source_diversity",
    "max_credibility",
    "avg_credibility",
    "max_rumor_strength",
    "avg_rumor_strength",
    "season",
    "direction",
    "transfer_type",
    "is_loan",
    "age",
    "position",
    "market_value_eur",
    "transfer_fee_eur",
    "wage_eur_annual",
    "fee_to_market",
    "market_minus_fee_eur",
    "transfer_quality",
    "transfer_indicator",
    "rumor_indicator",
    "pre_stock_return_7d",
    "pre_stock_return_30d",
    "pre_stock_volatility_30d",
    "pre_market_return_30d",
    "stock_context_indicator",
    "car_m1_p1",
    "car_0_p1",
    "car_0_p3",
    "car_0_p7",
    "target_car",
    "target_label",
    "label",
]


def parse_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def transfer_from_row(row: dict[str, str]) -> Transfer:
    return Transfer(
        date=date.fromisoformat(row["date"]),
        club=row.get("club", ""),
        player=row.get("player", ""),
        direction=row.get("direction", "in"),
        from_club="",
        to_club="",
        age=None if row.get("age", "") == "" else float(row["age"]),
        position=row.get("position", ""),
        market_value_eur=None if row.get("market_value_eur", "") == "" else float(row["market_value_eur"]),
        transfer_fee_eur=None if row.get("transfer_fee_eur", "") == "" else float(row["transfer_fee_eur"]),
        wage_eur_annual=None if row.get("wage_eur_annual", "") == "" else float(row["wage_eur_annual"]),
        source=row.get("source", ""),
        source_url=row.get("url", ""),
        season=row.get("season", ""),
        transfer_type=row.get("transfer_type", "permanent"),
        is_loan=row.get("is_loan", "0") in {"1", "true", "True"},
    )


def fee_to_market(row: dict[str, str]) -> float:
    fee = parse_float(row.get("transfer_fee_eur"))
    market = parse_float(row.get("market_value_eur"))
    if market <= 0 or fee <= 0:
        return 0.0
    return round(fee / market, 4)


def market_minus_fee(row: dict[str, str]) -> float:
    market = parse_float(row.get("market_value_eur"))
    fee = parse_float(row.get("transfer_fee_eur"))
    if market <= 0 and fee <= 0:
        return 0.0
    return round(market - fee, 2)


def transfer_indicator(row: dict[str, str]) -> float:
    base = transfer_quality_score(transfer_from_row(row))
    fee_ratio = fee_to_market(row)
    age = parse_float(row.get("age"), 27.0)
    direction = row.get("direction", "in")

    if fee_ratio <= 0:
        fee_component = 0.5
    elif direction == "in":
        fee_component = clamp(1.15 - fee_ratio)
    else:
        fee_component = clamp(0.5 + (fee_ratio - 1.0) / 2.0)

    if direction == "in":
        age_component = clamp(1.0 - abs(age - 24.0) / 12.0)
    else:
        age_component = clamp(0.55 + max(age - 26.0, 0.0) / 14.0)

    loan_penalty = 0.08 if row.get("is_loan", "0") in {"1", "true", "True"} else 0.0
    return round(clamp(0.50 * base + 0.30 * fee_component + 0.20 * age_component - loan_penalty), 4)


def rumor_indicator(row: dict[str, str]) -> float:
    credibility = parse_float(row.get("max_credibility") or row.get("credibility_score"), 0.5)
    strength = parse_float(row.get("max_rumor_strength") or row.get("rumor_strength"), 0.5)
    count = parse_float(row.get("rumor_count"), 1.0)
    count_component = clamp(count / 4.0)
    title = row.get("title", "").lower()
    language_component = 0.0
    for phrase, boost in [
        ("here we go", 0.15),
        ("agreement", 0.10),
        ("medical", 0.10),
        ("confirm", 0.08),
        ("complete", 0.08),
        ("talks", 0.04),
        ("interested", 0.02),
    ]:
        if phrase in title:
            language_component += boost
    return round(clamp(0.45 * credibility + 0.35 * strength + 0.20 * count_component + language_component), 4)


def club_lookup(clubs: dict[str, Club]) -> dict[str, Club]:
    lookup: dict[str, Club] = {}
    for club in clubs.values():
        lookup[club.name.lower()] = club
        for alias in club.aliases:
            lookup[alias.lower()] = club
    return lookup


def load_bars(path: Path) -> list[PriceBar]:
    if not path.exists():
        return []
    return load_price_bars(path)


def closes_before(bars: list[PriceBar], event_date: date, lookback: int) -> list[PriceBar]:
    prior = [bar for bar in bars if bar.date < event_date]
    return prior[-lookback:]


def simple_return(bars: list[PriceBar]) -> float:
    if len(bars) < 2 or bars[0].close <= 0:
        return 0.0
    return bars[-1].close / bars[0].close - 1.0


def volatility(bars: list[PriceBar]) -> float:
    if len(bars) < 3:
        return 0.0
    returns = [
        current.close / previous.close - 1.0
        for previous, current in zip(bars, bars[1:])
        if previous.close > 0
    ]
    if len(returns) < 2:
        return 0.0
    return pstdev(returns)


def stock_context_indicator(pre_return_7d: float, pre_return_30d: float, pre_volatility_30d: float, pre_market_return_30d: float) -> float:
    momentum = clamp(0.5 + 3.0 * (0.65 * pre_return_7d + 0.35 * pre_return_30d))
    market = clamp(0.5 + 2.0 * pre_market_return_30d)
    stability = clamp(1.0 - 12.0 * pre_volatility_30d)
    return round(clamp(0.45 * momentum + 0.25 * market + 0.30 * stability), 4)


def enrich_rumor_events(input_path: Path, output_path: Path, clubs: dict[str, Club]) -> list[dict[str, object]]:
    rows = read_csv(input_path)
    clubs_by_name = club_lookup(clubs)
    output: list[dict[str, object]] = []
    for row in rows:
        event_date = date.fromisoformat(row["date"])
        club = clubs_by_name.get(row.get("club", "").lower())
        stock_bars = load_bars(Path("data/raw/stocks") / f"{club.key}.csv") if club else []
        market_bars = load_bars(Path("data/raw/stocks") / f"{club.key}_market.csv") if club else []
        stock_7 = closes_before(stock_bars, event_date, 7)
        stock_30 = closes_before(stock_bars, event_date, 30)
        market_30 = closes_before(market_bars, event_date, 30)
        pre_7 = simple_return(stock_7)
        pre_30 = simple_return(stock_30)
        vol_30 = volatility(stock_30)
        market_pre_30 = simple_return(market_30)
        enriched = {
            **row,
            "source_diversity": row.get("source_diversity", "1"),
            "wage_eur_annual": row.get("wage_eur_annual", ""),
            "fee_to_market": fee_to_market(row),
            "market_minus_fee_eur": market_minus_fee(row),
            "transfer_indicator": transfer_indicator(row),
            "rumor_indicator": rumor_indicator(row),
            "pre_stock_return_7d": round(pre_7, 6),
            "pre_stock_return_30d": round(pre_30, 6),
            "pre_stock_volatility_30d": round(vol_30, 6),
            "pre_market_return_30d": round(market_pre_30, 6),
            "stock_context_indicator": stock_context_indicator(pre_7, pre_30, vol_30, market_pre_30),
        }
        output.append(enriched)
    write_csv(output_path, output, ENRICHED_RUMOR_FIELDS)
    return output


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def group_enriched_rumor_events(input_path: Path, output_path: Path) -> list[dict[str, object]]:
    rows = read_csv(input_path)
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault((row["date"], row["club"], row["player"]), []).append(row)

    output: list[dict[str, object]] = []
    for (_, _, _), items in sorted(groups.items()):
        first = items[0]
        sources = sorted({item.get("source", "") for item in items if item.get("source", "")})
        urls = sorted({item.get("url", "") for item in items if item.get("url", "")})
        titles = [item.get("title", "") for item in items if item.get("title", "")]
        credibility = [parse_float(item.get("credibility_score"), 0.0) for item in items]
        strength = [parse_float(item.get("rumor_strength"), 0.0) for item in items]
        row = {
            **first,
            "source": " | ".join(sources[:5]),
            "title": " || ".join(titles[:5]),
            "url": " | ".join(urls[:5]),
            "rumor_count": len(items),
            "source_diversity": len(sources),
            "max_credibility": round(max(credibility), 4) if credibility else "",
            "avg_credibility": round(average(credibility), 4) if credibility else "",
            "max_rumor_strength": round(max(strength), 4) if strength else "",
            "avg_rumor_strength": round(average(strength), 4) if strength else "",
        }
        row["rumor_indicator"] = rumor_indicator({key: str(value) for key, value in row.items()})
        output.append(row)

    write_csv(output_path, output, ENRICHED_RUMOR_FIELDS)
    return output
