from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from .config import Club
from .http import FetchError
from .news_sources import NewsSource, mentions_club, mentions_transfer


def _pick_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None and value != "":
                return value
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if hasattr(value, "to_pydatetime"):
        try:
            converted = value.to_pydatetime()
        except (TypeError, ValueError):
            converted = None
        if isinstance(converted, datetime):
            return converted.astimezone(UTC) if converted.tzinfo else converted.replace(tzinfo=UTC)
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _coerce_authors(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _coerce_text(article: Any) -> str:
    for name in ("plaintext", "plain_text", "text", "body", "article_body"):
        value = _pick_attr(article, name)
        if value:
            return str(value).strip()
    return ""


def _coerce_url(article: Any) -> str:
    value = _pick_attr(article, "url", "link")
    if value:
        return str(value).strip()
    html = _pick_attr(article, "html")
    if html is not None:
        html_url = _pick_attr(html, "requested_url", "responded_url", "url")
        if html_url:
            return str(html_url).strip()
    return ""


def _coerce_source(article: Any) -> str:
    publisher = _pick_attr(article, "publisher")
    if publisher is None:
        return ""
    name = _pick_attr(publisher, "name")
    if name:
        return str(name).strip()
    return str(publisher).strip()


def fetch_fundus_rows(
    source: NewsSource,
    club: Club,
    start: date,
    end: date,
    max_records: int,
) -> list[dict[str, object]]:
    try:
        from fundus import Crawler, PublisherCollection
    except ImportError as exc:
        raise FetchError("Fundus is not installed. Run `pip install -e \".[scrape_v2]\"`.") from exc

    publisher_groups = source.publisher_groups
    if not publisher_groups:
        raise FetchError(f"{source.key} is missing publisher_groups.")

    collections = []
    missing_groups: list[str] = []
    for group in publisher_groups:
        collection = getattr(PublisherCollection, group, None)
        if collection is None:
            missing_groups.append(group)
            continue
        collections.append(collection)
    if not collections:
        joined = ", ".join(missing_groups or publisher_groups)
        raise FetchError(f"Fundus publisher groups unavailable: {joined}")

    crawler = Crawler(*collections)
    rows: list[dict[str, object]] = []
    max_scan = max(max_records * 5, 40)
    for article in crawler.crawl(max_articles=max_scan):
        published_dt = _coerce_datetime(
            _pick_attr(article, "publishing_date", "published_at", "published", "date")
        )
        if published_dt is not None and not (start <= published_dt.date() <= end):
            continue

        title = str(_pick_attr(article, "title", "headline") or "").strip()
        body_text = _coerce_text(article)
        summary = str(_pick_attr(article, "summary", "description", "teaser") or "").strip()
        haystack = " ".join(part for part in (title, summary, body_text) if part)
        if not haystack:
            continue
        if not mentions_club(haystack, club):
            continue
        if not mentions_transfer(haystack):
            continue

        rows.append(
            {
                "seen_at": datetime.now(tz=UTC).isoformat(),
                "published_at": published_dt.isoformat().replace("+00:00", "Z") if published_dt else "",
                "source": _coerce_source(article) or source.name,
                "journalist": _coerce_authors(_pick_attr(article, "authors", "author")),
                "title": title,
                "url": _coerce_url(article),
                "snippet": summary or body_text[:300],
                "body_text": body_text,
                "language": source.language,
                "provider": source.key,
                "club": club.name,
                "crawl_method": "fundus",
                "extraction_confidence": 0.75,
            }
        )
        if len(rows) >= max_records:
            break
    return rows
