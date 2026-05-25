from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from .api import create_app
from .agent import DEFAULT_AGENT_OUTPUT_DIR, DEFAULT_DASHBOARD_AGENT, DEFAULT_DASHBOARD_AGENT_REPORT, run_agent
from .analyst import ask_analyst
from .article_store import article_store_stats, normalize_article_file, read_article_store
from .backtesting import backtest_stats, run_backtests
from .briefing import DEFAULT_BRIEFING_JSON, DEFAULT_BRIEFING_MD, generate_daily_briefing
from .claims import claim_stats, extract_claims_from_file, read_claims
from .config import DATA_DIR, load_clubs, load_credibility
from .credibility_engine import credibility_outputs, credibility_stats, read_scored_claims
from .dcaribou import import_dcaribou_transfers
from .demo import demo_payload_stats, write_demo_payload
from .ewenme import DEFAULT_LEAGUES, import_ewenme_transfers
from .event_dates import infer_event_dates
from .event_study import cumulative_abnormal_return, load_bars_if_exists
from .evidence_rag import (
    DEFAULT_BRIEFING,
    DEFAULT_EVIDENCE_INDEX,
    DEFAULT_SCENARIO,
    build_evidence_index,
    retrieve_from_index_file,
)
from .features import article_features, transfer_quality_score
from .ingestion_v2 import fetch_articles_v2
from .indicators import enrich_rumor_events, group_enriched_rumor_events
from .io import append_jsonl, read_csv, read_jsonl, write_csv, write_jsonl
from .market_features import build_market_features, market_feature_stats
from .match_results import fetch_match_results_for_clubs
from .ml import train_and_predict
from .matching import match_claims_file, match_stats, read_matches
from .model import heuristic_market_impact, impact_label
from .ml_v2 import build_stage6_dataset, train_stage6_models
from .live_refresh import analyze_live_articles, fetch_live_articles, refresh_live_dashboard
from .news_sources import SOURCE_PRESETS, load_news_sources, methods_for_preset, select_source_preset, select_sources, source_preset_names
from .http import FetchError, polite_pause
from .news import article_to_row, fetch_gdelt_articles, fetch_gdelt_articles_for_event
from .provider_news import fetch_provider_club_articles, fetch_provider_event_articles
from .report import build_report
from .rumor_events import build_rumor_events
from .scenario_swarm import DEFAULT_DASHBOARD_SCENARIO, DEFAULT_DASHBOARD_SCENARIO_REPORT, run_scenario_swarm
from .stock import fetch_daily, save_price_bars
from .targets import target_stats
from .transfers import clean_transfer_files, filter_loans, load_transfers


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def date_to_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def selected_clubs(clubs: dict[str, object], requested: list[str] | None) -> list[object]:
    if not requested:
        return list(clubs.values())
    lookup: dict[str, object] = {}
    for key, club in clubs.items():
        lookup[key.lower()] = club
        lookup[getattr(club, "name").lower()] = club
        for alias in getattr(club, "aliases"):
            lookup[str(alias).lower()] = club
    chosen = []
    seen = set()
    for item in requested:
        club = lookup.get(item.lower())
        if club is None:
            raise ValueError(f"Unknown club selection: {item}")
        key = getattr(club, "key")
        if key in seen:
            continue
        seen.add(key)
        chosen.append(club)
    return chosen


def cmd_demo(_: argparse.Namespace) -> None:
    transfers = load_transfers(DATA_DIR / "raw" / "sample_transfers.csv")
    rows = []
    for item in transfers:
        quality = transfer_quality_score(item)
        prediction = heuristic_market_impact(0.65, quality, item.direction)
        rows.append(
            {
                "date": item.date.isoformat(),
                "club": item.club,
                "player": item.player,
                "direction": item.direction,
                "season": item.season,
                "transfer_type": item.transfer_type,
                "is_loan": int(item.is_loan),
                "transfer_quality": quality,
                **prediction,
            }
        )
    write_csv(
        DATA_DIR / "processed" / "demo_scores.csv",
        rows,
        [
            "date",
            "season",
            "club",
            "player",
            "direction",
            "transfer_type",
            "is_loan",
            "transfer_quality",
            "predicted_car",
            "label",
            "confidence",
        ],
    )
    print(f"Wrote {len(rows)} demo rows to data/processed/demo_scores.csv")


def cmd_clean_transfers(args: argparse.Namespace) -> None:
    transfers = clean_transfer_files(Path(args.input), Path(args.output), loan_policy=args.loan_policy)
    loans = sum(1 for item in transfers if item.is_loan)
    print(f"Wrote {len(transfers)} cleaned transfers to {args.output} ({loans} loans)")


def cmd_import_ewenme(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    rows = import_ewenme_transfers(
        clubs=clubs,
        raw_dir=Path(args.raw_dir),
        output_path=Path(args.output),
        leagues=args.leagues,
        start_season=args.start_season,
        end_season=args.end_season,
        download=not args.no_download,
        timeout=args.timeout,
        retries=args.retries,
    )
    loans = sum(1 for row in rows if str(row.get("is_loan", "0")) == "1")
    print(f"Wrote {len(rows)} imported ewenme transfer rows to {args.output} ({loans} loans)")


def cmd_import_dcaribou(args: argparse.Namespace) -> None:
    rows = import_dcaribou_transfers(
        configured_clubs=load_clubs(),
        raw_dir=Path(args.raw_dir),
        output_path=Path(args.output),
        start_season=args.start_season,
        end_season=args.end_season,
        download=not args.no_download,
        timeout=args.timeout,
        retries=args.retries,
    )
    print(f"Wrote {len(rows)} exact-date dcaribou transfer rows to {args.output}")


def cmd_fetch_stocks(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    start = parse_date(args.start)
    end = parse_date(args.end)
    stooq_api_key = os.environ.get("STOOQ_API_KEY")
    for club in selected_clubs(clubs, getattr(args, "clubs", None)):
        symbol = club.stooq_symbol if args.source == "stooq" else club.yahoo_symbol
        if not symbol:
            print(f"{club.name}: skipped stock fetch (no {args.source} symbol configured)")
            continue
        bars = fetch_daily(symbol, start, end, source=args.source, stooq_api_key=stooq_api_key)
        out = DATA_DIR / "raw" / "stocks" / f"{club.key}.csv"
        save_price_bars(out, bars)
        print(f"{club.name}: wrote {len(bars)} bars to {out}")

        market_symbol = club.market_index_symbol if args.source == "stooq" else club.yahoo_market_symbol
        if market_symbol:
            index_bars = fetch_daily(market_symbol, start, end, source=args.source, stooq_api_key=stooq_api_key)
            index_out = DATA_DIR / "raw" / "stocks" / f"{club.key}_market.csv"
            save_price_bars(index_out, index_bars)
            print(f"{club.name} market index: wrote {len(index_bars)} bars to {index_out}")


def cmd_fetch_match_results(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    chosen = selected_clubs(clubs, args.clubs)
    outputs = fetch_match_results_for_clubs(
        chosen,
        seasons=args.seasons,
        output_dir=Path(args.output_dir),
        timeout=args.timeout,
        retries=args.retries,
        pause=args.pause,
        resume=args.resume,
    )
    for key, item in outputs.items():
        print(f"{item['club']}: wrote {item['rows']} rows to {item['path']} ({item['new_rows']} fetched)")
        for warning in item.get("warnings", []):
            print(f"- {warning}")


def cmd_ask(args: argparse.Namespace) -> None:
    result = ask_analyst(
        args.question,
        payload_path=Path(args.payload),
        include_evidence=args.with_evidence,
        evidence_index_path=Path(args.evidence_index),
        evidence_top_k=args.evidence_top_k,
    )
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent))


def cmd_build_evidence_index(args: argparse.Namespace) -> None:
    article_paths = [Path(item) for item in args.articles] if args.articles else None
    result = build_evidence_index(
        payload_path=Path(args.payload),
        article_paths=article_paths,
        scenario_path=Path(args.scenario),
        briefing_path=Path(args.briefing),
        output_path=Path(args.output),
    )
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent))


def cmd_query_evidence(args: argparse.Namespace) -> None:
    result = retrieve_from_index_file(Path(args.index), args.question, top_k=args.top_k)
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent))


