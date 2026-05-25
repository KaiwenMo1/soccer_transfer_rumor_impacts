from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .analyst import (
    DEFAULT_PAYLOAD,
    ask_analyst,
    candidate_names,
    find_signal_for_player,
    load_dashboard_payload,
    match_clubs,
    match_name,
    parse_float,
    row_club,
)
from .config import DATA_DIR, ROOT
from .io import ensure_parent


DEFAULT_OUTPUT_DIR = DATA_DIR / "simulations"
DEFAULT_DASHBOARD_SCENARIO = ROOT / "app" / "static" / "data" / "scenario_latest.json"
DEFAULT_DASHBOARD_SCENARIO_REPORT = ROOT / "app" / "static" / "data" / "scenario_latest_report.md"

ROLE_AGENTS = [
    {
        "id": "club_finance",
        "name": "Club Finance Agent",
        "description": "Reads the rumor through fee, wage, transfer value, and club balance-sheet pressure.",
    },
    {
        "id": "market_reaction",
        "name": "Market Reaction Agent",
        "description": "Reads the rumor through stock context, model signal, liquidity, and match-result timing.",
    },
    {
        "id": "journalist_credibility",
        "name": "Journalist Credibility Agent",
        "description": "Reads the rumor through source mix, journalist history, and rumor-stage reliability.",
    },
    {
        "id": "fan_sentiment",
        "name": "Fan/Sentiment Agent",
        "description": "Reads the rumor through fan narrative, player importance, age, and role.",
    },
    {
        "id": "risk_officer",
        "name": "Risk Officer Agent",
        "description": "Challenges the scenario, flags weak evidence, and reduces overconfident conclusions.",
    },
]


def slugify(value: str, fallback: str = "scenario") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or fallback


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def stance_score(stance: str) -> int:
    return {"bearish": -1, "watch": 0, "neutral": 0, "bullish": 1}.get(stance, 0)


def stance_label(score: float) -> str:
    if score >= 0.35:
        return "bullish"
    if score <= -0.35:
        return "bearish"
    if abs(score) <= 0.12:
        return "neutral"
    return "watch"


def canonical_club(payload: dict[str, Any], club: str) -> str:
    if not club:
        return ""
    exact = {name.lower(): name for name in candidate_names(payload, "club")}
    if club.lower() in exact:
        return exact[club.lower()]
    matches = match_clubs(club, payload)
    return matches[0] if matches else club


def signal_matches_club(row: dict[str, Any], club: str) -> bool:
    if not club:
        return True
    return row_club(row) == club or str(row.get("club") or "") == club


def find_signal(
    payload: dict[str, Any],
    *,
    question: str = "",
    player: str = "",
    club: str = "",
) -> dict[str, Any]:
    club = canonical_club(payload, club)
    if question and not club:
        question_clubs = match_clubs(question, payload)
        club = question_clubs[0] if question_clubs else ""
    if player:
        row = find_signal_for_player(payload, player)
        if row and signal_matches_club(row, club):
            return row
    if question:
        answer = ask_analyst(question, payload=payload)
        player_name = ""
        for table in answer.get("tables", []):
            for row in table.get("rows", []):
                if row.get("player"):
                    player_name = str(row["player"])
                    break
            if player_name:
                break
        if player_name:
            row = find_signal_for_player(payload, player_name)
            if row and signal_matches_club(row, club):
                return row
        matched_player = match_name(question, candidate_names(payload, "player"))
        if matched_player:
            row = find_signal_for_player(payload, matched_player)
            if row and signal_matches_club(row, club):
                return row
    rows = payload.get("live_watchlist", []) or []
    if club:
        rows = [row for row in rows if signal_matches_club(row, club)]
    if rows:
        return rows[0]
    raise ValueError("No matching rumor signal found for scenario simulation")


def recent_match_markers(payload: dict[str, Any], club: str, limit: int = 6) -> list[dict[str, Any]]:
    markers = (payload.get("club_stock_paths", {}).get(club, {}) or {}).get("markers", []) or []
    return list(reversed(markers[-limit:]))


