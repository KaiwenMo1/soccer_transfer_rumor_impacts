from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .analyst import DEFAULT_PAYLOAD, ask_analyst
from .config import ROOT
from .evidence_rag import DEFAULT_EVIDENCE_INDEX
from .io import ensure_parent


DEFAULT_AGENT_MANIFEST = ROOT / "app" / "static" / ".well-known" / "transfer-stock-agent.json"


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def build_agent_manifest(*, base_url: str = "") -> dict[str, Any]:
    prefix = base_url.rstrip("/")
    return {
        "schema_version": "0.1",
        "name": "Transfer Stock Analyst",
        "description": (
            "A local football-finance intelligence site for transfer rumors, reporter "
            "credibility, listed-club exposure, and market-context research."
        ),
        "generated_at": now_iso(),
        "inspired_by": {
            "pattern": "NLWeb-style natural-language website endpoint",
            "source": "https://github.com/microsoft/NLWeb",
        },
        "endpoints": {
            "manifest": f"{prefix}/nlweb/manifest" if prefix else "/nlweb/manifest",
            "ask": f"{prefix}/nlweb/ask" if prefix else "/nlweb/ask",
            "static_manifest": (
                f"{prefix}/.well-known/transfer-stock-agent.json"
                if prefix
                else "/.well-known/transfer-stock-agent.json"
            ),
        },
        "capabilities": [
            {
                "name": "ask",
                "description": "Ask a grounded natural-language question over the local dashboard payload and evidence index.",
                "input_schema": {"question": "string"},
                "output_schema": {
                    "question": "string",
                    "short_answer": "string",
                    "confidence": "number",
                    "evidence": "array",
                    "warnings": "array",
                    "source_paths": "object",
                },
            },
            {
                "name": "club_context",
                "description": "Explain public-club exposure, stock-path context, match markers, and current rumor signals.",
            },
            {
                "name": "reporter_context",
                "description": "Explain reporter/source credibility from local historical claim outcomes.",
            },
            {
                "name": "scenario_context",
                "description": "Summarize bounded scenario-swarm outputs when available.",
            },
        ],
        "example_questions": [
            "What changed today?",
            "Compare Manchester United and Juventus",
            "Explain the strongest current listed-club rumor",
            "Who are the strongest reporters for Borussia Dortmund?",
            "What happened to Ajax stock around recent match results?",
        ],
        "data_sources": [
            "app/static/data/dashboard_data.json",
            "data/processed/evidence/evidence_index.json",
            "app/static/data/operator_latest.json",
            "app/static/data/data_quality_latest.json",
        ],
        "safety": {
            "trading_advice": False,
            "uses_local_data": True,
            "requires_api_keys": False,
            "notes": [
                "Outputs are research context, not investment advice.",
                "Stock-impact language is only valid when a listed-club ticker is directly mapped.",
                "Football club stocks can move for match results, ownership news, liquidity, earnings, qualification, and broader markets.",
            ],
        },
    }


def nlweb_ask(
    question: str,
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    evidence_index_path: str | Path = DEFAULT_EVIDENCE_INDEX,
    top_k: int = 5,
) -> dict[str, Any]:
    result = ask_analyst(
        question,
        payload_path=payload_path,
        include_evidence=True,
        evidence_index_path=evidence_index_path,
        evidence_top_k=top_k,
    )
    normalized_question = question.strip().lower()
    if result.get("intent") == "unknown" and any(
        phrase in normalized_question
        for phrase in ("what changed", "today", "daily brief", "latest", "one read")
    ):
        result = today_brief_result(
            question,
            payload_path=payload_path,
            evidence_result=result,
            evidence_index_path=evidence_index_path,
        )
    citations = result.get("evidence_citations", []) or []
    return {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "question": result.get("question", question),
        "intent": result.get("intent", "unknown"),
        "short_answer": result.get("short_answer", ""),
        "confidence": result.get("confidence", 0.0),
        "evidence": [
            {
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "source_path": item.get("source_path", ""),
                "url": item.get("url", ""),
                "score": item.get("score", 0.0),
            }
            for item in citations
        ],
        "evidence_cards": result.get("evidence_cards", []),
        "tables": result.get("tables", []),
        "warnings": result.get("warnings", []),
        "what_would_change_mind": result.get("what_would_change_mind", []),
        "source_paths": result.get("source_paths", {}),
        "safety": {
            "research_only": True,
            "trading_advice": False,
        },
    }


def today_brief_result(
    question: str,
    *,
    payload_path: str | Path,
    evidence_result: dict[str, Any],
    evidence_index_path: str | Path,
) -> dict[str, Any]:
    payload_file = Path(payload_path)
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    watchlist = payload.get("live_watchlist", []) or []
    meta = payload.get("live_watchlist_meta", {}) or {}
    top = watchlist[0] if watchlist else {}
    if top:
        player = top.get("player", "the top current rumor")
        club = top.get("target_club") or top.get("club") or "unknown club"
        stage = top.get("latest_rumor_stage") or top.get("rumor_stage") or "unclear stage"
        latest = top.get("latest_published_at") or meta.get("latest_published_at") or ""
        short_answer = (
            f"The latest local package puts {player} at {club} at the top of the live board "
            f"({stage}, latest evidence {str(latest)[:10] or 'unknown date'}). "
            "Treat this as a research watch item, then inspect credibility, source breadth, "
            "and market context before drawing any stock conclusion."
        )
        confidence = 0.72
        evidence_cards = [
            {
                "title": "Top live item",
                "value": f"{player} · {club}",
                "detail": str(top.get("signal_summary") or top.get("primary_headline") or stage),
            },
            {
                "title": "Freshness",
                "value": "stale" if meta.get("is_stale") else "fresh",
                "detail": f"{meta.get('recent_cluster_count', len(watchlist))} recent clusters tracked.",
            },
            {
                "title": "Prediction scope",
                "value": top.get("prediction_scope", "unknown"),
                "detail": "Stock-impact language is only valid for directly mapped public tickers.",
            },
        ]
    else:
        short_answer = "No live watchlist rows are loaded in the local payload. Run a live refresh before asking for today's changes."
        confidence = 0.35
        evidence_cards = [
            {
                "title": "Live watchlist",
                "value": "empty",
                "detail": "Use the daily research cycle or light news refresh runbook.",
            }
        ]
    return {
        **evidence_result,
        "question": question,
        "intent": "today_brief",
        "short_answer": short_answer,
        "confidence": confidence,
        "evidence_cards": evidence_cards,
        "warnings": [
            "This is a current research brief, not a trading recommendation.",
            "Football-club stocks can also move because of match results, ownership news, earnings, liquidity, and broader markets.",
        ],
        "source_paths": {
            "dashboard_payload": str(payload_file),
            "evidence_index": str(evidence_index_path),
        },
    }


def write_agent_manifest(
    output_path: str | Path = DEFAULT_AGENT_MANIFEST,
    *,
    base_url: str = "",
) -> dict[str, Any]:
    manifest = build_agent_manifest(base_url=base_url)
    output = Path(output_path)
    ensure_parent(output)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "output": str(output),
        "capability_count": len(manifest["capabilities"]),
    }
