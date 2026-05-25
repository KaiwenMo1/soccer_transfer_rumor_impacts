from __future__ import annotations

import hashlib
import html
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ROOT
from .io import ensure_parent, read_jsonl


DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"
DEFAULT_EVIDENCE_INDEX = DATA_DIR / "processed" / "evidence" / "evidence_index.json"
DEFAULT_SCENARIO = ROOT / "app" / "static" / "data" / "scenario_latest.json"
DEFAULT_BRIEFING = DATA_DIR / "reports" / "daily_briefing.md"
DEFAULT_ARTICLE_PATHS = [
    DATA_DIR / "raw" / "articles" / "current_fast.jsonl",
    DATA_DIR / "raw" / "articles" / "current_live.jsonl",
    DATA_DIR / "raw" / "articles" / "articles_v2.jsonl",
]

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_'-]*")
STOPWORDS = {
    "a",
    "about",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "club",
    "do",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "show",
    "stock",
    "the",
    "this",
    "to",
    "transfer",
    "what",
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


def tokenize(value: Any) -> list[str]:
    return [
        token.strip("'")
        for token in TOKEN_RE.findall(str(value or "").lower())
        if len(token.strip("'")) > 1 and token.strip("'") not in STOPWORDS
    ]


def safe_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def text_join(parts: list[Any]) -> str:
    return " ".join(str(part).strip() for part in parts if str(part or "").strip())


def compact(value: Any, limit: int = 1800) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) >= 10 and re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return text[:10]


def stable_doc_id(doc_type: str, source_path: str, key: Any) -> str:
    raw = f"{doc_type}|{source_path}|{key}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def make_doc(
    *,
    doc_type: str,
    title: str,
    text: str,
    source_path: str,
    key: Any,
    date: str = "",
    club: str = "",
    player: str = "",
    reporter: str = "",
    source: str = "",
    url: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_path = rel_path(source_path)
    return {
        "doc_id": stable_doc_id(doc_type, source_path, key or title),
        "doc_type": doc_type,
        "title": compact(title, 260),
        "text": compact(text, 2400),
        "source_path": source_path,
        "date": normalize_date(date),
        "club": str(club or ""),
        "player": str(player or ""),
        "reporter": str(reporter or ""),
        "source": str(source or ""),
        "url": str(url or ""),
        "metadata": metadata or {},
    }


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def row_club(row: dict[str, Any]) -> str:
    return str(row.get("target_club") or row.get("club") or row.get("subject_club") or "").strip()


def row_date(row: dict[str, Any]) -> str:
    value = str(row.get("latest_published_at") or row.get("published_at") or row.get("date") or "").strip()
    return normalize_date(value)


def row_stage(row: dict[str, Any]) -> str:
    return str(row.get("latest_rumor_stage") or row.get("rumor_stage") or "").strip()


