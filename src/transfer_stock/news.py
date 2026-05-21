from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

from .config import Club
from .http import get_json


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


@dataclass(frozen=True)
class Article:
    seen_at: str
    club: str
    title: str
    url: str
    source: str
    language: str
    published_at: str
    snippet: str
    player: str = ""
    event_date: str = ""


def gdelt_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def build_transfer_query(club: Club) -> str:
    aliases = []
    for alias in dict.fromkeys((club.name, *club.aliases)):
        compact = alias.replace(" ", "")
        if len(compact) >= 5 and all(len(part) >= 4 for part in alias.split()):
            aliases.append(alias)
    alias_expr = " OR ".join(f'"{alias}"' for alias in aliases)
    return f"({alias_expr}) (transfer OR signing OR signed OR agreement OR talks OR medical OR loan)"


def fetch_gdelt_articles(
    club: Club,
    days: int = 14,
    max_records: int = 50,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    end = datetime.now(tz=UTC)
    start = end - timedelta(days=days)
    params = {
        "query": build_transfer_query(club),
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sort": "HybridRel",
        "startdatetime": gdelt_datetime(start),
        "enddatetime": gdelt_datetime(end),
    }
    data = get_json(GDELT_DOC_URL, params=params, timeout=timeout, retries=retries)
    articles: list[Article] = []
    for item in data.get("articles", []):
        articles.append(
            Article(
                seen_at=end.isoformat(),
                club=club.name,
                title=item.get("title", ""),
                url=item.get("url", ""),
                source=item.get("sourceCommonName", "") or item.get("domain", ""),
                language=item.get("language", ""),
                published_at=item.get("seendate", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return articles


def build_event_query(club: str, player: str) -> str:
    club_part = f'"{club}"' if club else ""
    player_part = f'"{player}"' if player else ""
    subject = " ".join(part for part in [player_part, club_part] if part)
    return f"{subject} (transfer OR signing OR signed OR agreement OR talks OR medical OR loan)"


def fetch_gdelt_articles_for_event(
    club: str,
    player: str,
    start: datetime,
    end: datetime,
    event_date: str,
    max_records: int = 25,
    timeout: int = 30,
    retries: int = 2,
) -> list[Article]:
    params = {
        "query": build_event_query(club, player),
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sort": "HybridRel",
        "startdatetime": gdelt_datetime(start),
        "enddatetime": gdelt_datetime(end),
    }
    data = get_json(GDELT_DOC_URL, params=params, timeout=timeout, retries=retries)
    seen_at = datetime.now(tz=UTC).isoformat()
    articles: list[Article] = []
    for item in data.get("articles", []):
        articles.append(
            Article(
                seen_at=seen_at,
                club=club,
                player=player,
                event_date=event_date,
                title=item.get("title", ""),
                url=item.get("url", ""),
                source=item.get("sourceCommonName", "") or item.get("domain", ""),
                language=item.get("language", ""),
                published_at=item.get("seendate", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return articles


def article_to_row(article: Article) -> dict[str, object]:
    return {
        "seen_at": article.seen_at,
        "club": article.club,
        "player": article.player,
        "event_date": article.event_date,
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "language": article.language,
        "published_at": article.published_at,
        "snippet": article.snippet,
    }


def gdelt_web_url(club: Club) -> str:
    return f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote_plus(build_transfer_query(club))}&mode=ArtList&format=json"
