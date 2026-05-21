from __future__ import annotations

from datetime import date
from pathlib import Path

from .config import Club
from .http import get_text
from .io import read_csv, write_csv
from .transfers import CLEAN_TRANSFER_FIELDS, infer_season


BASE_URL = "https://raw.githubusercontent.com/ewenme/transfers/master/data/{league}.csv"
DEFAULT_LEAGUES = ["premier-league", "1-bundesliga", "serie-a"]


def season_label_to_years(label: str) -> tuple[int, int] | None:
    label = label.strip()
    if "/" in label:
        left, right = label.split("/", 1)
        if left.isdigit() and right.isdigit():
            return int(left), int(right)
    if "-" in label:
        left, right = label.split("-", 1)
        if left.isdigit() and right.isdigit():
            end = int(right) if len(right) == 4 else int(left[:2] + right)
            return int(left), end
    return None


def canonical_season(label: str, fallback_year: str = "") -> str:
    years = season_label_to_years(label)
    if years:
        return f"{years[0]}-{str(years[1])[-2:]}"
    if fallback_year.isdigit():
        return infer_season(date(int(fallback_year), 7, 1))
    return label


def season_in_range(season: str, start_season: str, end_season: str) -> bool:
    years = season_label_to_years(season)
    start = season_label_to_years(start_season)
    end = season_label_to_years(end_season)
    if not years or not start or not end:
        return True
    return start[0] <= years[0] <= end[0]


def movement_to_direction(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"in", "out"}:
        return lowered
    raise ValueError(f"Unsupported transfer movement: {value!r}")


def proxy_transfer_date(year: str, period: str) -> date:
    transfer_year = int(year)
    if period.strip().lower() == "winter":
        return date(transfer_year + 1, 1, 1)
    return date(transfer_year, 7, 1)


def fee_cleaned_to_eur(value: str) -> float | None:
    value = value.strip()
    if not value or value.upper() == "NA":
        return None
    return float(value) * 1_000_000


def is_loan_fee(fee: str) -> bool:
    return "loan" in fee.lower()


def club_names(clubs: dict[str, Club]) -> set[str]:
    names: set[str] = set()
    for club in clubs.values():
        names.add(club.name.lower())
        names.update(alias.lower() for alias in club.aliases)
    return names


def download_league(league: str, output_dir: Path, timeout: int = 60, retries: int = 3) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{league}.csv"
    text = get_text(BASE_URL.format(league=league), timeout=timeout, retries=retries)
    output_path.write_text(text, encoding="utf-8")
    return output_path


def convert_rows(
    files: list[Path],
    clubs: dict[str, Club],
    start_season: str,
    end_season: str,
) -> list[dict[str, object]]:
    allowed_clubs = club_names(clubs)
    rows: list[dict[str, object]] = []
    for path in files:
        for row in read_csv(path):
            club_name = row.get("club_name", "").strip()
            raw_season = row.get("season", "").strip()
            season = canonical_season(raw_season, row.get("year", ""))
            if club_name.lower() not in allowed_clubs:
                continue
            if not season_in_range(season, start_season, end_season):
                continue
            fee = row.get("fee", "")
            event_date = proxy_transfer_date(row.get("year", "1970"), row.get("transfer_period", "Summer"))
            direction = movement_to_direction(row.get("transfer_movement", ""))
            if direction == "in":
                from_club = row.get("club_involved_name", "").strip()
                to_club = club_name
            else:
                from_club = club_name
                to_club = row.get("club_involved_name", "").strip()
            is_loan = is_loan_fee(fee)
            rows.append(
                {
                    "date": event_date.isoformat(),
                    "season": season,
                    "club": club_name,
                    "player": row.get("player_name", "").strip(),
                    "direction": direction,
                    "from_club": from_club,
                    "to_club": to_club,
                    "age": row.get("age", "").strip(),
                    "position": row.get("position", "").strip(),
                    "market_value_eur": "",
                    "transfer_fee_eur": "" if fee_cleaned_to_eur(row.get("fee_cleaned", "")) is None else fee_cleaned_to_eur(row.get("fee_cleaned", "")),
                    "wage_eur_annual": "",
                    "transfer_type": "loan" if is_loan else "permanent",
                    "is_loan": int(is_loan),
                    "source": "ewenme/transfers",
                    "source_url": f"https://github.com/ewenme/transfers/blob/master/data/{path.name}",
                }
            )
    return sorted(rows, key=lambda item: (str(item["date"]), str(item["club"]), str(item["player"])))


def import_ewenme_transfers(
    clubs: dict[str, Club],
    raw_dir: Path,
    output_path: Path,
    leagues: list[str] | None = None,
    start_season: str = "2021-22",
    end_season: str = "2025-26",
    download: bool = True,
    timeout: int = 60,
    retries: int = 3,
) -> list[dict[str, object]]:
    selected_leagues = leagues or DEFAULT_LEAGUES
    files: list[Path] = []
    for league in selected_leagues:
        path = raw_dir / f"{league}.csv"
        if download or not path.exists():
            path = download_league(league, raw_dir, timeout=timeout, retries=retries)
        files.append(path)
    rows = convert_rows(files, clubs, start_season=start_season, end_season=end_season)
    write_csv(output_path, rows, CLEAN_TRANSFER_FIELDS)
    return rows
