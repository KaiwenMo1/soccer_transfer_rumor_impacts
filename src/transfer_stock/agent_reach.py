from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ROOT
from .evidence_rag import DEFAULT_EVIDENCE_INDEX
from .io import ensure_parent
from .nlweb import DEFAULT_AGENT_MANIFEST, build_agent_manifest


DEFAULT_AGENT_REACH = ROOT / "app" / "static" / "data" / "agent_reach.json"
DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def file_check(path: str | Path, *, label: str, required: bool = True) -> dict[str, Any]:
    file_path = Path(path)
    exists = file_path.exists()
    size = file_path.stat().st_size if exists else 0
    return {
        "id": label,
        "path": str(file_path),
        "required": required,
        "status": "pass" if exists else ("fail" if required else "warn"),
        "exists": exists,
        "size_bytes": size,
        "message": "available" if exists else "missing",
    }


def optional_module_check(module_name: str, *, label: str, install_hint: str) -> dict[str, Any]:
    available = importlib.util.find_spec(module_name) is not None
    return {
        "id": label,
        "required": False,
        "status": "pass" if available else "warn",
        "module": module_name,
        "available": available,
        "message": "installed" if available else install_hint,
    }


def command_check(command_name: str, *, label: str, install_hint: str) -> dict[str, Any]:
    command_path = shutil.which(command_name)
    return {
        "id": label,
        "required": False,
        "status": "pass" if command_path else "warn",
        "command": command_name,
        "path": command_path or "",
        "available": bool(command_path),
        "message": "installed" if command_path else install_hint,
    }


