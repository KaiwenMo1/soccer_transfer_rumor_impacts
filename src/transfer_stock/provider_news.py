from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Iterable

from .http import FetchError, get_json
from .news import Article, build_event_query


GUARDIAN_URL = "https://content.guardianapis.com/search"
GNEWS_URL = "https://gnews.io/api/v4/search"


def require_key(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise FetchError(f"Missing required environment variable: {name}")
    return value


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_club_query(club: str, aliases: Iterable[str]) -> str:
    names = [item.strip() for item in [club, *aliases] if item and item.strip()]
    alias_expr = " OR ".join(f'"{name}"' for name in dict.fromkeys(names))
    return f"({alias_expr}) (transfer OR signing OR signed OR agreement OR talks OR medical OR bid OR bids OR loan)"


def fetch_guardian_event_articles(
    club: str,
    player: str,
    start: datetime,
    end: datetime,
    event_date: str,
    max_records: int = 10,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    key = require_key("GUARDIAN_API_KEY")
    data = get_json(
        GUARDIAN_URL,
        params={
            "q": build_event_query(club, player),
            "from-date": start.date().isoformat(),
            "to-date": end.date().isoformat(),
            "page-size": min(max_records, 50),
            "order-by": "relevance",
            "show-fields": "trailText,byline",
            "api-key": key,
        },
        timeout=timeout,
        retries=retries,
    )
    seen_at = datetime.now(tz=UTC).isoformat()
    articles: list[Article] = []
    for item in data.get("response", {}).get("results", []):
        fields = item.get("fields", {})
        source = "The Guardian"
        byline = fields.get("byline", "")
        if byline:
            source = f"{source} / {byline}"
        articles.append(
            Article(
                seen_at=seen_at,
                club=club,
                player=player,
                event_date=event_date,
                title=item.get("webTitle", ""),
                url=item.get("webUrl", ""),
                source=source,
                language="English",
                published_at=item.get("webPublicationDate", ""),
                snippet=fields.get("trailText", ""),
            )
        )
    return articles


def fetch_gnews_event_articles(
    club: str,
    player: str,
    start: datetime,
    end: datetime,
    event_date: str,
    max_records: int = 10,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    # GNews free tier is useful for recent/current news, but not historical
    # transfer windows. Avoid burning quota on dates it cannot return.
    if end < datetime.now(tz=UTC) - timedelta(days=31):
        return []
    key = require_key("GNEWS_API_KEY")
    data = get_json(
        GNEWS_URL,
        params={
            "q": build_event_query(club, player),
            "from": iso_utc(start),
            "to": iso_utc(end),
            "lang": "en",
            "max": min(max_records, 10),
            "apikey": key,
        },
        timeout=timeout,
        retries=retries,
    )
    seen_at = datetime.now(tz=UTC).isoformat()
    articles: list[Article] = []
    for item in data.get("articles", []):
        source = item.get("source") or {}
        articles.append(
            Article(
                seen_at=seen_at,
                club=club,
                player=player,
                event_date=event_date,
                title=item.get("title", ""),
                url=item.get("url", ""),
                source=source.get("name", "GNews"),
                language="English",
                published_at=item.get("publishedAt", ""),
                snippet=item.get("description", ""),
            )
        )
    return articles


def fetch_provider_event_articles(
    provider: str,
    club: str,
    player: str,
    start: datetime,
    end: datetime,
    event_date: str,
    max_records: int = 10,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    if provider == "guardian":
        return fetch_guardian_event_articles(club, player, start, end, event_date, max_records, timeout, retries)
    if provider == "gnews":
        return fetch_gnews_event_articles(club, player, start, end, event_date, max_records, timeout, retries)
    raise ValueError(f"Unsupported provider: {provider}")


def fetch_guardian_club_articles(
    club: str,
    aliases: Iterable[str],
    start: datetime,
    end: datetime,
    max_records: int = 100,
    page_size: int = 50,
    max_pages: int = 5,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    key = require_key("GUARDIAN_API_KEY")
    seen_at = datetime.now(tz=UTC).isoformat()
    query = build_club_query(club, aliases)
    articles: list[Article] = []
    seen_urls: set[str] = set()
    target = max(1, max_records)
    size = max(1, min(page_size, 50, target))
    page = 1
    while len(articles) < target and page <= max_pages:
        data = get_json(
            GUARDIAN_URL,
            params={
                "q": query,
                "from-date": start.date().isoformat(),
                "to-date": end.date().isoformat(),
                "page-size": size,
                "page": page,
                "order-by": "newest",
                "section": "football",
                "show-fields": "trailText,byline",
                "api-key": key,
            },
            timeout=timeout,
            retries=retries,
        )
        response = data.get("response", {})
        results = response.get("results", [])
        if not results:
            break
        for item in results:
            url = item.get("webUrl", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            fields = item.get("fields", {})
            source = "The Guardian"
            byline = fields.get("byline", "")
            if byline:
                source = f"{source} / {byline}"
            articles.append(
                Article(
                    seen_at=seen_at,
                    club=club,
                    title=item.get("webTitle", ""),
                    url=url,
                    source=source,
                    language="English",
                    published_at=item.get("webPublicationDate", ""),
                    snippet=fields.get("trailText", ""),
                )
            )
            if len(articles) >= target:
                break
        total_pages = int(response.get("pages") or page)
        if page >= total_pages:
            break
        page += 1
    return articles


def fetch_gnews_club_articles(
    club: str,
    aliases: Iterable[str],
    start: datetime,
    end: datetime,
    max_records: int = 10,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    if end < datetime.now(tz=UTC) - timedelta(days=31):
        return []
    key = require_key("GNEWS_API_KEY")
    data = get_json(
        GNEWS_URL,
        params={
            "q": build_club_query(club, aliases),
            "from": iso_utc(start),
            "to": iso_utc(end),
            "lang": "en",
            "max": min(max_records, 10),
            "apikey": key,
        },
        timeout=timeout,
        retries=retries,
    )
    seen_at = datetime.now(tz=UTC).isoformat()
    articles: list[Article] = []
    seen_urls: set[str] = set()
    for item in data.get("articles", []):
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        source = item.get("source") or {}
        articles.append(
            Article(
                seen_at=seen_at,
                club=club,
                title=item.get("title", ""),
                url=url,
                source=source.get("name", "GNews"),
                language="English",
                published_at=item.get("publishedAt", ""),
                snippet=item.get("description", ""),
            )
        )
    return articles


def fetch_provider_club_articles(
    provider: str,
    club: str,
    aliases: Iterable[str],
    start: datetime,
    end: datetime,
    max_records: int = 100,
    page_size: int = 50,
    max_pages: int = 5,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    if provider == "guardian":
        return fetch_guardian_club_articles(
            club=club,
            aliases=aliases,
            start=start,
            end=end,
            max_records=max_records,
            page_size=page_size,
            max_pages=max_pages,
            timeout=timeout,
            retries=retries,
        )
    if provider == "gnews":
        return fetch_gnews_club_articles(
            club=club,
            aliases=aliases,
            start=start,
            end=end,
            max_records=max_records,
            timeout=timeout,
            retries=retries,
        )
    raise ValueError(f"Unsupported provider: {provider}")
