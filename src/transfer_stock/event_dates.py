from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from .io import read_csv, write_csv
from .transfers import CLEAN_TRANSFER_FIELDS


EVENT_DATE_FIELDS = CLEAN_TRANSFER_FIELDS


def parse_gdelt_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z") and "-" in value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def key_for(row: dict[str, str], date_field: str = "date") -> tuple[str, str, str]:
    return (
        row.get(date_field, ""),
        row.get("club", "").strip().lower(),
        row.get("player", "").strip().lower(),
    )


def index_news_by_transfer(scored_news: list[dict[str, str]], min_credibility: float) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in scored_news:
        credibility = float(row.get("credibility_score") or 0)
        if credibility < min_credibility:
            continue
        published = parse_gdelt_datetime(row.get("published_at", ""))
        if published is None:
            continue
        grouped.setdefault(key_for(row, "event_date"), []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda item: parse_gdelt_datetime(item.get("published_at", "")) or datetime.max.replace(tzinfo=UTC))
    return grouped


def date_source_without_news(row: dict[str, str]) -> str:
    source = row.get("source", "")
    day = row.get("date", "")
    if source == "ewenme/transfers" and (day.endswith("-07-01") or day.endswith("-01-01")):
        return "proxy_transfer_window"
    return row.get("event_date_source") or "transfer_source"


def infer_event_date_rows(
    transfers: list[dict[str, str]],
    scored_news: list[dict[str, str]],
    min_credibility: float = 0.5,
) -> list[dict[str, object]]:
    news_by_transfer = index_news_by_transfer(scored_news, min_credibility)
    output: list[dict[str, object]] = []
    for row in transfers:
        original_date = row.get("original_transfer_date") or row.get("date", "")
        related = news_by_transfer.get(key_for(row))
        updated = {field: row.get(field, "") for field in EVENT_DATE_FIELDS}
        updated["original_transfer_date"] = original_date
        if related:
            first = related[0]
            published = parse_gdelt_datetime(first.get("published_at", ""))
            assert published is not None
            updated["date"] = published.date().isoformat()
            updated["event_date_source"] = "first_credible_news"
            updated["event_date_confidence"] = first.get("credibility_score", "")
        else:
            updated["event_date_source"] = date_source_without_news(row)
            updated["event_date_confidence"] = row.get("event_date_confidence", "")
        output.append(updated)
    return output


def infer_event_dates(
    transfers_path: Path,
    scored_news_path: Path,
    output_path: Path,
    min_credibility: float = 0.5,
) -> list[dict[str, object]]:
    transfers = read_csv(transfers_path)
    scored_news = read_csv(scored_news_path) if scored_news_path.exists() else []
    rows = infer_event_date_rows(transfers, scored_news, min_credibility=min_credibility)
    write_csv(output_path, rows, EVENT_DATE_FIELDS)
    return rows
