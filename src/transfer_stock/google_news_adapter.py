from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from .article_store import compact_whitespace
from .http import FetchError


GOOGLE_NEWS_HOSTS = {"news.google.com", "www.news.google.com"}


def is_google_news_url(url: str) -> bool:
    split = urlsplit(str(url or ""))
    return split.netloc.lower() in GOOGLE_NEWS_HOSTS and (
        "/rss/articles/" in split.path or "/articles/" in split.path or "/read/" in split.path
    )


def title_suffix_source(title: str) -> str:
    text = compact_whitespace(title)
    text = re.sub(r"\s+-\s+Google News$", "", text, flags=re.IGNORECASE).strip()
    if " - " not in text:
        return ""
    suffix = text.rsplit(" - ", 1)[-1].strip()
    if not suffix or len(suffix) > 80:
        return ""
    return suffix


def decode_google_news_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int | None = None,
    interval: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    candidates = [row for row in rows if is_google_news_url(str(row.get("url", "")))]
    if limit is not None:
        candidates = candidates[:limit]
    if not candidates:
        return rows, 0

    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError as exc:
        raise FetchError("googlenewsdecoder is not installed. Run `pip install -e \".[google_news_decode]\"`.") from exc

    updates = 0
    for row in candidates:
        original_url = str(row.get("url", "")).strip()
        try:
            result = gnewsdecoder(original_url, interval=interval)
        except Exception:
            continue
        decoded_url = compact_whitespace(str(result.get("decoded_url", ""))) if result.get("status") else ""
        if not decoded_url or is_google_news_url(decoded_url):
            continue
        row["original_url"] = original_url
        row["url"] = decoded_url
        row["crawl_method"] = "google-news-decode"
        source = title_suffix_source(str(row.get("title", "")))
        if source:
            row["source"] = source
        row["extraction_confidence"] = max(float(row.get("extraction_confidence", 0.5) or 0.5), 0.68)
        updates += 1
    return rows, updates
