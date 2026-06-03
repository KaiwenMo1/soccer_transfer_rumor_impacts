from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .io import ensure_parent


DEFAULT_QUALITY_JSON = Path("app") / "static" / "data" / "data_quality_latest.json"
DEFAULT_QUALITY_MD = Path("data") / "reports" / "data_quality_audit.md"


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z") and "-" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    if text.endswith("Z") and "T" in text:
        try:
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except ValueError:
            pass
    for fmt, size in (("%Y-%m-%d", 10), ("%Y%m%d%H%M%S", 14)):
        try:
            return datetime.strptime(text[:size], fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(text).astimezone(UTC)
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def parse_date(value: Any) -> date | None:
    dt = parse_datetime(value)
    return dt.date() if dt else None


def score_status(score: float) -> str:
    if score >= 0.82:
        return "strong"
    if score >= 0.62:
        return "usable"
    if score >= 0.42:
        return "watch"
    return "needs_refresh"


def freshness_score(days_stale: int | None) -> float:
    if days_stale is None:
        return 0.0
    if days_stale <= 2:
        return 1.0
    if days_stale <= 7:
        return 0.76
    if days_stale <= 14:
        return 0.52
    if days_stale <= 30:
        return 0.28
    return 0.12


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def all_signal_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(payload.get("live_watchlist") or [])
    for season_rows in (payload.get("signals_by_season") or {}).values():
        rows.extend(season_rows or [])
    rows.extend((payload.get("watchlist_details") or {}).values())
    seen: set[str] = set()
    unique = []
    for row in rows:
        key = str(row.get("group_key") or f"{row.get('club')}::{row.get('player')}::{row.get('latest_published_at') or row.get('published_at')}")
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def all_transfer_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for season_rows in (payload.get("transfers_by_season") or {}).values():
        rows.extend(season_rows or [])
    return rows


def latest_signal_datetime(payload: dict[str, Any]) -> datetime | None:
    dates = []
    for row in all_signal_rows(payload):
        for field in ("published_at", "latest_published_at", "published_date", "date"):
            dt = parse_datetime(row.get(field))
            if dt:
                dates.append(dt)
                break
    return max(dates) if dates else None


def dimension(name: str, score: float, summary: str, warnings: list[str] | None = None, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    rounded = round(clamp(score), 4)
    return {
        "name": name,
        "score": rounded,
        "status": score_status(rounded),
        "summary": summary,
        "warnings": warnings or [],
        "evidence": evidence or {},
    }


def build_freshness_dimension(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    latest = latest_signal_datetime(payload)
    generated_at = parse_datetime(payload.get("generated_at"))
    days_stale = (now.date() - latest.date()).days if latest else None
    generated_stale = (now.date() - generated_at.date()).days if generated_at else None
    score = freshness_score(days_stale)
    warnings = []
    if days_stale is None:
        warnings.append("No signal dates were found in the dashboard payload.")
    elif days_stale > 7:
        warnings.append(f"Latest signal is {days_stale} days old; refresh live news before presenting this as current.")
    if generated_stale is not None and generated_stale > 7:
        warnings.append(f"Dashboard payload was generated {generated_stale} days ago.")
    return dimension(
        "Freshness",
        score,
        f"Latest signal date: {latest.date().isoformat() if latest else 'unknown'}",
        warnings,
        {
            "latest_signal_date": latest.date().isoformat() if latest else "",
            "days_stale": "" if days_stale is None else days_stale,
            "payload_generated_at": generated_at.isoformat() if generated_at else "",
            "payload_age_days": "" if generated_stale is None else generated_stale,
        },
    )


def build_source_dimension(payload: dict[str, Any]) -> dict[str, Any]:
    live_rows = payload.get("live_watchlist") or []
    sources = set()
    journalists = set()
    article_count = 0
    multi_source = 0
    missing_journalist = 0
    thin_clusters = 0
    for row in live_rows:
        row_sources = [str(item).strip() for item in row.get("sources", []) if str(item).strip()]
        if row.get("latest_source"):
            row_sources.append(str(row.get("latest_source")).strip())
        if row.get("source"):
            row_sources.append(str(row.get("source")).strip())
        for item in row.get("source_breakdown", []) or []:
            if item.get("source"):
                row_sources.append(str(item.get("source")).strip())
        for item in row.get("evidence_articles", []) or []:
            if item.get("source"):
                row_sources.append(str(item.get("source")).strip())
        row_sources = sorted({source for source in row_sources if source})
        sources.update(row_sources)
        source_count = int(row.get("source_count") or len(row_sources) or 0)
        article_count += int(row.get("article_count") or 0)
        if source_count >= 2:
            multi_source += 1
        row_journalists = [str(item).strip() for item in row.get("journalists", []) if str(item).strip()]
        if row.get("latest_journalist"):
            row_journalists.append(str(row.get("latest_journalist")).strip())
        if row.get("journalist"):
            row_journalists.append(str(row.get("journalist")).strip())
        for item in row.get("evidence_articles", []) or []:
            if item.get("journalist"):
                row_journalists.append(str(item.get("journalist")).strip())
        row_journalists = sorted({journalist for journalist in row_journalists if journalist})
        if not row_journalists:
            missing_journalist += 1
        if source_count < 2 or int(row.get("article_count") or 0) < 2:
            thin_clusters += 1
        journalists.update(row_journalists)
    row_count = len(live_rows)
    score = (
        0.35 * clamp(len(sources) / 8)
        + 0.25 * clamp(article_count / 24)
        + 0.20 * clamp(len(journalists) / 6)
        + 0.20 * (multi_source / row_count if row_count else 0)
    )
    warnings = []
    if row_count == 0:
        warnings.append("No live watchlist rows are available.")
    if thin_clusters:
        warnings.append(f"{thin_clusters} live clusters have only one article/source; consensus is thin.")
    if missing_journalist:
        warnings.append(f"{missing_journalist} live clusters are missing journalist attribution.")
    return dimension(
        "Source Coverage",
        score,
        f"{row_count} live clusters, {len(sources)} sources, {len(journalists)} journalists",
        warnings,
        {
            "live_clusters": row_count,
            "article_count": article_count,
            "unique_sources": len(sources),
            "unique_journalists": len(journalists),
            "multi_source_clusters": multi_source,
            "thin_clusters": thin_clusters,
        },
    )


def build_market_dimension(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    paths = payload.get("club_stock_paths") or {}
    clubs = payload.get("club_media") or {}
    stale_paths = 0
    missing_paths = 0
    marker_count = 0
    latest_dates = []
    for club_name in clubs:
        path = paths.get(club_name) or {}
        latest = parse_date(path.get("latest_date"))
        if not path:
            missing_paths += 1
            continue
        if latest:
            latest_dates.append(latest)
            if (now.date() - latest).days > 14:
                stale_paths += 1
        marker_count += len(path.get("markers") or [])
    total_clubs = max(len(clubs), 1)
    coverage_score = 1 - missing_paths / total_clubs
    stale_score = 1 - stale_paths / total_clubs
    marker_score = clamp(marker_count / (total_clubs * 3))
    score = 0.45 * coverage_score + 0.35 * stale_score + 0.20 * marker_score
    warnings = []
    if missing_paths:
        warnings.append(f"{missing_paths} configured clubs have no stock path in the dashboard payload.")
    if stale_paths:
        warnings.append(f"{stale_paths} club stock paths are older than 14 days.")
    if marker_count == 0:
        warnings.append("No match-result markers are attached to stock paths.")
    latest = max(latest_dates).isoformat() if latest_dates else "unknown"
    return dimension(
        "Market Context",
        score,
        f"{len(paths)} stock paths, latest stock date {latest}, {marker_count} match markers",
        warnings,
        {
            "stock_path_count": len(paths),
            "missing_stock_paths": missing_paths,
            "stale_stock_paths": stale_paths,
            "match_marker_count": marker_count,
            "latest_stock_date": latest,
        },
    )


def build_matching_dimension(payload: dict[str, Any]) -> dict[str, Any]:
    rows = all_signal_rows(payload)
    direct = [row for row in rows if row.get("prediction_scope") == "direct"]
    scores = [float(row.get("match_score") or 0) for row in direct]
    weak = sum(1 for score in scores if score < 0.65)
    avg = sum(scores) / len(scores) if scores else 0
    direct_ratio = len(direct) / len(rows) if rows else 0
    score = 0.55 * clamp(avg) + 0.30 * direct_ratio + 0.15 * (1 - weak / len(scores) if scores else 0)
    warnings = []
    if weak:
        warnings.append(f"{weak} direct signal rows have weak entity-match scores below 0.65.")
    if rows and direct_ratio < 0.5:
        warnings.append("Many signals are intelligence-only, so stock-impact predictions should be limited.")
    return dimension(
        "Entity + Target Matching",
        score,
        f"{len(direct)} direct public-target rows out of {len(rows)} total signals",
        warnings,
        {
            "signal_rows": len(rows),
            "direct_rows": len(direct),
            "direct_ratio": round(direct_ratio, 4),
            "avg_match_score": round(avg, 4),
            "weak_match_rows": weak,
        },
    )


def build_model_dimension(payload: dict[str, Any]) -> dict[str, Any]:
    model = ((payload.get("model_summary") or {}).get("xgboost") or {}).get("test") or {}
    n = int(model.get("n") or 0)
    accuracy = float(model.get("accuracy") or payload.get("overview", {}).get("xgboost_test_accuracy") or 0)
    macro_f1 = float(model.get("macro_f1") or payload.get("overview", {}).get("xgboost_test_macro_f1") or 0)
    balance = model.get("class_balance") or {}
    positive = int(balance.get("positive") or 0)
    score = 0.35 * clamp(accuracy) + 0.35 * clamp(macro_f1) + 0.20 * clamp(n / 120) + 0.10 * clamp(positive / max(n * 0.12, 1))
    warnings = []
    if n < 50:
        warnings.append("Model holdout set is small; treat feature importance and accuracy as directional.")
    if positive <= max(2, n * 0.08):
        warnings.append("Positive class is sparse in holdout data; positive predictions need extra skepticism.")
    if macro_f1 < 0.4:
        warnings.append("Macro F1 is low, so the model is more useful for triage than final decisions.")
    return dimension(
        "Model Reliability",
        score,
        f"Holdout n={n}, accuracy={accuracy:.3f}, macro F1={macro_f1:.3f}",
        warnings,
        {
            "holdout_rows": n,
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "class_balance": balance,
        },
    )


def build_date_dimension(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    future_rows = []
    field_counts: Counter[str] = Counter()
    for kind, rows in (("signal", all_signal_rows(payload)), ("transfer", all_transfer_rows(payload))):
        for row in rows:
            label = f"{row.get('club') or row.get('target_club') or ''} / {row.get('player') or ''}".strip(" /")
            for field in ("date", "published_at", "latest_published_at", "confirmed_date"):
                day = parse_date(row.get(field))
                if day and day > now.date():
                    field_counts[f"{kind}.{field}"] += 1
                    if len(future_rows) < 8:
                        future_rows.append({"kind": kind, "field": field, "date": day.isoformat(), "row": label})
            for link in row.get("confirmed_transfer_links") or []:
                day = parse_date(link.get("date"))
                if day and day > now.date():
                    field_counts[f"{kind}.confirmed_transfer_links.date"] += 1
                    if len(future_rows) < 8:
                        future_rows.append({"kind": kind, "field": "confirmed_transfer_links.date", "date": day.isoformat(), "row": label})
    total_future = sum(field_counts.values())
    score = 1.0 if total_future == 0 else max(0.15, 1 - min(total_future, 20) / 20)
    warnings = []
    if total_future:
        warnings.append(f"{total_future} future-dated fields were found relative to {now.date().isoformat()}.")
    return dimension(
        "Date Hygiene",
        score,
        "No future-dated rows found" if not total_future else f"{total_future} future-dated values need review",
        warnings,
        {
            "future_date_count": total_future,
            "future_date_fields": dict(field_counts),
            "examples": future_rows,
        },
    )


def recommended_commands(audit: dict[str, Any]) -> list[str]:
    commands = []
    statuses = {item["name"]: item["status"] for item in audit.get("dimensions", [])}
    if statuses.get("Freshness") in {"watch", "needs_refresh"}:
        commands.append(
            "PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-fetch --source-preset wide_no_api --max-records 20 --resume"
        )
        commands.append(
            "PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-analyze --input data/raw/articles/current_live.jsonl --slug live_manual"
        )
    if statuses.get("Source Coverage") == "needs_refresh":
        commands.append("pip install -e '.[scrapling_scrape]'")
        commands.append(
            "PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-fetch --source-preset scrapling_wide_no_api --max-records 20 --resume"
        )
    if statuses.get("Market Context") in {"watch", "needs_refresh"}:
        commands.append("PYTHONPATH=src python3 -m transfer_stock.cli fetch-stocks --source yahoo")
        commands.append("PYTHONPATH=src python3 -m transfer_stock.cli fetch-match-results --seasons 2025-26 --resume")
    commands.append("PYTHONPATH=src python3 -m transfer_stock.cli audit-data-quality")
    return commands


def build_data_quality_audit(
    payload: dict[str, Any],
    *,
    payload_path: str = "app/static/data/dashboard_data.json",
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    dimensions = [
        build_freshness_dimension(payload, current),
        build_source_dimension(payload),
        build_market_dimension(payload, current),
        build_matching_dimension(payload),
        build_model_dimension(payload),
        build_date_dimension(payload, current),
    ]
    weights = {
        "Freshness": 0.24,
        "Source Coverage": 0.18,
        "Market Context": 0.18,
        "Entity + Target Matching": 0.16,
        "Model Reliability": 0.14,
        "Date Hygiene": 0.10,
    }
    overall = sum(item["score"] * weights[item["name"]] for item in dimensions)
    warnings = [warning for item in dimensions for warning in item.get("warnings", [])]
    audit = {
        "available": True,
        "audit_generated_at": current.isoformat(),
        "payload_path": payload_path,
        "overall_score": round(overall, 4),
        "overall_status": score_status(overall),
        "summary": f"Data quality is {score_status(overall).replace('_', ' ')} ({overall:.0%}).",
        "dimensions": dimensions,
        "warnings": warnings,
        "recommended_commands": [],
        "source_paths": [payload_path],
    }
    audit["recommended_commands"] = recommended_commands(audit)
    return audit


def data_quality_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Data Quality Audit",
        "",
        f"Generated: `{audit.get('audit_generated_at', '')}`",
        f"Payload: `{audit.get('payload_path', '')}`",
        "",
        f"Overall: **{audit.get('overall_status', '').replace('_', ' ')}** ({audit.get('overall_score', 0):.0%})",
        "",
        "## Dimensions",
        "",
        "| Area | Score | Status | Summary |",
        "| --- | ---: | --- | --- |",
    ]
    for item in audit.get("dimensions", []):
        lines.append(
            f"| {item['name']} | {item['score']:.0%} | {item['status'].replace('_', ' ')} | {item['summary']} |"
        )
    if audit.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in audit["warnings"])
    if audit.get("recommended_commands"):
        lines.extend(["", "## Recommended Commands", ""])
        for command in audit["recommended_commands"]:
            lines.extend(["```bash", command, "```"])
    lines.append("")
    return "\n".join(lines)


def write_data_quality_audit(
    payload_path: Path,
    output_json: Path = DEFAULT_QUALITY_JSON,
    output_markdown: Path | None = DEFAULT_QUALITY_MD,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    with payload_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    audit = build_data_quality_audit(payload, payload_path=str(payload_path), now=now)
    ensure_parent(output_json)
    output_json.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    audit["json_path"] = str(output_json)
    if output_markdown is not None:
        ensure_parent(output_markdown)
        output_markdown.write_text(data_quality_markdown(audit), encoding="utf-8")
        audit["markdown_path"] = str(output_markdown)
    return audit