def signal_docs(payload: dict[str, Any], source_path: str | Path) -> list[dict[str, Any]]:
    rows = list(payload.get("live_watchlist", []) or [])
    rows.extend((payload.get("watchlist_details", {}) or {}).values())
    for season_rows in (payload.get("signals_by_season", {}) or {}).values():
        rows.extend(season_rows or [])
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("group_key") or row.get("claim_ids") or (row.get("player"), row_club(row), row_date(row)))
        if key in seen:
            continue
        seen.add(key)
        player = str(row.get("player") or "")
        club = row_club(row)
        title = str(row.get("primary_headline") or row.get("title") or f"{player} / {club} rumor signal")
        text = text_join(
            [
                f"Rumor signal for {player}.",
                f"Target club {club}.",
                f"Target role {row.get('target_role', '')}.",
                f"Counterparty {row.get('counterparty_club', '')}.",
                f"Buyer {row.get('buyer_club', '')}. Seller {row.get('seller_club', '')}.",
                f"Stage {row_stage(row)}.",
                f"Source count {row.get('source_count', '')}. Sources {', '.join(row.get('sources', []) or [])}.",
                f"Journalists {', '.join(row.get('journalists', []) or [])}.",
                f"Credibility score {row.get('credibility_score', '')}.",
                f"Transfer indicator {row.get('transfer_indicator', '')}. Rumor indicator {row.get('rumor_indicator', '')}.",
                f"Prediction scope {row.get('prediction_scope', '')}. Predicted label {row.get('predicted_label', '')}.",
                f"Blended label {row.get('blended_label', '')}. Confidence {row.get('prediction_confidence', '')}.",
                row.get("confidence_reason", ""),
                row.get("signal_summary", ""),
                row.get("deal_path", ""),
            ]
        )
        docs.append(
            make_doc(
                doc_type="signal",
                title=title,
                text=text,
                source_path=source_path,
                key=key,
                date=row_date(row),
                club=club,
                player=player,
                reporter=str(row.get("latest_journalist") or row.get("journalist") or ""),
                source=str(row.get("latest_source") or row.get("source") or ""),
                metadata={
                    "group_key": row.get("group_key", ""),
                    "stage": row_stage(row),
                    "target_role": row.get("target_role", ""),
                    "prediction_scope": row.get("prediction_scope", ""),
                    "credibility_score": row.get("credibility_score", ""),
                    "prediction_confidence": row.get("prediction_confidence", ""),
                    "blended_label": row.get("blended_label", ""),
                },
            )
        )
        for article in row.get("evidence_articles", []) or []:
            article_title = str(article.get("title") or title)
            docs.append(
                make_doc(
                    doc_type="article",
                    title=article_title,
                    text=text_join(
                        [
                            article_title,
                            f"Article source {article.get('source', '')}.",
                            f"Journalist {article.get('journalist', '')}.",
                            f"Rumor stage {article.get('rumor_stage', '')}.",
                            f"Extraction confidence {article.get('extraction_confidence', '')}.",
                            f"Transfer related {article.get('is_transfer_related', '')}.",
                            f"Connected signal: {player} / {club}.",
                        ]
                    ),
                    source_path=source_path,
                    key=article.get("url") or article.get("headline_fingerprint") or article_title,
                    date=article.get("published_at", ""),
                    club=club,
                    player=player,
                    reporter=str(article.get("journalist") or ""),
                    source=str(article.get("source") or ""),
                    url=str(article.get("url") or ""),
                    metadata={
                        "feed_source": article.get("feed_source", ""),
                        "rumor_stage": article.get("rumor_stage", ""),
                        "extraction_confidence": article.get("extraction_confidence", ""),
                    },
                )
            )
    return docs


def club_docs(payload: dict[str, Any], source_path: str | Path) -> list[dict[str, Any]]:
    docs = []
    for club, dossier in (payload.get("club_dossiers", {}) or {}).items():
        reporters = dossier.get("reporters", []) or []
        text = text_join(
            [
                f"Club dossier for {club}.",
                f"Live signal count {dossier.get('live_signal_count', '')}.",
                f"Average live credibility {dossier.get('avg_live_credibility', '')}.",
                f"Average transfer index {dossier.get('avg_transfer_index', '')}.",
                f"Average realized CAR t+3 {dossier.get('avg_realized_car_p3', '')}.",
                f"Realized positive share {dossier.get('realized_positive_share', '')}.",
                f"Recent transfer count {dossier.get('recent_transfer_count', '')}.",
                "Top reporters "
                + ", ".join(str(row.get("journalist", "")) for row in reporters[:6] if row.get("journalist")),
            ]
        )
        docs.append(
            make_doc(
                doc_type="club_dossier",
                title=f"{club} club dossier",
                text=text,
                source_path=source_path,
                key=club,
                club=club,
                metadata={
                    "live_signal_count": dossier.get("live_signal_count", 0),
                    "avg_live_credibility": dossier.get("avg_live_credibility", ""),
                    "avg_realized_car_p3": dossier.get("avg_realized_car_p3", ""),
                },
            )
        )
    return docs


