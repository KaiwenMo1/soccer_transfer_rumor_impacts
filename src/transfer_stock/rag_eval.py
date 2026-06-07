from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ROOT
from .data_quality import clamp, parse_datetime, score_status
from .io import ensure_parent


DEFAULT_AGENT_SNAPSHOT = ROOT / "app" / "static" / "data" / "agent_latest.json"
DEFAULT_RAG_AUDIT_JSON = ROOT / "app" / "static" / "data" / "rag_audit_latest.json"
DEFAULT_RAG_AUDIT_MD = DATA_DIR / "reports" / "rag_trust_audit.md"

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_'-]*")
STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "into",
    "not",
    "that",
    "the",
    "this",
    "with",
}


def rel_path(path: str | Path) -> str:
    path_obj = Path(path)
    if not path_obj.is_absolute():
        path_obj = ROOT / path_obj
    try:
        return path_obj.relative_to(ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    ensure_parent(output)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def tokenize(value: Any) -> list[str]:
    return [
        token.strip("'")
        for token in TOKEN_RE.findall(str(value or "").lower())
        if len(token.strip("'")) > 2 and token.strip("'") not in STOPWORDS
    ]


def hit_text(hit: dict[str, Any]) -> str:
    metadata = hit.get("metadata", {}) or {}
    return " ".join(
        str(part or "")
        for part in [
            hit.get("title", ""),
            hit.get("snippet", ""),
            hit.get("doc_type", ""),
            hit.get("club", ""),
            hit.get("player", ""),
            hit.get("reporter", ""),
            hit.get("source", ""),
            " ".join(str(value) for value in metadata.values() if value not in {"", None}),
        ]
    )


def citation_support_score(answer_text: str, citations: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    answer_tokens = [token for token in tokenize(answer_text) if len(token) > 3]
    if not answer_tokens:
        return 0.0, {"answer_terms": 0, "covered_terms": 0, "missing_terms": []}
    evidence_tokens = Counter()
    for hit in citations:
        evidence_tokens.update(tokenize(hit_text(hit)))
    unique_terms = sorted(set(answer_tokens))
    covered = [token for token in unique_terms if evidence_tokens.get(token, 0) > 0]
    missing = [token for token in unique_terms if token not in covered]
    score = len(covered) / max(len(unique_terms), 1)
    return clamp(score), {
        "answer_terms": len(unique_terms),
        "covered_terms": len(covered),
        "missing_terms": missing[:12],
    }


def citation_strength_score(citations: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    if not citations:
        return 0.0, {"citation_count": 0, "avg_normalized_score": 0.0}
    scores = [float(hit.get("normalized_score", 0.0) or 0.0) for hit in citations]
    doc_types = Counter(str(hit.get("doc_type") or "evidence") for hit in citations)
    return clamp(sum(scores) / len(scores)), {
        "citation_count": len(citations),
        "avg_normalized_score": round(sum(scores) / len(scores), 4),
        "doc_type_mix": dict(doc_types.most_common()),
    }


def source_diversity_score(citations: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    if not citations:
        return 0.0, {"unique_sources": 0}
    sources = [
        str(hit.get("source") or hit.get("source_path") or "local").strip()
        for hit in citations
    ]
    unique_sources = sorted(set(source for source in sources if source))
    source_counts = Counter(sources)
    score = clamp((len(unique_sources) / max(len(citations), 1)) * 1.35)
    return score, {
        "unique_sources": len(unique_sources),
        "top_sources": dict(source_counts.most_common(6)),
    }


def retrieval_health_score(agent: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    lens = agent.get("rag_lens", {}) or {}
    query_count = len(lens.get("query_plan", []) or [])
    methods = {item.get("method") for item in lens.get("retrieval_methods", []) or [] if item.get("method")}
    total_candidates = int(lens.get("total_candidates", 0) or 0)
    per_query = lens.get("per_query", []) or []
    empty_queries = [item.get("purpose", "query") for item in per_query if int(item.get("count", 0) or 0) == 0]
    score = (
        clamp(query_count / 5.0) * 0.35
        + clamp(len(methods) / 3.0) * 0.35
        + clamp(total_candidates / 10.0) * 0.30
    )
    return clamp(score), {
        "query_count": query_count,
        "retrieval_methods": sorted(methods),
        "total_candidates": total_candidates,
        "empty_queries": empty_queries[:6],
    }


def freshness_score(agent: dict[str, Any], citations: list[dict[str, Any]], now: datetime | None = None) -> tuple[float, dict[str, Any]]:
    current = now or datetime.now(tz=UTC)
    dated_hits = []
    for hit in citations:
        dt = parse_datetime(hit.get("date", ""))
        if dt:
            dated_hits.append((hit, dt))
    if not dated_hits:
        return 0.45, {"dated_citations": 0, "latest_citation_date": ""}
    days = [(current.date() - dt.date()).days for _, dt in dated_hits]
    latest_date = max(dt.date().isoformat() for _, dt in dated_hits)
    avg_days = sum(max(day, 0) for day in days) / len(days)
    if avg_days <= 14:
        score = 1.0
    elif avg_days <= 45:
        score = 0.76
    elif avg_days <= 120:
        score = 0.55
    elif avg_days <= 365:
        score = 0.34
    else:
        score = 0.18
    return clamp(score), {
        "dated_citations": len(dated_hits),
        "latest_citation_date": latest_date,
        "avg_citation_age_days": round(avg_days, 1),
    }


def uncertainty_score(agent: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    answer = agent.get("answer", {}) or {}
    lens = agent.get("rag_lens", {}) or {}
    warnings = list(answer.get("warnings", []) or [])
    change_notes = list(lens.get("what_would_change_mind", []) or [])
    score = clamp((0.45 if warnings else 0.0) + (0.55 if change_notes else 0.0))
    return score, {
        "warnings": warnings[:6],
        "what_would_change_mind": change_notes[:6],
    }


def dimension(name: str, score: float, evidence: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "score": round(clamp(score), 4),
        "status": score_status(score),
        "evidence": evidence,
        "warnings": warnings or [],
    }


def build_rag_audit(agent: dict[str, Any], *, agent_path: str | Path = DEFAULT_AGENT_SNAPSHOT, now: datetime | None = None) -> dict[str, Any]:
    if not agent or not agent.get("available", True):
        return {
            "available": False,
            "generated_at": now_iso(),
            "summary": "No agent snapshot was available for RAG evaluation.",
            "dimensions": [],
            "recommendations": ["Run PYTHONPATH=src python3 -m transfer_stock.cli agent-run --goal \"Explain the strongest current rumor\""],
            "source_paths": {"agent_snapshot": rel_path(agent_path)},
        }
    answer = agent.get("answer", {}) or {}
    citations = list(agent.get("evidence_citations", []) or [])
    support, support_evidence = citation_support_score(answer.get("short_answer", ""), citations)
    strength, strength_evidence = citation_strength_score(citations)
    diversity, diversity_evidence = source_diversity_score(citations)
    retrieval, retrieval_evidence = retrieval_health_score(agent)
    freshness, freshness_evidence = freshness_score(agent, citations, now=now)
    uncertainty, uncertainty_evidence = uncertainty_score(agent)
    dimensions = [
        dimension("Answer Support", support, support_evidence, ["Some answer terms were not found in citations."] if support < 0.55 else []),
        dimension("Citation Strength", strength, strength_evidence, ["Attach more high-scoring citations."] if strength < 0.55 else []),
        dimension("Source Diversity", diversity, diversity_evidence, ["Evidence comes from a narrow source set."] if diversity < 0.5 else []),
        dimension("Retrieval Health", retrieval, retrieval_evidence, ["Some subqueries returned no evidence."] if retrieval_evidence.get("empty_queries") else []),
        dimension("Citation Freshness", freshness, freshness_evidence, ["Citations are old for a live market read."] if freshness < 0.5 else []),
        dimension("Uncertainty Disclosure", uncertainty, uncertainty_evidence, ["Add warnings and what-would-change-mind notes."] if uncertainty < 0.5 else []),
    ]
    weights = {
        "Answer Support": 0.26,
        "Citation Strength": 0.18,
        "Source Diversity": 0.14,
        "Retrieval Health": 0.18,
        "Citation Freshness": 0.12,
        "Uncertainty Disclosure": 0.12,
    }
    overall = sum(item["score"] * weights[item["name"]] for item in dimensions)
    recommendations = []
    if support < 0.65:
        recommendations.append("Improve grounding: answer terms should appear in retrieved titles/snippets/entities.")
    if diversity < 0.6:
        recommendations.append("Improve source diversity: fetch more independent articles before presenting the read strongly.")
    if retrieval < 0.65:
        recommendations.append("Improve retrieval health: rebuild the evidence index and inspect subqueries with low hit counts.")
    if freshness < 0.55:
        recommendations.append("Refresh live articles and rerun agent-autopilot before using this as a current read.")
    if not recommendations:
        recommendations.append("RAG audit is usable; review citations before making any market interpretation.")
    return {
        "available": True,
        "generated_at": now_iso(),
        "agent_run_id": agent.get("run_id", ""),
        "agent_goal": agent.get("goal", ""),
        "answer": answer.get("short_answer", ""),
        "overall_score": round(clamp(overall), 4),
        "overall_status": score_status(overall),
        "summary": f"RAG trust audit is {score_status(overall).replace('_', ' ')} ({overall:.0%}).",
        "dimensions": dimensions,
        "recommendations": recommendations,
        "source_paths": {"agent_snapshot": rel_path(agent_path)},
    }


def rag_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# RAG Trust Audit",
        "",
        audit.get("summary", "No audit summary."),
        "",
        "This audit is inspired by RAG evaluation patterns such as answer support, citation strength, source diversity, retrieval health, freshness, and uncertainty disclosure.",
        "",
        "## Dimensions",
        "",
        "| Dimension | Score | Status |",
        "| --- | --- | --- |",
    ]
    for item in audit.get("dimensions", []) or []:
        lines.append(f"| {item.get('name')} | {item.get('score')} | {item.get('status')} |")
    lines.extend(["", "## Recommendations", ""])
    for item in audit.get("recommendations", []) or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def write_rag_audit(
    *,
    agent_path: str | Path = DEFAULT_AGENT_SNAPSHOT,
    output_json: str | Path = DEFAULT_RAG_AUDIT_JSON,
    output_markdown: str | Path | None = DEFAULT_RAG_AUDIT_MD,
    now: datetime | None = None,
) -> dict[str, Any]:
    agent_file = Path(agent_path)
    agent = load_json(agent_file) if agent_file.exists() else {}
    audit = build_rag_audit(agent, agent_path=agent_file, now=now)
    write_json(output_json, audit)
    audit["json_path"] = rel_path(output_json)
    if output_markdown is not None:
        output_md = Path(output_markdown)
        ensure_parent(output_md)
        output_md.write_text(rag_audit_markdown(audit), encoding="utf-8")
        audit["markdown_path"] = rel_path(output_md)
    return audit
