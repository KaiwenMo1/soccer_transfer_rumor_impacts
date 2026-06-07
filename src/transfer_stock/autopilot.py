from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent import DEFAULT_AGENT_OUTPUT_DIR, run_agent
from .analyst import load_dashboard_payload
from .briefing import DEFAULT_BRIEFING_JSON, DEFAULT_BRIEFING_MD, generate_daily_briefing
from .config import DATA_DIR, ROOT
from .data_quality import DEFAULT_QUALITY_JSON, DEFAULT_QUALITY_MD, write_data_quality_audit
from .evidence_rag import DEFAULT_EVIDENCE_INDEX, build_evidence_index
from .io import ensure_parent
from .rag_eval import DEFAULT_RAG_AUDIT_JSON, DEFAULT_RAG_AUDIT_MD, write_rag_audit


DEFAULT_AUTOPILOT_JSON = DATA_DIR / "agents" / "autopilot_latest.json"
DEFAULT_AUTOPILOT_REPORT = DATA_DIR / "agents" / "autopilot_latest.md"
DEFAULT_DASHBOARD_AUTOPILOT = ROOT / "app" / "static" / "data" / "autopilot_latest.json"


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def rel_path(path: str | Path) -> str:
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = ROOT / path_obj
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def slugify(value: str, fallback: str = "autopilot") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or fallback


def write_json(path: str | Path, payload: Any) -> None:
    output = Path(path)
    ensure_parent(output)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def signal_score(row: dict[str, Any]) -> float:
    score = 0.0
    if row.get("prediction_scope") == "direct":
        score += 2.0
    score += float(row.get("credibility_score") or 0.0)
    score += float(row.get("prediction_confidence") or 0.0)
    score += min(float(row.get("source_count") or 1.0), 5.0) * 0.08
    stage = str(row.get("latest_rumor_stage") or row.get("rumor_stage") or "").lower()
    if stage in {"advanced", "agreed", "medical", "official"}:
        score += 0.35
    return score


def choose_autopilot_goal(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("live_watchlist", []) or [])
    if not rows:
        return {
            "goal": "Summarize the latest transfer-stock dashboard state",
            "reason": "No live watchlist rows are available.",
            "signal": {},
        }
    row = sorted(rows, key=signal_score, reverse=True)[0]
    player = str(row.get("player") or "").strip()
    club = str(row.get("target_club") or row.get("club") or "").strip()
    if player and club:
        goal = f"Explain {player} at {club}"
    elif club:
        goal = f"Find the strongest current {club} transfer-stock watch item"
    else:
        goal = "Explain the strongest current transfer-stock watch item"
    return {
        "goal": goal,
        "reason": "Highest-scoring live watchlist row by directness, credibility, confidence, source count, and stage.",
        "signal": {
            "player": player,
            "club": club,
            "stage": row.get("latest_rumor_stage") or row.get("rumor_stage") or "",
            "credibility_score": row.get("credibility_score", ""),
            "prediction_confidence": row.get("prediction_confidence", ""),
            "prediction_scope": row.get("prediction_scope", ""),
            "source_count": row.get("source_count", ""),
        },
    }


def autopilot_plan(payload: dict[str, Any]) -> list[dict[str, str]]:
    goal = choose_autopilot_goal(payload)
    return [
        {
            "id": "audit_data_quality",
            "action": "write_data_quality_audit",
            "reason": "Check freshness, coverage, market context, date hygiene, and model readiness.",
        },
        {
            "id": "build_evidence_index",
            "action": "build_evidence_index",
            "reason": "Refresh the local hybrid RAG layer over dashboard/articles/reports.",
        },
        {
            "id": "generate_briefing",
            "action": "generate_daily_briefing",
            "reason": "Create a human-readable daily research briefing from local evidence.",
        },
        {
            "id": "run_analyst_agent",
            "action": "agent_run",
            "reason": f"Run the local analyst agent on: {goal['goal']}",
        },
        {
            "id": "audit_rag_grounding",
            "action": "write_rag_audit",
            "reason": "Evaluate whether the agent answer is supported by retrieved citations.",
        },
        {
            "id": "write_autopilot_snapshot",
            "action": "write_report",
            "reason": "Publish a traceable JSON/Markdown summary for the dashboard and GitHub artifacts.",
        },
    ]