def reporter_docs(payload: dict[str, Any], source_path: str | Path) -> list[dict[str, Any]]:
    docs = []
    for reporter, profile in (payload.get("reporter_profiles", {}) or {}).items():
        clubs = profile.get("clubs", []) or []
        sources = profile.get("sources", []) or []
        text = text_join(
            [
                f"Reporter profile for {reporter}.",
                f"Claims {profile.get('n_claims', '')}.",
                f"Smoothed rate {profile.get('smoothed_rate', '')}.",
                f"Average match score {profile.get('avg_match_score', '')}.",
                f"Average realized CAR t+3 {profile.get('avg_realized_car_p3', '')}.",
                "Club coverage " + ", ".join(f"{row.get('club', '')}: {row.get('count', '')}" for row in clubs[:8]),
                "Source mix " + ", ".join(f"{row.get('source', '')}: {row.get('count', '')}" for row in sources[:8]),
            ]
        )
        docs.append(
            make_doc(
                doc_type="reporter_profile",
                title=f"{reporter} reporter profile",
                text=text,
                source_path=source_path,
                key=reporter,
                reporter=reporter,
                metadata={
                    "n_claims": profile.get("n_claims", 0),
                    "smoothed_rate": profile.get("smoothed_rate", ""),
                    "avg_match_score": profile.get("avg_match_score", ""),
                },
            )
        )
    return docs


def transfer_docs(payload: dict[str, Any], source_path: str | Path) -> list[dict[str, Any]]:
    docs = []
    for season, rows in (payload.get("transfers_by_season", {}) or {}).items():
        for row in rows or []:
            club = row_club(row)
            player = str(row.get("player") or "")
            key = str(row.get("transfer_key") or (season, row.get("date"), club, player, row.get("target_role")))
            text = text_join(
                [
                    f"Confirmed transfer row for {player}.",
                    f"Season {season}. Date {row.get('date', '')}.",
                    f"Public target club {club}. Target role {row.get('target_role', '')}.",
                    f"Buyer {row.get('buyer_club', '')}. Seller {row.get('seller_club', '')}.",
                    f"Transfer type {row.get('transfer_type', '')}. Position {row.get('position', '')}. Age {row.get('age', '')}.",
                    f"Fee EUR {row.get('transfer_fee_eur', '')}. Market value EUR {row.get('market_value_eur', '')}.",
                    f"Transfer indicator {row.get('transfer_indicator', '')}. Actual label {row.get('actual_label', '')}.",
                    f"Actual abnormal return p3 {row.get('actual_abnormal_return_p3', '')}.",
                ]
            )
            docs.append(
                make_doc(
                    doc_type="transfer",
                    title=f"{player} confirmed transfer / {club} / {season}",
                    text=text,
                    source_path=source_path,
                    key=key,
                    date=row.get("date", ""),
                    club=club,
                    player=player,
                    metadata={
                        "season": season,
                        "target_role": row.get("target_role", ""),
                        "actual_label": row.get("actual_label", ""),
                        "transfer_indicator": row.get("transfer_indicator", ""),
                    },
                )
            )
    return docs


def stock_match_docs(payload: dict[str, Any], source_path: str | Path) -> list[dict[str, Any]]:
    docs = []
    for club, path in (payload.get("club_stock_paths", {}) or {}).items():
        docs.append(
            make_doc(
                doc_type="stock_path",
                title=f"{club} stock path context",
                text=text_join(
                    [
                        f"Stock path for {club}.",
                        f"Ticker {path.get('ticker', '')}.",
                        f"Latest date {path.get('latest_date', '')}.",
                        f"Latest change {path.get('latest_change', '')}.",
                        f"Match marker count {path.get('match_marker_count', len(path.get('markers', []) or []))}.",
                    ]
                ),
                source_path=source_path,
                key=(club, path.get("latest_date", "")),
                club=club,
                date=path.get("latest_date", ""),
                metadata={"ticker": path.get("ticker", ""), "latest_change": path.get("latest_change", "")},
            )
        )
        for marker in path.get("markers", []) or []:
            docs.append(
                make_doc(
                    doc_type="match_result",
                    title=f"{club} {marker.get('result', '')} vs {marker.get('opponent', '')}",
                    text=text_join(
                        [
                            f"Match result marker for {club}.",
                            f"Opponent {marker.get('opponent', '')}. Competition {marker.get('competition', '')}.",
                            f"Venue {marker.get('venue', '')}. Result {marker.get('result', '')}. Score {marker.get('score', '')}.",
                            f"Match date {marker.get('match_date', '')}. Trading date {marker.get('trading_date', '')}.",
                        ]
                    ),
                    source_path=source_path,
                    key=(club, marker.get("match_date", ""), marker.get("opponent", "")),
                    date=marker.get("match_date", ""),
                    club=club,
                    url=str(marker.get("source_url") or ""),
                    metadata={"trading_date": marker.get("trading_date", ""), "result": marker.get("result", "")},
                )
            )
    return docs


