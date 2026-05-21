from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import Club
from .http import FetchError
from .io import ensure_parent, read_jsonl, write_jsonl


ARTICLE_FIELDS = [
    "article_id",
    "seen_at",
    "published_at",
    "source",
    "journalist",
    "title",
    "url",
    "normalized_url",
    "language",
    "body_text",
    "snippet",
    "club_candidates",
    "player_candidates",
    "crawl_method",
    "extraction_confidence",
    "provider",
    "club",
    "player",
    "event_date",
]

TRACKING_QUERY_PREFIXES = (
    "utm_",
    "fbclid",
    "gclid",
    "cmpid",
    "output",
    "ref",
    "refsrc",
)


@dataclass(frozen=True)
class ArticleRecord:
    article_id: str
    seen_at: str
    published_at: str
    source: str
    journalist: str
    title: str
    url: str
    normalized_url: str
    language: str
    body_text: str
    snippet: str
    club_candidates: tuple[str, ...]
    player_candidates: tuple[str, ...]
    crawl_method: str
    extraction_confidence: float
    provider: str
    club: str = ""
    player: str = ""
    event_date: str = ""

    def to_row(self) -> dict[str, object]:
        return {
            "article_id": self.article_id,
            "seen_at": self.seen_at,
            "published_at": self.published_at,
            "source": self.source,
            "journalist": self.journalist,
            "title": self.title,
            "url": self.url,
            "normalized_url": self.normalized_url,
            "language": self.language,
            "body_text": self.body_text,
            "snippet": self.snippet,
            "club_candidates": list(self.club_candidates),
            "player_candidates": list(self.player_candidates),
            "crawl_method": self.crawl_method,
            "extraction_confidence": round(self.extraction_confidence, 4),
            "provider": self.provider,
            "club": self.club,
            "player": self.player,
            "event_date": self.event_date,
        }


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    split = urlsplit(url.strip())
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(split.query, keep_blank_values=False)
        if not any(key.lower().startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES)
    ]
    path = split.path.rstrip("/") or "/"
    cleaned = split._replace(query=urlencode(query_pairs), fragment="", path=path)
    return urlunsplit(cleaned)


def infer_journalist(source: str, row: dict[str, Any]) -> str:
    if row.get("journalist"):
        return compact_whitespace(str(row["journalist"]))
    if " / " in source:
        return compact_whitespace(source.split(" / ", 1)[1])
    if " by " in source.lower():
        lowered = source.lower()
        index = lowered.find(" by ")
        return compact_whitespace(source[index + 4 :])
    return ""


def canonical_source(row: dict[str, Any]) -> str:
    source = compact_whitespace(str(row.get("source", "")))
    if source:
        return source
    provider = compact_whitespace(str(row.get("provider", "")))
    if provider:
        return provider
    split = urlsplit(str(row.get("url", "")))
    return split.netloc.lower()


def parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [compact_whitespace(str(item)) for item in value if compact_whitespace(str(item))]
    if isinstance(value, tuple):
        return [compact_whitespace(str(item)) for item in value if compact_whitespace(str(item))]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [compact_whitespace(str(item)) for item in parsed if compact_whitespace(str(item))]
        if "|" in text:
            return [compact_whitespace(part) for part in text.split("|") if compact_whitespace(part)]
        if "," in text:
            return [compact_whitespace(part) for part in text.split(",") if compact_whitespace(part)]
        return [compact_whitespace(text)]
    return [compact_whitespace(str(value))]


def candidate_clubs(text: str, clubs: dict[str, Club]) -> list[str]:
    haystack = f" {compact_whitespace(text).lower()} "
    matches: list[str] = []
    for club in clubs.values():
        names = (club.name, *club.aliases)
        for name in dict.fromkeys(names):
            label = compact_whitespace(name).lower()
            if not label:
                continue
            if f" {label} " in haystack:
                matches.append(club.name)
                break
    return list(dict.fromkeys(matches))


def candidate_players(row: dict[str, Any]) -> list[str]:
    candidates = parse_list(row.get("player_candidates"))
    if candidates:
        return candidates
    player = compact_whitespace(str(row.get("player", "")))
    return [player] if player else []


