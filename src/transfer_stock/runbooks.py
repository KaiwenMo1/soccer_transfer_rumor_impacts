from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ROOT
from .io import ensure_parent


DEFAULT_DASHBOARD_RUNBOOKS = ROOT / "app" / "static" / "data" / "runbooks.json"


RUNBOOKS: tuple[dict[str, Any], ...] = (
    {
        "id": "daily_research_cycle",
        "title": "Daily Research Cycle",
        "tagline": "One button for today's transfer-stock brief.",
        "purpose": (
            "Check freshness, refresh stale live evidence when allowed, rebuild the research "
            "operator package, and publish the decision queue."
        ),
        "best_for": "Opening the project each morning or before a demo.",
        "github_pattern": "Dify-style workflow card plus LangGraph-style bounded run state.",
        "automation": "operator",
        "api_supported": True,
        "estimated_time": "1-4 min",
        "operator_request": {
            "mode": "smart",
            "allow_network": True,
            "source_preset": "fast_no_api",
            "max_records": 20,
            "clubs": [],
        },
        "command": (
            "PYTHONPATH=src python3 -m transfer_stock.cli research-cycle "
            "--mode smart --allow-network"
        ),
        "outputs": [
            "app/static/data/operator_latest.json",
            "data/operators/operator_latest.md",
            "app/static/data/dashboard_data.json",
            "data/reports/daily_briefing.md",
        ],
        "guardrail": "Research context only; no automated trade execution.",
    },
    {
        "id": "light_news_refresh",
        "title": "Light Live-News Refresh",
        "tagline": "Refresh current coverage without going full heavy mode.",
        "purpose": (
            "Force a bounded current-news refresh with the no-key source preset, then rebuild "
            "the dashboard package."
        ),
        "best_for": "When the watchlist looks stale but you want a fast local update.",
        "github_pattern": "OpenBB-style explicit data refresh with visible outputs.",
        "automation": "operator",
        "api_supported": True,
        "estimated_time": "3-8 min",
        "operator_request": {
            "mode": "refresh",
            "allow_network": True,
            "source_preset": "fast_no_api",
            "max_records": 12,
            "clubs": [],
        },
        "command": (
            "PYTHONPATH=src python3 -m transfer_stock.cli research-cycle "
            "--mode refresh --allow-network --source-preset fast_no_api --max-records 12"
        ),
        "outputs": [
            "data/raw/articles/current_live.jsonl",
            "app/static/data/dashboard_data.json",
            "app/static/data/operator_latest.json",
        ],
        "guardrail": "If a source times out, the operator continues with the latest valid payload.",
    },
    {
        "id": "agent_deep_dive",
        "title": "Agent Deep Dive",
        "tagline": "Ask the local analyst agent to investigate one goal.",
        "purpose": (
            "Build or reuse the evidence index, retrieve citations, produce a plan/trace, "
            "and write an analyst report."
        ),
        "best_for": "Explaining one player, club, reporter, or suspicious market move.",
        "github_pattern": "FinRobot-style financial analyst agent with cited local evidence.",
        "automation": "manual_cli",
        "api_supported": False,
        "estimated_time": "1-3 min",
        "operator_request": {},
        "command": (
            "PYTHONPATH=src python3 -m transfer_stock.cli agent-run "
            "--goal \"Explain today's strongest listed-club transfer rumor\""
        ),
        "outputs": [
            "data/agents/<run_id>/agent_report.md",
            "data/agents/<run_id>/trace.jsonl",
            "app/static/data/agent_latest.json",
        ],
        "guardrail": "Agent answers must cite local evidence and show uncertainty.",
    },
    {
        "id": "scenario_boardroom",
        "title": "Scenario Boardroom",
        "tagline": "Run role agents over one rumor.",
        "purpose": (
            "Create a bounded scenario with finance, market, credibility, fan/sentiment, "
            "and risk-officer perspectives."
        ),
        "best_for": "Showing why a rumor is not just positive or negative in one dimension.",
        "github_pattern": "CrewAI/AutoGen-style role agents, bounded to deterministic research output.",
        "automation": "manual_cli",
        "api_supported": False,
        "estimated_time": "1-2 min",
        "operator_request": {},
        "command": (
            "PYTHONPATH=src python3 -m transfer_stock.cli simulate-scenario "
            "--player Casemiro --club \"Manchester United\" --rounds 2"
        ),
        "outputs": [
            "data/simulations/<simulation_id>/report.md",
            "app/static/data/scenario_latest.json",
        ],
        "guardrail": "Scenario reports are research narratives, not trading recommendations.",
    },
    {
        "id": "evidence_rag_refresh",
        "title": "Evidence RAG Refresh",
        "tagline": "Rebuild the local citation layer.",
        "purpose": (
            "Re-index dashboard rows, reports, scenarios, and article snippets so analyst "
            "answers can cite evidence."
        ),
        "best_for": "Before asking RAG questions or after changing dashboard data.",
        "github_pattern": "RAGFlow/Haystack-style evidence-first retrieval, kept local and inspectable.",
        "automation": "manual_cli",
        "api_supported": False,
        "estimated_time": "<1 min",
        "operator_request": {},
        "command": "PYTHONPATH=src python3 -m transfer_stock.cli build-evidence-index",
        "outputs": ["data/processed/evidence/evidence_index.json"],
        "guardrail": "RAG retrieval supports answers; it does not replace data-quality checks.",
    },
)


def list_runbooks() -> dict[str, Any]:
    return {
        "generated_by": "transfer_stock.runbooks",
        "purpose": "Offer one-click or copy-paste research workflows over the local project data.",
        "runbook_count": len(RUNBOOKS),
        "runbooks": deepcopy(list(RUNBOOKS)),
        "notes": [
            "API-supported runbooks require the FastAPI workbench.",
            "Static GitHub Pages can show runbooks and commands, but cannot execute local workflows.",
            "All workflows are research context only; they do not place trades.",
        ],
    }


def get_runbook(runbook_id: str) -> dict[str, Any]:
    normalized = runbook_id.strip().lower()
    for runbook in RUNBOOKS:
        if runbook["id"] == normalized:
            return deepcopy(runbook)
    raise KeyError(f"Unknown runbook: {runbook_id}")


def runbook_operator_kwargs(runbook_id: str) -> dict[str, Any]:
    runbook = get_runbook(runbook_id)
    if not runbook.get("api_supported") or runbook.get("automation") != "operator":
        raise ValueError(f"Runbook is not API-runnable: {runbook_id}")
    request = dict(runbook.get("operator_request") or {})
    request.setdefault("mode", "smart")
    request.setdefault("allow_network", False)
    request.setdefault("source_preset", "fast_no_api")
    request.setdefault("max_records", 20)
    request.setdefault("clubs", [])
    return request


def write_runbook_snapshot(output_path: str | Path = DEFAULT_DASHBOARD_RUNBOOKS) -> dict[str, Any]:
    snapshot = list_runbooks()
    output = Path(output_path)
    ensure_parent(output)
    output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return {
        "output": str(output),
        "runbook_count": snapshot["runbook_count"],
    }
