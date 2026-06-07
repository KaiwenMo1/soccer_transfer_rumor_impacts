from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ROOT
from .io import ensure_parent


DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"
DEFAULT_RUMOR_GRAPH = DATA_DIR / "processed" / "graphs" / "rumor_graph.json"
DEFAULT_DASHBOARD_RUMOR_GRAPH = ROOT / "app" / "static" / "data" / "rumor_graph.json"


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def first_value(row: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value not in {"", None}:
            return str(value)
    return default


def short_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 10:
        return text[:10]
    return text


def add_node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, label: str, **extra: Any) -> None:
    if not label:
        return
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "weight": 0,
            "score": 0.0,
            **extra,
        }
    else:
        existing.update({key: value for key, value in extra.items() if value not in {"", None}})
    nodes[node_id]["weight"] = int(nodes[node_id].get("weight", 0)) + 1
    nodes[node_id]["score"] = max(safe_float(nodes[node_id].get("score")), safe_float(extra.get("score")))


def edge_key(source: str, target: str, edge_type: str) -> str:
    return f"{source}->{target}:{edge_type}"


def add_edge(
    edges: dict[str, dict[str, Any]],
    source: str,
    target: str,
    edge_type: str,
    *,
    date: str = "",
    weight: float = 1.0,
    score: float = 0.0,
    evidence: str = "",
) -> None:
    if not source or not target:
        return
    key = edge_key(source, target, edge_type)
    item = edges.get(key)
    if item is None:
        edges[key] = {
            "id": key,
            "source": source,
            "target": target,
            "type": edge_type,
            "weight": 0.0,
            "score": 0.0,
            "first_seen": date,
            "last_seen": date,
            "evidence": [],
        }
        item = edges[key]
    item["weight"] = round(safe_float(item.get("weight")) + weight, 4)
    item["score"] = max(safe_float(item.get("score")), score)
    if date:
        if not item.get("first_seen") or date < item["first_seen"]:
            item["first_seen"] = date
        if not item.get("last_seen") or date > item["last_seen"]:
            item["last_seen"] = date
    if evidence and evidence not in item["evidence"]:
        item["evidence"].append(evidence)
        item["evidence"] = item["evidence"][:4]


