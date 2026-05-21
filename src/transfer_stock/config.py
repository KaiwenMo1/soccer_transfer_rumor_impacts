from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


@dataclass(frozen=True)
class Club:
    key: str
    name: str
    aliases: tuple[str, ...]
    exchange_timezone: str
    stooq_symbol: str = ""
    yahoo_symbol: str = ""
    market_index_symbol: str = ""
    yahoo_market_symbol: str = ""
    entity_type: str = "club"
    country: str = ""
    exchange: str = ""


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_clubs(path: Path = CONFIG_DIR / "clubs.yml") -> dict[str, Club]:
    raw = load_yaml(path).get("clubs", {})
    clubs: dict[str, Club] = {}
    for key, item in raw.items():
        clubs[key] = Club(
            key=key,
            name=item["name"],
            aliases=tuple(item.get("aliases", [])),
            stooq_symbol=item.get("stooq_symbol", ""),
            yahoo_symbol=item.get("yahoo_symbol", ""),
            market_index_symbol=item.get("market_index_symbol", ""),
            yahoo_market_symbol=item.get("yahoo_market_symbol", ""),
            exchange_timezone=item.get("exchange_timezone", "UTC"),
            entity_type=item.get("entity_type", "club"),
            country=item.get("country", ""),
            exchange=item.get("exchange", ""),
        )
    return clubs


def load_credibility(path: Path = CONFIG_DIR / "credibility.yml") -> dict[str, Any]:
    return load_yaml(path)
