from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .io import read_csv, write_csv


TRANSFER_FIELDS = [
    "date",
    "club",
    "player",
    "direction",
    "from_club",
    "to_club",
    "age",
    "position",
    "market_value_eur",
    "transfer_fee_eur",
    "wage_eur_annual",
    "source",
    "source_url",
]

OPTIONAL_TRANSFER_FIELDS = [
    "season",
    "transfer_type",
    "is_loan",
]

CLEAN_TRANSFER_FIELDS = [
    "date",
    "original_transfer_date",
    "event_date_source",
    "event_date_confidence",
    "season",
    "club",
    "player",
    "direction",
    "from_club",
    "to_club",
    "age",
    "position",
    "market_value_eur",
    "transfer_fee_eur",
    "wage_eur_annual",
    "transfer_type",
    "is_loan",
    "source",
    "source_url",
]


@dataclass(frozen=True)
class Transfer:
    date: date
    club: str
    player: str
    direction: str
    from_club: str
    to_club: str
    age: float | None
    position: str
    market_value_eur: float | None
    transfer_fee_eur: float | None
    wage_eur_annual: float | None
    source: str
    source_url: str
    season: str = ""
    transfer_type: str = "permanent"
    is_loan: bool = False
    original_transfer_date: str = ""
    event_date_source: str = ""
    event_date_confidence: float | None = None


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    if not value or value.upper() in {"NA", "N/A", "NULL"}:
        return None
    return float(value)


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "loan"}


def infer_season(day: date) -> str:
    if day.month >= 7:
        return f"{day.year}-{str(day.year + 1)[-2:]}"
    return f"{day.year - 1}-{str(day.year)[-2:]}"


def infer_transfer_type(row: dict[str, str]) -> str:
    explicit = row.get("transfer_type", "").strip().lower()
    if explicit:
        return explicit
    haystack = " ".join(
        row.get(field, "")
        for field in ["source", "source_url", "from_club", "to_club", "position"]
    ).lower()
    return "loan" if "loan" in haystack else "permanent"


def is_loan_transfer(row: dict[str, str], transfer_type: str) -> bool:
    return parse_bool(row.get("is_loan")) or "loan" in transfer_type.lower()


def load_transfers(path: Path) -> list[Transfer]:
    rows = read_csv(path)
    missing = sorted(set(TRANSFER_FIELDS) - set(rows[0].keys())) if rows else []
    if missing:
        raise ValueError(f"{path} is missing transfer fields: {', '.join(missing)}")
    transfers: list[Transfer] = []
    for row in rows:
        transfer_date = date.fromisoformat(row["date"].strip())
        direction = row["direction"].strip().lower()
        if direction not in {"in", "out"}:
            raise ValueError(f"Invalid direction {direction!r} for {row.get('player')}")
        transfer_type = infer_transfer_type(row)
        transfers.append(
            Transfer(
                date=transfer_date,
                club=row["club"].strip(),
                player=row["player"].strip(),
                direction=direction,
                from_club=row["from_club"].strip(),
                to_club=row["to_club"].strip(),
                age=parse_float(row.get("age")),
                position=row.get("position", "").strip(),
                market_value_eur=parse_float(row.get("market_value_eur")),
                transfer_fee_eur=parse_float(row.get("transfer_fee_eur")),
                wage_eur_annual=parse_float(row.get("wage_eur_annual")),
                source=row.get("source", "").strip(),
                source_url=row.get("source_url", "").strip(),
                season=row.get("season", "").strip() or infer_season(transfer_date),
                transfer_type=transfer_type,
                is_loan=is_loan_transfer(row, transfer_type),
                original_transfer_date=row.get("original_transfer_date", "").strip(),
                event_date_source=row.get("event_date_source", "").strip(),
                event_date_confidence=parse_float(row.get("event_date_confidence")),
            )
        )
    return transfers


def transfer_to_clean_row(transfer: Transfer) -> dict[str, object]:
    return {
        "date": transfer.date.isoformat(),
        "original_transfer_date": transfer.original_transfer_date or transfer.date.isoformat(),
        "event_date_source": transfer.event_date_source or "transfer_source",
        "event_date_confidence": "" if transfer.event_date_confidence is None else transfer.event_date_confidence,
        "season": transfer.season or infer_season(transfer.date),
        "club": transfer.club,
        "player": transfer.player,
        "direction": transfer.direction,
        "from_club": transfer.from_club,
        "to_club": transfer.to_club,
        "age": "" if transfer.age is None else transfer.age,
        "position": transfer.position,
        "market_value_eur": "" if transfer.market_value_eur is None else transfer.market_value_eur,
        "transfer_fee_eur": "" if transfer.transfer_fee_eur is None else transfer.transfer_fee_eur,
        "wage_eur_annual": "" if transfer.wage_eur_annual is None else transfer.wage_eur_annual,
        "transfer_type": transfer.transfer_type,
        "is_loan": int(transfer.is_loan),
        "source": transfer.source,
        "source_url": transfer.source_url,
    }


def load_transfers_from_path(path: Path) -> list[Transfer]:
    if path.is_file():
        return load_transfers(path)
    files = sorted(item for item in path.glob("*.csv") if item.is_file())
    transfers: list[Transfer] = []
    for file_path in files:
        transfers.extend(load_transfers(file_path))
    return sorted(transfers, key=lambda item: (item.date, item.club, item.player))


def filter_loans(transfers: list[Transfer], loan_policy: str) -> list[Transfer]:
    if loan_policy == "include":
        return transfers
    if loan_policy == "exclude":
        return [item for item in transfers if not item.is_loan]
    if loan_policy == "only":
        return [item for item in transfers if item.is_loan]
    raise ValueError(f"Unsupported loan policy: {loan_policy}")


def clean_transfer_files(input_path: Path, output_path: Path, loan_policy: str = "include") -> list[Transfer]:
    transfers = filter_loans(load_transfers_from_path(input_path), loan_policy)
    write_csv(output_path, [transfer_to_clean_row(item) for item in transfers], CLEAN_TRANSFER_FIELDS)
    return transfers
