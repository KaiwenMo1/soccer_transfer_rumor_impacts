from __future__ import annotations

from dataclasses import replace
from typing import Any

from .article_store import compact_whitespace
from .config import Club
from .features import transfer_quality_score
from .indicators import fee_to_market, market_minus_fee, transfer_indicator
from .transfers import Transfer


TARGET_FIELDS = [
    "subject_club",
    "subject_direction",
    "buyer_club",
    "seller_club",
    "target_club",
    "target_role",
    "target_direction",
    "target_entity_type",
    "target_ticker",
    "target_market_symbol",
    "prediction_scope",
    "public_target_count",
    "has_public_buyer",
    "has_public_seller",
]


def normalize_name(value: str) -> str:
    return compact_whitespace(value).lower()


def club_lookup(clubs: dict[str, Club]) -> dict[str, Club]:
    lookup: dict[str, Club] = {}
    for club in clubs.values():
        lookup[normalize_name(club.name)] = club
        lookup[normalize_name(club.key)] = club
        for alias in club.aliases:
            lookup[normalize_name(alias)] = club
    return lookup


def public_club(name: str, clubs: dict[str, Club]) -> Club | None:
    return club_lookup(clubs).get(normalize_name(name))


def target_role_from_direction(direction: str) -> str:
    if direction == "in":
        return "buyer"
    if direction == "out":
        return "seller"
    return ""


def target_direction_from_role(role: str) -> str:
    if role == "buyer":
        return "in"
    if role == "seller":
        return "out"
    return "unclear"


def base_transfer_row(transfer: Transfer, target_club: str, target_direction: str) -> dict[str, str]:
    return {
        "date": transfer.date.isoformat(),
        "club": target_club,
        "player": transfer.player,
        "direction": target_direction,
        "age": "" if transfer.age is None else str(transfer.age),
        "position": transfer.position,
        "market_value_eur": "" if transfer.market_value_eur is None else str(transfer.market_value_eur),
        "transfer_fee_eur": "" if transfer.transfer_fee_eur is None else str(transfer.transfer_fee_eur),
        "wage_eur_annual": "" if transfer.wage_eur_annual is None else str(transfer.wage_eur_annual),
        "transfer_type": transfer.transfer_type,
        "is_loan": "1" if transfer.is_loan else "0",
        "season": transfer.season,
    }


def target_features(transfer: Transfer, target_club: str, target_direction: str) -> dict[str, object]:
    target_transfer = replace(transfer, club=target_club, direction=target_direction)
    target_row = base_transfer_row(target_transfer, target_club, target_direction)
    return {
        "club": target_club,
        "direction": target_direction,
        "fee_to_market": fee_to_market(target_row),
        "market_minus_fee_eur": market_minus_fee(target_row),
        "transfer_quality": transfer_quality_score(target_transfer),
        "transfer_indicator": transfer_indicator(target_row),
    }


def direct_target_rows(base_row: dict[str, object], transfer: Transfer, clubs: dict[str, Club]) -> list[dict[str, object]]:
    buyer = public_club(transfer.to_club, clubs)
    seller = public_club(transfer.from_club, clubs)
    public_targets: list[tuple[Club, str]] = []
    if buyer is not None:
        public_targets.append((buyer, "buyer"))
    if seller is not None and (buyer is None or seller.key != buyer.key):
        public_targets.append((seller, "seller"))

    if not public_targets:
        fallback = public_club(transfer.club, clubs)
        fallback_role = target_role_from_direction(transfer.direction)
        if fallback is not None and fallback_role:
            public_targets.append((fallback, fallback_role))

    rows: list[dict[str, object]] = []
    public_target_count = len(public_targets)
    buyer_name = compact_whitespace(transfer.to_club)
    seller_name = compact_whitespace(transfer.from_club)
    has_public_buyer = 1 if buyer is not None else 0
    has_public_seller = 1 if seller is not None else 0

    if not public_targets:
        rows.append(
            {
                **base_row,
                "subject_club": base_row.get("club", ""),
                "subject_direction": base_row.get("direction", ""),
                "buyer_club": buyer_name,
                "seller_club": seller_name,
                "target_club": "",
                "target_role": "",
                "target_direction": "",
                "target_entity_type": "",
                "target_ticker": "",
                "target_market_symbol": "",
                "prediction_scope": "none",
                "public_target_count": 0,
                "has_public_buyer": has_public_buyer,
                "has_public_seller": has_public_seller,
            }
        )
        return rows

    for club, role in public_targets:
        target_direction = target_direction_from_role(role)
        target_row = {
            **base_row,
            **target_features(transfer, club.name, target_direction),
            "subject_club": base_row.get("club", ""),
            "subject_direction": base_row.get("direction", ""),
            "buyer_club": buyer_name,
            "seller_club": seller_name,
            "target_club": club.name,
            "target_role": role,
            "target_direction": target_direction,
            "target_entity_type": club.entity_type,
            "target_ticker": club.yahoo_symbol or club.stooq_symbol,
            "target_market_symbol": club.yahoo_market_symbol or club.market_index_symbol,
            "prediction_scope": "direct",
            "public_target_count": public_target_count,
            "has_public_buyer": has_public_buyer,
            "has_public_seller": has_public_seller,
        }
        rows.append(target_row)
    return rows


def target_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prediction_scope_counts: dict[str, int] = {}
    target_role_counts: dict[str, int] = {}
    target_clubs: dict[str, int] = {}
    for row in rows:
        scope = str(row.get("prediction_scope", "") or "unknown")
        prediction_scope_counts[scope] = prediction_scope_counts.get(scope, 0) + 1
        role = str(row.get("target_role", "") or "none")
        target_role_counts[role] = target_role_counts.get(role, 0) + 1
        target_club = str(row.get("target_club", "") or "")
        if target_club:
            target_clubs[target_club] = target_clubs.get(target_club, 0) + 1
    return {
        "rows": len(rows),
        "prediction_scope_counts": dict(sorted(prediction_scope_counts.items())),
        "target_role_counts": dict(sorted(target_role_counts.items())),
        "distinct_target_clubs": len(target_clubs),
    }
