from __future__ import annotations

import json
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .analyst import DEFAULT_PAYLOAD, load_dashboard_payload, parse_float
from .config import DATA_DIR, ROOT
from .io import ensure_parent
from .scenario_swarm import DEFAULT_DASHBOARD_SCENARIO


DEFAULT_BRIEFING_MD = DATA_DIR / "reports" / "daily_briefing.md"
DEFAULT_BRIEFING_JSON = DATA_DIR / "reports" / "daily_briefing.json"


def fmt_number(value: Any, digits: int = 3) -> str:
    if value in {"", None}:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def fmt_pct(value: Any, digits: int = 1) -> str:
    if value in {"", None}:
        return "-"
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "-"


def fmt_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    if len(text) >= 10 and text[:4].isdigit() and text[4] == "-":
        return text[:10]
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return text[:10]


def load_optional_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    json_path = Path(path)
    if not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8"))


def briefing_source_path(path: str | Path) -> str:
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = ROOT / path_obj
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path_obj)


def direct_target_rows(payload: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    rows = [
        row for row in payload.get("live_watchlist", []) or []
        if str(row.get("prediction_scope", "")) == "direct"
    ]
    return sorted(
        rows,
        key=lambda row: (
            abs(parse_float(row.get("blended_score"), 0.0)),
            parse_float(row.get("consensus_score"), 0.0),
            str(row.get("latest_published_at") or row.get("published_at") or ""),
        ),
        reverse=True,
    )[:limit]


def top_consensus_rows(payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    rows = payload.get("live_watchlist", []) or []
    return sorted(
        rows,
        key=lambda row: (
            parse_float(row.get("consensus_score"), 0.0),
            parse_float(row.get("source_count"), 0.0),
            parse_float(row.get("event_strength"), 0.0),
        ),
        reverse=True,
    )[:limit]


def club_watch_rows(payload: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    dossiers = payload.get("club_dossiers", {}) or {}
    rows = list(dossiers.values())
    return sorted(
        rows,
        key=lambda row: (
            parse_float(row.get("live_signal_count"), 0.0),
            abs(parse_float(row.get("avg_realized_car_p3"), 0.0)),
            parse_float(row.get("avg_transfer_index"), 0.0),
        ),
        reverse=True,
    )[:limit]


def stock_context_rows(payload: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    paths = payload.get("club_stock_paths", {}) or {}
    rows = []
    for club, path in paths.items():
        rows.append(
            {
                "club": club,
                "ticker": path.get("ticker", ""),
                "latest_date": path.get("latest_date", ""),
                "latest_change": path.get("latest_change", ""),
                "match_marker_count": path.get("match_marker_count", len(path.get("markers", []) or [])),
                "recent_matches": list(reversed((path.get("markers", []) or [])[-3:])),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            int(parse_float(row.get("match_marker_count"), 0.0)),
            abs(parse_float(row.get("latest_change"), 0.0)),
        ),
        reverse=True,
    )[:limit]


def confirmed_link_rows(payload: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("live_watchlist", []) or []:
        links = row.get("confirmed_transfer_links", []) or []
        if not links:
            detail = (payload.get("watchlist_details", {}) or {}).get(str(row.get("group_key", "")), {})
            links = detail.get("confirmed_transfer_links", []) or []
        if not links:
            continue
        best = sorted(links, key=lambda item: parse_float(item.get("match_score"), 0.0), reverse=True)[0]
        rows.append({"rumor": row, "confirmed": best})
    return sorted(rows, key=lambda item: parse_float(item["confirmed"].get("match_score"), 0.0), reverse=True)[:limit]


def data_quality_warnings(payload: dict[str, Any], scenario: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    quality = payload.get("quality_summary", {}) or {}
    meta = payload.get("live_watchlist_meta", {}) or {}
    if quality.get("live_status") == "stale" or meta.get("is_stale"):
        warnings.append(f"Live data may be stale; latest live article is {quality.get('latest_live_date') or fmt_date(meta.get('latest_published_at'))}.")
    if parse_float(payload.get("overview", {}).get("xgboost_test_accuracy"), 0.0) < 0.55:
        warnings.append("Model accuracy is still early/weak; use predictions as ranking signals, not as proof.")
    if not payload.get("live_watchlist"):
        warnings.append("No live watchlist rows are available in the current payload.")
    if not scenario:
        warnings.append("No Scenario Swarm snapshot is available; run simulate-scenario for a richer scenario verdict.")
    warnings.append("This briefing is deterministic research context, not a trading recommendation.")
    return warnings


def build_briefing_sections(payload: dict[str, Any], scenario: dict[str, Any] | None = None) -> dict[str, Any]:
    scenario = scenario or {}
    leaderboards = payload.get("leaderboards", {}) or {}
    return {
        "freshness": {
            "generated_at": payload.get("generated_at", ""),
            "latest_season": payload.get("latest_season", ""),
            "live_status": (payload.get("quality_summary", {}) or {}).get("live_status", "unknown"),
            "latest_live_date": (payload.get("quality_summary", {}) or {}).get("latest_live_date", ""),
            "recent_live_clusters": (payload.get("quality_summary", {}) or {}).get("recent_live_clusters", 0),
        },
        "top_direct_rumors": direct_target_rows(payload, limit=8),
        "strongest_consensus": top_consensus_rows(payload, limit=5),
        "top_journalists": (leaderboards.get("journalists", []) or [])[:5],
        "top_sources": (leaderboards.get("sources", []) or [])[:5],
        "club_watch": club_watch_rows(payload, limit=6),
        "stock_context": stock_context_rows(payload, limit=5),
        "confirmed_relationships": confirmed_link_rows(payload, limit=6),
        "scenario": scenario if scenario.get("available") else {},
        "warnings": data_quality_warnings(payload, scenario if scenario.get("available") else {}),
        "source_paths": {
            "dashboard_payload": briefing_source_path(DEFAULT_PAYLOAD),
            "scenario_snapshot": briefing_source_path(DEFAULT_DASHBOARD_SCENARIO),
        },
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    if not rows:
        lines.append("| " + " | ".join(["-"] * len(headers)) + " |")
        return lines
    for row in rows:
        lines.append("| " + " | ".join(str(item).replace("|", "/") for item in row) + " |")
    return lines


def briefing_markdown(sections: dict[str, Any]) -> str:
    freshness = sections["freshness"]
    scenario = sections.get("scenario", {})
    lines = [
        "# Daily Transfer-Stock Briefing",
        "",
        f"Generated from local dashboard payload: `{sections['source_paths']['dashboard_payload']}`",
        "",
        "## Freshness",
        "",
        f"- Dashboard generated at: {freshness.get('generated_at') or '-'}",
        f"- Latest season: {freshness.get('latest_season') or '-'}",
        f"- Live status: {freshness.get('live_status') or 'unknown'}",
        f"- Latest live date: {freshness.get('latest_live_date') or '-'}",
        f"- Recent live clusters: {freshness.get('recent_live_clusters', 0)}",
        "",
        "## Top Current Direct-Target Rumors",
        "",
    ]
    lines.extend(
        markdown_table(
            ["Player", "Target club", "Role", "Stage", "Sources", "Cred", "Blend", "Model"],
            [
                [
                    row.get("player", "-"),
                    row.get("target_club") or row.get("club", "-"),
                    row.get("target_role", "-"),
                    row.get("rumor_stage") or row.get("latest_rumor_stage", "-"),
                    row.get("source_count", "-"),
                    fmt_number(row.get("credibility_score"), 3),
                    row.get("blended_label", "-"),
                    row.get("predicted_label", "-"),
                ]
                for row in sections["top_direct_rumors"]
            ],
        )
    )
    lines.extend(["", "## Strongest Consensus Events", ""])
    lines.extend(
        markdown_table(
            ["Player", "Club", "Tier", "Consensus", "Articles", "Primary headline"],
            [
                [
                    row.get("player", "-"),
                    row.get("target_club") or row.get("club", "-"),
                    str(row.get("confidence_tier", "-")).replace("_", " "),
                    f"{row.get('consensus_label', '-')} ({fmt_number(row.get('consensus_score'), 3)})",
                    row.get("article_count", "-"),
                    row.get("primary_headline", "-"),
                ]
                for row in sections["strongest_consensus"]
            ],
        )
    )
    lines.extend(["", "## Credibility Leaders", ""])
    lines.extend(
        markdown_table(
            ["Journalist", "Claims", "Smoothed", "Avg match"],
            [
                [row.get("journalist", "-"), row.get("n_claims", 0), fmt_number(row.get("smoothed_rate"), 3), fmt_number(row.get("avg_match_score"), 3)]
                for row in sections["top_journalists"]
            ],
        )
    )
    lines.append("")
    lines.extend(
        markdown_table(
            ["Source", "Claims", "Smoothed", "Avg match"],
            [
                [row.get("source", "-"), row.get("n_claims", 0), fmt_number(row.get("smoothed_rate"), 3), fmt_number(row.get("avg_match_score"), 3)]
                for row in sections["top_sources"]
            ],
        )
    )
    lines.extend(["", "## Biggest Club Watch Items", ""])
    lines.extend(
        markdown_table(
            ["Club", "Live", "Current", "Avg cred", "Avg transfer index", "CAR t+3"],
            [
                [
                    row.get("club", "-"),
                    row.get("live_signal_count", 0),
                    row.get("current_signal_count", 0),
                    fmt_number(row.get("avg_live_credibility"), 3),
                    fmt_number(row.get("avg_transfer_index"), 3),
                    fmt_number(row.get("avg_realized_car_p3"), 4),
                ]
                for row in sections["club_watch"]
            ],
        )
    )
    lines.extend(["", "## Match Result + Stock Context", ""])
    lines.extend(
        markdown_table(
            ["Club", "Ticker", "Latest date", "Latest change", "Match markers", "Recent matches"],
            [
                [
                    row.get("club", "-"),
                    row.get("ticker", "-"),
                    row.get("latest_date", "-"),
                    fmt_pct(row.get("latest_change"), 1),
                    row.get("match_marker_count", 0),
                    "; ".join(
                        f"{item.get('match_date', '-')}: {item.get('result', '-')} {item.get('score', '')} vs {item.get('opponent', '-')}"
                        for item in row.get("recent_matches", [])[:3]
                    ) or "-",
                ]
                for row in sections["stock_context"]
            ],
        )
    )
    lines.extend(["", "## Confirmed vs Rumored Relationships", ""])
    lines.extend(
        markdown_table(
            ["Rumor", "Club", "Confirmed row", "Match", "Actual", "CAR t+3"],
            [
                [
                    item["rumor"].get("player", "-"),
                    item["rumor"].get("target_club") or item["rumor"].get("club", "-"),
                    f"{item['confirmed'].get('player', '-')} / {item['confirmed'].get('date', '-')}",
                    fmt_number(item["confirmed"].get("match_score"), 3),
                    item["confirmed"].get("actual_label", "-"),
                    fmt_number(item["confirmed"].get("actual_abnormal_return_p3"), 4),
                ]
                for item in sections["confirmed_relationships"]
            ],
        )
    )
    lines.extend(["", "## Latest Scenario Swarm", ""])
    if scenario:
        signal = scenario.get("signal", {}) or {}
        summary = scenario.get("summary", {}) or {}
        lines.extend(
            [
                f"- Question: {scenario.get('question', '-')}",
                f"- Player / club: {signal.get('player', '-')} / {signal.get('target_club') or signal.get('club', '-')}",
                f"- Consensus: {summary.get('consensus_stance', 'watch')} ({fmt_pct(summary.get('consensus_confidence'), 0)} confidence)",
                f"- Agent votes: {', '.join(f'{key}: {value}' for key, value in (summary.get('stance_counts', {}) or {}).items()) or '-'}",
                f"- Report: `{scenario.get('report_href', '-')}`",
            ]
        )
    else:
        lines.append("No Scenario Swarm snapshot is available yet. Run `python3 -m transfer_stock.cli simulate-scenario --player Casemiro --club \"Manchester United\"`.")
    lines.extend(["", "## Data-Quality Warnings", ""])
    for warning in sections["warnings"]:
        lines.append(f"- {warning}")
    lines.extend(["", "## Source Files", ""])
    for label, path in sections["source_paths"].items():
        lines.append(f"- {label}: `{path}`")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def generate_daily_briefing(
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    scenario_path: str | Path | None = DEFAULT_DASHBOARD_SCENARIO,
    output_markdown: str | Path = DEFAULT_BRIEFING_MD,
    output_json: str | Path | None = DEFAULT_BRIEFING_JSON,
) -> dict[str, Any]:
    payload = load_dashboard_payload(payload_path)
    scenario = load_optional_json(scenario_path)
    sections = build_briefing_sections(payload, scenario)
    markdown = briefing_markdown(sections)
    output_md_path = Path(output_markdown)
    ensure_parent(output_md_path)
    output_md_path.write_text(markdown, encoding="utf-8")
    result = {
        "markdown": str(output_md_path),
        "json": str(output_json) if output_json else "",
        "sections": sections,
    }
    if output_json:
        write_json(Path(output_json), sections)
    return result
