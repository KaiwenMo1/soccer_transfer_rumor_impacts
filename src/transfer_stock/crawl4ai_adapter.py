from __future__ import annotations

import asyncio
from typing import Any

from .http import FetchError


def _markdown_text(result: Any) -> str:
    markdown = getattr(result, "markdown", "")
    if isinstance(markdown, str):
        return markdown.strip()
    for name in ("fit_markdown", "raw_markdown", "markdown"):
        value = getattr(markdown, name, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _crawl_many(urls: list[str]) -> dict[str, str]:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise FetchError("Crawl4AI is not installed. Run `pip install -e \".[ai_scrape]\"`.") from exc

    output: dict[str, str] = {}
    async with AsyncWebCrawler() as crawler:
        for url in urls:
            try:
                result = await crawler.arun(url=url)
            except Exception:
                continue
            markdown = _markdown_text(result)
            if markdown:
                output[url] = markdown
    return output


def enrich_rows_with_crawl4ai(
    rows: list[dict[str, object]],
    *,
    limit: int | None = None,
    min_body_chars: int = 400,
) -> tuple[list[dict[str, object]], int]:
    candidates = [
        row for row in rows
        if str(row.get("url", "")).strip() and len(str(row.get("body_text", "")).strip()) < min_body_chars
    ]
    if limit is not None:
        candidates = candidates[:limit]
    if not candidates:
        return rows, 0

    crawled = asyncio.run(_crawl_many([str(row.get("url", "")).strip() for row in candidates]))
    updates = 0
    for row in candidates:
        url = str(row.get("url", "")).strip()
        markdown = crawled.get(url, "")
        if not markdown:
            continue
        row["body_text"] = markdown
        row["crawl_method"] = "crawl4ai"
        row["extraction_confidence"] = max(float(row.get("extraction_confidence", 0.5) or 0.5), 0.85)
        updates += 1
    return rows, updates
