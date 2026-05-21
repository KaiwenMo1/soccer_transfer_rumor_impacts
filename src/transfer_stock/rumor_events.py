from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
import re

from .config import Club
from .event_study import cumulative_abnormal_return, load_bars_if_exists
from .features import transfer_quality_score
from .io import read_csv, write_csv
from .model import impact_label
from .transfers import Transfer, infer_season, load_transfers


RUMOR_EVENT_FIELDS = [
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
    "transfer_quality",
    "car_m1_p1",
    "car_0_p1",
    "car_0_p3",
    "car_0_p7",
    "target_car",
    "target_label",
    "label",
]


def parse_gdelt_datetime(value: str) -> date | None:
    if not value:
        return None
    if value.endswith("Z") and "-" in value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    return None


def transfer_index(transfers: list[Transfer]) -> dict[tuple[str, str, str], Transfer]:
    index: dict[tuple[str, str, str], Transfer] = {}
    for transfer in transfers:
        key = (transfer.original_transfer_date or transfer.date.isoformat(), transfer.club.lower(), transfer.player.lower())
        index[key] = transfer
        index[(transfer.date.isoformat(), transfer.club.lower(), transfer.player.lower())] = transfer
    return index


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


TRANSFER_KEYWORDS = {
    "transfer",
    "signing",
    "sign",
    "signed",
    "agreement",
    "agree",
    "agreed",
    "talks",
    "bid",
    "bids",
    "deal",
    "clause",
    "medical",
    "join",
    "joins",
    "move",
    "moves",
    "sell",
    "sale",
    "buy",
    "loan",
    "future",
    "contract",
    "exit",
}

NON_TRANSFER_PATTERNS = (
    "as it happened",
    "match report",
    "minute by minute",
    "live updates",
    "live blog",
    "preview",
    "player ratings",
)


def is_transfer_story(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if any(pattern in normalized for pattern in NON_TRANSFER_PATTERNS):
        return False
    return any(keyword in normalized.split() for keyword in TRANSFER_KEYWORDS)


def text_mentions_player(text: str, player: str) -> bool:
    haystack = f" {normalize_text(text)} "
    name = normalize_text(player)
    if not name:
        return False
    if f" {name} " in haystack:
        return True
    parts = [part for part in name.split() if len(part) >= 4]
    if len(parts) >= 2:
        surname = parts[-1]
        return f" {surname} " in haystack
    return False


def build_club_transfer_lookup(transfers: list[Transfer]) -> dict[str, list[Transfer]]:
    lookup: dict[str, list[Transfer]] = {}
    for transfer in transfers:
        lookup.setdefault(transfer.club.lower(), []).append(transfer)
    return lookup


def resolve_transfer_for_article(
    article: dict[str, str],
    published_date: date,
    indexed_transfers: dict[tuple[str, str, str], Transfer],
    club_transfers: dict[str, list[Transfer]],
) -> Transfer | None:
    text = " ".join([article.get("title", ""), article.get("snippet", "")])
    if not is_transfer_story(text):
        return None
    explicit = indexed_transfers.get(
        (
            article.get("event_date", ""),
            article.get("club", "").lower(),
            article.get("player", "").lower(),
        )
    )
    if explicit is not None and text_mentions_player(text, explicit.player):
        return explicit
    club_name = article.get("club", "").lower()
    if not club_name:
        return None
    candidates = []
    article_season = infer_season(published_date)
    for transfer in club_transfers.get(club_name, []):
        if transfer.season and transfer.season != article_season:
            continue
        if not text_mentions_player(text, transfer.player):
            continue
        distance = abs((transfer.date - published_date).days)
        candidates.append((distance, transfer))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def club_lookup(clubs: dict[str, Club]) -> dict[str, Club]:
    lookup: dict[str, Club] = {}
    for club in clubs.values():
        lookup[club.name.lower()] = club
        for alias in club.aliases:
            lookup[alias.lower()] = club
    return lookup


def build_rumor_events(
    scored_news_path: Path,
    transfers_path: Path,
    output_path: Path,
    clubs: dict[str, Club],
) -> list[dict[str, object]]:
    news_rows = read_csv(scored_news_path)
    loaded_transfers = load_transfers(transfers_path)
    transfers = transfer_index(loaded_transfers)
    club_transfers = build_club_transfer_lookup(loaded_transfers)
    clubs_by_name = club_lookup(clubs)
    rows: list[dict[str, object]] = []
    for article in news_rows:
        published_date = parse_gdelt_datetime(article.get("published_at", ""))
        if published_date is None:
            continue
        transfer = resolve_transfer_for_article(article, published_date, transfers, club_transfers)
        if transfer is None:
            continue
        club = clubs_by_name.get(transfer.club.lower())
        stock_bars = load_bars_if_exists(Path("data/raw/stocks") / f"{club.key}.csv") if club else []
        market_bars = load_bars_if_exists(Path("data/raw/stocks") / f"{club.key}_market.csv") if club else []
        if stock_bars and market_bars:
            car_m1_p1 = cumulative_abnormal_return(stock_bars, market_bars, published_date, window_start=-1, window_end=1)
            car_0_p1 = cumulative_abnormal_return(stock_bars, market_bars, published_date, window_start=0, window_end=1)
            car_0_p3 = cumulative_abnormal_return(stock_bars, market_bars, published_date, window_start=0, window_end=3)
            car_0_p7 = cumulative_abnormal_return(stock_bars, market_bars, published_date, window_start=0, window_end=7)
        else:
            car_m1_p1 = None
            car_0_p1 = None
            car_0_p3 = None
            car_0_p7 = None
        target_car = car_0_p3 if car_0_p3 is not None else car_m1_p1
        target_label = "" if target_car is None else impact_label(float(target_car))
        quality = transfer_quality_score(transfer)
        rows.append(
            {
                "published_date": published_date.isoformat(),
                "date": published_date.isoformat(),
                "club": transfer.club,
                "player": transfer.player,
                "source": article.get("source", ""),
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "credibility_score": article.get("credibility_score", ""),
                "rumor_strength": article.get("rumor_strength", ""),
                "rumor_count": 1,
                "max_credibility": article.get("credibility_score", ""),
                "avg_credibility": article.get("credibility_score", ""),
                "max_rumor_strength": article.get("rumor_strength", ""),
                "avg_rumor_strength": article.get("rumor_strength", ""),
                "season": transfer.season,
                "direction": transfer.direction,
                "transfer_type": transfer.transfer_type,
                "is_loan": int(transfer.is_loan),
                "age": "" if transfer.age is None else transfer.age,
                "position": transfer.position,
                "market_value_eur": "" if transfer.market_value_eur is None else transfer.market_value_eur,
                "transfer_fee_eur": "" if transfer.transfer_fee_eur is None else transfer.transfer_fee_eur,
                "transfer_quality": quality,
                "car_m1_p1": "" if car_m1_p1 is None else car_m1_p1,
                "car_0_p1": "" if car_0_p1 is None else car_0_p1,
                "car_0_p3": "" if car_0_p3 is None else car_0_p3,
                "car_0_p7": "" if car_0_p7 is None else car_0_p7,
                "target_car": "" if target_car is None else target_car,
                "target_label": target_label,
                "label": target_label,
            }
        )
    write_csv(output_path, rows, RUMOR_EVENT_FIELDS)
    return rows