def article_id_from_parts(normalized_url: str, title: str, published_at: str, source: str) -> str:
    digest = hashlib.sha1(
        "||".join([normalized_url, compact_whitespace(title).lower(), published_at, source.lower()]).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def as_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_article_row(
    row: dict[str, Any],
    clubs: dict[str, Club],
    crawl_method: str | None = None,
    provider: str | None = None,
) -> dict[str, object]:
    title = compact_whitespace(str(row.get("title", "")))
    url = compact_whitespace(str(row.get("url", "")))
    normalized = normalize_url(url)
    source = canonical_source(row)
    published_at = compact_whitespace(str(row.get("published_at", "")))
    seen_at = compact_whitespace(str(row.get("seen_at", ""))) or now_iso()
    snippet = compact_whitespace(str(row.get("snippet", "")))
    body_text = compact_whitespace(str(row.get("body_text", "")))
    club_hint = compact_whitespace(str(row.get("club", "")))
    clubs_found = parse_list(row.get("club_candidates"))
    if not clubs_found:
        clubs_found = candidate_clubs(" ".join([title, snippet, body_text, club_hint]), clubs)
    players_found = candidate_players(row)
    method = compact_whitespace(str(crawl_method or row.get("crawl_method") or row.get("method") or "legacy"))
    provider_name = compact_whitespace(str(provider or row.get("provider") or source.split(" / ", 1)[0]))
    confidence = as_float(row.get("extraction_confidence"), 0.5)

    record = ArticleRecord(
        article_id=compact_whitespace(str(row.get("article_id", "")))
        or article_id_from_parts(normalized, title, published_at, source),
        seen_at=seen_at,
        published_at=published_at,
        source=source,
        journalist=infer_journalist(source, row),
        title=title,
        url=url,
        normalized_url=normalized,
        language=compact_whitespace(str(row.get("language", ""))) or "English",
        body_text=body_text,
        snippet=snippet,
        club_candidates=tuple(dict.fromkeys(clubs_found)),
        player_candidates=tuple(dict.fromkeys(players_found)),
        crawl_method=method,
        extraction_confidence=max(0.0, min(1.0, confidence)),
        provider=provider_name,
        club=club_hint,
        player=compact_whitespace(str(row.get("player", ""))),
        event_date=compact_whitespace(str(row.get("event_date", ""))),
    )
    return record.to_row()


def article_dedupe_key(row: dict[str, Any]) -> tuple[str, str, str]:
    normalized = normalize_url(str(row.get("normalized_url") or row.get("url") or ""))
    title = compact_whitespace(str(row.get("title", ""))).lower()
    published = compact_whitespace(str(row.get("published_at", "")))[:10]
    return normalized, title, published


def dedupe_articles(rows: Iterable[dict[str, Any]]) -> list[dict[str, object]]:
    kept: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = article_dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        kept.append(dict(row))
    return kept


def normalize_article_file(
    input_path: Path,
    output_path: Path,
    clubs: dict[str, Club],
    crawl_method: str | None = None,
    provider: str | None = None,
    dedupe: bool = True,
) -> list[dict[str, object]]:
    if not input_path.exists():
        raise FetchError(f"Input article file not found: {input_path}")
    rows = [normalize_article_row(row, clubs, crawl_method=crawl_method, provider=provider) for row in read_jsonl(input_path)]
    if dedupe:
        rows = dedupe_articles(rows)
    write_article_store(output_path, rows)
    return rows


def read_article_store(path: Path) -> list[dict[str, object]]:
    return read_jsonl(path)


def write_article_store(path: Path, rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    normalized_rows = []
    for row in rows:
        cleaned = {field: row.get(field, [] if field.endswith("_candidates") else "") for field in ARTICLE_FIELDS}
        if not isinstance(cleaned["club_candidates"], list):
            cleaned["club_candidates"] = parse_list(cleaned["club_candidates"])
        if not isinstance(cleaned["player_candidates"], list):
            cleaned["player_candidates"] = parse_list(cleaned["player_candidates"])
        normalized_rows.append(cleaned)
    write_jsonl(path, normalized_rows)


def article_store_stats(rows: Iterable[dict[str, Any]]) -> dict[str, object]:
    by_source: dict[str, int] = {}
    by_method: dict[str, int] = {}
    duplicates = 0
    seen: set[tuple[str, str, str]] = set()
    total = 0
    for row in rows:
        total += 1
        source = compact_whitespace(str(row.get("source", ""))) or "unknown"
        method = compact_whitespace(str(row.get("crawl_method", ""))) or "unknown"
        by_source[source] = by_source.get(source, 0) + 1
        by_method[method] = by_method.get(method, 0) + 1
        key = article_dedupe_key(row)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return {
        "n_rows": total,
        "n_unique": len(seen),
        "duplicate_rows": duplicates,
        "sources": dict(sorted(by_source.items(), key=lambda item: (-item[1], item[0]))),
        "methods": dict(sorted(by_method.items(), key=lambda item: (-item[1], item[0]))),
    }
