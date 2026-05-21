from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from .article_store import dedupe_articles, normalize_article_row, read_article_store, write_article_store
from .crawl4ai_adapter import enrich_rows_with_crawl4ai
from .config import Club
from .fundus_adapter import fetch_fundus_rows
from .http import FetchError, get_text, polite_pause
from .news_sources import NewsSource, mentions_club, mentions_transfer, render_source_url, source_supports_club
from .provider_news import fetch_provider_club_articles


SUPPORTED_METHODS = {"provider", "rss", "fundus", "crawl4ai", "scrapy-playwright"}


@dataclass(frozen=True)
class IngestionResult:
    rows: list[dict[str, object]]
    fetched_rows: int
    skipped_duplicates: int
    warnings: tuple[str, ...] = ()


def parse_dt(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        return None


def in_date_window(value: str, start: date, end: date) -> bool:
    parsed = parse_dt(value)
    if parsed is None:
        return True
    return start <= parsed.date() <= end


def xml_text(element: ElementTree.Element | None, names: Iterable[str]) -> str:
    if element is None:
        return ""
    for name in names:
        found = element.findtext(name)
        if found:
            return found.strip()
    return ""


def provider_name_from_kind(kind: str) -> str:
    if kind == "guardian_api":
        return "guardian"
    if kind == "gnews_api":
        return "gnews"
    raise ValueError(f"Unsupported provider kind: {kind}")


def method_allowed(kind: str, allowed_methods: set[str]) -> bool:
    if kind in {"guardian_api", "gnews_api"}:
        return "provider" in allowed_methods
    if kind == "rss":
        return "rss" in allowed_methods
    if kind == "fundus":
        return "fundus" in allowed_methods
    if kind == "crawl4ai":
        return "crawl4ai" in allowed_methods
    if kind == "scrapy_playwright":
        return "scrapy-playwright" in allowed_methods
    return False


def fetch_source_rows(
    source: NewsSource,
    club: Club,
    start: date,
    end: date,
    max_records: int,
    timeout: int,
    retries: int,
) -> list[dict[str, object]]:
    if source.kind in {"guardian_api", "gnews_api"}:
        provider = provider_name_from_kind(source.kind)
        articles = fetch_provider_club_articles(
            provider=provider,
            club=club.name,
            aliases=club.aliases,
            start=datetime.combine(start, datetime.min.time(), tzinfo=UTC),
            end=datetime.combine(end, datetime.max.time(), tzinfo=UTC),
            max_records=max_records,
            timeout=timeout,
            retries=retries,
        )
        return [
            {
                "seen_at": article.seen_at,
                "published_at": article.published_at,
                "source": article.source,
                "title": article.title,
                "url": article.url,
                "snippet": article.snippet,
                "language": article.language,
                "provider": provider,
                "club": club.name,
                "crawl_method": "provider_api",
            }
            for article in articles
        ]
    if source.kind == "rss":
        return fetch_rss_rows(source, club, start, end, max_records=max_records, timeout=timeout, retries=retries)
    if source.kind == "fundus":
        return fetch_fundus_rows(source, club, start, end, max_records=max_records)
    if source.kind == "crawl4ai":
        raise FetchError("Crawl4AI adapter scaffolded but not enabled yet; install crawl4ai and add page strategy.")
    if source.kind == "scrapy_playwright":
        raise FetchError("Scrapy/Playwright adapter scaffolded but not enabled yet; run a dedicated spider entrypoint.")
    raise FetchError(f"Unsupported source kind: {source.kind}")


def fetch_rss_rows(
    source: NewsSource,
    club: Club,
    start: date,
    end: date,
    max_records: int,
    timeout: int,
    retries: int,
) -> list[dict[str, object]]:
    xml_text_content = get_text(render_source_url(source, club), timeout=timeout, retries=retries)
    root = ElementTree.fromstring(xml_text_content)
    items = list(root.findall(".//item")) or list(root.findall(".//{http://www.w3.org/2005/Atom}entry"))
    rows: list[dict[str, object]] = []
    for item in items:
        title = xml_text(item, ["title", "{http://www.w3.org/2005/Atom}title"])
        snippet = xml_text(
            item,
            [
                "description",
                "{http://search.yahoo.com/mrss/}description",
                "{http://www.w3.org/2005/Atom}summary",
            ],
        )
        body_text = xml_text(item, ["{http://purl.org/rss/1.0/modules/content/}encoded"])
        url = xml_text(item, ["link"])
        if not url:
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                url = (link_node.attrib.get("href") or "").strip()
        published_at = xml_text(
            item,
            [
                "pubDate",
                "{http://www.w3.org/2005/Atom}updated",
                "{http://www.w3.org/2005/Atom}published",
                "{http://purl.org/dc/elements/1.1/}date",
            ],
        )
        if not in_date_window(published_at, start, end):
            continue
        haystack = " ".join([title, snippet, body_text])
        if not mentions_club(haystack, club):
            continue
        if not mentions_transfer(haystack):
            continue
        journalist = xml_text(item, ["author", "{http://purl.org/dc/elements/1.1/}creator"])
        rows.append(
            {
                "seen_at": datetime.now(tz=UTC).isoformat(),
                "published_at": published_at,
                "source": source.name,
                "journalist": journalist,
                "title": title,
                "url": url,
                "snippet": snippet,
                "body_text": body_text,
                "language": source.language,
                "provider": source.key,
                "club": club.name,
                "crawl_method": "rss",
            }
        )
        if len(rows) >= max_records:
            break
    return rows


def existing_article_keys(output_path: Path) -> set[tuple[str, str, str]]:
    if not output_path.exists():
        return set()
    return {(
        str(row.get("normalized_url", "")),
        str(row.get("title", "")),
        str(row.get("published_at", ""))[:10],
    ) for row in read_article_store(output_path)}


def fetch_articles_v2(
    clubs: Iterable[Club],
    sources: Iterable[NewsSource],
    start: date,
    end: date,
    output_path: Path,
    max_records: int = 100,
    methods: Iterable[str] = ("provider", "rss"),
    timeout: int = 45,
    retries: int = 3,
    pause: float = 1.0,
    resume: bool = False,
) -> IngestionResult:
    allowed_methods = set(methods)
    invalid_methods = sorted(allowed_methods - SUPPORTED_METHODS)
    if invalid_methods:
        raise ValueError(f"Unsupported methods: {', '.join(invalid_methods)}")
    seen_keys = existing_article_keys(output_path) if resume else set()
    rows: list[dict[str, object]] = read_article_store(output_path) if resume and output_path.exists() else []
    fetched_rows = 0
    skipped_duplicates = 0
    warnings: list[str] = []
    club_list = list(clubs)
    for club in club_list:
        for source in sources:
            if not source_supports_club(source, club):
                continue
            if not method_allowed(source.kind, allowed_methods):
                continue
            try:
                raw_rows = fetch_source_rows(
                    source,
                    club,
                    start=start,
                    end=end,
                    max_records=max_records,
                    timeout=timeout,
                    retries=retries,
                )
            except FetchError as exc:
                warnings.append(f"{source.key}:{club.name}: {exc}")
                polite_pause(pause)
                continue
            normalized_rows = [
                normalize_article_row(row, {club.key: club}, crawl_method=row.get("crawl_method", source.crawl_method or source.kind), provider=source.key)
                for row in raw_rows
            ]
            for row in normalized_rows:
                key = (
                    str(row.get("normalized_url", "")),
                    str(row.get("title", "")),
                    str(row.get("published_at", ""))[:10],
                )
                if key in seen_keys:
                    skipped_duplicates += 1
                    continue
                seen_keys.add(key)
                rows.append(row)
                fetched_rows += 1
            polite_pause(pause)
    deduped = dedupe_articles(rows)
    if "crawl4ai" in allowed_methods and deduped:
        try:
            deduped, crawl4ai_updates = enrich_rows_with_crawl4ai(
                deduped,
                limit=max_records * max(1, len(club_list)),
            )
        except FetchError as exc:
            warnings.append(f"crawl4ai: {exc}")
        else:
            if crawl4ai_updates:
                warnings.append(f"crawl4ai: enriched {crawl4ai_updates} article bodies")
    write_article_store(output_path, deduped)
    return IngestionResult(rows=deduped, fetched_rows=fetched_rows, skipped_duplicates=skipped_duplicates, warnings=tuple(warnings))