def article_store_docs(article_paths: list[str | Path] | None) -> list[dict[str, Any]]:
    paths = article_paths if article_paths is not None else [path for path in DEFAULT_ARTICLE_PATHS if path.exists()]
    docs: list[dict[str, Any]] = []
    for path in paths:
        article_path = Path(path)
        if not article_path.exists():
            continue
        for row in read_jsonl(article_path):
            title = str(row.get("title") or row.get("headline") or "")
            body = str(row.get("body_text") or row.get("body") or row.get("snippet") or row.get("description") or "")
            if not title and not body:
                continue
            clubs = row.get("club_candidates") or []
            players = row.get("player_candidates") or []
            docs.append(
                make_doc(
                    doc_type="article",
                    title=title or compact(body, 120),
                    text=text_join(
                        [
                            title,
                            body,
                            f"Source {row.get('source', '')}. Journalist {row.get('journalist', '')}.",
                            f"Club candidates {', '.join(clubs) if isinstance(clubs, list) else clubs}.",
                            f"Player candidates {', '.join(players) if isinstance(players, list) else players}.",
                        ]
                    ),
                    source_path=article_path,
                    key=row.get("article_id") or row.get("url") or title,
                    date=row.get("published_at", ""),
                    club=", ".join(clubs) if isinstance(clubs, list) else str(clubs or ""),
                    player=", ".join(players) if isinstance(players, list) else str(players or ""),
                    reporter=str(row.get("journalist") or ""),
                    source=str(row.get("source") or row.get("provider") or ""),
                    url=str(row.get("url") or ""),
                    metadata={
                        "crawl_method": row.get("crawl_method", ""),
                        "language": row.get("language", ""),
                        "extraction_confidence": row.get("extraction_confidence", ""),
                    },
                )
            )
    return docs


def scenario_doc(path: str | Path) -> list[dict[str, Any]]:
    scenario_path = Path(path)
    if not scenario_path.exists():
        return []
    scenario = load_json(scenario_path)
    if not scenario:
        return []
    signal = scenario.get("signal", {}) or {}
    summary = scenario.get("summary", {}) or {}
    text = text_join(
        [
            f"Scenario Swarm report for {scenario.get('question', '')}.",
            f"Consensus {summary.get('consensus_verdict', '')}.",
            f"Confidence {summary.get('mean_confidence', '')}.",
            f"Disagreement {summary.get('disagreement_score', '')}.",
            f"Player {signal.get('player', '')}. Club {signal.get('target_club') or signal.get('club', '')}.",
            "Risk notes " + " ".join(scenario.get("risk_notes", []) or []),
        ]
    )
    return [
        make_doc(
            doc_type="scenario",
            title=f"Scenario Swarm: {scenario.get('question', 'latest')}",
            text=text,
            source_path=scenario_path,
            key=scenario.get("simulation_id") or scenario.get("question", ""),
            date=scenario.get("generated_at", ""),
            club=str(signal.get("target_club") or signal.get("club") or ""),
            player=str(signal.get("player") or ""),
            metadata={"simulation_id": scenario.get("simulation_id", ""), "consensus": summary.get("consensus_verdict", "")},
        )
    ]


def briefing_doc(path: str | Path) -> list[dict[str, Any]]:
    briefing_path = Path(path)
    if not briefing_path.exists():
        return []
    text = briefing_path.read_text(encoding="utf-8")
    return [
        make_doc(
            doc_type="briefing",
            title="Daily transfer-stock briefing",
            text=text,
            source_path=briefing_path,
            key=briefing_path.stat().st_mtime,
            metadata={"bytes": len(text.encode("utf-8"))},
        )
    ]


