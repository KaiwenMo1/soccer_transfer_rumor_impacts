from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .analyst import ask_analyst, candidate_names, load_dashboard_payload, match_clubs, match_name
from .config import DATA_DIR, ROOT
from .evidence_rag import DEFAULT_EVIDENCE_INDEX, build_evidence_index, load_evidence_index, retrieve_evidence
from .io import ensure_parent
from .scenario_swarm import run_scenario_swarm


DEFAULT_AGENT_OUTPUT_DIR = DATA_DIR / "agents"
DEFAULT_AGENT_MEMORY = DATA_DIR / "agents" / "memory.json"
DEFAULT_DASHBOARD_AGENT = ROOT / "app" / "static" / "data" / "agent_latest.json"
DEFAULT_DASHBOARD_AGENT_REPORT = ROOT / "app" / "static" / "data" / "agent_latest_report.md"


def rel_path(path: str | Path) -> str:
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = ROOT / path_obj
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def slugify(value: str, fallback: str = "agent") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or fallback


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    path.write_text("\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def read_optional_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        return {}
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def append_trace(trace: list[dict[str, Any]], step: str, status: str, detail: dict[str, Any] | None = None) -> None:
    trace.append(
        {
            "time": now_iso(),
            "step": step,
            "status": status,
            "detail": detail or {},
        }
    )


def freshness_summary(payload: dict[str, Any]) -> dict[str, Any]:
    quality = payload.get("quality_summary", {}) or {}
    meta = payload.get("live_watchlist_meta", {}) or {}
    return {
        "generated_at": payload.get("generated_at", ""),
        "latest_season": payload.get("latest_season", ""),
        "live_status": quality.get("live_status") or ("stale" if meta.get("is_stale") else "unknown"),
        "latest_live_date": quality.get("latest_live_date") or meta.get("latest_published_at", ""),
        "recent_live_clusters": quality.get("recent_live_clusters", 0),
        "live_watchlist_count": len(payload.get("live_watchlist", []) or []),
        "warnings": data_quality_warnings(payload),
    }


def data_quality_warnings(payload: dict[str, Any]) -> list[str]:
    warnings = []
    quality = payload.get("quality_summary", {}) or {}
    meta = payload.get("live_watchlist_meta", {}) or {}
    if quality.get("live_status") == "stale" or meta.get("is_stale"):
        warnings.append("Live data appears stale; refresh live articles before making current-watchlist claims.")
    if not payload.get("live_watchlist"):
        warnings.append("No live watchlist rows are available in the current payload.")
    warnings.append("Outputs are research context, not trading recommendations.")
    return warnings


def goal_to_question(goal: str, payload: dict[str, Any]) -> str:
    normalized = goal.lower()
    clubs = match_clubs(goal, payload)
    if ("strongest" in normalized or "top" in normalized or "best" in normalized) and clubs:
        return f"What are {clubs[0]} current signals?"
    if ("today" in normalized or "current" in normalized or "latest" in normalized) and clubs and "compare" not in normalized:
        return f"What are {clubs[0]} current signals?"
    return goal


def scenario_seed(goal: str, question: str, answer: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    player = match_name(goal, candidate_names(payload, "player")) or match_name(question, candidate_names(payload, "player"))
    club_matches = match_clubs(goal, payload) or match_clubs(question, payload)
    club = club_matches[0] if club_matches else ""
    for table in answer.get("tables", []) or []:
        for row in table.get("rows", []) or []:
            if not player and row.get("player"):
                player = str(row["player"])
            if not club and row.get("club"):
                club = str(row["club"])
            if player and club:
                return {"player": player, "club": club}
    return {"player": player, "club": club}


def plan_agent_run(goal: str, payload: dict[str, Any], scenario_policy: str = "auto") -> dict[str, Any]:
    question = goal_to_question(goal, payload)
    steps = [
        {
            "id": "inspect_goal",
            "tool": "agent_planner",
            "reason": "Classify the user goal and choose a grounded analyst question.",
        },
        {
            "id": "check_freshness",
            "tool": "dashboard_payload",
            "reason": "Read local freshness/data-quality status before answering.",
        },
        {
            "id": "build_evidence_index",
            "tool": "build_evidence_index",
            "reason": "Create a local cited evidence layer over dashboard/articles/reports.",
        },
        {
            "id": "plan_retrieval",
            "tool": "agentic_rag_planner",
            "reason": "Break the goal into focused evidence queries for signals, market context, and credibility.",
        },
        {
            "id": "ask_with_evidence",
            "tool": "ask_analyst + Hybrid Evidence RAG",
            "reason": "Answer the selected question with evidence citations and uncertainty.",
        },
        {
            "id": "retrieve_evidence",
            "tool": "agentic_hybrid_retrieval",
            "reason": "Capture merged supporting evidence from multiple targeted retrieval queries.",
        },
        {
            "id": "compare_previous_run",
            "tool": "agent_memory",
            "reason": "Compare this result with the previous agent run when one exists.",
        },
    ]
    if scenario_policy != "never":
        steps.append(
            {
                "id": "scenario_swarm",
                "tool": "simulate_scenario",
                "reason": "Run bounded role agents when a concrete rumor signal can be identified.",
                "policy": scenario_policy,
            }
        )
    steps.append(
        {
            "id": "write_report",
            "tool": "agent_report",
            "reason": "Write a traceable Markdown report and machine-readable JSON outputs.",
        }
    )
    return {
        "goal": goal,
        "primary_question": question,
        "scenario_policy": scenario_policy,
        "steps": steps,
    }


def add_query(queries: list[dict[str, str]], purpose: str, query: str) -> None:
    clean = re.sub(r"\s+", " ", query).strip()
    if not clean:
        return
    if any(item["query"].lower() == clean.lower() for item in queries):
        return
    queries.append({"purpose": purpose, "query": clean})


def agentic_rag_queries(goal: str, primary_question: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    clubs = match_clubs(f"{goal} {primary_question}", payload)
    player = match_name(f"{goal} {primary_question}", candidate_names(payload, "player"))
    reporter = match_name(f"{goal} {primary_question}", candidate_names(payload, "reporter"))
    queries: list[dict[str, str]] = []
    add_query(queries, "primary_answer", text_join_for_agent([primary_question, goal]))
    if player:
        add_query(queries, "rumor_signal", text_join_for_agent([player, "rumor signal transfer indicator credibility"]))
        add_query(queries, "historical_transfer", text_join_for_agent([player, "confirmed transfer similar examples actual abnormal return"]))
    for club in clubs[:2]:
        add_query(queries, "club_market_context", f"{club} stock path match result latest change market context")
        add_query(queries, "club_reporters", f"{club} reporter profile credibility smoothed rate source")
        add_query(queries, "club_transfers", f"{club} confirmed transfer buyer seller transfer indicator")
    if reporter:
        add_query(queries, "reporter_credibility", f"{reporter} reporter profile credibility smoothed rate source clubs")
    if not clubs and not player and not reporter:
        add_query(queries, "broad_context", "latest live watchlist strongest credibility transfer stock signals")
    return queries[:8]


def text_join_for_agent(parts: list[Any]) -> str:
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def retrieve_agentic_evidence(
    *,
    index_path: str | Path,
    goal: str,
    primary_question: str,
    payload: dict[str, Any],
    top_k: int = 5,
    query_plan: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    index = load_evidence_index(index_path)
    queries = query_plan or agentic_rag_queries(goal, primary_question, payload)
    merged: dict[str, dict[str, Any]] = {}
    per_query: list[dict[str, Any]] = []
    per_query_top_k = max(top_k, 1)
    for item in queries:
        query = item["query"]
        purpose = item["purpose"]
        hits = retrieve_evidence(index, query, top_k=per_query_top_k)
        per_query.append(
            {
                "purpose": purpose,
                "query": query,
                "count": len(hits),
                "top_doc_types": sorted({str(hit.get("doc_type") or "") for hit in hits[:3] if hit.get("doc_type")}),
            }
        )
        for hit in hits:
            key = str(hit.get("doc_id") or hit.get("title") or hit.get("url") or "")
            if not key:
                continue
            enriched_hit = dict(hit)
            enriched_hit["retrieval_query"] = query
            enriched_hit["query_purpose"] = purpose
            enriched_hit["supporting_queries"] = [{"purpose": purpose, "query": query}]
            if key not in merged:
                merged[key] = enriched_hit
                continue
            existing = merged[key]
            existing["score"] = max(float(existing.get("score", 0.0) or 0.0), float(hit.get("score", 0.0) or 0.0))
            existing["normalized_score"] = max(
                float(existing.get("normalized_score", 0.0) or 0.0),
                float(hit.get("normalized_score", 0.0) or 0.0),
            )
            existing["retrieval_methods"] = sorted(
                set(existing.get("retrieval_methods", []) or []) | set(hit.get("retrieval_methods", []) or [])
            )
            existing["matched_terms"] = sorted(set(existing.get("matched_terms", []) or []) | set(hit.get("matched_terms", []) or []))[:12]
            existing["matched_fields"] = sorted(set(existing.get("matched_fields", []) or []) | set(hit.get("matched_fields", []) or []))
            existing["supporting_queries"].append({"purpose": purpose, "query": query})
    hits = sorted(merged.values(), key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
    limit = max(top_k * 2, top_k, 1)
    selected = hits[:limit]
    return {
        "query": goal,
        "primary_question": primary_question,
        "mode": "agentic_hybrid_rag",
        "index": rel_path(index_path),
        "generated_at": index.get("generated_at", ""),
        "retriever": (index.get("retriever") or {}).get("type", "local_hybrid"),
        "query_plan": queries,
        "per_query": per_query,
        "count": len(selected),
        "total_candidates": len(hits),
        "hits": selected,
    }


def run_created_at(run_dir: Path) -> str:
    goal = read_optional_json(run_dir / "goal.json")
    return str(goal.get("created_at") or datetime.fromtimestamp(run_dir.stat().st_mtime, tz=UTC).isoformat())


def previous_run_dir(output_dir: str | Path, current_run_id: str) -> Path | None:
    root = Path(output_dir)
    if not root.exists():
        return None
    candidates = [
        path for path in root.iterdir()
        if path.is_dir() and path.name != current_run_id and (path / "answer.json").exists()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=run_created_at, reverse=True)[0]


def citation_key(hit: dict[str, Any]) -> str:
    return str(hit.get("doc_id") or hit.get("title") or hit.get("url") or "").strip()


def citation_label(hit: dict[str, Any]) -> str:
    title = str(hit.get("title") or hit.get("doc_id") or "Evidence")
    doc_type = str(hit.get("doc_type") or "evidence")
    date = str(hit.get("date") or "")
    return f"{doc_type}: {title}" + (f" ({date})" if date else "")


def compare_previous_run(
    *,
    output_dir: str | Path,
    current_run_id: str,
    answer: dict[str, Any],
    evidence: dict[str, Any],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    previous_dir = previous_run_dir(output_dir, current_run_id)
    if previous_dir is None:
        return {
            "available": False,
            "summary": "No previous agent run was found.",
            "changes": ["No previous agent run was found."],
        }
    previous_goal = read_optional_json(previous_dir / "goal.json")
    previous_answer = read_optional_json(previous_dir / "answer.json")
    previous_evidence = read_optional_json(previous_dir / "evidence.json")
    previous_hits = list(previous_answer.get("evidence_citations", []) or previous_evidence.get("hits", []) or [])
    current_hits = list(answer.get("evidence_citations", []) or evidence.get("hits", []) or [])
    previous_map = {citation_key(hit): citation_label(hit) for hit in previous_hits if citation_key(hit)}
    current_map = {citation_key(hit): citation_label(hit) for hit in current_hits if citation_key(hit)}
    new_keys = [key for key in current_map if key not in previous_map]
    dropped_keys = [key for key in previous_map if key not in current_map]
    confidence_delta = round(float(answer.get("confidence", 0.0) or 0.0) - float(previous_answer.get("confidence", 0.0) or 0.0), 4)
    changes: list[str] = []
    if previous_answer.get("short_answer") != answer.get("short_answer"):
        changes.append("The analyst short answer changed.")
    if abs(confidence_delta) >= 0.03:
        direction = "increased" if confidence_delta > 0 else "decreased"
        changes.append(f"Answer confidence {direction} by {abs(confidence_delta):.2f}.")
    if new_keys:
        changes.append(f"{len(new_keys)} new evidence citation(s) entered the top set.")
    if dropped_keys:
        changes.append(f"{len(dropped_keys)} previous citation(s) left the top set.")
    previous_latest_live = str((previous_answer.get("freshness") or {}).get("latest_live_date") or "")
    current_latest_live = str(freshness.get("latest_live_date") or "")
    if previous_latest_live and current_latest_live and previous_latest_live != current_latest_live:
        changes.append(f"Latest live date moved from {previous_latest_live} to {current_latest_live}.")
    if not changes:
        changes.append("No major answer/evidence change from the previous agent run.")
    return {
        "available": True,
        "previous_run_id": previous_dir.name,
        "previous_created_at": run_created_at(previous_dir),
        "previous_goal": previous_goal.get("goal", ""),
        "summary": changes[0],
        "changes": changes,
        "new_evidence": [current_map[key] for key in new_keys[:6]],
        "dropped_evidence": [previous_map[key] for key in dropped_keys[:6]],
        "confidence_delta": confidence_delta,
    }


def default_memory() -> dict[str, Any]:
    return {
        "schema_version": "agent-memory-v1",
        "created_at": now_iso(),
        "updated_at": "",
        "runs_total": 0,
        "recent_runs": [],
        "frequent_entities": {},
        "useful_evidence": {},
        "warnings_seen": {},
    }


def load_agent_memory(path: str | Path) -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return default_memory()
    try:
        payload = json.loads(memory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_memory()
    base = default_memory()
    base.update(payload if isinstance(payload, dict) else {})
    return base


def increment_counter_map(mapping: dict[str, Any], key: str, amount: int = 1) -> None:
    clean = str(key or "").strip()
    if not clean:
        return
    mapping[clean] = int(mapping.get(clean, 0) or 0) + amount


def update_agent_memory(
    *,
    memory_path: str | Path,
    run_id: str,
    goal: str,
    primary_question: str,
    answer: dict[str, Any],
    evidence: dict[str, Any],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    memory = load_agent_memory(memory_path)
    memory["updated_at"] = now_iso()
    memory["runs_total"] = int(memory.get("runs_total", 0) or 0) + 1
    hits = list(answer.get("evidence_citations", []) or []) + list(evidence.get("hits", []) or [])
    seen_doc_ids: set[str] = set()
    useful_evidence = dict(memory.get("useful_evidence", {}) or {})
    frequent_entities = dict(memory.get("frequent_entities", {}) or {})
    for hit in hits:
        doc_id = str(hit.get("doc_id") or hit.get("title") or hit.get("url") or "").strip()
        if doc_id and doc_id not in seen_doc_ids:
            seen_doc_ids.add(doc_id)
            previous = useful_evidence.get(doc_id, {}) or {}
            useful_evidence[doc_id] = {
                "doc_id": doc_id,
                "count": int(previous.get("count", 0) or 0) + 1,
                "last_seen": memory["updated_at"],
                "title": hit.get("title", previous.get("title", "")),
                "doc_type": hit.get("doc_type", previous.get("doc_type", "")),
                "source_path": hit.get("source_path", previous.get("source_path", "")),
                "club": hit.get("club", previous.get("club", "")),
                "player": hit.get("player", previous.get("player", "")),
                "reporter": hit.get("reporter", previous.get("reporter", "")),
                "source": hit.get("source", previous.get("source", "")),
            }
        for field in ["club", "player", "reporter", "source"]:
            value = str(hit.get(field) or "").strip()
            if value:
                increment_counter_map(frequent_entities, f"{field}:{value}")
    warnings_seen = dict(memory.get("warnings_seen", {}) or {})
    for warning in list(freshness.get("warnings", []) or []) + list(answer.get("warnings", []) or []):
        increment_counter_map(warnings_seen, warning)
    recent_runs = list(memory.get("recent_runs", []) or [])
    recent_runs.append(
        {
            "run_id": run_id,
            "time": memory["updated_at"],
            "goal": goal,
            "primary_question": primary_question,
            "intent": answer.get("intent", ""),
            "confidence": answer.get("confidence", 0.0),
            "latest_live_date": freshness.get("latest_live_date", ""),
            "top_evidence": list(seen_doc_ids)[:6],
        }
    )
    memory["recent_runs"] = recent_runs[-20:]
    memory["frequent_entities"] = dict(sorted(frequent_entities.items()))
    memory["useful_evidence"] = dict(sorted(useful_evidence.items()))
    memory["warnings_seen"] = dict(sorted(warnings_seen.items()))
    output_path = Path(memory_path)
    write_json(output_path, memory)
    return {
        "path": rel_path(output_path),
        "summary": agent_memory_summary(memory),
    }


def agent_memory_summary(memory: dict[str, Any]) -> dict[str, Any]:
    entity_counts = Counter({key: int(value or 0) for key, value in (memory.get("frequent_entities", {}) or {}).items()})
    evidence_counts = Counter(
        {
            key: int((value or {}).get("count", 0) or 0)
            for key, value in (memory.get("useful_evidence", {}) or {}).items()
        }
    )
    useful_evidence = memory.get("useful_evidence", {}) or {}
    return {
        "runs_total": int(memory.get("runs_total", 0) or 0),
        "updated_at": memory.get("updated_at", ""),
        "top_entities": [
            {"entity": key.split(":", 1)[-1], "kind": key.split(":", 1)[0], "count": count}
            for key, count in entity_counts.most_common(8)
        ],
        "top_evidence": [
            {
                "doc_id": doc_id,
                "count": count,
                "title": (useful_evidence.get(doc_id, {}) or {}).get("title", ""),
                "doc_type": (useful_evidence.get(doc_id, {}) or {}).get("doc_type", ""),
                "source_path": (useful_evidence.get(doc_id, {}) or {}).get("source_path", ""),
            }
            for doc_id, count in evidence_counts.most_common(6)
        ],
        "recent_run_count": len(memory.get("recent_runs", []) or []),
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


def agent_report_markdown(
    *,
    goal: str,
    plan: dict[str, Any],
    freshness: dict[str, Any],
    answer: dict[str, Any],
    evidence: dict[str, Any],
    scenario: dict[str, Any] | None,
    memory: dict[str, Any],
    outputs: dict[str, str],
) -> str:
    lines = [
        "# Agent Run Report",
        "",
        f"Goal: {goal}",
        "",
        "## Plan",
        "",
    ]
    lines.extend(
        markdown_table(
            ["Step", "Tool", "Reason"],
            [[step["id"], step["tool"], step["reason"]] for step in plan.get("steps", [])],
        )
    )
    lines.extend(
        [
            "",
            "## Freshness",
            "",
            f"- Dashboard generated at: {freshness.get('generated_at') or '-'}",
            f"- Latest season: {freshness.get('latest_season') or '-'}",
            f"- Live status: {freshness.get('live_status') or 'unknown'}",
            f"- Latest live date: {freshness.get('latest_live_date') or '-'}",
            f"- Live watchlist rows: {freshness.get('live_watchlist_count', 0)}",
            "",
            "## Analyst Answer",
            "",
            f"- Intent: {answer.get('intent', '-')}",
            f"- Confidence: {answer.get('confidence', '-')}",
            f"- Short answer: {answer.get('short_answer', '-')}",
            "",
            "## Evidence Citations",
            "",
        ]
    )
    citations = answer.get("evidence_citations", []) or evidence.get("hits", []) or []
    lines.extend(
        markdown_table(
            ["Type", "Title", "Date", "Source", "Path"],
            [
                [
                    hit.get("doc_type", "-"),
                    hit.get("title", "-"),
                    hit.get("date", "-"),
                    hit.get("source", "-"),
                    hit.get("source_path", "-"),
                ]
                for hit in citations[:8]
            ],
        )
    )
    if scenario:
        lines.extend(
            [
                "",
                "## Scenario Swarm",
                "",
                f"- Simulation: {scenario.get('simulation_id', '-')}",
                f"- Consensus: {(scenario.get('summary') or {}).get('consensus_stance', '-')}",
                f"- Confidence: {(scenario.get('summary') or {}).get('consensus_confidence', '-')}",
                f"- Report: `{scenario.get('report', '-')}`",
            ]
        )
    else:
        lines.extend(["", "## Scenario Swarm", "", "No scenario was run for this goal."])
    lines.extend(["", "## What Changed Since Last Run", ""])
    if memory.get("available"):
        lines.append(f"Previous run: `{memory.get('previous_run_id', '-')}`")
        lines.append("")
    for item in memory.get("changes", []) or ["No previous agent run was found."]:
        lines.append(f"- {item}")
    if memory.get("new_evidence"):
        lines.extend(["", "New top evidence:"])
        lines.extend(f"- {item}" for item in memory.get("new_evidence", []))
    persistent = memory.get("persistent", {}) or {}
    if persistent:
        lines.extend(["", "## Persistent Agent Memory", ""])
        lines.append(f"- Remembered runs: {persistent.get('runs_total', 0)}")
        top_entities = persistent.get("top_entities", []) or []
        if top_entities:
            lines.append("- Recurring entities: " + ", ".join(f"{item.get('kind')}: {item.get('entity')} ({item.get('count')})" for item in top_entities[:5]))
        top_evidence = persistent.get("top_evidence", []) or []
        if top_evidence:
            lines.append("- Reused evidence: " + ", ".join(str(item.get("title") or item.get("doc_id")) for item in top_evidence[:4]))
    lines.extend(["", "## What Would Change The Read", ""])
    for item in answer.get("what_would_change_mind", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Warnings", ""])
    for item in (freshness.get("warnings", []) or []) + (answer.get("warnings", []) or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Outputs", ""])
    for key, path in outputs.items():
        lines.append(f"- {key}: `{path}`")
    lines.append("")
    return "\n".join(lines)


def dashboard_report_href(path: str | Path) -> str:
    report_path = Path(path)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    try:
        return report_path.relative_to(ROOT / "app" / "static").as_posix()
    except ValueError:
        return rel_path(report_path)


def build_dashboard_agent_payload(
    *,
    run_id: str,
    goal: str,
    primary_question: str,
    created_at: str,
    freshness: dict[str, Any],
    answer: dict[str, Any],
    evidence: dict[str, Any],
    scenario: dict[str, Any] | None,
    memory: dict[str, Any],
    outputs: dict[str, str],
    report_path: str | Path,
) -> dict[str, Any]:
    citations = list(answer.get("evidence_citations", []) or evidence.get("hits", []) or [])
    method_counts = Counter(
        method
        for hit in citations
        for method in (hit.get("retrieval_methods", []) or [])
    )
    doc_type_counts = Counter(str(hit.get("doc_type") or "evidence") for hit in citations)
    source_counts = Counter(str(hit.get("source") or hit.get("source_path") or "local") for hit in citations)
    return {
        "available": True,
        "run_id": run_id,
        "generated_at": created_at,
        "goal": goal,
        "primary_question": primary_question,
        "freshness": freshness,
        "answer": {
            "intent": answer.get("intent", ""),
            "short_answer": answer.get("short_answer", ""),
            "confidence": answer.get("confidence", 0.0),
            "warnings": answer.get("warnings", []),
            "what_would_change_mind": answer.get("what_would_change_mind", []),
            "citation_count": len(citations),
        },
        "evidence_citations": citations[:8],
        "rag_lens": {
            "mode": evidence.get("mode") or (answer.get("agentic_rag", {}) or {}).get("mode", ""),
            "retriever": evidence.get("retriever") or (answer.get("rag", {}) or {}).get("retriever", ""),
            "query_plan": evidence.get("query_plan", [])[:8],
            "per_query": evidence.get("per_query", [])[:8],
            "total_candidates": evidence.get("total_candidates", len(citations)),
            "shown_citations": len(citations[:8]),
            "retrieval_methods": [
                {"method": method, "count": count}
                for method, count in method_counts.most_common()
            ],
            "doc_type_mix": [
                {"doc_type": doc_type, "count": count}
                for doc_type, count in doc_type_counts.most_common()
            ],
            "source_mix": [
                {"source": source, "count": count}
                for source, count in source_counts.most_common(6)
            ],
            "what_would_change_mind": answer.get("what_would_change_mind", []),
        },
        "memory": memory,
        "scenario": {
            "available": bool(scenario),
            "simulation_id": (scenario or {}).get("simulation_id", ""),
            "summary": (scenario or {}).get("summary", {}),
            "report": (scenario or {}).get("report", ""),
        },
        "outputs": outputs,
        "report_href": dashboard_report_href(report_path),
    }


def publish_dashboard_agent(path: str | Path, report_path: str | Path, payload: dict[str, Any], report: str) -> None:
    write_json(Path(path), payload)
    ensure_parent(Path(report_path))
    Path(report_path).write_text(report, encoding="utf-8")


def run_agent(
    *,
    goal: str,
    payload_path: str | Path = ROOT / "app" / "static" / "data" / "dashboard_data.json",
    output_dir: str | Path = DEFAULT_AGENT_OUTPUT_DIR,
    evidence_index: str | Path = DEFAULT_EVIDENCE_INDEX,
    run_id: str = "",
    scenario_policy: str = "auto",
    rounds: int = 2,
    top_k: int = 5,
    rebuild_index: bool = True,
    memory_path: str | Path | None = None,
    dashboard_output: str | Path | None = DEFAULT_DASHBOARD_AGENT,
    dashboard_report_output: str | Path = DEFAULT_DASHBOARD_AGENT_REPORT,
) -> dict[str, Any]:
    if not goal.strip():
        raise ValueError("Agent goal is required")
    payload_file = Path(payload_path)
    payload = load_dashboard_payload(payload_file)
    created_at = datetime.now(tz=UTC)
    agent_run_id = run_id or f"{created_at.strftime('%Y%m%dT%H%M%SZ')}_{slugify(goal)}"
    run_dir = Path(output_dir) / agent_run_id
    trace: list[dict[str, Any]] = []

    append_trace(trace, "inspect_goal", "started", {"goal": goal})
    plan = plan_agent_run(goal, payload, scenario_policy=scenario_policy)
    append_trace(trace, "inspect_goal", "completed", {"primary_question": plan["primary_question"]})

    append_trace(trace, "check_freshness", "started", {"payload": rel_path(payload_file)})
    freshness = freshness_summary(payload)
    append_trace(trace, "check_freshness", "completed", freshness)

    evidence_path = Path(evidence_index)
    append_trace(trace, "build_evidence_index", "started", {"output": rel_path(evidence_path), "rebuild": rebuild_index})
    if rebuild_index or not evidence_path.exists():
        evidence_result = build_evidence_index(payload_path=payload_file, output_path=evidence_path)
    else:
        evidence_result = {"output": rel_path(evidence_path), "stats": {}, "reused": True}
    append_trace(trace, "build_evidence_index", "completed", evidence_result)

    append_trace(trace, "plan_retrieval", "started", {"goal": goal, "primary_question": plan["primary_question"]})
    query_plan = agentic_rag_queries(goal, plan["primary_question"], payload)
    append_trace(
        trace,
        "plan_retrieval",
        "completed",
        {"query_count": len(query_plan), "purposes": [item["purpose"] for item in query_plan]},
    )

    append_trace(trace, "ask_with_evidence", "started", {"question": plan["primary_question"]})
    answer = ask_analyst(
        plan["primary_question"],
        payload=payload,
        payload_path=payload_file,
        include_evidence=True,
        evidence_index_path=evidence_path,
        evidence_top_k=top_k,
    )
    append_trace(trace, "ask_with_evidence", "completed", {"intent": answer.get("intent"), "confidence": answer.get("confidence")})

    append_trace(trace, "retrieve_evidence", "started", {"query_count": len(query_plan), "top_k": top_k})
    evidence = retrieve_agentic_evidence(
        index_path=evidence_path,
        goal=goal,
        primary_question=plan["primary_question"],
        payload=payload,
        top_k=top_k,
        query_plan=query_plan,
    )
    answer["agentic_rag"] = {
        "mode": evidence.get("mode", "agentic_hybrid_rag"),
        "query_count": len(query_plan),
        "queries": query_plan,
        "retrieval_methods": sorted({method for hit in evidence.get("hits", []) for method in hit.get("retrieval_methods", [])}),
    }
    append_trace(trace, "retrieve_evidence", "completed", {"count": evidence.get("count", 0), "total_candidates": evidence.get("total_candidates", 0)})

    append_trace(trace, "compare_previous_run", "started", {"output_dir": rel_path(output_dir)})
    memory = compare_previous_run(
        output_dir=output_dir,
        current_run_id=agent_run_id,
        answer=answer,
        evidence=evidence,
        freshness=freshness,
    )
    resolved_memory_path = Path(memory_path) if memory_path else Path(output_dir) / "memory.json"
    persistent_memory = update_agent_memory(
        memory_path=resolved_memory_path,
        run_id=agent_run_id,
        goal=goal,
        primary_question=plan["primary_question"],
        answer=answer,
        evidence=evidence,
        freshness=freshness,
    )
    memory["persistent"] = persistent_memory["summary"]
    memory["persistent_path"] = persistent_memory["path"]
    append_trace(
        trace,
        "compare_previous_run",
        "completed",
        {
            "available": memory.get("available"),
            "summary": memory.get("summary"),
            "persistent_runs_total": (memory.get("persistent") or {}).get("runs_total", 0),
        },
    )

    scenario_result: dict[str, Any] | None = None
    if scenario_policy != "never":
        seed = scenario_seed(goal, plan["primary_question"], answer, payload)
        should_run = scenario_policy == "always" or bool(seed.get("player"))
        if should_run:
            append_trace(trace, "scenario_swarm", "started", seed)
            try:
                scenario_result = run_scenario_swarm(
                    question=plan["primary_question"],
                    player=seed.get("player", ""),
                    club=seed.get("club", ""),
                    payload_path=payload_file,
                    output_dir=run_dir / "scenario",
                    rounds=rounds,
                    dashboard_output=None,
                )
                append_trace(trace, "scenario_swarm", "completed", {"simulation_id": scenario_result.get("simulation_id")})
            except (KeyError, ValueError) as exc:
                append_trace(trace, "scenario_swarm", "skipped", {"reason": str(exc), "seed": seed})
        else:
            append_trace(trace, "scenario_swarm", "skipped", {"reason": "No concrete player signal found", "seed": seed})

    outputs = {
        "goal": rel_path(run_dir / "goal.json"),
        "plan": rel_path(run_dir / "plan.json"),
        "trace": rel_path(run_dir / "trace.jsonl"),
        "answer": rel_path(run_dir / "answer.json"),
        "evidence": rel_path(run_dir / "evidence.json"),
        "memory": rel_path(resolved_memory_path),
        "report": rel_path(run_dir / "agent_report.md"),
    }
    goal_doc = {
        "run_id": agent_run_id,
        "goal": goal,
        "created_at": created_at.isoformat(),
        "payload_path": rel_path(payload_file),
        "evidence_index": rel_path(evidence_path),
        "memory_path": rel_path(resolved_memory_path),
    }
    report = agent_report_markdown(
        goal=goal,
        plan=plan,
        freshness=freshness,
        answer=answer,
        evidence=evidence,
        scenario=scenario_result,
        memory=memory,
        outputs=outputs,
    )
    write_json(run_dir / "goal.json", goal_doc)
    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "answer.json", answer)
    write_json(run_dir / "evidence.json", evidence)
    ensure_parent(run_dir / "agent_report.md")
    (run_dir / "agent_report.md").write_text(report, encoding="utf-8")
    append_trace(trace, "write_report", "completed", outputs)
    write_jsonl(run_dir / "trace.jsonl", trace)
    dashboard_payload = {}
    if dashboard_output is not None:
        dashboard_payload = build_dashboard_agent_payload(
            run_id=agent_run_id,
            goal=goal,
            primary_question=plan["primary_question"],
            created_at=created_at.isoformat(),
            freshness=freshness,
            answer=answer,
            evidence=evidence,
            scenario=scenario_result,
            memory=memory,
            outputs=outputs,
            report_path=dashboard_report_output,
        )
        publish_dashboard_agent(dashboard_output, dashboard_report_output, dashboard_payload, report)
    return {
        "run_id": agent_run_id,
        "run_dir": rel_path(run_dir),
        "goal": goal,
        "primary_question": plan["primary_question"],
        "status": "completed",
        "outputs": outputs,
        "answer": {
            "intent": answer.get("intent", ""),
            "short_answer": answer.get("short_answer", ""),
            "confidence": answer.get("confidence", 0.0),
            "citation_count": len(answer.get("evidence_citations", []) or []),
        },
        "scenario": scenario_result or {},
        "freshness": freshness,
        "memory": memory,
        "dashboard_agent": rel_path(dashboard_output) if dashboard_output is not None else "",
        "dashboard_report": rel_path(dashboard_report_output) if dashboard_output is not None else "",
    }