def collect_evidence(
    payload: dict[str, Any],
    *,
    question: str = "",
    player: str = "",
    club: str = "",
) -> dict[str, Any]:
    signal = find_signal(payload, question=question, player=player, club=club)
    target_club = row_club(signal)
    dossier = payload.get("club_dossiers", {}).get(target_club, {})
    stock_path = payload.get("club_stock_paths", {}).get(target_club, {})
    reporter = signal.get("journalist") or signal.get("latest_journalist") or ""
    reporter_profile = payload.get("reporter_profiles", {}).get(reporter, {}) if reporter else {}
    return {
        "question": question or f"Scenario for {signal.get('player', '')} / {target_club}",
        "created_at": datetime.now(tz=UTC).isoformat(),
        "signal": signal,
        "club_dossier": dossier,
        "stock_path": {
            "club": stock_path.get("club", target_club),
            "ticker": stock_path.get("ticker", ""),
            "latest_change": stock_path.get("latest_change", ""),
            "latest_date": stock_path.get("latest_date", ""),
            "match_marker_count": stock_path.get("match_marker_count", len(stock_path.get("markers", []) or [])),
            "recent_match_markers": recent_match_markers(payload, target_club),
        },
        "confirmed_transfer_links": signal.get("confirmed_transfer_links", []) or [],
        "similar_examples": signal.get("similar_examples", []) or ([] if not signal.get("top_similar_example") else [signal.get("top_similar_example")]),
        "reporter_profile": reporter_profile,
        "data_warnings": [
            "Scenario Swarm is deterministic research context, not investment advice.",
            "The agents all read the same local evidence bundle and do not fetch external facts.",
        ],
    }


def finance_agent(evidence: dict[str, Any], round_index: int) -> dict[str, Any]:
    signal = evidence["signal"]
    role = str(signal.get("target_role", ""))
    transfer_index = parse_float(signal.get("transfer_indicator"), 0.0)
    fee = parse_float(signal.get("transfer_fee_eur"), 0.0)
    market_value = parse_float(signal.get("market_value_eur"), 0.0)
    age = parse_float(signal.get("age"), 0.0)
    bullets = []
    caveats = ["Wage data is often incomplete, so fee/value logic may miss salary pressure."]
    score = 0.0
    if role == "seller":
        score += 0.25
        bullets.append("Selling-side rumors can be financially constructive if they reduce wages or monetize an aging player.")
    elif role == "buyer":
        score -= 0.15
        bullets.append("Buying-side rumors can pressure short-term cash expectations through fee and wage commitments.")
    if market_value and fee:
        if fee <= market_value * 0.9:
            score += 0.15
            bullets.append("Fee appears at or below the available market-value proxy.")
        elif fee > market_value * 1.15:
            score -= 0.15
            bullets.append("Fee appears above the available market-value proxy.")
    if transfer_index >= 0.6:
        score += 0.10 if role == "buyer" else 0.05
        bullets.append("Transfer index is relatively high, suggesting the player/deal quality is not trivial.")
    if age >= 31 and role == "seller":
        score += 0.10
        bullets.append("Older-player sale can be read as wage/roster cleanup by finance-focused investors.")
    if not bullets:
        bullets.append("Financial read is thin because fee/value/age evidence is limited.")
    score *= 0.92 ** max(round_index - 1, 0)
    return {
        "agent_id": "club_finance",
        "stance": stance_label(score),
        "confidence": round(clamp(0.48 + abs(score)), 4),
        "evidence_bullets": bullets[:4],
        "risk_caveats": caveats,
    }