def external_agent_reach_status(*, run_doctor: bool = False, timeout: int = 30) -> dict[str, Any]:
    command_path = shutil.which("agent-reach")
    status: dict[str, Any] = {
        "project": "Panniantong/Agent-Reach",
        "url": "https://github.com/Panniantong/Agent-Reach",
        "available": bool(command_path),
        "command_path": command_path or "",
        "role_in_this_project": (
            "Optional upstream capability layer for web/RSS/GitHub/social discovery. "
            "This repo still normalizes, scores, matches, models, and publishes the football-finance research outputs."
        ),
        "useful_channels": [
            {
                "channel": "web",
                "project_use": "Read arbitrary club, league, or publisher pages when RSS/API coverage is thin.",
                "ci_safe": True,
            },
            {
                "channel": "rss",
                "project_use": "Improve no-key feed collection and source freshness checks.",
                "ci_safe": True,
            },
            {
                "channel": "github",
                "project_use": "Research public source projects, data providers, and ingestion tools.",
                "ci_safe": True,
            },
            {
                "channel": "youtube",
                "project_use": "Summarize press conference or club media transcripts as future sentiment/context evidence.",
                "ci_safe": False,
            },
            {
                "channel": "twitter/reddit/xueqiu/xiaohongshu",
                "project_use": "Optional rumor/sentiment discovery. Keep cookies local and out of GitHub Actions.",
                "ci_safe": False,
            },
        ],
        "install_hint": "pipx install https://github.com/Panniantong/agent-reach/archive/main.zip",
        "safe_mode_hint": "agent-reach install --env=auto --safe",
        "doctor": {},
    }
    if not command_path:
        return status
    if not run_doctor:
        status["doctor"] = {
            "skipped": True,
            "command": "agent-reach doctor",
            "message": "Use --external-doctor to run the external health check.",
        }
        return status
    try:
        completed = subprocess.run(
            [command_path, "doctor", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        parsed: dict[str, Any] | None = None
        if completed.stdout.strip():
            try:
                parsed = json.loads(completed.stdout)
            except json.JSONDecodeError:
                parsed = None
        status["doctor"] = {
            "command": "agent-reach doctor --json",
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "json": parsed or {},
            "stdout_preview": completed.stdout[-2000:],
            "stderr_preview": completed.stderr[-2000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        status["doctor"] = {
            "command": "agent-reach doctor --json",
            "ok": False,
            "error": str(exc),
        }
    return status


def payload_summary(payload_path: str | Path) -> dict[str, Any]:
    path = Path(payload_path)
    if not path.exists():
        return {
            "available": False,
            "generated_at": "",
            "latest_season": "",
            "signal_count": 0,
            "watchlist_count": 0,
            "club_count": 0,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "generated_at": "",
            "latest_season": "",
            "signal_count": 0,
            "watchlist_count": 0,
            "club_count": 0,
        }
    signals_by_season = payload.get("signals_by_season", {}) or {}
    return {
        "available": True,
        "generated_at": payload.get("generated_at", ""),
        "latest_season": payload.get("latest_season", ""),
        "signal_count": sum(len(rows or []) for rows in signals_by_season.values()),
        "watchlist_count": len(payload.get("live_watchlist", []) or []),
        "club_count": len(payload.get("club_dossiers", {}) or {}),
    }


def capability_catalog(*, base_url: str = "") -> list[dict[str, Any]]:
    prefix = base_url.rstrip("/")
    return [
        {
            "id": "ask_transfer_analyst",
            "label": "Ask Transfer Analyst",
            "purpose": "Answer grounded questions over the local dashboard payload.",
            "risk": "read_only",
            "cli": 'PYTHONPATH=src python -m transfer_stock.cli ask --question "Compare Manchester United and Juventus"',
            "http": f"{prefix}/ask" if prefix else "/ask",
            "inputs": {"question": "string"},
            "outputs": ["short_answer", "evidence_cards", "tables", "warnings", "confidence"],
        },
        {
            "id": "ask_rag",
            "label": "Ask With Evidence RAG",
            "purpose": "Attach local citations from dashboard, article, report, and scenario evidence.",
            "risk": "read_only",
            "cli": 'PYTHONPATH=src python -m transfer_stock.cli ask-rag --question "Explain Casemiro" --rebuild-index',
            "http": f"{prefix}/nlweb/ask" if prefix else "/nlweb/ask",
            "inputs": {"question": "string", "top_k": "integer"},
            "outputs": ["short_answer", "evidence", "warnings", "what_would_change_mind"],
        },
        {
            "id": "research_cycle",
            "label": "Research Cycle",
            "purpose": "Run the local research operator and publish a decision queue.",
            "risk": "writes_local_reports",
            "cli": "PYTHONPATH=src python -m transfer_stock.cli research-cycle --mode research",
            "http": f"{prefix}/operator/run" if prefix else "/operator/run",
            "inputs": {"mode": "research|smart|refresh", "allow_network": "boolean"},
            "outputs": ["data/operators/latest", "app/static/data/operator_latest.json"],
        },
        {
            "id": "scenario_swarm",
            "label": "Scenario Swarm",
            "purpose": "Run bounded role agents over one rumor as a research scenario.",
            "risk": "writes_local_reports",
            "cli": 'PYTHONPATH=src python -m transfer_stock.cli simulate-scenario --player Casemiro --club "Manchester United"',
            "http": "",
            "inputs": {"player": "string", "club": "string", "rounds": "integer"},
            "outputs": ["data/simulations/<simulation_id>/", "app/static/data/scenario_latest.json"],
        },
        {
            "id": "daily_briefing",
            "label": "Daily Briefing",
            "purpose": "Generate a deterministic Markdown and JSON research brief.",
            "risk": "writes_local_reports",
            "cli": "PYTHONPATH=src python -m transfer_stock.cli generate-briefing",
            "http": "",
            "inputs": {},
            "outputs": ["data/reports/daily_briefing.md", "data/reports/daily_briefing.json"],
        },
        {
            "id": "agent_manifest",
            "label": "Agent Manifest",
            "purpose": "Publish the AI-readable website/tool manifest.",
            "risk": "writes_static_manifest",
            "cli": "PYTHONPATH=src python -m transfer_stock.cli publish-agent-manifest",
            "http": f"{prefix}/nlweb/manifest" if prefix else "/nlweb/manifest",
            "inputs": {},
            "outputs": ["app/static/.well-known/transfer-stock-agent.json"],
        },
    ]


def build_agent_reach_report(
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    evidence_index_path: str | Path = DEFAULT_EVIDENCE_INDEX,
    agent_manifest_path: str | Path = DEFAULT_AGENT_MANIFEST,
    base_url: str = "",
    external_doctor: bool = False,
) -> dict[str, Any]:
    manifest = build_agent_manifest(base_url=base_url)
    external_status = external_agent_reach_status(run_doctor=external_doctor)
    checks = [
        file_check(payload_path, label="dashboard_payload"),
        file_check(evidence_index_path, label="evidence_index", required=False),
        file_check(agent_manifest_path, label="static_agent_manifest", required=False),
        file_check(ROOT / "AGENTS.md", label="agent_instructions"),
        file_check(ROOT / "docs" / "mcp_tools.md", label="mcp_tool_contract"),
        optional_module_check("fastapi", label="fastapi_optional_api", install_hint='Install with: pip install -e ".[api_server]"'),
        command_check(
            "agent-reach",
            label="external_agent_reach_cli",
            install_hint="Optional: install Panniantong/Agent-Reach for wider web/RSS/GitHub/social discovery.",
        ),
    ]
    failed_required = [check for check in checks if check["required"] and check["status"] != "pass"]
    warnings = [check for check in checks if check["status"] == "warn"]
    score = round((len(checks) - len(failed_required) - 0.35 * len(warnings)) / max(len(checks), 1), 3)
    status = "ready" if not failed_required and score >= 0.75 else "partial" if not failed_required else "blocked"
    return {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "name": "Transfer Stock Analyst Agent Reachability",
        "status": status,
        "readiness_score": max(0.0, min(1.0, score)),
        "summary": payload_summary(payload_path),
        "inspired_by": [
            {
                "pattern": "Panniantong/Agent-Reach capability router",
                "adaptation": "Detect the optional external CLI and document which internet channels can feed this research pipeline.",
                "url": "https://github.com/Panniantong/Agent-Reach",
            },
            {
                "pattern": "MCP and NLWeb-style tool manifests",
                "adaptation": "Keep this project usable by local agents without requiring a full MCP server dependency.",
            },
        ],
        "external_agent_reach": external_status,
        "capabilities": capability_catalog(base_url=base_url),
        "manifest_preview": {
            "name": manifest.get("name", ""),
            "capability_count": len(manifest.get("capabilities", []) or []),
            "endpoints": manifest.get("endpoints", {}),
            "safety": manifest.get("safety", {}),
        },
        "readiness_checks": checks,
        "recommended_next_actions": recommended_next_actions(checks),
        "agent_rules": [
            "Use local data by default.",
            "Do not claim trading advice.",
            "Show uncertainty and source paths.",
            "Use stock-impact language only for directly mapped listed-club targets.",
            "Keep cookie-based social channels local; never put platform cookies in GitHub Actions secrets unless you fully understand the risk.",
            "Prefer research-cycle --mode research before network refreshes.",
        ],
    }


def recommended_next_actions(checks: list[dict[str, Any]]) -> list[str]:
    actions = []
    by_id = {check["id"]: check for check in checks}
    if by_id.get("evidence_index", {}).get("status") != "pass":
        actions.append("PYTHONPATH=src python -m transfer_stock.cli build-evidence-index")
    if by_id.get("static_agent_manifest", {}).get("status") != "pass":
        actions.append("PYTHONPATH=src python -m transfer_stock.cli publish-agent-manifest")
    if by_id.get("fastapi_optional_api", {}).get("status") != "pass":
        actions.append('pip install -e ".[api_server]"')
    if by_id.get("external_agent_reach_cli", {}).get("status") != "pass":
        actions.append("Optional: pipx install https://github.com/Panniantong/agent-reach/archive/main.zip")
    actions.append("PYTHONPATH=src python -m transfer_stock.cli agent-reach")
    return actions


def write_agent_reach_report(
    output_path: str | Path = DEFAULT_AGENT_REACH,
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    evidence_index_path: str | Path = DEFAULT_EVIDENCE_INDEX,
    agent_manifest_path: str | Path = DEFAULT_AGENT_MANIFEST,
    base_url: str = "",
    external_doctor: bool = False,
) -> dict[str, Any]:
    report = build_agent_reach_report(
        payload_path=payload_path,
        evidence_index_path=evidence_index_path,
        agent_manifest_path=agent_manifest_path,
        base_url=base_url,
        external_doctor=external_doctor,
    )
    output = Path(output_path)
    ensure_parent(output)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {
        "output": str(output),
        "status": report["status"],
        "readiness_score": report["readiness_score"],
        "capability_count": len(report["capabilities"]),
        "recommended_next_actions": report["recommended_next_actions"],
    }
