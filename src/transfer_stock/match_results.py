from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any

from .config import Club
from .http import get_text, polite_pause
from .io import read_csv, write_csv


FOOTBALL_DATA_BASE_URL = "https://www.football-data.co.uk/mmz4281/{season_code}/{league_code}.csv"

FOOTBALL_DATA_LEAGUES_BY_CLUB = {
    "manchester_united": ["E0"],
    "borussia_dortmund": ["D1"],
    "juventus": ["I1"],
    "lazio": ["I1"],
    "ajax": ["N1"],
    "sporting_cp": ["P1"],
    "fc_porto": ["P1"],
    "celtic": ["SC0"],
    "benfica": ["P1"],
    "eagle_football_group": ["F1"],
}

FOOTBALL_DATA_TEAM_ALIASES = {
    "manchester_united": {"Man United", "Manchester United"},
    "borussia_dortmund": {"Dortmund", "Borussia Dortmund"},
    "juventus": {"Juventus"},
    "lazio": {"Lazio"},
    "ajax": {"Ajax"},
    "sporting_cp": {"Sporting", "Sporting CP", "Sporting Lisbon", "Sp Lisbon"},
    "fc_porto": {"Porto", "FC Porto"},
    "celtic": {"Celtic"},
    "benfica": {"Benfica"},
    "eagle_football_group": {"Lyon", "Olympique Lyon"},
}

MATCH_RESULT_FIELDS = [
    "date",
    "club",
    "opponent",
    "competition",
    "venue",
    "result",
    "goals_for",
    "goals_against",
    "score",
    "source",
    "source_url",
]


@dataclass(frozen=True)
class FetchedResults:
    rows: list[dict[str, Any]]
    warnings: list[str]


def football_data_season_code(season: str) -> str:
    left, _, right = season.partition("-")
    if not left.isdigit() or not right.isdigit():
        raise ValueError(f"Expected football season like 2025-26, got {season!r}")
    return f"{int(left) % 100:02d}{int(right) % 100:02d}"


def parse_football_data_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def football_data_result_for_club(row: dict[str, str], *, home: bool) -> tuple[str, str, str, str]:
    try:
        home_goals = int(float(row.get("FTHG") or 0))
        away_goals = int(float(row.get("FTAG") or 0))
    except ValueError:
        home_goals = 0
        away_goals = 0
    result = (row.get("FTR") or "").strip().upper()
    if home:
        goals_for, goals_against = home_goals, away_goals
        mapped = "W" if result == "H" else "L" if result == "A" else "D"
    else:
        goals_for, goals_against = away_goals, home_goals
        mapped = "W" if result == "A" else "L" if result == "H" else "D"
    return mapped, str(goals_for), str(goals_against), f"{goals_for}-{goals_against}"


def football_data_club_aliases(club: Club) -> set[str]:
    aliases = {club.name, club.key, *club.aliases}
    aliases.update(FOOTBALL_DATA_TEAM_ALIASES.get(club.key, set()))
    return {item.strip().lower() for item in aliases if item.strip()}


def fetch_football_data_league_rows(
    season: str,
    league_code: str,
    *,
    timeout: int = 45,
    retries: int = 2,
) -> list[dict[str, str]]:
    season_code = football_data_season_code(season)
    url = FOOTBALL_DATA_BASE_URL.format(season_code=season_code, league_code=league_code.lower())
    text = get_text(url, timeout=timeout, retries=retries)
    return list(csv.DictReader(StringIO(text)))


def normalize_football_data_rows(
    club: Club,
    rows: list[dict[str, str]],
    *,
    season: str,
    league_code: str,
) -> list[dict[str, Any]]:
    aliases = football_data_club_aliases(club)
    normalized: list[dict[str, Any]] = []
    source_url = FOOTBALL_DATA_BASE_URL.format(
        season_code=football_data_season_code(season),
        league_code=league_code.lower(),
    )
    for row in rows:
        home_team = (row.get("HomeTeam") or "").strip()
        away_team = (row.get("AwayTeam") or "").strip()
        home = home_team.lower() in aliases
        away = away_team.lower() in aliases
        if not home and not away:
            continue
        match_date = parse_football_data_date(row.get("Date", ""))
        if match_date is None:
            continue
        result, goals_for, goals_against, score = football_data_result_for_club(row, home=home)
        normalized.append(
            {
                "date": match_date.isoformat(),
                "club": club.name,
                "opponent": away_team if home else home_team,
                "competition": league_code,
                "venue": "H" if home else "A",
                "result": result,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "score": score,
                "source": "football-data.co.uk",
                "source_url": source_url,
            }
        )
    return normalized


def fetch_club_match_results(
    club: Club,
    *,
    seasons: list[str],
    timeout: int = 45,
    retries: int = 2,
    pause: float = 0.1,
    league_cache: dict[tuple[str, str], list[dict[str, str]]] | None = None,
) -> FetchedResults:
    league_codes = FOOTBALL_DATA_LEAGUES_BY_CLUB.get(club.key, [])
    if not league_codes:
        return FetchedResults([], [f"{club.name}: no football-data.co.uk league configured"])
    output: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for season in seasons:
        for league_code in league_codes:
            try:
                cache_key = (season, league_code)
                if league_cache is not None and cache_key in league_cache:
                    raw_rows = league_cache[cache_key]
                else:
                    raw_rows = fetch_football_data_league_rows(
                        season,
                        league_code,
                        timeout=timeout,
                        retries=retries,
                    )
                    if league_cache is not None:
                        league_cache[cache_key] = raw_rows
            except Exception as exc:  # noqa: BLE001 - CLI reports per-source failures.
                warnings.append(f"{club.name} {season} {league_code}: {exc}")
                continue
            for row in normalize_football_data_rows(club, raw_rows, season=season, league_code=league_code):
                key = (str(row.get("date", "")), str(row.get("club", "")), str(row.get("opponent", "")))
                if key in seen:
                    continue
                seen.add(key)
                output.append(row)
            polite_pause(pause)
    output.sort(key=lambda row: str(row.get("date", "")))
    return FetchedResults(output, warnings)


def write_club_match_results(path: Path, rows: list[dict[str, Any]], *, resume: bool = False) -> list[dict[str, Any]]:
    merged = []
    if resume and path.exists():
        merged.extend(read_csv(path))
    merged.extend(rows)
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in merged:
        key = (str(row.get("date", "")), str(row.get("club", "")), str(row.get("opponent", "")))
        deduped[key] = row
    output = sorted(deduped.values(), key=lambda row: str(row.get("date", "")))
    write_csv(path, output, MATCH_RESULT_FIELDS)
    return output


def fetch_match_results_for_clubs(
    clubs: list[Club],
    *,
    seasons: list[str],
    output_dir: Path,
    timeout: int = 45,
    retries: int = 2,
    pause: float = 0.1,
    resume: bool = False,
) -> dict[str, Any]:
    outputs: dict[str, Any] = {}
    league_cache: dict[tuple[str, str], list[dict[str, str]]] = {}
    for club in clubs:
        fetched = fetch_club_match_results(
            club,
            seasons=seasons,
            timeout=timeout,
            retries=retries,
            pause=pause,
            league_cache=league_cache,
        )
        path = output_dir / f"{club.key}.csv"
        rows = write_club_match_results(path, fetched.rows, resume=resume)
        outputs[club.key] = {
            "club": club.name,
            "path": str(path),
            "rows": len(rows),
            "new_rows": len(fetched.rows),
            "warnings": fetched.warnings,
        }
    return outputs
