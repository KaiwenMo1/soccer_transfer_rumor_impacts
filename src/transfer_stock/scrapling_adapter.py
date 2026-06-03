from __future__ import annotations

import re
from html import unescape
from typing import Any

from .http import FetchError


ARTICLE_TEXT_SELECTORS = (
    "article ::text",
    "main ::text",
    "[itemprop='articleBody'] ::text",
    ".article-body ::text",
    ".article__body ::text",
    ".story-body ::text",
    ".entry-content ::text",
    ".post-content ::text",
)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def strip_html(value: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", value or "")
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return compact_text(text)


def page_text_from_selector(page: Any, selector: str) -> str:
    try:
        selected = page.css(selector)
        values = selected.getall()
    except Exception:
        return ""
    return compact_text(" ".join(str(item) for item in values if str(item).strip()))


def readable_page_text(page: Any, *, min_chars: int = 250, max_chars: int = 8000) -> str:
    for selector in ARTICLE_TEXT_SELECTORS:
        text = page_text_from_selector(page, selector)
        if len(text) >= min_chars:
            return text[:max_chars]

    body = getattr(page, "body", b"")
    if isinstance(body, bytes):
        try:
            body_text = body.decode(getattr(page, "encoding", None) or "utf-8", errors="ignore")
        except LookupError:
            body_text = body.decode("utf-8", errors="ignore")
    else:
        body_text = str(body or "")
    fallback = strip_html(body_text)
    return fallback[:max_chars] if len(fallback) >= min_chars else ""


def page_title(page: Any) -> str:
    try:
        return compact_text(str(page.css("title::text").get("") or ""))
    except Exception:
        return ""


def row_needs_enrichment(row: dict[str, object], min_body_chars: int) -> bool:
    return bool(str(row.get("url", "")).strip()) and len(str(row.get("body_text", "")).strip()) < min_body_chars


def enrich_rows_with_scrapling(
    rows: list[dict[str, object]],
    *,
    limit: int | None = None,
    min_body_chars: int = 400,
    timeout: int = 30,
    retries: int = 2,
    impersonate: str = "chrome",
) -> tuple[list[dict[str, object]], int]:
    candidates = [row for row in rows if row_needs_enrichment(row, min_body_chars)]
    if limit is not None:
        candidates = candidates[:limit]
    if not candidates:
        return rows, 0

    try:
        from scrapling.fetchers import FetcherSession
    except ImportError as exc:
        raise FetchError("Scrapling is not installed. Run `pip install -e \".[scrapling_scrape]\"`.") from exc

    updates = 0
    with FetcherSession(
        impersonate=impersonate,
        stealthy_headers=True,
        timeout=timeout,
        retries=retries,
    ) as session:
        for row in candidates:
            url = str(row.get("url", "")).strip()
            try:
                page = session.get(url, follow_redirects="safe")
            except Exception:
                continue
            status = int(getattr(page, "status", 0) or 0)
            if status and not (200 <= status < 400):
                continue
            text = readable_page_text(page)
            if not text:
                continue
            title = page_title(page)
            if title and not str(row.get("title", "")).strip():
                row["title"] = title
            row["body_text"] = text
            row["crawl_method"] = "scrapling"
            row["extraction_confidence"] = max(float(row.get("extraction_confidence", 0.5) or 0.5), 0.82)
            updates += 1
    return rows, updates
