from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable

from .backtesting import run_backtests
from .claims import extract_claims_from_file
from .config import Club, DATA_DIR
from .credibility_engine import credibility_outputs
from .ingestion_v2 import fetch_articles_v2
from .news_sources import load_news_sources, select_sources
from .ml_v2 import build_stage6_dataset, train_stage6_models
from .matching import match_claims_file
from .demo import write_demo_payload
from .stock import fetch_daily, save_price_bars


@dataclass(frozen=True)
class LiveRefreshArtifacts:
    run_dir: Path
    raw_news: Path
    normalized_articles: Path
    claims: Path
    matches: Path
    credibility_dir: Path
    base_dataset: Path
    market_dataset: Path
    predictions_dir: Path
    metrics: Path
    backtests_dir: Path
    dashboard: Path


def utc_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def run_slug(start: date, end: date) -> str:
    return f"live_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"


def default_artifacts(output_root: Path, start: date, end: date, dashboard_output: Path) -> LiveRefreshArtifacts:
    run_dir = output_root / run_slug(start, end)
    return LiveRefreshArtifacts(
        run_dir=run_dir,
        raw_news=run_dir / "raw" / "news" / "provider_club_news.jsonl",
        normalized_articles=run_dir / "raw" / "articles" / "articles_normalized.jsonl",
        claims=run_dir / "processed" / "claims" / "claims.jsonl",
        matches=run_dir / "processed" / "matched_claims" / "matches.csv",
        credibility_dir=run_dir / "processed" / "credibility",
        base_dataset=run_dir / "processed" / "modeling" / "stage6_claims_base.csv",
        market_dataset=run_dir / "processed" / "modeling" / "stage6_claims_market.csv",
        predictions_dir=run_dir / "models" / "stage6",
        metrics=run_dir / "models" / "stage6" / "metrics_stage6.json",
        backtests_dir=run_dir / "reports" / "backtests",
        dashboard=dashboard_output,
    )


def named_artifacts(output_root: Path, slug: str, dashboard_output: Path) -> LiveRefreshArtifacts:
    safe_slug = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in slug).strip("_") or "live_manual"
    run_dir = output_root / safe_slug
    return LiveRefreshArtifacts(
        run_dir=run_dir,
        raw_news=run_dir / "raw" / "news" / "provider_club_news.jsonl",
        normalized_articles=run_dir / "raw" / "articles" / "articles_normalized.jsonl",
        claims=run_dir / "processed" / "claims" / "claims.jsonl",
        matches=run_dir / "processed" / "matched_claims" / "matches.csv",
        credibility_dir=run_dir / "processed" / "credibility",
        base_dataset=run_dir / "processed" / "modeling" / "stage6_claims_base.csv",
        market_dataset=run_dir / "processed" / "modeling" / "stage6_claims_market.csv",
        predictions_dir=run_dir / "models" / "stage6",
        metrics=run_dir / "models" / "stage6" / "metrics_stage6.json",
        backtests_dir=run_dir / "reports" / "backtests",
        dashboard=dashboard_output,
    )


def fetch_current_stock_cache(
    clubs: Iterable[Club],
    start: date,
    end: date,
    source: str = "yahoo",
) -> dict[str, int]:
    stock_start = min(date(2021, 1, 1), start - timedelta(days=450))
    stooq_api_key = os.environ.get("STOOQ_API_KEY")
    counts: dict[str, int] = {}
    for club in clubs:
        symbol = club.stooq_symbol if source == "stooq" else club.yahoo_symbol
        if not symbol:
            counts[club.key] = 0
            continue
        bars = fetch_daily(symbol, stock_start, end, source=source, stooq_api_key=stooq_api_key)
        save_price_bars(DATA_DIR / "raw" / "stocks" / f"{club.key}.csv", bars)
        counts[club.key] = len(bars)

        market_symbol = club.market_index_symbol if source == "stooq" else club.yahoo_market_symbol
        if market_symbol:
            index_bars = fetch_daily(market_symbol, stock_start, end, source=source, stooq_api_key=stooq_api_key)
            save_price_bars(DATA_DIR / "raw" / "stocks" / f"{club.key}_market.csv", index_bars)
    return counts


def resolve_sources(
    *,
    provider: str,
    source_keys: Iterable[str] | None,
) -> list:
    available_sources = load_news_sources()
    selected_source_keys = list(source_keys or [])
    if selected_source_keys:
        return select_sources(available_sources, selected_source_keys)
    if provider == "guardian":
        return select_sources(available_sources, ["guardian_api", "guardian_rss"])
    if provider == "gnews":
        return select_sources(available_sources, ["gnews_api", "google_news_global_en"])
    return select_sources(available_sources, None)


def fetch_live_articles(
    selected: list[Club],
    *,
    start: date,
    end: date,
    provider: str = "all",
    source_keys: Iterable[str] | None = None,
    methods: Iterable[str] = ("provider", "rss"),
    output_path: Path,
    max_records: int = 100,
    timeout: int = 45,
    retries: int = 3,
    pause: float = 0.0,
    resume: bool = False,
):
    sources = resolve_sources(provider=provider, source_keys=source_keys)
    return fetch_articles_v2(
        clubs=selected,
        sources=sources,
        start=start,
        end=end,
        output_path=output_path,
        max_records=max_records,
        methods=methods,
        timeout=timeout,
        retries=retries,
        pause=pause,
        resume=resume,
    )