def market_agent(evidence: dict[str, Any], round_index: int) -> dict[str, Any]:
    signal = evidence["signal"]
    stock = evidence["stock_path"]
    label = str(signal.get("blended_label") or signal.get("predicted_label") or "")
    confidence = parse_float(signal.get("prediction_confidence"), 0.0)
    stock_change = parse_float(stock.get("latest_change"), 0.0)
    markers = int(parse_float(stock.get("match_marker_count"), 0.0))
    score = 0.0
    bullets = []
    caveats = ["Football club stocks are thin and can react to non-transfer news."]
    if label == "positive":
        score += 0.35
        bullets.append("Model/blended label is positive in the current payload.")
    elif label == "negative":
        score -= 0.35
        bullets.append("Model/blended label is negative in the current payload.")
    else:
        bullets.append("Model/blended label is neutral or unclear.")
    if confidence >= 0.65:
        score *= 1.15
        bullets.append("Prediction confidence is above the usual weak-signal band.")
    if abs(stock_change) > 0.08:
        caveats.append("Recent stock path already moved materially, so some rumor/match information may be priced in.")
        bullets.append(f"Loaded stock path latest change is {stock_change:.2%}.")
    if markers:
        caveats.append("Match-result markers overlap the stock path and can confound transfer-rumor interpretation.")
        bullets.append(f"{markers} match markers are present on the club stock path.")
    score *= 0.94 ** max(round_index - 1, 0)
    return {
        "agent_id": "market_reaction",
        "stance": stance_label(score),
        "confidence": round(clamp(0.50 + abs(score)), 4),
        "evidence_bullets": bullets[:4],
        "risk_caveats": caveats,
    }


def journalist_agent(evidence: dict[str, Any], round_index: int) -> dict[str, Any]:
    signal = evidence["signal"]
    profile = evidence.get("reporter_profile", {})
    credibility = parse_float(signal.get("credibility_score"), 0.0)
    source_count = int(parse_float(signal.get("source_count"), 0.0))
    stage = str(signal.get("rumor_stage") or signal.get("latest_rumor_stage") or "")
    score = 0.0
    bullets = []
    caveats = []
    if credibility >= 0.6:
        score += 0.25
        bullets.append("Credibility score is relatively strong for the local dataset.")
    elif credibility < 0.4:
        score -= 0.15
        bullets.append("Credibility score is weak, so the rumor should stay in watch mode.")
    else:
        bullets.append("Credibility score is moderate.")
    if source_count >= 3:
        score += 0.12
        bullets.append("Multiple sources support the event cluster.")
    if stage in {"advanced", "agreed", "medical", "official"}:
        score += 0.15
        bullets.append(f"Rumor stage is {stage}, which is stronger than a loose link.")
    if profile:
        bullets.append(f"Reporter profile has {profile.get('n_claims', 0)} tracked claims.")
        score += min(0.12, parse_float(profile.get("smoothed_rate"), 0.0) * 0.12)
    else:
        caveats.append("No reporter profile is attached to this signal.")
    caveats.append("Aggregated articles can repeat the same underlying report, so source count is not pure independence.")
    score *= 0.95 ** max(round_index - 1, 0)
    return {
        "agent_id": "journalist_credibility",
        "stance": "watch" if score > 0 and credibility < 0.6 else stance_label(score),
        "confidence": round(clamp(0.45 + abs(score)), 4),
        "evidence_bullets": bullets[:4],
        "risk_caveats": caveats,
    }


def fan_sentiment_agent(evidence: dict[str, Any], round_index: int) -> dict[str, Any]:
    signal = evidence["signal"]
    role = str(signal.get("target_role", ""))
    age = parse_float(signal.get("age"), 0.0)
    position = str(signal.get("position") or "")
    player = str(signal.get("player") or "the player")
    score = 0.0
    bullets = []
    caveats = ["Fan sentiment is proxied from role/age/position only; no social feed is included yet."]
    if role == "seller":
        if age >= 30:
            score += 0.12
            bullets.append(f"Fans may accept selling {player} if the narrative is squad refresh.")
        else:
            score -= 0.18
            bullets.append(f"Selling {player} could be read as losing talent if he is viewed as important.")
    elif role == "buyer":
        score += 0.10
        bullets.append(f"Buying {player} can support fan optimism if the player fills a perceived squad need.")
    if any(token in position.lower() for token in ("forward", "winger", "striker")):
        score += 0.04
        bullets.append("Attacking signings/departures tend to carry stronger narrative attention.")
    if not bullets:
        bullets.append("Fan/sentiment read is neutral because role and player context are limited.")
    score *= 0.92 ** max(round_index - 1, 0)
    return {
        "agent_id": "fan_sentiment",
        "stance": stance_label(score),
        "confidence": round(clamp(0.42 + abs(score)), 4),
        "evidence_bullets": bullets[:4],
        "risk_caveats": caveats,
    }