def dedupe_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output = []
    for doc in documents:
        doc_id = str(doc.get("doc_id", ""))
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        output.append(doc)
    return output


def index_stats(documents: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts = Counter(str(doc.get("doc_type", "")) for doc in documents)
    source_counts = Counter(str(doc.get("source_path", "")) for doc in documents)
    return {
        "documents": len(documents),
        "types": dict(sorted(type_counts.items())),
        "source_paths": dict(sorted(source_counts.items())),
    }


def build_evidence_index_from_payload(
    payload: dict[str, Any],
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    article_paths: list[str | Path] | None = None,
    scenario_path: str | Path = DEFAULT_SCENARIO,
    briefing_path: str | Path = DEFAULT_BRIEFING,
) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    docs.extend(signal_docs(payload, payload_path))
    docs.extend(club_docs(payload, payload_path))
    docs.extend(reporter_docs(payload, payload_path))
    docs.extend(transfer_docs(payload, payload_path))
    docs.extend(stock_match_docs(payload, payload_path))
    docs.extend(article_store_docs(article_paths))
    docs.extend(scenario_doc(scenario_path))
    docs.extend(briefing_doc(briefing_path))
    docs = dedupe_documents(docs)
    return {
        "schema_version": "evidence-index-v1",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "retriever": {
            "type": "local_lexical",
            "description": "Deterministic BM25-style lexical retrieval over local project evidence.",
        },
        "stats": index_stats(docs),
        "documents": docs,
    }


def build_evidence_index(
    *,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    article_paths: list[str | Path] | None = None,
    scenario_path: str | Path = DEFAULT_SCENARIO,
    briefing_path: str | Path = DEFAULT_BRIEFING,
    output_path: str | Path = DEFAULT_EVIDENCE_INDEX,
) -> dict[str, Any]:
    payload = load_json(payload_path)
    index = build_evidence_index_from_payload(
        payload,
        payload_path=payload_path,
        article_paths=article_paths,
        scenario_path=scenario_path,
        briefing_path=briefing_path,
    )
    output = Path(output_path)
    ensure_parent(output)
    output.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return {
        "output": rel_path(output),
        "generated_at": index["generated_at"],
        "stats": index["stats"],
    }


def load_evidence_index(path: str | Path = DEFAULT_EVIDENCE_INDEX) -> dict[str, Any]:
    index_path = Path(path)
    if not index_path.exists():
        raise FileNotFoundError(f"Evidence index not found: {index_path}")
    return load_json(index_path)


def doc_search_text(doc: dict[str, Any]) -> str:
    meta = doc.get("metadata", {}) or {}
    return text_join(
        [
            doc.get("title", ""),
            doc.get("title", ""),
            doc.get("text", ""),
            doc.get("club", ""),
            doc.get("player", ""),
            doc.get("reporter", ""),
            doc.get("source", ""),
            " ".join(str(value) for value in meta.values() if value not in {"", None}),
        ]
    )


def retrieval_scores(index: dict[str, Any], query: str) -> list[tuple[float, dict[str, Any], list[str]]]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []
    documents = index.get("documents", []) or []
    doc_tokens = [tokenize(doc_search_text(doc)) for doc in documents]
    df = Counter()
    for tokens in doc_tokens:
        df.update(set(tokens))
    corpus_size = max(len(documents), 1)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for doc, tokens in zip(documents, doc_tokens):
        if not tokens:
            continue
        tf = Counter(tokens)
        length_norm = 1.0 / math.sqrt(max(len(tokens), 1))
        score = 0.0
        matched = []
        for token in query_tokens:
            if token not in tf:
                continue
            idf = math.log((corpus_size + 1) / (df[token] + 0.5)) + 1.0
            score += (1.0 + math.log(tf[token])) * idf
            matched.append(token)
        if not matched:
            continue
        normalized_query = " ".join(query_tokens)
        title_tokens = " ".join(tokenize(doc.get("title", "")))
        text_tokens = " ".join(tokens)
        if normalized_query and normalized_query in title_tokens:
            score += 4.0
        elif normalized_query and normalized_query in text_tokens:
            score += 2.0
        if str(doc.get("doc_type")) in {"signal", "article"}:
            score *= 1.12
        score *= 1.0 + min(0.25, len(set(matched)) / max(len(set(query_tokens)), 1) * 0.25)
        score *= max(0.35, length_norm * 9.0)
        scored.append((score, doc, sorted(set(matched))))
    return sorted(scored, key=lambda item: item[0], reverse=True)


def snippet_for(doc: dict[str, Any], matched_tokens: list[str], limit: int = 260) -> str:
    text = str(doc.get("text") or "")
    if not text:
        return ""
    lowered = text.lower()
    positions = [lowered.find(token) for token in matched_tokens if lowered.find(token) >= 0]
    if not positions:
        return compact(text, limit)
    start = max(0, min(positions) - 80)
    end = min(len(text), start + limit)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def retrieve_evidence(index: dict[str, Any], query: str, *, top_k: int = 6) -> list[dict[str, Any]]:
    scored = retrieval_scores(index, query)[: max(top_k, 0)]
    max_score = scored[0][0] if scored else 1.0
    hits = []
    for score, doc, matched in scored:
        hits.append(
            {
                "doc_id": doc.get("doc_id", ""),
                "doc_type": doc.get("doc_type", ""),
                "title": doc.get("title", ""),
                "score": round(score, 4),
                "normalized_score": round(score / max_score, 4) if max_score else 0.0,
                "matched_terms": matched[:12],
                "snippet": snippet_for(doc, matched),
                "source_path": doc.get("source_path", ""),
                "url": doc.get("url", ""),
                "date": doc.get("date", ""),
                "club": doc.get("club", ""),
                "player": doc.get("player", ""),
                "reporter": doc.get("reporter", ""),
                "source": doc.get("source", ""),
                "metadata": doc.get("metadata", {}),
            }
        )
    return hits


def retrieve_from_index_file(index_path: str | Path, query: str, *, top_k: int = 6) -> dict[str, Any]:
    index = load_evidence_index(index_path)
    hits = retrieve_evidence(index, query, top_k=top_k)
    return {
        "query": query,
        "index": rel_path(index_path),
        "generated_at": index.get("generated_at", ""),
        "count": len(hits),
        "hits": hits,
    }


def what_would_change_mind(hits: list[dict[str, Any]]) -> list[str]:
    doc_types = {hit.get("doc_type") for hit in hits}
    notes = []
    if "article" not in doc_types:
        notes.append("More primary article evidence would improve the answer.")
    if "transfer" not in doc_types:
        notes.append("A confirmed-transfer match would strengthen historical comparison.")
    if "stock_path" not in doc_types and "match_result" not in doc_types:
        notes.append("Fresh stock and match-result context would reduce market-context uncertainty.")
    notes.append("Newer high-credibility reports or official club disclosures can overturn the current read.")
    return notes[:4]


def attach_evidence_to_answer(
    answer: dict[str, Any],
    question: str,
    *,
    payload: dict[str, Any] | None = None,
    payload_path: str | Path = DEFAULT_PAYLOAD,
    index_path: str | Path | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    if index_path and Path(index_path).exists():
        index = load_evidence_index(index_path)
        index_source = rel_path(index_path)
    else:
        if payload is None:
            payload = load_json(payload_path)
        index = build_evidence_index_from_payload(payload, payload_path=payload_path, article_paths=[])
        index_source = "in_memory_dashboard_payload"
    retrieval_query = text_join([question, answer.get("short_answer", "")])
    hits = retrieve_evidence(index, retrieval_query, top_k=top_k)
    enriched = dict(answer)
    enriched["evidence_citations"] = hits
    enriched["what_would_change_mind"] = what_would_change_mind(hits)
    enriched["rag"] = {
        "retriever": "local_lexical",
        "index": index_source,
        "top_k": top_k,
        "citation_count": len(hits),
    }
    warnings = list(enriched.get("warnings", []) or [])
    warnings.append("Evidence citations use local lexical retrieval; read them as grounded context, not proof of causality.")
    enriched["warnings"] = warnings
    source_paths = dict(enriched.get("source_paths", {}) or {})
    source_paths["evidence_index"] = index_source
    enriched["source_paths"] = source_paths
    return enriched