def analyze_live_articles(
    clubs_by_key: dict[str, Club],
    selected: list[Club],
    *,
    articles_path: Path,
    transfers_path: Path,
    claim_backend: str = "heuristic",
    train_end_season: str = "2024-25",
    base_scored_claim_paths: Iterable[Path] | None = None,
    stats_claim_paths: Iterable[Path] | None = None,
    stats_match_paths: Iterable[Path] | None = None,
    output_root: Path = DATA_DIR / "live",
    slug: str = "live_manual",
    dashboard_output: Path = Path("app") / "static" / "data" / "dashboard_data.json",
) -> dict[str, Path]:
    artifacts = named_artifacts(output_root, slug, dashboard_output)
    if articles_path != artifacts.normalized_articles:
        artifacts.normalized_articles.parent.mkdir(parents=True, exist_ok=True)
        artifacts.normalized_articles.write_text(articles_path.read_text(encoding="utf-8"), encoding="utf-8")
    artifacts.raw_news.parent.mkdir(parents=True, exist_ok=True)
    artifacts.raw_news.write_text("[]\n", encoding="utf-8")

    extract_claims_from_file(
        artifacts.normalized_articles,
        artifacts.claims,
        clubs_by_key,
        transfers_path=transfers_path,
        backend=claim_backend,
    )
    match_claims_file(
        artifacts.claims,
        transfers_path,
        artifacts.matches,
        clubs_by_key,
    )
    credibility_paths = credibility_outputs(
        artifacts.claims,
        artifacts.matches,
        transfers_path,
        artifacts.credibility_dir,
        stats_claim_paths=stats_claim_paths,
        stats_match_paths=stats_match_paths,
    )

    scored_claim_paths = [Path(path) for path in (base_scored_claim_paths or []) if Path(path).exists()]
    scored_claim_paths.append(credibility_paths["scored_claims_csv"])
    build_stage6_dataset(
        scored_claim_paths,
        transfers_path,
        artifacts.base_dataset,
        artifacts.market_dataset,
        clubs_by_key,
    )
    train_stage6_models(
        artifacts.market_dataset,
        artifacts.metrics,
        artifacts.predictions_dir,
        train_end_season=train_end_season,
    )
    backtest_paths = run_backtests(
        artifacts.predictions_dir / "stage6_xgboost_predictions.csv",
        artifacts.backtests_dir,
        clubs_by_key,
        stocks_dir=DATA_DIR / "raw" / "stocks",
    )
    write_demo_payload(
        artifacts.predictions_dir / "stage6_xgboost_predictions.csv",
        artifacts.metrics,
        backtest_paths["summary"],
        backtest_paths["trades"],
        artifacts.dashboard,
        transfers_path=transfers_path,
        journalist_stats_path=credibility_paths["journalist_stats"],
        source_stats_path=credibility_paths["source_stats"],
        club_journalist_stats_path=credibility_paths["club_journalist_stats"],
    )
    return {
        "run_dir": artifacts.run_dir,
        "normalized_articles": artifacts.normalized_articles,
        "claims": artifacts.claims,
        "matches": artifacts.matches,
        "scored_claims": credibility_paths["scored_claims_csv"],
        "journalist_stats": credibility_paths["journalist_stats"],
        "source_stats": credibility_paths["source_stats"],
        "club_journalist_stats": credibility_paths["club_journalist_stats"],
        "base_dataset": artifacts.base_dataset,
        "market_dataset": artifacts.market_dataset,
        "metrics": artifacts.metrics,
        "predictions": artifacts.predictions_dir / "stage6_xgboost_predictions.csv",
        "backtest_summary": backtest_paths["summary"],
        "backtest_trades": backtest_paths["trades"],
        "dashboard": artifacts.dashboard,
    }


def refresh_live_dashboard(
    clubs_by_key: dict[str, Club],
    selected: list[Club],
    *,
    start: date,
    end: date,
    transfers_path: Path,
    provider: str = "all",
    source_keys: Iterable[str] | None = None,
    methods: Iterable[str] = ("provider", "rss"),
    max_records: int = 100,
    page_size: int = 50,
    max_pages: int = 5,
    timeout: int = 45,
    retries: int = 3,
    pause: float = 0.0,
    claim_backend: str = "heuristic",
    stock_source: str = "yahoo",
    refresh_stocks: bool = True,
    train_end_season: str = "2024-25",
    base_scored_claim_paths: Iterable[Path] | None = None,
    stats_claim_paths: Iterable[Path] | None = None,
    stats_match_paths: Iterable[Path] | None = None,
    output_root: Path = DATA_DIR / "live",
    dashboard_output: Path = Path("app") / "static" / "data" / "dashboard_data.json",
) -> dict[str, Path]:
    artifacts = default_artifacts(output_root, start, end, dashboard_output)

    if refresh_stocks:
        fetch_current_stock_cache(selected, start, end, source=stock_source)

    fetch_live_articles(
        selected,
        start=start,
        end=end,
        provider=provider,
        source_keys=source_keys,
        methods=methods,
        output_path=artifacts.normalized_articles,
        max_records=max_records,
        timeout=timeout,
        retries=retries,
        pause=pause,
        resume=False,
    )
    outputs = analyze_live_articles(
        clubs_by_key,
        selected,
        articles_path=artifacts.normalized_articles,
        transfers_path=transfers_path,
        claim_backend=claim_backend,
        train_end_season=train_end_season,
        base_scored_claim_paths=base_scored_claim_paths,
        stats_claim_paths=stats_claim_paths,
        stats_match_paths=stats_match_paths,
        output_root=output_root,
        slug=run_slug(start, end),
        dashboard_output=dashboard_output,
    )
    outputs["fetched_articles"] = artifacts.normalized_articles
    outputs["raw_news"] = artifacts.raw_news
    return outputs