def graph_rows(payload: dict[str, Any], limit: int = 80) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(payload.get("live_watchlist", []) or [])
    for season_rows in (payload.get("signals_by_season", {}) or {}).values():
        rows.extend(season_rows or [])
    details = payload.get("watchlist_details", {}) or {}
    rows.extend(details.values())
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = first_value(row, ["group_key", "claim_ids", "article_id"]) or repr(
            (
                row.get("player"),
                row.get("target_club") or row.get("club"),
                row.get("latest_published_at") or row.get("published_at") or row.get("date"),
            )
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return sorted(
        output,
        key=lambda row: first_value(row, ["latest_published_at", "published_at", "date"]),
        reverse=True,
    )[:limit]


def build_rumor_graph(payload: dict[str, Any], *, limit: int = 80) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    timelines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stage_counts: Counter[str] = Counter()
    club_counts: Counter[str] = Counter()
    reporter_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for row in graph_rows(payload, limit=limit):
        player = first_value(row, ["player", "primary_player"])
        club = first_value(row, ["target_club", "club", "primary_club"])
        reporter = first_value(row, ["latest_journalist", "journalist"], "Unknown reporter")
        source = first_value(row, ["latest_source", "source"], "Unknown source")
        stage = first_value(row, ["latest_rumor_stage", "rumor_stage"], "unclear")
        label = first_value(row, ["blended_label", "predicted_label", "actual_label"], "unknown")
        date = short_date(first_value(row, ["latest_published_at", "published_at", "date"]))
        confidence = safe_float(row.get("prediction_confidence"), 0.0)
        credibility = safe_float(row.get("credibility_score"), 0.0)
        score = max(confidence, credibility)
        evidence = first_value(row, ["primary_headline", "signal_summary", "title", "url"])
        role = first_value(row, ["target_role", "deal_path"], "")
        ticker = first_value(row, ["target_ticker"], "")

        if not player or not club:
            continue

        reporter_id = f"reporter:{reporter}"
        source_id = f"source:{source}"
        player_id = f"player:{player}"
        club_id = f"club:{club}"
        stage_id = f"stage:{stage}"
        label_id = f"market:{label}"

        add_node(nodes, reporter_id, "reporter", reporter, score=credibility)
        add_node(nodes, source_id, "source", source, score=credibility)
        add_node(nodes, player_id, "player", player, score=score, latest_stage=stage)
        add_node(nodes, club_id, "club", club, score=score, ticker=ticker)
        add_node(nodes, stage_id, "stage", stage, score=score)
        add_node(nodes, label_id, "market", label, score=confidence)

        add_edge(edges, reporter_id, source_id, "published_via", date=date, score=credibility, evidence=evidence)
        add_edge(edges, source_id, player_id, "reported_player", date=date, score=credibility, evidence=evidence)
        add_edge(edges, player_id, club_id, f"linked_to_{role or 'club'}", date=date, score=score, evidence=evidence)
        add_edge(edges, player_id, stage_id, "rumor_stage", date=date, score=score, evidence=evidence)
        add_edge(edges, club_id, label_id, "market_read", date=date, score=confidence, evidence=evidence)

        timelines[f"{player}::{club}"].append(
            {
                "date": date,
                "player": player,
                "club": club,
                "stage": stage,
                "reporter": reporter,
                "source": source,
                "label": label,
                "confidence": confidence,
                "credibility": credibility,
                "headline": evidence,
            }
        )
        stage_counts[stage] += 1
        club_counts[club] += 1
        reporter_counts[reporter] += 1
        source_counts[source] += 1

    timeline_items = []
    for key, items in timelines.items():
        items_sorted = sorted(items, key=lambda item: item.get("date", ""))
        latest = items_sorted[-1] if items_sorted else {}
        timeline_items.append(
            {
                "id": key,
                "player": latest.get("player", ""),
                "club": latest.get("club", ""),
                "event_count": len(items_sorted),
                "first_seen": items_sorted[0].get("date", "") if items_sorted else "",
                "last_seen": latest.get("date", ""),
                "latest_stage": latest.get("stage", ""),
                "latest_label": latest.get("label", ""),
                "avg_credibility": round(sum(safe_float(item.get("credibility")) for item in items_sorted) / max(len(items_sorted), 1), 4),
                "events": items_sorted[-8:],
            }
        )

    return {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "inspired_by": {
            "project": "Graphiti",
            "url": "https://github.com/getzep/graphiti",
            "idea": "Temporal knowledge graphs for changing facts and agent context.",
        },
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "timeline_count": len(timeline_items),
            "top_clubs": [{"club": key, "count": value} for key, value in club_counts.most_common(8)],
            "top_sources": [{"source": key, "count": value} for key, value in source_counts.most_common(8)],
            "top_reporters": [{"reporter": key, "count": value} for key, value in reporter_counts.most_common(8)],
            "stage_mix": [{"stage": key, "count": value} for key, value in stage_counts.most_common()],
        },
        "nodes": sorted(nodes.values(), key=lambda item: (item["type"], -int(item.get("weight", 0)), item["label"])),
        "edges": sorted(edges.values(), key=lambda item: (-safe_float(item.get("weight")), item["type"])),
        "timelines": sorted(timeline_items, key=lambda item: (item["last_seen"], item["event_count"]), reverse=True)[:20],
        "warnings": [
            "This graph shows evidence relationships, not causal proof of stock movement.",
            "Changing rumor stages are useful context, but dates may reflect article publication rather than the true private negotiation date.",
        ],
    }


def write_rumor_graph(
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    output_path: str | Path = DEFAULT_RUMOR_GRAPH,
    dashboard_output: str | Path | None = DEFAULT_DASHBOARD_RUMOR_GRAPH,
    limit: int = 80,
) -> dict[str, Any]:
    payload_file = Path(payload_path)
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    graph = build_rumor_graph(payload, limit=limit)
    output = Path(output_path)
    ensure_parent(output)
    output.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    if dashboard_output is not None:
        dashboard_path = Path(dashboard_output)
        ensure_parent(dashboard_path)
        dashboard_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return {
        "output": str(output),
        "dashboard_output": "" if dashboard_output is None else str(dashboard_output),
        "node_count": graph["summary"]["node_count"],
        "edge_count": graph["summary"]["edge_count"],
        "timeline_count": graph["summary"]["timeline_count"],
    }