def cmd_ask_rag(args: argparse.Namespace) -> None:
    index_path = Path(args.index)
    if args.rebuild_index or not index_path.exists():
        article_paths = [Path(item) for item in args.articles] if args.articles else None
        build_evidence_index(
            payload_path=Path(args.payload),
            article_paths=article_paths,
            scenario_path=Path(args.scenario),
            briefing_path=Path(args.briefing),
            output_path=index_path,
        )
    result = ask_analyst(
        args.question,
        payload_path=Path(args.payload),
        include_evidence=True,
        evidence_index_path=index_path,
        evidence_top_k=args.top_k,
    )
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent))


def cmd_agent_run(args: argparse.Namespace) -> None:
    result = run_agent(
        goal=args.goal,
        payload_path=Path(args.payload),
        output_dir=Path(args.output_dir),
        evidence_index=Path(args.evidence_index),
        run_id=args.run_id,
        scenario_policy=args.scenario,
        rounds=args.rounds,
        top_k=args.top_k,
        rebuild_index=not args.no_rebuild_index,
        dashboard_output=None if args.no_dashboard_publish else Path(args.dashboard_agent_output),
        dashboard_report_output=Path(args.dashboard_report_output),
    )
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent))


def cmd_simulate_scenario(args: argparse.Namespace) -> None:
    if not args.question and not args.player:
        raise ValueError("Provide either --question or --player for scenario simulation")
    result = run_scenario_swarm(
        question=args.question,
        player=args.player,
        club=args.club,
        payload_path=Path(args.payload),
        output_dir=Path(args.output_dir),
        rounds=args.rounds,
        simulation_id=args.simulation_id,
        dashboard_output=None if args.no_dashboard_publish else Path(args.dashboard_scenario_output),
        dashboard_report_output=Path(args.dashboard_report_output),
    )
    indent = None if args.compact else 2
    print(json.dumps(result, indent=indent))


def cmd_generate_briefing(args: argparse.Namespace) -> None:
    result = generate_daily_briefing(
        payload_path=Path(args.payload),
        scenario_path=None if args.no_scenario else Path(args.scenario),
        output_markdown=Path(args.output),
        output_json=None if args.no_json else Path(args.json_output),
    )
    print(f"markdown: {result['markdown']}")
    if result.get("json"):
        print(f"json: {result['json']}")