def risk_agent(evidence: dict[str, Any], round_index: int) -> dict[str, Any]:
    signal = evidence["signal"]
    links = evidence.get("confirmed_transfer_links", [])
    similar = evidence.get("similar_examples", [])
    stage = str(signal.get("rumor_stage") or signal.get("latest_rumor_stage") or "")
    credibility = parse_float(signal.get("credibility_score"), 0.0)
    source_count = int(parse_float(signal.get("source_count"), 0.0))
    score = 0.0
    bullets = []
    caveats = [
        "Scenario output is for research triage only, not a buy/sell instruction.",
        "No agent isolates causality from match results, ownership news, earnings, or market liquidity.",
    ]
    if credibility < 0.5:
        score -= 0.18
        bullets.append("Credibility is below the stronger-evidence band.")
    if source_count <= 1:
        score -= 0.12
        bullets.append("Source breadth is limited.")
    if stage in {"unclear", "linked", ""}:
        score -= 0.12
        bullets.append("Rumor stage is early or unclear.")
    if not links:
        score -= 0.08
        bullets.append("No confirmed-transfer link is attached yet.")
    if not similar:
        score -= 0.05
        bullets.append("No similar historical cases are attached to anchor the scenario.")
    if not bullets:
        bullets.append("Main risk is still market confounding rather than missing local evidence.")
    score *= 1.0 + max(round_index - 1, 0) * 0.02
    return {
        "agent_id": "risk_officer",
        "stance": "watch" if score > -0.2 else "bearish",
        "confidence": round(clamp(0.50 + abs(score)), 4),
        "evidence_bullets": bullets[:4],
        "risk_caveats": caveats,
    }


AGENT_FUNCTIONS = {
    "club_finance": finance_agent,
    "market_reaction": market_agent,
    "journalist_credibility": journalist_agent,
    "fan_sentiment": fan_sentiment_agent,
    "risk_officer": risk_agent,
}


def run_agents(evidence: dict[str, Any], rounds: int = 2) -> list[dict[str, Any]]:
    bounded_rounds = max(1, min(int(rounds), 5))
    trace: list[dict[str, Any]] = []
    for round_index in range(1, bounded_rounds + 1):
        previous = trace[-len(ROLE_AGENTS):] if round_index > 1 else []
        for agent in ROLE_AGENTS:
            result = AGENT_FUNCTIONS[agent["id"]](evidence, round_index)
            if previous:
                opposing = sum(1 for item in previous if stance_score(item.get("stance", "")) != stance_score(result["stance"]))
                if opposing >= 3:
                    result["risk_caveats"].append("Prior round had broad disagreement, so confidence is tempered.")
                    result["confidence"] = round(clamp(parse_float(result["confidence"], 0.0) - 0.05), 4)
            trace.append(
                {
                    "round": round_index,
                    **agent,
                    **result,
                }
            )
    return trace


def summarize_trace(trace: list[dict[str, Any]]) -> dict[str, Any]:
    if not trace:
        return {"consensus_stance": "watch", "consensus_confidence": 0.0, "stance_counts": {}}
    last_round = [row for row in trace if row.get("round") == max(item.get("round", 1) for item in trace)]
    stance_counts: dict[str, int] = {}
    weighted_score = 0.0
    weight_sum = 0.0
    for row in last_round:
        stance = str(row.get("stance", "watch"))
        confidence = parse_float(row.get("confidence"), 0.0)
        stance_counts[stance] = stance_counts.get(stance, 0) + 1
        weighted_score += stance_score(stance) * confidence
        weight_sum += confidence
    consensus_score = weighted_score / weight_sum if weight_sum else 0.0
    avg_confidence = sum(parse_float(row.get("confidence"), 0.0) for row in last_round) / len(last_round)
    return {
        "consensus_stance": stance_label(consensus_score),
        "consensus_score": round(consensus_score, 4),
        "consensus_confidence": round(clamp(avg_confidence), 4),
        "stance_counts": stance_counts,
    }