def recommended_commands(audit: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    commands = [
        "PYTHONPATH=src python3 -m transfer_stock.cli ask-rag --question \"Explain the strongest current rumor\" --rebuild-index",
        "PYTHONPATH=src python3 -m transfer_stock.cli agent-autopilot",
    ]
    status = str(audit.get("overall_status") or "").lower()
    quality = payload.get("quality_summary", {}) or {}
    if status in {"needs_refresh", "watch"} or quality.get("live_status") == "stale":
        commands.insert(
            0,
            "PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-fetch --source-preset wide_no_api --max-records 30 --resume",
        )
        commands.insert(
            1,
            "PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-analyze --input data/raw/articles/current_live.jsonl --slug live_manual",
        )
    if "Source Coverage" in json.dumps(audit):
        commands.append(
            "PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-fetch --source-preset scrapling_wide_no_api --max-records 30 --resume"
        )
    return commands


def autopilot_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Transfer-Stock Agent Autopilot",
        "",
        f"Generated: {payload.get('generated_at', '-')}",
        "",
        "This is a bounded local automation report. It is research context, not a trading recommendation.",
        "",
        "## Selected Goal",
        "",
        f"- Goal: {payload.get('selected_goal', {}).get('goal', '-')}",
        f"- Reason: {payload.get('selected_goal', {}).get('reason', '-')}",
        "",
        "## Steps",
        "",
        "| Step | Status | Output |",
        "| --- | --- | --- |",
    ]
    for step in payload.get("steps", []) or []:
        lines.append(f"| {step.get('id', '-')} | {step.get('status', '-')} | {step.get('output', '-')} |")
    lines.extend(["", "## Recommendations", ""])
    for command in payload.get("recommended_commands", []) or []:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Outputs", ""])
    for key, value in (payload.get("outputs", {}) or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def run_autopilot(
    *,
    payload_path: str | Path = ROOT / "app" / "static" / "data" / "dashboard_data.json",
    output_json: str | Path = DEFAULT_AUTOPILOT_JSON,
    output_report: str | Path = DEFAULT_AUTOPILOT_REPORT,
    dashboard_output: str | Path | None = DEFAULT_DASHBOARD_AUTOPILOT,
    evidence_index: str | Path = DEFAULT_EVIDENCE_INDEX,
    agent_output_dir: str | Path = DEFAULT_AGENT_OUTPUT_DIR,
    dry_run: bool = False,
    scenario_policy: str = "never",
    top_k: int = 5,
) -> dict[str, Any]:
    payload_file = Path(payload_path)
    payload = load_dashboard_payload(payload_file)
    selected_goal = choose_autopilot_goal(payload)
    plan = autopilot_plan(payload)
    steps: list[dict[str, Any]] = []
    outputs: dict[str, str] = {}
    generated_at = now_iso()

    def record(step_id: str, status: str, output: str = "", detail: dict[str, Any] | None = None) -> None:
        steps.append({"id": step_id, "status": status, "output": output, "detail": detail or {}, "time": now_iso()})

    audit: dict[str, Any] = {"overall_status": "dry_run"}
    agent_result: dict[str, Any] = {}
    if dry_run:
        for step in plan:
            record(step["id"], "planned", "", {"reason": step["reason"]})
    else:
        audit = write_data_quality_audit(payload_file, output_json=DEFAULT_QUALITY_JSON, output_markdown=DEFAULT_QUALITY_MD)
        record("audit_data_quality", "completed", rel_path(audit.get("json_path", DEFAULT_QUALITY_JSON)), {"overall_status": audit.get("overall_status")})
        outputs["data_quality"] = rel_path(audit.get("json_path", DEFAULT_QUALITY_JSON))

        evidence = build_evidence_index(payload_path=payload_file, output_path=Path(evidence_index))
        record("build_evidence_index", "completed", evidence.get("output", rel_path(evidence_index)), evidence.get("stats", {}))
        outputs["evidence_index"] = evidence.get("output", rel_path(evidence_index))

        briefing = generate_daily_briefing(payload_path=payload_file, output_markdown=DEFAULT_BRIEFING_MD, output_json=DEFAULT_BRIEFING_JSON)
        record("generate_briefing", "completed", rel_path(briefing["markdown"]), {"json": rel_path(briefing.get("json", ""))})
        outputs["daily_briefing"] = rel_path(briefing["markdown"])

        run_id = f"autopilot-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{slugify(selected_goal['goal'])}"
        agent_result = run_agent(
            goal=selected_goal["goal"],
            payload_path=payload_file,
            output_dir=Path(agent_output_dir),
            evidence_index=Path(evidence_index),
            run_id=run_id,
            scenario_policy=scenario_policy,
            top_k=top_k,
            rebuild_index=False,
        )
        record("run_analyst_agent", "completed", agent_result.get("run_dir", ""), {"intent": (agent_result.get("answer") or {}).get("intent", "")})
        outputs["agent_run"] = agent_result.get("run_dir", "")

        rag_audit = write_rag_audit(output_json=DEFAULT_RAG_AUDIT_JSON, output_markdown=DEFAULT_RAG_AUDIT_MD)
        record("audit_rag_grounding", "completed", rag_audit.get("json_path", rel_path(DEFAULT_RAG_AUDIT_JSON)), {"overall_status": rag_audit.get("overall_status")})
        outputs["rag_audit"] = rag_audit.get("json_path", rel_path(DEFAULT_RAG_AUDIT_JSON))

    result = {
        "available": True,
        "generated_at": generated_at,
        "dry_run": dry_run,
        "payload_path": rel_path(payload_file),
        "selected_goal": selected_goal,
        "plan": plan,
        "steps": steps,
        "audit_summary": {
            "overall_status": audit.get("overall_status", ""),
            "overall_score": audit.get("overall_score", ""),
            "summary": audit.get("summary", ""),
        },
        "agent_summary": {
            "run_id": agent_result.get("run_id", ""),
            "answer": agent_result.get("answer", {}),
            "run_dir": agent_result.get("run_dir", ""),
        },
        "recommended_commands": recommended_commands(audit, payload),
        "outputs": outputs,
    }
    output_json_path = Path(output_json)
    output_report_path = Path(output_report)
    result["outputs"]["autopilot_json"] = rel_path(output_json_path)
    result["outputs"]["autopilot_report"] = rel_path(output_report_path)
    if dashboard_output is not None:
        result["outputs"]["dashboard_autopilot"] = rel_path(dashboard_output)
    report = autopilot_markdown(result)
    ensure_parent(output_report_path)
    output_report_path.write_text(report, encoding="utf-8")
    write_json(output_json_path, result)
    if dashboard_output is not None:
        write_json(dashboard_output, result)
    return result
