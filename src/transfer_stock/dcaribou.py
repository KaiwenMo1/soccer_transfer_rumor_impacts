from __future__ import annotations

import csv
import gzip
import io
from datetime import date
from pathlib import Path

from .config import Club
from .http import get_bytes
from .io import write_csv
from .transfers import CLEAN_TRANSFER_FIELDS, infer_season


BASE_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/{name}.csv.gz"


def canonical_season(value: str) -> str:
    value = value.strip()
    if "/" in value:
        left, right = value.split("/", 1)
        if len(left) == 2:
            start = int("20" + left)
        else:
            start = int(left)
        return f"{start}-{right[-2:]}"
    return value


def season_start(season: str) -> int:
    left = season.split("-", 1)[0]
    return int(left) if left.isdigit() else 0


def season_in_range(season: str, start_season: str, end_season: str) -> bool:
    return season_start(start_season) <= season_start(season) <= season_start(end_season)


def read_gzip_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def download_table(name: str, raw_dir: Path, timeout: int = 60, retries: int = 3) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{name}.csv.gz"
    path.write_bytes(get_bytes(BASE_URL.format(name=name), timeout=timeout, retries=retries))
    return path


def load_table(name: str, raw_dir: Path, download: bool, timeout: int, retries: int) -> list[dict[str, str]]:
    path = raw_dir / f"{name}.csv.gz"
    if download or not path.exists():
        path = download_table(name, raw_dir, timeout=timeout, retries=retries)
    return read_gzip_csv(path)


def club_id_map(clubs_rows: list[dict[str, str]], configured_clubs: dict[str, Club]) -> dict[str, str]:
    names: dict[str, str] = {}
    for club in configured_clubs.values():
        names[club.name.lower()] = club.name
        for alias in club.aliases:
            names[alias.lower()] = club.name

    ids: dict[str, str] = {}
    for row in clubs_rows:
        candidates = {
            row.get("name", "").lower(),
            row.get("club_code", "").replace("-", " ").lower(),
        }
        for candidate in candidates:
            for alias, canonical in names.items():
                if alias in candidate or candidate in alias:
                    ids[row["club_id"]] = canonical
    return ids


def player_profile_map(players_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["player_id"]: row for row in players_rows}


def age_on_date(date_of_birth: str, transfer_date: date) -> int | None:
    if not date_of_birth:
        return None
    born = date.fromisoformat(date_of_birth[:10])
    return transfer_date.year - born.year - ((transfer_date.month, transfer_date.day) < (born.month, born.day))


def parse_money(value: str) -> float | None:
    if not value:
        return None
    return float(value)


def transfer_kind_tags(rows: list[dict[str, str]]) -> list[str]:
    tags = ["permanent"] * len(rows)
    history: dict[str, list[int]] = {}
    ordered = sorted(
        range(len(rows)),
        key=lambda index: (
            rows[index].get("player_id", ""),
            rows[index].get("transfer_date", ""),
            rows[index].get("from_club_id", ""),
            rows[index].get("to_club_id", ""),
        ),
    )
    for index in ordered:
        row = rows[index]
        player_id = row.get("player_id", "")
        transfer_date = date.fromisoformat(row["transfer_date"])
        fee = parse_money(row.get("transfer_fee", ""))
        prior_indexes = history.setdefault(player_id, [])
        if fee in {None, 0.0}:
            for prior_index in reversed(prior_indexes):
                prior = rows[prior_index]
                prior_date = date.fromisoformat(prior["transfer_date"])
                prior_fee = parse_money(prior.get("transfer_fee", ""))
                if prior.get("from_club_id", "") != row.get("to_club_id", ""):
                    continue
                if prior.get("to_club_id", "") != row.get("from_club_id", ""):
                    continue
                if prior_fee not in {None, 0.0}:
                    continue
                day_gap = (transfer_date - prior_date).days
                if 0 <= day_gap <= 400:
                    tags[index] = "loan_return"
                    if tags[prior_index] == "permanent":
                        tags[prior_index] = "loan"
                    break
        prior_indexes.append(index)
    return tags


def transfer_row(
    row: dict[str, str],
    canonical_club: str,
    direction: str,
    player: dict[str, str] | None,
    transfer_type: str,
) -> dict[str, object]:
    transfer_date = date.fromisoformat(row["transfer_date"])
    is_in = direction == "in"
    from_club = row.get("from_club_name", "")
    to_club = row.get("to_club_name", "")
    fee = parse_money(row.get("transfer_fee", ""))
    market_value = parse_money(row.get("market_value_in_eur", ""))
    age = age_on_date(player.get("date_of_birth", "") if player else "", transfer_date)
    position = player.get("sub_position") or player.get("position") if player else ""
    return {
        "date": transfer_date.isoformat(),
        "original_transfer_date": transfer_date.isoformat(),
        "event_date_source": "exact_transfer_date",
        "event_date_confidence": 0.85,
        "season": canonical_season(row.get("transfer_season", "")) or infer_season(transfer_date),
        "club": canonical_club,
        "player": row.get("player_name", ""),
        "direction": direction,
        "from_club": from_club if is_in else canonical_club,
        "to_club": canonical_club if is_in else to_club,
        "age": "" if age is None else age,
        "position": position or "",
        "market_value_eur": "" if market_value is None else market_value,
        "transfer_fee_eur": "" if fee is None else fee,
        "wage_eur_annual": "",
        "transfer_type": transfer_type,
        "is_loan": int("loan" in transfer_type),
        "source": "dcaribou/transfermarkt-datasets",
        "source_url": BASE_URL.format(name="transfers"),
    }


def import_dcaribou_transfers(
    configured_clubs: dict[str, Club],
    raw_dir: Path,
    output_path: Path,
    start_season: str = "2021-22",
    end_season: str = "2025-26",
    download: bool = True,
    timeout: int = 60,
    retries: int = 3,
) -> list[dict[str, object]]:
    transfers = load_table("transfers", raw_dir, download=download, timeout=timeout, retries=retries)
    players = player_profile_map(load_table("players", raw_dir, download=download, timeout=timeout, retries=retries))
    club_ids = club_id_map(
        load_table("clubs", raw_dir, download=download, timeout=timeout, retries=retries),
        configured_clubs,
    )
    kind_tags = transfer_kind_tags(transfers)
    today = date.today()
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for row, transfer_type in zip(transfers, kind_tags, strict=True):
        season = canonical_season(row.get("transfer_season", ""))
        if not season_in_range(season, start_season, end_season):
            continue
        if date.fromisoformat(row["transfer_date"]) > today:
            continue
        for club_id_field, direction in [("to_club_id", "in"), ("from_club_id", "out")]:
            club_id = row.get(club_id_field, "")
            if club_id not in club_ids:
                continue
            key = (row["transfer_date"], club_ids[club_id], row.get("player_name", ""), direction)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                transfer_row(
                    row,
                    club_ids[club_id],
                    direction,
                    players.get(row.get("player_id", "")),
                    transfer_type,
                )
            )
    rows.sort(key=lambda item: (str(item["date"]), str(item["club"]), str(item["player"]), str(item["direction"])))
    write_csv(output_path, rows, CLEAN_TRANSFER_FIELDS)
    return rows
