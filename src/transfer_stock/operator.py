from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .autopilot import (
    DEFAULT_AGENT_OUTPUT_DIR,
    DEFAULT_AUTOPILOT_JSON,
    DEFAULT_AUTOPILOT_REPORT,
    DEFAULT_DASHBOARD_AUTOPILOT,
    run_autopilot,
)
from .config import DATA_DIR, ROOT, Club, load_clubs
from .data_quality import build_data_quality_audit
from .evidence_rag import DEFAULT_EVIDENCE_INDEX
from .io import ensure_parent
from .live_refresh import refresh_live_dashboard
from .news_sources import SOURCE_PRESETS, methods_for_preset


PRODUCT_PURPOSE = (
    "Turn noisy football transfer coverage into a daily, evidence-backed intelligence brief "
    "for publicly listed clubs."
)
USER_OUTCOME = (
    "Know what changed, how credible it is, whether a listed club is directly exposed, "
    "what could move the same stock, and what deserves inspection next."
)

DEFAULT_OPERATOR_JSON = DATA_DIR / "operators" / "operator_latest.json"
DEFAULT_OPERATOR_REPORT = DATA_DIR / "operators" / "operator_latest.md"
DEFAULT_DASHBOARD_OPERATOR = ROOT / "app" / "static" / "data" / "operator_latest.json"
DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"
DEFAULT_TRANSFERS = DATA_DIR / "processed" / "transfers_exact_dates.csv"
DEFAULT_BASE_SCORED_CLAIMS = (
    DATA_DIR / "processed" / "credibility" / "historical_event_news_2021_25" / "scored_claims.csv",
    DATA_DIR / "processed" / "credibility" / "provider_event_news_2025_26_top50" / "scored_claims.csv",
)
DEFAULT_STATS_CLAIMS = (
    DATA_DIR / "processed" / "claims" / "historical_event_news_2021_25_claims.jsonl",
    DATA_DIR / "processed" / "claims" / "provider_event_news_2025_26_top50_claims.jsonl",
)
DEFAULT_STATS_MATCHES = (
    DATA_DIR / "processed" / "matched_claims" / "historical_event_news_2021_25_matches.csv",
    DATA_DIR / "processed" / "matched_claims" / "provider_event_news_2025_26_top50_matches.csv",
)


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def load_json(path: str | Path, fallback: Any = None) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return fallback
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    ensure_parent(output)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def relative_path(path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    try:
        return candidate.relative_to(ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def signal_priority(row: dict[str, Any]) -> float:
    direct = row.get("prediction_scope") == "direct"
    stage = str(row.get("latest_rumor_stage") or row.get("rumor_stage") or "").lower()
    stage_score = {
        "official": 1.0,
        "medical": 0.92,
        "agreed": 0.86,
        "advanced": 0.76,
        "bid": 0.62,
        "talks": 0.5,
        "linked": 0.28,
    }.get(stage, 0.2)
    credibility = clamp(parse_float(row.get("credibility_score")))
    confidence = clamp(parse_float(row.get("prediction_confidence")))
    source_breadth = clamp(parse_float(row.get("source_count"), 1.0) / 4.0)
    impact = clamp(abs(parse_float(row.get("blended_score"))) / 70.0)
    return round(
        (0.25 if direct else 0.0)
        + credibility * 0.24
        + confidence * 0.18
        + source_breadth * 0.14
        + stage_score * 0.11
        + impact * 0.08,
        4,
    )


def decision_for_signal(row: dict[str, Any]) -> dict[str, Any]:
    score = signal_priority(row)
    direct = row.get("prediction_scope") == "direct"
    source_count = int(parse_float(row.get("source_count"), 0.0))
    credibility = parse_float(row.get("credibility_score"))
    if not direct:
        action = "credibility_only"
        label = "Transfer intelligence only"
        reason = "No listed-club ticker is directly mapped, so do not invent a stock-impact prediction."
    elif score >= 0.66 and source_count >= 2:
        action = "monitor"
        label = "Monitor closely"
        reason = "Direct listed-club exposure with comparatively strong evidence and source breadth."
    elif score >= 0.48 or credibility >= 0.55:
        action = "verify"
        label = "Verify next"
        reason = "Potentially relevant, but it needs stronger confirmation or cleaner market context."
    else:
        action = "background"
        label = "Background watch"
        reason = "The evidence is thin relative to the rest of the current queue."
    return {
        "action": action,
        "label": label,
        "priority_score": score,
        "reason": reason,
        "player": row.get("player", ""),
        "club": row.get("target_club") or row.get("club", ""),
        "ticker": row.get("target_ticker", ""),
        "target_role": row.get("target_role", ""),
        "rumor_stage": row.get("latest_rumor_stage") or row.get("rumor_stage", ""),
        "published_at": row.get("latest_published_at") or row.get("published_at", ""),
        "credibility_score": row.get("credibility_score", ""),
        "prediction_confidence": row.get("prediction_confidence", ""),
        "source_count": row.get("source_count", 0),
        "group_key": row.get("group_key", ""),
    }


def build_decision_queue(payload: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    decisions = [decision_for_signal(row) for row in payload.get("live_watchlist", []) or []]
    return sorted(decisions, key=lambda item: item["priority_score"], reverse=True)[: max(1, limit)]


def selected_clubs(clubs: dict[str, Club], requested: Iterable[str] | None = None) -> list[Club]:
    requested_names = [str(item).strip().lower() for item in requested or [] if str(item).strip()]
    if not requested_names:
        return list(clubs.values())
    lookup: dict[str, Club] = {}
    for key, club in clubs.items():
        lookup[key.lower()] = club
        lookup[club.name.lower()] = club
        for alias in club.aliases:
            lookup[str(alias).lower()] = club
    selected: list[Club] = []
    seen: set[str] = set()
    for name in requested_names:
        club = lookup.get(name)
        if club is None:
            raise ValueError(f"Unknown club selection: {name}")
        if club.key not in seen:
            selected.append(club)
            seen.add(club.key)
    return selected


def should_refresh(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    audit = build_data_quality_audit(payload)
    freshness = next((item for item in audit.get("dimensions", []) if item.get("name") == "Freshness"), {})
    stale = bool((payload.get("live_watchlist_meta") or {}).get("is_stale"))
    needs_refresh = stale or freshness.get("status") in {"watch", "needs_refresh"} or not payload.get("live_watchlist")
    return needs_refresh, {
        "overall_status": audit.get("overall_status", ""),
        "overall_score": audit.get("overall_score", ""),
        "freshness_status": freshness.get("status", ""),
        "freshness_summary": freshness.get("summary", ""),
    }


def operator_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# Transfer-Stock Research Operator",
        "",
        f"Generated: {snapshot.get('generated_at', '-')}",
        "",
        f"**Purpose:** {snapshot.get('purpose', PRODUCT_PURPOSE)}",
        "",
        f"**User outcome:** {snapshot.get('user_outcome', USER_OUTCOME)}",
        "",
        f"**Cycle status:** {snapshot.get('status', '-')}",
        "",
        "This is research context and evidence triage, not a trading recommendation.",
        "",
        "## Today In One Read",
        "",
        snapshot.get("summary", "No summary available."),
        "",
        "## Decision Queue",
        "",
        "| Priority | Action | Player | Club | Why |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in snapshot.get("decision_queue", []) or []:
        lines.append(
            f"| {item.get('priority_score', '-')} | {item.get('label', '-')} | "
            f"{item.get('player', '-')} | {item.get('club', '-')} | {item.get('reason', '-')} |"
        )
    lines.extend(["", "## Trust State", ""])
    for key, value in (snapshot.get("trust_state", {}) or {}).items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    lines.extend(["", "## Outputs", ""])
    for key, value in (snapshot.get("outputs", {}) or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def run_research_cycle(
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    mode: str = "smart",
    allow_network: bool = False,
    dry_run: bool = False,
    source_preset: str = "fast_no_api",
    max_records: int = 20,
    clubs: Iterable[str] | None = None,
    output_json: str | Path = DEFAULT_OPERATOR_JSON,
    output_report: str | Path = DEFAULT_OPERATOR_REPORT,
    dashboard_output: str | Path | None = DEFAULT_DASHBOARD_OPERATOR,
    autopilot_output: str | Path = DEFAULT_AUTOPILOT_JSON,
    autopilot_report: str | Path = DEFAULT_AUTOPILOT_REPORT,
    dashboard_autopilot: str | Path | None = DEFAULT_DASHBOARD_AUTOPILOT,
    evidence_index: str | Path = DEFAULT_EVIDENCE_INDEX,
    agent_output_dir: str | Path = DEFAULT_AGENT_OUTPUT_DIR,
) -> dict[str, Any]:
    if mode not in {"research", "smart", "refresh"}:
        raise ValueError("mode must be one of: research, smart, refresh")
    payload_file = Path(payload_path)
    payload = load_json(payload_file, {})
    if not payload:
        raise FileNotFoundError(f"Dashboard payload not found or invalid: {payload_file}")

    refresh_needed, preflight = should_refresh(payload)
    refresh_requested = mode == "refresh" or (mode == "smart" and refresh_needed)
    refresh_summary: dict[str, Any] = {
        "requested": refresh_requested,
        "allowed": allow_network,
        "status": "not_needed" if not refresh_requested else "planned",
        "source_preset": source_preset,
        "max_records": max_records,
        "error": "",
        "outputs": {},
    }
    warnings: list[str] = []

    if refresh_requested and not allow_network:
        refresh_summary["status"] = "skipped_permission"
        warnings.append("Live refresh was needed but network refresh was not permitted; research used the existing payload.")
    elif refresh_requested and dry_run:
        refresh_summary["status"] = "planned"
    elif refresh_requested:
        try:
            club_map = load_clubs()
            chosen = selected_clubs(club_map, clubs)
            source_keys = list(SOURCE_PRESETS[source_preset])
            methods = methods_for_preset(source_preset) or ["rss"]
            end = date.today()
            start = end - timedelta(days=21)
            refresh_outputs = refresh_live_dashboard(
                club_map,
                chosen,
                start=start,
                end=end,
                transfers_path=DEFAULT_TRANSFERS,
                source_keys=source_keys,
                methods=methods,
                max_records=max_records,
                timeout=35,
                retries=2,
                pause=0.1,
                refresh_stocks=False,
                base_scored_claim_paths=DEFAULT_BASE_SCORED_CLAIMS,
                stats_claim_paths=DEFAULT_STATS_CLAIMS,
                stats_match_paths=DEFAULT_STATS_MATCHES,
                dashboard_output=payload_file,
            )
            refresh_summary["status"] = "completed"
            refresh_summary["outputs"] = {key: relative_path(value) for key, value in refresh_outputs.items()}
            payload = load_json(payload_file, payload)
        except Exception as exc:  # keep the operator useful when a source is down
            refresh_summary["status"] = "failed"
            refresh_summary["error"] = str(exc)
            warnings.append("Live refresh failed; the operator continued using the previous dashboard payload.")

    autopilot = run_autopilot(
        payload_path=payload_file,
        output_json=Path(autopilot_output),
        output_report=Path(autopilot_report),
        dashboard_output=Path(dashboard_autopilot) if dashboard_autopilot is not None else None,
        evidence_index=Path(evidence_index),
        agent_output_dir=Path(agent_output_dir),
        dry_run=dry_run,
        scenario_policy="never",
        top_k=6,
    )
    payload = load_json(payload_file, payload)
    queue = build_decision_queue(payload)
    top = queue[0] if queue else {}
    audit = autopilot.get("audit_summary", {}) or {}
    agent = autopilot.get("agent_summary", {}) or {}
    answer = agent.get("answer", {}) or {}
    status = "planned" if dry_run else ("completed_with_warnings" if warnings else "completed")
    if top:
        summary = (
            f"{top.get('label', 'Watch')}: {top.get('player', '-')} at {top.get('club', '-')}. "
            f"{top.get('reason', '')}"
        )
    else:
        summary = "No current rumor entered the decision queue. Refresh coverage before making a live read."

    snapshot = {
        "available": True,
        "generated_at": now_iso(),
        "status": status,
        "mode": mode,
        "purpose": PRODUCT_PURPOSE,
        "user_outcome": USER_OUTCOME,
        "summary": summary,
        "preflight": preflight,
        "refresh": refresh_summary,
        "decision_queue": queue,
        "trust_state": {
            "data_quality_status": audit.get("overall_status", "unknown"),
            "data_quality_score": audit.get("overall_score", ""),
            "agent_confidence": answer.get("confidence", ""),
            "agent_citations": answer.get("citation_count", 0),
            "prediction_scope_rule": "Stock impact only when a listed-club ticker is directly mapped.",
        },
        "warnings": warnings
        + [
            "Football-club stocks can also move because of match results, ownership news, earnings, liquidity, qualification, and broader markets."
        ],
        "outputs": {
            "dashboard_payload": relative_path(payload_file),
            "autopilot": relative_path(autopilot_output),
            "autopilot_report": relative_path(autopilot_report),
            "evidence_index": relative_path(evidence_index),
        },
    }
    output_json_path = Path(output_json)
    output_report_path = Path(output_report)
    snapshot["outputs"]["operator_json"] = relative_path(output_json_path)
    snapshot["outputs"]["operator_report"] = relative_path(output_report_path)
    if dashboard_output is not None:
        snapshot["outputs"]["dashboard_operator"] = relative_path(dashboard_output)
    write_json(output_json_path, snapshot)
    ensure_parent(output_report_path)
    output_report_path.write_text(operator_markdown(snapshot), encoding="utf-8")
    if dashboard_output is not None:
        write_json(dashboard_output, snapshot)
    return snapshot