def cmd_fetch_news(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    rows = []
    for club in clubs.values():
        try:
            articles = fetch_gdelt_articles(
                club,
                days=args.days,
                max_records=args.max_records,
                timeout=args.timeout,
                retries=args.retries,
            )
        except FetchError as exc:
            print(f"{club.name}: skipped news fetch ({exc})")
            articles = []
        rows.extend(article_to_row(article) for article in articles)
        print(f"{club.name}: fetched {len(articles)} articles")
        polite_pause(args.pause)
    out = DATA_DIR / "raw" / "news" / "gdelt_articles.jsonl"
    write_jsonl(out, rows)
    print(f"Wrote {len(rows)} articles to {out}")


def cmd_score_news(args: argparse.Namespace) -> None:
    credibility = load_credibility()
    in_path = Path(args.input)
    rows = read_jsonl(in_path)
    scored = []
    for row in rows:
        features = article_features(row, credibility)
        prediction = heuristic_market_impact(float(features["rumor_strength"]))
        scored.append({**features, **prediction})
    out = Path(args.output)
    write_csv(
        out,
        scored,
        [
            "seen_at",
            "published_at",
            "club",
            "player",
            "event_date",
            "source",
            "title",
            "url",
            "snippet",
            "credibility_score",
            "rumor_strength",
            "predicted_car",
            "label",
            "confidence",
        ],
    )
    print(f"Wrote {len(scored)} scored articles to {out}")


def cmd_merge_jsonl(args: argparse.Namespace) -> None:
    rows = []
    seen: set[tuple[object, object, object, object]] = set()
    for input_path in args.inputs:
        for row in read_jsonl(Path(input_path)):
            key = (row.get("published_at"), row.get("club"), row.get("player"), row.get("url"))
            if args.dedupe and key in seen:
                continue
            seen.add(key)
            rows.append(row)
    write_jsonl(Path(args.output), rows)
    print(f"Wrote {len(rows)} merged JSONL rows to {args.output}")


def cmd_build_model_dataset(args: argparse.Namespace) -> None:
    events = read_csv(Path(args.events))
    news_rows = read_csv(Path(args.scored_news)) if Path(args.scored_news).exists() else []
    grouped_news: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in news_rows:
        key = (
            row.get("event_date", ""),
            row.get("club", "").lower(),
            row.get("player", "").lower(),
        )
        grouped_news.setdefault(key, []).append(row)

    rows = []
    for event in events:
        news_event_date = event.get("original_transfer_date") or event.get("date", "")
        key = (
            news_event_date,
            event.get("club", "").lower(),
            event.get("player", "").lower(),
        )
        related_news = grouped_news.get(key, [])
        credibility = [float(row.get("credibility_score") or 0) for row in related_news]
        strength = [float(row.get("rumor_strength") or 0) for row in related_news]
        rumor_count = len(related_news)
        rows.append(
            {
                **event,
                "rumor_count": rumor_count,
                "max_credibility": "" if not credibility else round(max(credibility), 4),
                "avg_credibility": "" if not credibility else round(sum(credibility) / rumor_count, 4),
                "max_rumor_strength": "" if not strength else round(max(strength), 4),
                "avg_rumor_strength": "" if not strength else round(sum(strength) / rumor_count, 4),
            }
        )

    fieldnames = [
        "date",
        "original_transfer_date",
        "event_date_source",
        "event_date_confidence",
        "season",
        "club",
        "player",
        "direction",
        "transfer_type",
        "is_loan",
        "transfer_quality",
        "rumor_count",
        "max_credibility",
        "avg_credibility",
        "max_rumor_strength",
        "avg_rumor_strength",
        "car_m1_p1",
        "label",
    ]
    write_csv(Path(args.output), rows, fieldnames)
    print(f"Wrote {len(rows)} model rows to {args.output}")


def cmd_make_report(args: argparse.Namespace) -> None:
    rows = build_report(Path(args.model_dataset), Path(args.output_csv), Path(args.output_markdown))
    print(f"Wrote {len(rows)} report rows to {args.output_csv}")
    print(f"Wrote readable report to {args.output_markdown}")


def cmd_infer_event_dates(args: argparse.Namespace) -> None:
    rows = infer_event_dates(
        Path(args.transfers),
        Path(args.scored_news),
        Path(args.output),
        min_credibility=args.min_credibility,
    )
    news_dates = sum(1 for row in rows if row.get("event_date_source") == "first_credible_news")
    print(f"Wrote {len(rows)} transfer rows with inferred event dates to {args.output}")
    print(f"Used first credible news date for {news_dates} rows")


def cmd_train_model(args: argparse.Namespace) -> None:
    metrics = train_and_predict(
        Path(args.model_dataset),
        Path(args.predictions),
        Path(args.metrics),
        train_end_season=args.train_end_season,
        model_type=args.model,
        k=args.k,
    )
    print(f"Wrote ML predictions to {args.predictions}")
    print(f"Wrote ML metrics to {args.metrics}")
    print(f"Train accuracy: {metrics['train']['accuracy']}")
    print(f"Test accuracy: {metrics['test']['accuracy']}")


def cmd_build_rumor_events(args: argparse.Namespace) -> None:
    rows = build_rumor_events(
        scored_news_path=Path(args.scored_news),
        transfers_path=Path(args.transfers),
        output_path=Path(args.output),
        clubs=load_clubs(),
    )
    labeled = sum(1 for row in rows if row.get("label"))
    print(f"Wrote {len(rows)} rumor-event rows to {args.output} ({labeled} labeled)")


def cmd_enrich_rumor_events(args: argparse.Namespace) -> None:
    rows = enrich_rumor_events(Path(args.input), Path(args.output), load_clubs())
    print(f"Wrote {len(rows)} enriched rumor-event rows to {args.output}")


def cmd_group_rumor_events(args: argparse.Namespace) -> None:
    rows = group_enriched_rumor_events(Path(args.input), Path(args.output))
    print(f"Wrote {len(rows)} grouped rumor-event rows to {args.output}")


def cmd_build_events(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    club_by_name = {club.name.lower(): club for club in clubs.values()}
    for club in clubs.values():
        for alias in club.aliases:
            club_by_name[alias.lower()] = club

    transfers = filter_loans(load_transfers(Path(args.transfers)), args.loan_policy)
    rows = []
    for item in transfers:
        club = club_by_name.get(item.club.lower())
        if not club:
            continue
        stock_bars = load_bars_if_exists(DATA_DIR / "raw" / "stocks" / f"{club.key}.csv")
        market_bars = load_bars_if_exists(DATA_DIR / "raw" / "stocks" / f"{club.key}_market.csv")
        if not stock_bars or not market_bars:
            car = None
        else:
            car = cumulative_abnormal_return(stock_bars, market_bars, item.date)
        quality = transfer_quality_score(item)
        rows.append(
            {
                "date": item.date.isoformat(),
                "original_transfer_date": item.original_transfer_date or item.date.isoformat(),
                "event_date_source": item.event_date_source or "transfer_source",
                "event_date_confidence": "" if item.event_date_confidence is None else item.event_date_confidence,
                "season": item.season,
                "club": item.club,
                "player": item.player,
                "direction": item.direction,
                "transfer_type": item.transfer_type,
                "is_loan": int(item.is_loan),
                "transfer_quality": quality,
                "car_m1_p1": "" if car is None else car,
                "label": "" if car is None else impact_label(float(car)),
            }
        )
    out = Path(args.output)
    write_csv(
        out,
        rows,
        [
            "date",
            "original_transfer_date",
            "event_date_source",
            "event_date_confidence",
            "season",
            "club",
            "player",
            "direction",
            "transfer_type",
            "is_loan",
            "transfer_quality",
            "car_m1_p1",
            "label",
        ],
    )
    print(f"Wrote {len(rows)} event rows to {out}")


def cmd_fetch_event_news(args: argparse.Namespace) -> None:
    transfers = filter_loans(load_transfers(Path(args.transfers)), args.loan_policy)
    if args.min_fee:
        transfers = [item for item in transfers if (item.transfer_fee_eur or 0) >= args.min_fee]
    if args.sort_by == "fee":
        transfers = sorted(transfers, key=lambda item: item.transfer_fee_eur or 0, reverse=True)
    elif args.sort_by == "market-value":
        transfers = sorted(transfers, key=lambda item: item.market_value_eur or 0, reverse=True)
    if args.start_index:
        transfers = transfers[args.start_index :]
    if args.max_events:
        transfers = transfers[: args.max_events]
    output_path = Path(args.output)
    existing_keys = set()
    if args.resume and output_path.exists():
        for row in read_jsonl(output_path):
            existing_keys.add((row.get("event_date", ""), row.get("club", ""), row.get("player", "")))
    elif output_path.exists():
        output_path.unlink()

    total_articles = 0
    for item in transfers:
        event_key = (item.date.isoformat(), item.club, item.player)
        if event_key in existing_keys:
            print(f"{item.date} {item.club} / {item.player}: already fetched, skipping")
            continue
        start = date_to_utc(item.date - timedelta(days=args.days_before))
        end = date_to_utc(item.date + timedelta(days=args.days_after + 1))
        try:
            articles = fetch_gdelt_articles_for_event(
                club=item.club,
                player=item.player,
                start=start,
                end=end,
                event_date=item.date.isoformat(),
                max_records=args.max_records,
                timeout=args.timeout,
                retries=args.retries,
            )
        except FetchError as exc:
            print(f"{item.date} {item.club} / {item.player}: skipped ({exc})")
            articles = []
        article_rows = [article_to_row(article) for article in articles]
        append_jsonl(output_path, article_rows)
        total_articles += len(article_rows)
        print(f"{item.date} {item.club} / {item.player}: fetched {len(articles)} articles")
        polite_pause(args.pause)
    print(f"Wrote {total_articles} new event-news articles to {args.output}")


def cmd_fetch_provider_event_news(args: argparse.Namespace) -> None:
    transfers = filter_loans(load_transfers(Path(args.transfers)), args.loan_policy)
    if args.min_fee:
        transfers = [item for item in transfers if (item.transfer_fee_eur or 0) >= args.min_fee]
    if args.sort_by == "fee":
        transfers = sorted(transfers, key=lambda item: item.transfer_fee_eur or 0, reverse=True)
    elif args.sort_by == "market-value":
        transfers = sorted(transfers, key=lambda item: item.market_value_eur or 0, reverse=True)
    if args.start_index:
        transfers = transfers[args.start_index :]
    if args.max_events:
        transfers = transfers[: args.max_events]

    output_path = Path(args.output)
    if not args.resume and output_path.exists():
        output_path.unlink()

    providers = ["guardian", "gnews"] if args.provider == "all" else [args.provider]
    total_articles = 0
    for item in transfers:
        start = date_to_utc(item.date - timedelta(days=args.days_before))
        end = date_to_utc(item.date + timedelta(days=args.days_after + 1))
        for provider in providers:
            try:
                articles = fetch_provider_event_articles(
                    provider=provider,
                    club=item.club,
                    player=item.player,
                    start=start,
                    end=end,
                    event_date=item.date.isoformat(),
                    max_records=args.max_records,
                    timeout=args.timeout,
                    retries=args.retries,
                )
            except FetchError as exc:
                print(f"{provider}: {item.date} {item.club} / {item.player}: skipped ({exc})")
                articles = []
            rows = [article_to_row(article) for article in articles]
            append_jsonl(output_path, rows)
            total_articles += len(rows)
            print(f"{provider}: {item.date} {item.club} / {item.player}: fetched {len(rows)} articles")
            polite_pause(args.pause)
    print(f"Wrote {total_articles} provider event-news articles to {args.output}")


def cmd_fetch_provider_club_news(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    start = date_to_utc(parse_date(args.start))
    end = date_to_utc(parse_date(args.end))
    output_path = Path(args.output)
    if not args.resume and output_path.exists():
        output_path.unlink()

    providers = ["guardian", "gnews"] if args.provider == "all" else [args.provider]
    total_articles = 0
    for club in selected_clubs(clubs, args.clubs):
        for provider in providers:
            try:
                articles = fetch_provider_club_articles(
                    provider=provider,
                    club=club.name,
                    aliases=club.aliases,
                    start=start,
                    end=end + timedelta(days=1),
                    max_records=args.max_records,
                    page_size=args.page_size,
                    max_pages=args.max_pages,
                    timeout=args.timeout,
                    retries=args.retries,
                )
            except FetchError as exc:
                print(f"{provider}: {club.name}: skipped ({exc})")
                articles = []
            rows = [article_to_row(article) for article in articles]
            append_jsonl(output_path, rows)
            total_articles += len(rows)
            print(f"{provider}: {club.name}: fetched {len(rows)} articles")
            polite_pause(args.pause)
    print(f"Wrote {total_articles} provider club-news articles to {args.output}")


def cmd_fetch_news_v2(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    chosen_clubs = selected_clubs(clubs, args.clubs)
    all_sources = load_news_sources()
    sources = select_sources(all_sources, args.sources) if args.sources else select_source_preset(all_sources, getattr(args, "source_preset", None))
    methods = args.methods
    if getattr(args, "source_preset", None) and methods == ["provider", "rss"]:
        preset_methods = methods_for_preset(args.source_preset)
        if preset_methods is not None:
            methods = preset_methods
    result = fetch_articles_v2(
        clubs=chosen_clubs,
        sources=sources,
        start=parse_date(args.start),
        end=parse_date(args.end),
        output_path=Path(args.output),
        max_records=args.max_records,
        methods=methods,
        timeout=args.timeout,
        retries=args.retries,
        pause=args.pause,
        resume=args.resume,
    )
    print(f"Wrote {len(result.rows)} normalized article rows to {args.output}")
    print(f"Fetched {result.fetched_rows} new rows and skipped {result.skipped_duplicates} duplicates")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


def cmd_normalize_articles(args: argparse.Namespace) -> None:
    rows = normalize_article_file(
        Path(args.input),
        Path(args.output),
        load_clubs(),
        crawl_method=args.crawl_method,
        provider=args.provider,
        dedupe=not args.no_dedupe,
    )
    print(f"Wrote {len(rows)} normalized article rows to {args.output}")


def cmd_inspect_ingestion(args: argparse.Namespace) -> None:
    rows = read_article_store(Path(args.input))
    stats = article_store_stats(rows)
    print(f"Rows: {stats['n_rows']}")
    print(f"Unique: {stats['n_unique']}")
    print(f"Duplicates: {stats['duplicate_rows']}")
    print("Top sources:")
    for source, count in list(stats["sources"].items())[:10]:
        print(f"- {source}: {count}")
    print("Methods:")
    for method, count in stats["methods"].items():
        print(f"- {method}: {count}")


def cmd_extract_claims(args: argparse.Namespace) -> None:
    claims = extract_claims_from_file(
        Path(args.input),
        Path(args.output),
        load_clubs(),
        transfers_path=Path(args.transfers) if args.transfers else None,
        backend=args.backend,
    )
    print(f"Wrote {len(claims)} extracted claim rows to {args.output}")


def cmd_inspect_claims(args: argparse.Namespace) -> None:
    rows = read_claims(Path(args.input))
    stats = claim_stats(rows)
    print(f"Rows: {stats['n_rows']}")
    print(f"Transfer-related: {stats['transfer_related']}")
    print("Stages:")
    for stage, count in stats["stages"].items():
        print(f"- {stage}: {count}")
    print("Directions:")
    for direction, count in stats["directions"].items():
        print(f"- {direction}: {count}")
    print("Backends:")
    for backend, count in stats["backends"].items():
        print(f"- {backend}: {count}")


def cmd_match_claims(args: argparse.Namespace) -> None:
    rows = match_claims_file(
        Path(args.claims),
        Path(args.transfers),
        Path(args.output),
        load_clubs(),
        min_score=args.min_score,
        ambiguity_delta=args.ambiguity_delta,
    )
    matched = sum(1 for row in rows if row.get("matched_transfer_id"))
    ambiguous = sum(1 for row in rows if str(row.get("ambiguity_flag", "")) == "1")
    print(f"Wrote {len(rows)} matched claim rows to {args.output}")
    print(f"Matched: {matched}")
    print(f"Ambiguous: {ambiguous}")


def cmd_inspect_matches(args: argparse.Namespace) -> None:
    rows = read_matches(Path(args.input))
    stats = match_stats(rows)
    print(f"Rows: {stats['n_rows']}")
    print(f"Matched: {stats['matched']}")
    print(f"Unmatched: {stats['unmatched']}")
    print(f"Ambiguous: {stats['ambiguous']}")
    print("Top reasons:")
    for reason, count in list(stats["reasons"].items())[:10]:
        print(f"- {reason}: {count}")


def cmd_score_credibility(args: argparse.Namespace) -> None:
    outputs = credibility_outputs(
        Path(args.claims),
        Path(args.matches),
        Path(args.transfers),
        Path(args.output_dir),
        stats_claim_paths=[Path(item) for item in getattr(args, "stats_claims", [])],
        stats_match_paths=[Path(item) for item in getattr(args, "stats_matches", [])],
    )
    for label, path in outputs.items():
        print(f"{label}: {path}")


def cmd_inspect_credibility(args: argparse.Namespace) -> None:
    rows = read_scored_claims(Path(args.input))
    stats = credibility_stats(rows)
    print(f"Rows: {stats['n_rows']}")
    print(f"Average credibility score: {stats['avg_credibility_score']}")
    print("Article types:")
    for kind, count in stats["article_types"].items():
        print(f"- {kind}: {count}")


def cmd_build_market_features(args: argparse.Namespace) -> None:
    rows = build_market_features(
        Path(args.input),
        Path(args.output),
        load_clubs(),
        estimation_days=args.estimation_days,
        gap_days=args.gap_days,
        lookback_days=args.lookback_days,
    )
    print(f"Wrote {len(rows)} market-feature rows to {args.output}")


def cmd_inspect_market_features(args: argparse.Namespace) -> None:
    rows = read_csv(Path(args.input))
    stats = market_feature_stats(rows)
    print(f"Rows: {stats['n_rows']}")
    print(f"Rows with target p3: {stats['rows_with_target_p3']}")
    print(f"Average absolute target p3: {stats['avg_abs_target_p3']}")
    print("Statuses:")
    for status, count in stats["status_counts"].items():
        print(f"- {status}: {count}")


def cmd_build_stage6_dataset(args: argparse.Namespace) -> None:
    rows = build_stage6_dataset(
        [Path(item) for item in args.scored_claims],
        Path(args.transfers),
        Path(args.base_output),
        Path(args.output),
        load_clubs(),
    )
    print(f"Wrote {len(rows)} Stage 6 market-labeled rows to {args.output}")
    stats = target_stats(rows)
    print(f"Prediction scopes: {stats['prediction_scope_counts']}")
    print(f"Target roles: {stats['target_role_counts']}")
    print(f"Distinct target clubs: {stats['distinct_target_clubs']}")


def cmd_train_model_v2(args: argparse.Namespace) -> None:
    metrics = train_stage6_models(
        Path(args.dataset),
        Path(args.metrics),
        Path(args.predictions_dir),
        train_end_season=args.train_end_season,
        target_label_field=args.target_label_field,
    )
    print(f"Wrote Stage 6 metrics to {args.metrics}")
    for name, path in metrics.get("prediction_files", {}).items():
        print(f"{name}_predictions: {path}")


def cmd_run_backtests(args: argparse.Namespace) -> None:
    outputs = run_backtests(
        Path(args.predictions),
        Path(args.output_dir),
        load_clubs(),
        holding_days=args.holding_days,
        positive_threshold=args.positive_threshold,
        negative_threshold=args.negative_threshold,
        credibility_threshold=args.credibility_threshold,
        stocks_dir=Path(args.stocks_dir),
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")


def cmd_inspect_backtests(args: argparse.Namespace) -> None:
    stats = backtest_stats(Path(args.input))
    print(f"Rows: {stats['rows']}")
    print(f"Rows with trades: {stats['ok_rows']}")
    print(f"Best strategy: {stats['best_strategy']}")


def cmd_build_demo_data(args: argparse.Namespace) -> None:
    payload = write_demo_payload(
        Path(args.predictions),
        Path(args.metrics),
        Path(args.backtest_summary),
        Path(args.backtest_trades),
        Path(args.output),
        transfers_path=Path(args.transfers),
        journalist_stats_path=Path(args.journalist_stats) if args.journalist_stats else None,
        source_stats_path=Path(args.source_stats) if args.source_stats else None,
        club_journalist_stats_path=Path(args.club_journalist_stats) if args.club_journalist_stats else None,
    )
    print(
        f"Wrote dashboard payload with {len(payload['current_signals'])} latest-season signals "
        f"across {len(payload.get('available_seasons', []))} seasons to {args.output}"
    )


def cmd_refresh_live_dashboard(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    selected = selected_clubs(clubs, args.clubs)
    source_keys = args.sources
    if not source_keys and getattr(args, "source_preset", None):
        source_keys = list(SOURCE_PRESETS[args.source_preset])
    methods = args.methods
    if getattr(args, "source_preset", None) and methods == ["provider", "rss"]:
        preset_methods = methods_for_preset(args.source_preset)
        if preset_methods is not None:
            methods = preset_methods
    outputs = refresh_live_dashboard(
        clubs,
        selected,
        start=parse_date(args.start),
        end=parse_date(args.end),
        transfers_path=Path(args.transfers),
        provider=args.provider,
        source_keys=source_keys,
        methods=methods,
        max_records=args.max_records,
        page_size=args.page_size,
        max_pages=args.max_pages,
        timeout=args.timeout,
        retries=args.retries,
        pause=args.pause,
        claim_backend=args.backend,
        stock_source=args.stock_source,
        refresh_stocks=not args.no_refresh_stocks,
        train_end_season=args.train_end_season,
        base_scored_claim_paths=[Path(item) for item in args.base_scored_claims],
        stats_claim_paths=[Path(item) for item in args.stats_claims],
        stats_match_paths=[Path(item) for item in args.stats_matches],
        output_root=Path(args.output_root),
        dashboard_output=Path(args.dashboard_output),
    )
    for label, path in outputs.items():
        print(f"{label}: {path}")


def cmd_refresh_live_fetch(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    selected = selected_clubs(clubs, args.clubs)
    source_keys = args.sources
    if not source_keys and getattr(args, "source_preset", None):
        source_keys = list(SOURCE_PRESETS[args.source_preset])
    methods = args.methods
    if getattr(args, "source_preset", None) and methods == ["provider", "rss"]:
        preset_methods = methods_for_preset(args.source_preset)
        if preset_methods is not None:
            methods = preset_methods
    result = fetch_live_articles(
        selected,
        start=parse_date(args.start),
        end=parse_date(args.end),
        provider=args.provider,
        source_keys=source_keys,
        methods=methods,
        output_path=Path(args.output),
        max_records=args.max_records,
        timeout=args.timeout,
        retries=args.retries,
        pause=args.pause,
        resume=args.resume,
    )
    print(f"Wrote {len(result.rows)} normalized article rows to {args.output}")
    print(f"Fetched {result.fetched_rows} new rows and skipped {result.skipped_duplicates} duplicates")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


def cmd_refresh_live_analyze(args: argparse.Namespace) -> None:
    clubs = load_clubs()
    selected = selected_clubs(clubs, args.clubs)
    outputs = analyze_live_articles(
        clubs,
        selected,
        articles_path=Path(args.input),
        transfers_path=Path(args.transfers),
        claim_backend=args.backend,
        train_end_season=args.train_end_season,
        base_scored_claim_paths=[Path(item) for item in args.base_scored_claims],
        stats_claim_paths=[Path(item) for item in args.stats_claims],
        stats_match_paths=[Path(item) for item in args.stats_matches],
        output_root=Path(args.output_root),
        slug=args.slug,
        dashboard_output=Path(args.dashboard_output),
    )
    for label, path in outputs.items():
        print(f"{label}: {path}")


def cmd_serve_api(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("uvicorn is not installed. Install it with: pip install -e '.[api_server]'") from exc
    app = create_app(Path(args.payload))
    uvicorn.run(app, host=args.host, port=args.port)


def cmd_inspect_demo_data(args: argparse.Namespace) -> None:
    stats = demo_payload_stats(Path(args.input))
    print(f"Signals: {stats['signals']}")
    print(f"Latest season: {stats['latest_season']}")
    print(f"Seasons: {stats['seasons']}")
    print(f"Best backtest strategy: {stats['best_backtest_strategy']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transfer and football-club stock research pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run a local demo using bundled sample transfer rows")
    demo.set_defaults(func=cmd_demo)

    clean = sub.add_parser("clean-transfers", help="Combine raw transfer CSVs and add season/loan fields")
    clean.add_argument("--input", default=str(DATA_DIR / "raw" / "transfers"))
    clean.add_argument("--output", default=str(DATA_DIR / "processed" / "transfers_clean.csv"))
    clean.add_argument("--loan-policy", choices=["include", "exclude", "only"], default="include")
    clean.set_defaults(func=cmd_clean_transfers)

    ewenme = sub.add_parser("import-ewenme-transfers", help="Import public ewenme/transfers league CSVs")
    ewenme.add_argument("--raw-dir", default=str(DATA_DIR / "raw" / "external" / "ewenme"))
    ewenme.add_argument("--output", default=str(DATA_DIR / "raw" / "transfers" / "ewenme_public_clubs.csv"))
    ewenme.add_argument("--leagues", nargs="+", default=DEFAULT_LEAGUES)
    ewenme.add_argument("--start-season", default="2021-22")
    ewenme.add_argument("--end-season", default="2025-26")
    ewenme.add_argument("--no-download", action="store_true")
    ewenme.add_argument("--timeout", type=int, default=60)
    ewenme.add_argument("--retries", type=int, default=3)
    ewenme.set_defaults(func=cmd_import_ewenme)

    dcaribou = sub.add_parser("import-dcaribou-transfers", help="Import exact-date dcaribou Transfermarkt dataset")
    dcaribou.add_argument("--raw-dir", default=str(DATA_DIR / "raw" / "external" / "dcaribou"))
    dcaribou.add_argument("--output", default=str(DATA_DIR / "raw" / "transfers" / "dcaribou_exact_public_clubs.csv"))
    dcaribou.add_argument("--start-season", default="2021-22")
    dcaribou.add_argument("--end-season", default="2025-26")
    dcaribou.add_argument("--no-download", action="store_true")
    dcaribou.add_argument("--timeout", type=int, default=60)
    dcaribou.add_argument("--retries", type=int, default=3)
    dcaribou.set_defaults(func=cmd_import_dcaribou)

    stocks = sub.add_parser("fetch-stocks", help="Download daily stock prices")
    default_end = date.today()
    default_start = default_end - timedelta(days=365 * 3)
    stocks.add_argument("--start", default=default_start.isoformat())
    stocks.add_argument("--end", default=default_end.isoformat())
    stocks.add_argument("--source", choices=["yahoo", "stooq"], default="yahoo")
    stocks.add_argument("--clubs", nargs="*")
    stocks.set_defaults(func=cmd_fetch_stocks)

    match_results = sub.add_parser("fetch-match-results", help="Fetch no-key football match results into dashboard overlay CSVs")
    match_results.add_argument("--seasons", nargs="+", default=["2025-26"])
    match_results.add_argument("--clubs", nargs="*")
    match_results.add_argument("--output-dir", default=str(DATA_DIR / "raw" / "matches"))
    match_results.add_argument("--timeout", type=int, default=45)
    match_results.add_argument("--retries", type=int, default=2)
    match_results.add_argument("--pause", type=float, default=0.1)
    match_results.add_argument("--resume", action="store_true")
    match_results.set_defaults(func=cmd_fetch_match_results)

    news = sub.add_parser("fetch-news", help="Fetch transfer-related articles from GDELT")
    news.add_argument("--days", type=int, default=14)
    news.add_argument("--max-records", type=int, default=50)
    news.add_argument("--pause", type=float, default=1.0)
    news.add_argument("--timeout", type=int, default=45)
    news.add_argument("--retries", type=int, default=3)
    news.set_defaults(func=cmd_fetch_news)

    score_news = sub.add_parser("score-news", help="Score fetched news articles")
    score_news.add_argument("--input", default=str(DATA_DIR / "raw" / "news" / "gdelt_articles.jsonl"))
    score_news.add_argument("--output", default=str(DATA_DIR / "processed" / "scored_news.csv"))
    score_news.set_defaults(func=cmd_score_news)

    merge_jsonl = sub.add_parser("merge-jsonl", help="Merge JSONL article files")
    merge_jsonl.add_argument("--output", required=True)
    merge_jsonl.add_argument("--inputs", nargs="+", required=True)
    merge_jsonl.add_argument("--dedupe", action="store_true")
    merge_jsonl.set_defaults(func=cmd_merge_jsonl)

    events = sub.add_parser("build-events", help="Compute event-study labels for transfer rows")
    events.add_argument("--transfers", default=str(DATA_DIR / "raw" / "transfers.csv"))
    events.add_argument("--output", default=str(DATA_DIR / "processed" / "transfer_events.csv"))
    events.add_argument("--loan-policy", choices=["include", "exclude", "only"], default="include")
    events.set_defaults(func=cmd_build_events)

    event_dates = sub.add_parser("infer-event-dates", help="Replace proxy transfer dates with earliest credible news dates when available")
    event_dates.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_clean.csv"))
    event_dates.add_argument("--scored-news", default=str(DATA_DIR / "processed" / "scored_event_news.csv"))
    event_dates.add_argument("--output", default=str(DATA_DIR / "processed" / "transfers_event_dates.csv"))
    event_dates.add_argument("--min-credibility", type=float, default=0.5)
    event_dates.set_defaults(func=cmd_infer_event_dates)

    event_news = sub.add_parser("fetch-event-news", help="Fetch historical news around known transfer events")
    event_news.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_clean.csv"))
    event_news.add_argument("--output", default=str(DATA_DIR / "raw" / "news" / "event_news.jsonl"))
    event_news.add_argument("--days-before", type=int, default=30)
    event_news.add_argument("--days-after", type=int, default=3)
    event_news.add_argument("--max-records", type=int, default=25)
    event_news.add_argument("--max-events", type=int, default=0)
    event_news.add_argument("--start-index", type=int, default=0)
    event_news.add_argument("--min-fee", type=float, default=0.0)
    event_news.add_argument("--sort-by", choices=["date", "fee", "market-value"], default="date")
    event_news.add_argument("--pause", type=float, default=1.0)
    event_news.add_argument("--timeout", type=int, default=45)
    event_news.add_argument("--retries", type=int, default=3)
    event_news.add_argument("--resume", action="store_true")
    event_news.add_argument("--loan-policy", choices=["include", "exclude", "only"], default="include")
    event_news.set_defaults(func=cmd_fetch_event_news)

    provider_news = sub.add_parser("fetch-provider-event-news", help="Fetch event news from Guardian/GNews APIs")
    provider_news.add_argument("--provider", choices=["guardian", "gnews", "all"], default="guardian")
    provider_news.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    provider_news.add_argument("--output", default=str(DATA_DIR / "raw" / "news" / "provider_event_news.jsonl"))
    provider_news.add_argument("--days-before", type=int, default=30)
    provider_news.add_argument("--days-after", type=int, default=3)
    provider_news.add_argument("--max-records", type=int, default=10)
    provider_news.add_argument("--max-events", type=int, default=0)
    provider_news.add_argument("--start-index", type=int, default=0)
    provider_news.add_argument("--min-fee", type=float, default=0.0)
    provider_news.add_argument("--sort-by", choices=["date", "fee", "market-value"], default="date")
    provider_news.add_argument("--pause", type=float, default=1.0)
    provider_news.add_argument("--timeout", type=int, default=45)
    provider_news.add_argument("--retries", type=int, default=3)
    provider_news.add_argument("--resume", action="store_true")
    provider_news.add_argument("--loan-policy", choices=["include", "exclude", "only"], default="include")
    provider_news.set_defaults(func=cmd_fetch_provider_event_news)

    provider_club_news = sub.add_parser("fetch-provider-club-news", help="Fetch broader club transfer news from Guardian/GNews")
    provider_club_news.add_argument("--provider", choices=["guardian", "gnews", "all"], default="guardian")
    provider_club_news.add_argument("--start", required=True)
    provider_club_news.add_argument("--end", default=date.today().isoformat())
    provider_club_news.add_argument("--clubs", nargs="*")
    provider_club_news.add_argument("--output", default=str(DATA_DIR / "raw" / "news" / "provider_club_news.jsonl"))
    provider_club_news.add_argument("--max-records", type=int, default=100)
    provider_club_news.add_argument("--page-size", type=int, default=50)
    provider_club_news.add_argument("--max-pages", type=int, default=5)
    provider_club_news.add_argument("--pause", type=float, default=1.0)
    provider_club_news.add_argument("--timeout", type=int, default=45)
    provider_club_news.add_argument("--retries", type=int, default=3)
    provider_club_news.add_argument("--resume", action="store_true")
    provider_club_news.set_defaults(func=cmd_fetch_provider_club_news)

    news_v2 = sub.add_parser("fetch-news-v2", help="Fetch and normalize articles into the v2 article store")
    default_end = date.today()
    default_start = default_end - timedelta(days=30)
    news_v2.add_argument("--start", default=default_start.isoformat())
    news_v2.add_argument("--end", default=default_end.isoformat())
    news_v2.add_argument("--clubs", nargs="*")
    news_v2.add_argument("--sources", nargs="*")
    news_v2.add_argument("--source-preset", choices=source_preset_names())
    news_v2.add_argument("--methods", nargs="+", default=["provider", "rss"])
    news_v2.add_argument("--output", default=str(DATA_DIR / "raw" / "articles" / "articles_v2.jsonl"))
    news_v2.add_argument("--max-records", type=int, default=50)
    news_v2.add_argument("--pause", type=float, default=1.0)
    news_v2.add_argument("--timeout", type=int, default=45)
    news_v2.add_argument("--retries", type=int, default=3)
    news_v2.add_argument("--resume", action="store_true")
    news_v2.set_defaults(func=cmd_fetch_news_v2)

    normalize_articles = sub.add_parser("normalize-articles", help="Normalize raw JSONL article rows into the v2 article store")
    normalize_articles.add_argument("--input", required=True)
    normalize_articles.add_argument("--output", required=True)
    normalize_articles.add_argument("--crawl-method", default="")
    normalize_articles.add_argument("--provider", default="")
    normalize_articles.add_argument("--no-dedupe", action="store_true")
    normalize_articles.set_defaults(func=cmd_normalize_articles)

    inspect = sub.add_parser("inspect-ingestion", help="Inspect source/method counts in a normalized article file")
    inspect.add_argument("--input", required=True)
    inspect.set_defaults(func=cmd_inspect_ingestion)

    claims = sub.add_parser("extract-claims", help="Extract structured transfer claims from normalized article rows")
    claims.add_argument("--input", default=str(DATA_DIR / "raw" / "articles" / "articles_v2.jsonl"))
    claims.add_argument("--output", default=str(DATA_DIR / "processed" / "claims" / "claims_v1.jsonl"))
    claims.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    claims.add_argument("--backend", choices=["auto", "heuristic", "dspy"], default="auto")
    claims.set_defaults(func=cmd_extract_claims)

    inspect_claims = sub.add_parser("inspect-claims", help="Inspect extracted structured claim rows")
    inspect_claims.add_argument("--input", required=True)
    inspect_claims.set_defaults(func=cmd_inspect_claims)

    match_claims = sub.add_parser("match-claims", help="Match extracted claims to likely transfer candidates")
    match_claims.add_argument("--claims", default=str(DATA_DIR / "processed" / "claims" / "claims_v1.jsonl"))
    match_claims.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    match_claims.add_argument("--output", default=str(DATA_DIR / "processed" / "matched_claims" / "matched_claims_v1.csv"))
    match_claims.add_argument("--min-score", type=float, default=0.45)
    match_claims.add_argument("--ambiguity-delta", type=float, default=0.07)
    match_claims.set_defaults(func=cmd_match_claims)

    inspect_matches = sub.add_parser("inspect-matches", help="Inspect matched-claim outputs")
    inspect_matches.add_argument("--input", required=True)
    inspect_matches.set_defaults(func=cmd_inspect_matches)

    score_cred = sub.add_parser("score-credibility", help="Build learned credibility features and scored claims")
    score_cred.add_argument("--claims", default=str(DATA_DIR / "processed" / "claims" / "claims_v1.jsonl"))
    score_cred.add_argument("--matches", default=str(DATA_DIR / "processed" / "matched_claims" / "matched_claims_v1.csv"))
    score_cred.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    score_cred.add_argument("--output-dir", default=str(DATA_DIR / "processed" / "credibility"))
    score_cred.add_argument("--stats-claims", nargs="*", default=[])
    score_cred.add_argument("--stats-matches", nargs="*", default=[])
    score_cred.set_defaults(func=cmd_score_credibility)

    inspect_cred = sub.add_parser("inspect-credibility", help="Inspect scored credibility outputs")
    inspect_cred.add_argument("--input", required=True)
    inspect_cred.set_defaults(func=cmd_inspect_credibility)

    market = sub.add_parser("build-market-features", help="Build richer pre/post rumor stock-market research features")
    market.add_argument("--input", default=str(DATA_DIR / "processed" / "rumor_events_grouped.csv"))
    market.add_argument("--output", default=str(DATA_DIR / "processed" / "market_features" / "rumor_events_grouped_market.csv"))
    market.add_argument("--estimation-days", type=int, default=120)
    market.add_argument("--gap-days", type=int, default=5)
    market.add_argument("--lookback-days", type=int, default=20)
    market.set_defaults(func=cmd_build_market_features)

    inspect_market = sub.add_parser("inspect-market-features", help="Inspect richer market-feature outputs")
    inspect_market.add_argument("--input", required=True)
    inspect_market.set_defaults(func=cmd_inspect_market_features)

    stage6_data = sub.add_parser("build-stage6-dataset", help="Build a claim-level Stage 6 modeling dataset with market features")
    stage6_data.add_argument(
        "--scored-claims",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "scored_claims.csv"),
            str(DATA_DIR / "processed" / "credibility" / "provider_event_news_2025_26_top50" / "scored_claims.csv"),
        ],
    )
    stage6_data.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    stage6_data.add_argument("--base-output", default=str(DATA_DIR / "processed" / "modeling" / "stage6_claims_base.csv"))
    stage6_data.add_argument("--output", default=str(DATA_DIR / "processed" / "modeling" / "stage6_claims_market.csv"))
    stage6_data.set_defaults(func=cmd_build_stage6_dataset)

    train_v2 = sub.add_parser("train-model-v2", help="Train Stage 6 temporal tabular models")
    train_v2.add_argument("--dataset", default=str(DATA_DIR / "processed" / "modeling" / "stage6_claims_market.csv"))
    train_v2.add_argument("--predictions-dir", default=str(DATA_DIR / "models" / "stage6"))
    train_v2.add_argument("--metrics", default=str(DATA_DIR / "models" / "stage6" / "metrics_stage6.json"))
    train_v2.add_argument("--train-end-season", default="2024-25")
    train_v2.add_argument("--target-label-field", default="target_label_p3")
    train_v2.set_defaults(func=cmd_train_model_v2)

    backtest = sub.add_parser("run-backtests", help="Backtest Stage 6 rumor-impact signals with vectorbt-based portfolio metrics")
    backtest.add_argument("--predictions", default=str(DATA_DIR / "models" / "stage6" / "stage6_xgboost_predictions.csv"))
    backtest.add_argument("--output-dir", default=str(DATA_DIR / "reports" / "backtests"))
    backtest.add_argument("--stocks-dir", default=str(DATA_DIR / "raw" / "stocks"))
    backtest.add_argument("--holding-days", type=int, default=3)
    backtest.add_argument("--positive-threshold", type=float, default=0.55)
    backtest.add_argument("--negative-threshold", type=float, default=0.55)
    backtest.add_argument("--credibility-threshold", type=float, default=0.65)
    backtest.set_defaults(func=cmd_run_backtests)

    inspect_backtests = sub.add_parser("inspect-backtests", help="Inspect Stage 7 backtest summary output")
    inspect_backtests.add_argument("--input", default=str(DATA_DIR / "reports" / "backtests" / "backtest_summary.csv"))
    inspect_backtests.set_defaults(func=cmd_inspect_backtests)

    demo_data = sub.add_parser("build-demo-data", help="Build the Stage 8 dashboard payload JSON")
    demo_data.add_argument("--predictions", default=str(DATA_DIR / "models" / "stage6" / "stage6_xgboost_predictions.csv"))
    demo_data.add_argument("--metrics", default=str(DATA_DIR / "models" / "stage6" / "metrics_stage6.json"))
    demo_data.add_argument("--backtest-summary", default=str(DATA_DIR / "reports" / "backtests" / "backtest_summary.csv"))
    demo_data.add_argument("--backtest-trades", default=str(DATA_DIR / "reports" / "backtests" / "backtest_trades.csv"))
    demo_data.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    demo_data.add_argument("--journalist-stats", default=str(DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "journalist_stats.csv"))
    demo_data.add_argument("--source-stats", default=str(DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "source_stats.csv"))
    demo_data.add_argument("--club-journalist-stats", default=str(DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "club_journalist_stats.csv"))
    demo_data.add_argument("--output", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    demo_data.set_defaults(func=cmd_build_demo_data)

    live = sub.add_parser("refresh-live-dashboard", help="Fetch current provider news, score it, retrain Stage 6, and rebuild the dashboard")
    live_default_end = date.today()
    live_default_start = live_default_end - timedelta(days=21)
    live.add_argument("--start", default=live_default_start.isoformat())
    live.add_argument("--end", default=live_default_end.isoformat())
    live.add_argument("--clubs", nargs="*")
    live.add_argument("--provider", choices=["guardian", "gnews", "all"], default="all")
    live.add_argument("--sources", nargs="*")
    live.add_argument("--source-preset", choices=source_preset_names())
    live.add_argument("--methods", nargs="+", default=["provider", "rss"])
    live.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    live.add_argument(
        "--base-scored-claims",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "scored_claims.csv"),
            str(DATA_DIR / "processed" / "credibility" / "provider_event_news_2025_26_top50" / "scored_claims.csv"),
        ],
    )
    live.add_argument(
        "--stats-claims",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "claims" / "historical_event_news_2021_25_claims.jsonl"),
            str(DATA_DIR / "processed" / "claims" / "provider_event_news_2025_26_top50_claims.jsonl"),
        ],
    )
    live.add_argument(
        "--stats-matches",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "matched_claims" / "historical_event_news_2021_25_matches.csv"),
            str(DATA_DIR / "processed" / "matched_claims" / "provider_event_news_2025_26_top50_matches.csv"),
        ],
    )
    live.add_argument("--max-records", type=int, default=100)
    live.add_argument("--page-size", type=int, default=50)
    live.add_argument("--max-pages", type=int, default=5)
    live.add_argument("--pause", type=float, default=1.0)
    live.add_argument("--timeout", type=int, default=45)
    live.add_argument("--retries", type=int, default=3)
    live.add_argument("--backend", choices=["auto", "heuristic", "dspy"], default="heuristic")
    live.add_argument("--stock-source", choices=["yahoo", "stooq"], default="yahoo")
    live.add_argument("--no-refresh-stocks", action="store_true")
    live.add_argument("--train-end-season", default="2024-25")
    live.add_argument("--output-root", default=str(DATA_DIR / "live"))
    live.add_argument("--dashboard-output", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    live.set_defaults(func=cmd_refresh_live_dashboard)

    live_fetch = sub.add_parser("refresh-live-fetch", help="Fetch current articles only and write a normalized article store")
    live_fetch_default_end = date.today()
    live_fetch_default_start = live_fetch_default_end - timedelta(days=21)
    live_fetch.add_argument("--start", default=live_fetch_default_start.isoformat())
    live_fetch.add_argument("--end", default=live_fetch_default_end.isoformat())
    live_fetch.add_argument("--clubs", nargs="*")
    live_fetch.add_argument("--provider", choices=["guardian", "gnews", "all"], default="all")
    live_fetch.add_argument("--sources", nargs="*")
    live_fetch.add_argument("--source-preset", choices=source_preset_names())
    live_fetch.add_argument("--methods", nargs="+", default=["provider", "rss"])
    live_fetch.add_argument("--output", default=str(DATA_DIR / "raw" / "articles" / "current_live.jsonl"))
    live_fetch.add_argument("--max-records", type=int, default=25)
    live_fetch.add_argument("--pause", type=float, default=0.1)
    live_fetch.add_argument("--timeout", type=int, default=45)
    live_fetch.add_argument("--retries", type=int, default=3)
    live_fetch.add_argument("--resume", action="store_true")
    live_fetch.set_defaults(func=cmd_refresh_live_fetch)

    live_analyze = sub.add_parser("refresh-live-analyze", help="Analyze a normalized live article file and rebuild the dashboard")
    live_analyze.add_argument("--input", default=str(DATA_DIR / "raw" / "articles" / "current_live.jsonl"))
    live_analyze.add_argument("--clubs", nargs="*")
    live_analyze.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    live_analyze.add_argument(
        "--base-scored-claims",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "scored_claims.csv"),
            str(DATA_DIR / "processed" / "credibility" / "provider_event_news_2025_26_top50" / "scored_claims.csv"),
        ],
    )
    live_analyze.add_argument(
        "--stats-claims",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "claims" / "historical_event_news_2021_25_claims.jsonl"),
            str(DATA_DIR / "processed" / "claims" / "provider_event_news_2025_26_top50_claims.jsonl"),
        ],
    )
    live_analyze.add_argument(
        "--stats-matches",
        nargs="+",
        default=[
            str(DATA_DIR / "processed" / "matched_claims" / "historical_event_news_2021_25_matches.csv"),
            str(DATA_DIR / "processed" / "matched_claims" / "provider_event_news_2025_26_top50_matches.csv"),
        ],
    )
    live_analyze.add_argument("--backend", choices=["auto", "heuristic", "dspy"], default="heuristic")
    live_analyze.add_argument("--train-end-season", default="2024-25")
    live_analyze.add_argument("--output-root", default=str(DATA_DIR / "live"))
    live_analyze.add_argument("--slug", default="live_manual")
    live_analyze.add_argument("--dashboard-output", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    live_analyze.set_defaults(func=cmd_refresh_live_analyze)

    api = sub.add_parser("serve-api", help="Serve a small FastAPI interface over the dashboard payload")
    api.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8010)
    api.set_defaults(func=cmd_serve_api)

    ask = sub.add_parser("ask", help="Ask the local transfer-stock analyst a grounded question")
    ask.add_argument("--question", required=True)
    ask.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    ask.add_argument("--with-evidence", action="store_true", help="Attach local Evidence RAG citations to the analyst answer")
    ask.add_argument("--evidence-index", default=str(DEFAULT_EVIDENCE_INDEX), help="Path to an existing evidence index")
    ask.add_argument("--evidence-top-k", type=int, default=5, help="Number of evidence citations to attach")
    ask.add_argument("--compact", action="store_true", help="Print compact JSON instead of pretty JSON")
    ask.set_defaults(func=cmd_ask)

    evidence_index = sub.add_parser("build-evidence-index", help="Build a local Evidence RAG index from dashboard/articles/reports")
    evidence_index.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    evidence_index.add_argument("--articles", nargs="*", help="Optional normalized article JSONL files to include")
    evidence_index.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    evidence_index.add_argument("--briefing", default=str(DEFAULT_BRIEFING))
    evidence_index.add_argument("--output", default=str(DEFAULT_EVIDENCE_INDEX))
    evidence_index.add_argument("--compact", action="store_true", help="Print compact JSON instead of pretty JSON")
    evidence_index.set_defaults(func=cmd_build_evidence_index)

    evidence_query = sub.add_parser("query-evidence", help="Query the local Evidence RAG index directly")
    evidence_query.add_argument("--question", required=True)
    evidence_query.add_argument("--index", default=str(DEFAULT_EVIDENCE_INDEX))
    evidence_query.add_argument("--top-k", type=int, default=6)
    evidence_query.add_argument("--compact", action="store_true", help="Print compact JSON instead of pretty JSON")
    evidence_query.set_defaults(func=cmd_query_evidence)

    ask_rag = sub.add_parser("ask-rag", help="Ask the analyst with local Evidence RAG citations")
    ask_rag.add_argument("--question", required=True)
    ask_rag.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    ask_rag.add_argument("--index", default=str(DEFAULT_EVIDENCE_INDEX))
    ask_rag.add_argument("--articles", nargs="*", help="Optional normalized article JSONL files when rebuilding the index")
    ask_rag.add_argument("--scenario", default=str(DEFAULT_SCENARIO))
    ask_rag.add_argument("--briefing", default=str(DEFAULT_BRIEFING))
    ask_rag.add_argument("--top-k", type=int, default=5)
    ask_rag.add_argument("--rebuild-index", action="store_true", help="Rebuild the evidence index before answering")
    ask_rag.add_argument("--compact", action="store_true", help="Print compact JSON instead of pretty JSON")
    ask_rag.set_defaults(func=cmd_ask_rag)

    agent = sub.add_parser("agent-run", help="Run the local transfer-stock analyst agent over one goal")
    agent.add_argument("--goal", required=True, help="Research goal for the agent")
    agent.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    agent.add_argument("--output-dir", default=str(DEFAULT_AGENT_OUTPUT_DIR))
    agent.add_argument("--evidence-index", default=str(DEFAULT_EVIDENCE_INDEX))
    agent.add_argument("--run-id", default="", help="Optional stable output folder name")
    agent.add_argument("--scenario", choices=["auto", "always", "never"], default="auto", help="Whether to run Scenario Swarm")
    agent.add_argument("--rounds", type=int, default=2, help="Scenario Swarm rounds when a scenario runs")
    agent.add_argument("--top-k", type=int, default=5, help="Number of evidence citations to retrieve")
    agent.add_argument("--no-rebuild-index", action="store_true", help="Reuse an existing evidence index if available")
    agent.add_argument("--dashboard-agent-output", default=str(DEFAULT_DASHBOARD_AGENT), help="Static dashboard agent snapshot output")
    agent.add_argument("--dashboard-report-output", default=str(DEFAULT_DASHBOARD_AGENT_REPORT), help="Static dashboard agent report output")
    agent.add_argument("--no-dashboard-publish", action="store_true", help="Skip writing the static dashboard latest agent snapshot")
    agent.add_argument("--compact", action="store_true", help="Print compact JSON instead of pretty JSON")
    agent.set_defaults(func=cmd_agent_run)

    scenario = sub.add_parser("simulate-scenario", help="Run a bounded deterministic scenario swarm over a rumor signal")
    scenario.add_argument("--question", default="", help="Analyst-style question, for example: What is the current signal for Casemiro?")
    scenario.add_argument("--player", default="", help="Player name to anchor the scenario")
    scenario.add_argument("--club", default="", help="Optional target club filter")
    scenario.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    scenario.add_argument("--output-dir", default=str(DATA_DIR / "simulations"))
    scenario.add_argument("--rounds", type=int, default=2, help="Bounded agent rounds, clamped to 1-5")
    scenario.add_argument("--simulation-id", default="", help="Optional stable output folder name")
    scenario.add_argument("--dashboard-scenario-output", default=str(DEFAULT_DASHBOARD_SCENARIO))
    scenario.add_argument("--dashboard-report-output", default=str(DEFAULT_DASHBOARD_SCENARIO_REPORT))
    scenario.add_argument("--no-dashboard-publish", action="store_true", help="Skip writing the static dashboard scenario snapshot")
    scenario.add_argument("--compact", action="store_true", help="Print compact JSON instead of pretty JSON")
    scenario.set_defaults(func=cmd_simulate_scenario)

    briefing = sub.add_parser("generate-briefing", help="Generate a deterministic daily transfer-stock briefing")
    briefing.add_argument("--payload", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    briefing.add_argument("--scenario", default=str(DEFAULT_DASHBOARD_SCENARIO))
    briefing.add_argument("--output", default=str(DEFAULT_BRIEFING_MD))
    briefing.add_argument("--json-output", default=str(DEFAULT_BRIEFING_JSON))
    briefing.add_argument("--no-scenario", action="store_true", help="Skip loading the latest Scenario Swarm snapshot")
    briefing.add_argument("--no-json", action="store_true", help="Only write Markdown")
    briefing.set_defaults(func=cmd_generate_briefing)

    inspect_demo = sub.add_parser("inspect-demo-data", help="Inspect Stage 8 dashboard payload JSON")
    inspect_demo.add_argument("--input", default=str(Path("app") / "static" / "data" / "dashboard_data.json"))
    inspect_demo.set_defaults(func=cmd_inspect_demo_data)

    model_data = sub.add_parser("build-model-dataset", help="Join transfer events with scored rumor features")
    model_data.add_argument("--events", default=str(DATA_DIR / "processed" / "transfer_events.csv"))
    model_data.add_argument("--scored-news", default=str(DATA_DIR / "processed" / "scored_event_news.csv"))
    model_data.add_argument("--output", default=str(DATA_DIR / "processed" / "model_dataset.csv"))
    model_data.set_defaults(func=cmd_build_model_dataset)

    rumor_events = sub.add_parser("build-rumor-events", help="Build one-row-per-article ML dataset from scored rumors")
    rumor_events.add_argument("--scored-news", default=str(DATA_DIR / "processed" / "scored_event_news.csv"))
    rumor_events.add_argument("--transfers", default=str(DATA_DIR / "processed" / "transfers_exact_dates.csv"))
    rumor_events.add_argument("--output", default=str(DATA_DIR / "processed" / "rumor_events.csv"))
    rumor_events.set_defaults(func=cmd_build_rumor_events)

    enrich = sub.add_parser("enrich-rumor-events", help="Add transfer, rumor, and pre-rumor stock indicators")
    enrich.add_argument("--input", default=str(DATA_DIR / "processed" / "rumor_events_exact_top.csv"))
    enrich.add_argument("--output", default=str(DATA_DIR / "processed" / "rumor_events_enriched.csv"))
    enrich.set_defaults(func=cmd_enrich_rumor_events)

    group = sub.add_parser("group-rumor-events", help="Group same-day article rows into one rumor event")
    group.add_argument("--input", default=str(DATA_DIR / "processed" / "rumor_events_enriched.csv"))
    group.add_argument("--output", default=str(DATA_DIR / "processed" / "rumor_events_grouped.csv"))
    group.set_defaults(func=cmd_group_rumor_events)

    report = sub.add_parser("make-report", help="Create readable stock-impact report CSV and Markdown")
    report.add_argument("--model-dataset", default=str(DATA_DIR / "processed" / "model_dataset.csv"))
    report.add_argument("--output-csv", default=str(DATA_DIR / "reports" / "impact_report.csv"))
    report.add_argument("--output-markdown", default=str(DATA_DIR / "reports" / "impact_report.md"))
    report.set_defaults(func=cmd_make_report)

    train = sub.add_parser("train-model", help="Train a first temporal ML classifier on event-study labels")
    train.add_argument("--model-dataset", default=str(DATA_DIR / "processed" / "model_dataset.csv"))
    train.add_argument("--predictions", default=str(DATA_DIR / "models" / "predictions.csv"))
    train.add_argument("--metrics", default=str(DATA_DIR / "models" / "metrics.json"))
    train.add_argument("--train-end-season", default="2024-25")
    train.add_argument("--model", choices=["nb", "knn"], default="nb")
    train.add_argument("--k", type=int, default=1)
    train.set_defaults(func=cmd_train_model)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