def latest_round_rows(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not trace:
        return []
    latest_round = max(int(row.get("round", 1)) for row in trace)
    return [row for row in trace if int(row.get("round", 1)) == latest_round]


def markdown_report(scenario: dict[str, Any], agents: list[dict[str, Any]], trace: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    signal = scenario["evidence"]["signal"]
    stock = scenario["evidence"]["stock_path"]
    latest_round = latest_round_rows(trace)
    lines = [
        "# Scenario Swarm Report",
        "",
        f"Question: {scenario['question']}",
        "",
        f"Player: {signal.get('player', '-')}",
        f"Target club: {row_club(signal) or '-'}",
        f"Target role: {signal.get('target_role', '-')}",
        f"Consensus stance: {summary.get('consensus_stance', 'watch')} ({summary.get('consensus_confidence', 0.0):.2f} confidence)",
        "",
        "## Evidence Snapshot",
        "",
        f"- Rumor stage: {signal.get('rumor_stage') or signal.get('latest_rumor_stage') or '-'}",
        f"- Credibility score: {parse_float(signal.get('credibility_score'), 0.0):.3f}",
        f"- Transfer index: {parse_float(signal.get('transfer_indicator'), 0.0):.3f}",
        f"- Model/blended label: {signal.get('predicted_label', '-')} / {signal.get('blended_label', '-')}",
        f"- Stock ticker: {stock.get('ticker', '-')}",
        f"- Match markers on stock path: {stock.get('match_marker_count', 0)}",
        f"- Confirmed transfer links: {len(scenario['evidence'].get('confirmed_transfer_links', []))}",
        f"- Similar historical cases: {len(scenario['evidence'].get('similar_examples', []))}",
        "",
        "## Agent Votes",
        "",
    ]
    for row in latest_round:
        lines.extend(
            [
                f"### {row.get('name', row.get('agent_id', 'Agent'))}",
                "",
                f"- Stance: {row.get('stance', 'watch')}",
                f"- Confidence: {parse_float(row.get('confidence'), 0.0):.2f}",
                "- Evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in row.get("evidence_bullets", []))
        lines.append("- Caveats:")
        lines.extend(f"  - {item}" for item in row.get("risk_caveats", []))
        lines.append("")
    lines.extend(
        [
            "## Research Verdict",
            "",
            f"The swarm consensus is **{summary.get('consensus_stance', 'watch')}**. Treat this as a structured research view, not a trading recommendation.",
            "",
            "Key caution: listed football-club stocks can move on match results, ownership news, earnings, liquidity, and broader markets, so transfer-rumor scenarios are inherently confounded.",
            "",
        ]
    )
    return "\n".join(lines)


def write_json(path: Path, data: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def dashboard_report_href(path: Path) -> str:
    if not path.is_absolute():
        path = ROOT / path
    try:
        return path.relative_to(ROOT / "app" / "static").as_posix()
    except ValueError:
        return str(path)


def build_dashboard_scenario_payload(
    scenario: dict[str, Any],
    agents: list[dict[str, Any]],
    trace: list[dict[str, Any]],
    report: str,
    *,
    output_paths: dict[str, str],
    dashboard_report_path: str | Path = DEFAULT_DASHBOARD_SCENARIO_REPORT,
) -> dict[str, Any]:
    signal = scenario.get("evidence", {}).get("signal", {}) or {}
    evidence = scenario.get("evidence", {}) or {}
    latest_agents = latest_round_rows(trace)
    risk_notes: list[str] = []
    for row in latest_agents:
        for caveat in row.get("risk_caveats", []) or []:
            if caveat and caveat not in risk_notes:
                risk_notes.append(str(caveat))
    return {
        "available": True,
        "simulation_id": scenario.get("simulation_id", ""),
        "generated_at": scenario.get("created_at", ""),
        "question": scenario.get("question", ""),
        "rounds": scenario.get("rounds", 0),
        "summary": scenario.get("summary", {}),
        "signal": {
            "player": signal.get("player", ""),
            "target_club": row_club(signal),
            "club": signal.get("club", ""),
            "target_role": signal.get("target_role", ""),
            "rumor_stage": signal.get("rumor_stage") or signal.get("latest_rumor_stage", ""),
            "credibility_score": signal.get("credibility_score", ""),
            "transfer_indicator": signal.get("transfer_indicator", ""),
            "predicted_label": signal.get("predicted_label", ""),
            "blended_label": signal.get("blended_label", ""),
            "prediction_confidence": signal.get("prediction_confidence", ""),
            "latest_source": signal.get("latest_source") or signal.get("source", ""),
        },
        "agents": latest_agents,
        "agent_catalog": agents,
        "evidence": {
            "stock_path": evidence.get("stock_path", {}),
            "confirmed_transfer_links": (evidence.get("confirmed_transfer_links", []) or [])[:5],
            "similar_examples": (evidence.get("similar_examples", []) or [])[:5],
            "reporter_profile": evidence.get("reporter_profile", {}),
            "data_warnings": evidence.get("data_warnings", []),
        },
        "risk_notes": risk_notes[:8],
        "report_markdown": report,
        "report_href": dashboard_report_href(Path(dashboard_report_path)),
        "source_paths": {key: value for key, value in output_paths.items() if isinstance(value, str)},
    }


def publish_dashboard_scenario(
    path: str | Path,
    report_path: str | Path,
    payload: dict[str, Any],
) -> None:
    write_json(Path(path), payload)
    ensure_parent(Path(report_path))
    Path(report_path).write_text(str(payload.get("report_markdown", "")), encoding="utf-8")


def run_scenario_swarm(
    *,
    question: str = "",
    player: str = "",
    club: str = "",
    payload_path: str | Path = DEFAULT_PAYLOAD,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    rounds: int = 2,
    simulation_id: str = "",
    dashboard_output: str | Path | None = None,
    dashboard_report_output: str | Path = DEFAULT_DASHBOARD_SCENARIO_REPORT,
) -> dict[str, Any]:
    payload = load_dashboard_payload(payload_path)
    evidence = collect_evidence(payload, question=question, player=player, club=club)
    signal = evidence["signal"]
    scenario_question = question or f"What is the scenario impact for {signal.get('player', '')} / {row_club(signal)}?"
    created_at = datetime.now(tz=UTC)
    sim_id = simulation_id or f"{created_at.strftime('%Y%m%dT%H%M%SZ')}_{slugify(str(signal.get('player') or scenario_question))}"
    sim_dir = Path(output_dir) / sim_id
    agents = ROLE_AGENTS
    trace = run_agents(evidence, rounds=rounds)
    summary = summarize_trace(trace)
    scenario = {
        "simulation_id": sim_id,
        "question": scenario_question,
        "created_at": created_at.isoformat(),
        "rounds": max(1, min(int(rounds), 5)),
        "evidence": evidence,
        "summary": summary,
    }
    report = markdown_report(scenario, agents, trace, summary)
    write_json(sim_dir / "scenario.json", scenario)
    write_json(sim_dir / "agents.json", agents)
    write_jsonl(sim_dir / "trace.jsonl", trace)
    ensure_parent(sim_dir / "report.md")
    (sim_dir / "report.md").write_text(report, encoding="utf-8")
    result = {
        "simulation_id": sim_id,
        "simulation_dir": str(sim_dir),
        "scenario": str(sim_dir / "scenario.json"),
        "agents": str(sim_dir / "agents.json"),
        "trace": str(sim_dir / "trace.jsonl"),
        "report": str(sim_dir / "report.md"),
        "summary": summary,
    }
    if dashboard_output is not None:
        dashboard_payload = build_dashboard_scenario_payload(
            scenario,
            agents,
            trace,
            report,
            output_paths=result,
            dashboard_report_path=dashboard_report_output,
        )
        publish_dashboard_scenario(dashboard_output, dashboard_report_output, dashboard_payload)
        result["dashboard_scenario"] = str(dashboard_output)
        result["dashboard_report"] = str(dashboard_report_output)
    return result
