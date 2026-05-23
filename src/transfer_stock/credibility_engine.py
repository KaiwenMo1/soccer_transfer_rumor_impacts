from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .article_store import compact_whitespace, parse_list
from .claims import read_claims
from .config import Club, load_credibility
from .io import ensure_parent
from .matching import read_matches
from .transfers import load_transfers


SCORED_CLAIM_FIELDS = [
    "claim_id",
    "article_id",
    "title",
    "url",
    "snippet",
    "published_at",
    "source",
    "journalist",
    "primary_player",
    "primary_club",
    "rumor_stage",
    "transfer_direction",
    "is_transfer_related",
    "matched_transfer_id",
    "match_score",
    "match_reason",
    "ambiguity_flag",
    "credibility_score",
    "source_reputation_score",
    "journalist_reputation_score",
    "historical_conversion_score",
    "club_specific_score",
    "rumor_stage_score",
    "article_type_score",
    "time_to_confirmation_score",
    "article_type",
    "historical_support_n",
    "credibility_notes",
]

SOURCE_STATS_FIELDS = [
    "source",
    "n_claims",
    "n_matched",
    "match_rate",
    "smoothed_rate",
    "avg_match_score",
]

JOURNALIST_STATS_FIELDS = [
    "journalist",
    "n_claims",
    "n_matched",
    "match_rate",
    "smoothed_rate",
    "avg_match_score",
]

CLUB_JOURNALIST_STATS_FIELDS = [
    "club",
    "journalist",
    "n_claims",
    "n_matched",
    "match_rate",
    "smoothed_rate",
    "avg_match_score",
]

ARTICLE_TYPE_SCORES = {
    "exclusive": 0.85,
    "official": 0.9,
    "report": 0.65,
    "aggregate": 0.45,
    "live_blog": 0.2,
    "analysis": 0.35,
    "unclear": 0.5,
}

RUMOR_STAGE_SCORES = {
    "official": 0.95,
    "medical": 0.9,
    "agreed": 0.82,
    "advanced": 0.72,
    "bid": 0.6,
    "talks": 0.55,
    "linked": 0.48,
    "unclear": 0.4,
}

WEIGHTS = {
    "source_reputation_score": 0.25,
    "journalist_reputation_score": 0.20,
    "historical_conversion_score": 0.20,
    "club_specific_score": 0.10,
    "rumor_stage_score": 0.15,
    "article_type_score": 0.05,
    "time_to_confirmation_score": 0.05,
}


@dataclass(frozen=True)
class AggregateStat:
    key: str
    n_claims: int
    n_matched: int
    match_rate: float
    avg_match_score: float


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def parse_date(value: str) -> datetime | None:
    text = compact_whitespace(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def claim_index(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("claim_id", "")): dict(row) for row in rows if row.get("claim_id")}


def transfer_index(transfers_path: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for transfer in load_transfers(transfers_path):
        digest = __import__("hashlib").sha1(
            "||".join(
                [
                    transfer.date.isoformat(),
                    transfer.club,
                    transfer.player,
                    transfer.direction,
                    transfer.transfer_type,
                ]
            ).encode("utf-8")
        ).hexdigest()[:16]
        index[digest] = {
            "transfer_id": digest,
            "date": transfer.date.isoformat(),
            "season": transfer.season,
            "club": transfer.club,
            "player": transfer.player,
            "direction": transfer.direction,
            "transfer_type": transfer.transfer_type,
        }
    return index


def article_type(claim: dict[str, Any]) -> str:
    source = compact_whitespace(str(claim.get("source", ""))).lower()
    title = compact_whitespace(str(claim.get("title", ""))).lower()
    if "exclusive" in title or "exclusive" in source:
        return "exclusive"
    if "live" in title or "as it happened" in title:
        return "live_blog"
    if "official" in title or str(claim.get("rumor_stage", "")) == "official":
        return "official"
    if "rumours" in title or "rumors" in title or "latest" in title or "roundup" in title:
        return "aggregate"
    if "|" in str(claim.get("title", "")):
        return "analysis"
    return "report"


def source_prior(source: str, config: dict[str, Any]) -> float:
    default = parse_float(config.get("default_source_score"), 0.5)
    lowered = source.lower()
    best = default
    for name, score in config.get("sources", {}).items():
        if name.lower() in lowered:
            best = max(best, parse_float(score, default))
    return clamp(best)


def journalist_from_source(source: str, fallback: str) -> str:
    if fallback:
        return compact_whitespace(fallback)
    if " / " in source:
        return compact_whitespace(source.split(" / ", 1)[1])
    return ""


def aggregate_stats(
    claims: list[dict[str, Any]],
    matches_by_claim: dict[str, dict[str, Any]],
    key_fn,
) -> dict[str, AggregateStat]:
    buckets: dict[str, list[tuple[bool, float]]] = {}
    for claim in claims:
        key = key_fn(claim)
        if not key:
            continue
        match = matches_by_claim.get(str(claim.get("claim_id", "")), {})
        matched = bool(match.get("matched_transfer_id"))
        score = parse_float(match.get("match_score"), 0.0)
        buckets.setdefault(key, []).append((matched, score))
    stats: dict[str, AggregateStat] = {}
    for key, values in buckets.items():
        n_claims = len(values)
        n_matched = sum(1 for matched, _ in values if matched)
        avg_match_score = sum(score for _, score in values) / n_claims if n_claims else 0.0
        stats[key] = AggregateStat(
            key=key,
            n_claims=n_claims,
            n_matched=n_matched,
            match_rate=(n_matched / n_claims) if n_claims else 0.0,
            avg_match_score=avg_match_score,
        )
    return stats


def smoothed_rate(stat: AggregateStat | None, baseline: float = 0.5, prior_weight: float = 5.0) -> float:
    if stat is None:
        return clamp(baseline)
    return clamp((stat.n_matched + baseline * prior_weight) / (stat.n_claims + prior_weight))


def historical_conversion_score(
    source_stat: AggregateStat | None,
    journalist_stat: AggregateStat | None,
    baseline: float = 0.5,
) -> tuple[float, int]:
    matched = 0
    total = 0
    score_sum = 0.0
    n_sources = 0
    for stat in (source_stat, journalist_stat):
        if stat is None:
            continue
        matched += stat.n_matched
        total += stat.n_claims
        score_sum += smoothed_rate(stat, baseline=baseline)
        n_sources += 1
    if n_sources == 0:
        return 0.5, 0
    blended = score_sum / n_sources
    return clamp(blended), total


def club_specific_score(club_stat: AggregateStat | None, journalist_stat: AggregateStat | None, baseline: float = 0.5) -> float:
    if club_stat is not None:
        return clamp(0.6 * smoothed_rate(club_stat, baseline=baseline) + 0.4 * club_stat.avg_match_score)
    if journalist_stat is not None:
        return clamp(0.5 * smoothed_rate(journalist_stat, baseline=baseline) + 0.5 * journalist_stat.avg_match_score)
    return 0.5


def time_to_confirmation_score(claim: dict[str, Any], match: dict[str, Any], transfers_by_id: dict[str, dict[str, Any]]) -> float:
    transfer_id = str(match.get("matched_transfer_id", ""))
    if not transfer_id or transfer_id not in transfers_by_id:
        return 0.5
    transfer_row = transfers_by_id[transfer_id]
    published = parse_date(str(claim.get("published_at", "")))
    transfer_dt = parse_date(str(transfer_row.get("date", "")))
    if published is None or transfer_dt is None:
        return 0.5
    distance = abs((transfer_dt.date() - published.date()).days)
    if distance <= 3:
        return 0.95
    if distance <= 7:
        return 0.85
    if distance <= 30:
        return 0.65
    if distance <= 90:
        return 0.45
    return 0.25


def credibility_row(
    claim: dict[str, Any],
    match: dict[str, Any],
    config: dict[str, Any],
    source_stats: dict[str, AggregateStat],
    journalist_stats: dict[str, AggregateStat],
    club_journalist_stats: dict[str, AggregateStat],
    transfers_by_id: dict[str, dict[str, Any]],
) -> dict[str, object]:
    source = compact_whitespace(str(claim.get("source", "")))
    journalist = journalist_from_source(source, compact_whitespace(str(claim.get("journalist", ""))))
    transfer_related = str(claim.get("is_transfer_related", "")).strip() in {"1", "true", "True"}
    source_stat = source_stats.get(source)
    journalist_stat = journalist_stats.get(journalist)
    club_key = f"{compact_whitespace(str(claim.get('primary_club', '')))}||{journalist}"
    club_stat = club_journalist_stats.get(club_key)

    source_score = source_prior(source, config)
    journalist_history = smoothed_rate(journalist_stat, baseline=source_score)
    journalist_score = clamp(0.7 * journalist_history + 0.3 * source_score)
    conversion_score, support_n = historical_conversion_score(source_stat, journalist_stat, baseline=source_score)
    club_score = club_specific_score(club_stat, journalist_stat, baseline=journalist_score)
    stage_score = RUMOR_STAGE_SCORES.get(str(claim.get("rumor_stage", "unclear")), 0.4)
    article_kind = article_type(claim)
    article_score = ARTICLE_TYPE_SCORES.get(article_kind, 0.5)
    timing_score = time_to_confirmation_score(claim, match, transfers_by_id)
    ambiguity_flag = int(parse_float(match.get("ambiguity_flag"), 0.0))

    score = (
        source_score * WEIGHTS["source_reputation_score"]
        + journalist_score * WEIGHTS["journalist_reputation_score"]
        + conversion_score * WEIGHTS["historical_conversion_score"]
        + club_score * WEIGHTS["club_specific_score"]
        + stage_score * WEIGHTS["rumor_stage_score"]
        + article_score * WEIGHTS["article_type_score"]
        + timing_score * WEIGHTS["time_to_confirmation_score"]
    )
    notes = []
    if not transfer_related:
        notes.append("not_transfer_related")
        score = min(score * 0.35, 0.2)
    if not match.get("matched_transfer_id"):
        notes.append("unmatched_claim")
    if article_kind == "live_blog":
        notes.append("live_blog_penalty")
    if ambiguity_flag:
        notes.append("ambiguous_match")
        score *= 0.9
    if support_n < 3:
        notes.append("low_history_support")
    return {
        "claim_id": claim.get("claim_id", ""),
        "article_id": claim.get("article_id", ""),
        "title": claim.get("title", ""),
        "url": claim.get("url", ""),
        "snippet": claim.get("snippet", ""),
        "published_at": claim.get("published_at", ""),
        "source": source,
        "journalist": journalist,
        "primary_player": claim.get("primary_player", ""),
        "primary_club": claim.get("primary_club", ""),
        "rumor_stage": claim.get("rumor_stage", ""),
        "transfer_direction": claim.get("transfer_direction", ""),
        "is_transfer_related": int(transfer_related),
        "matched_transfer_id": match.get("matched_transfer_id", ""),
        "match_score": round(parse_float(match.get("match_score"), 0.0), 4),
        "match_reason": match.get("match_reason", ""),
        "ambiguity_flag": ambiguity_flag,
        "credibility_score": round(clamp(score), 4),
        "source_reputation_score": round(source_score, 4),
        "journalist_reputation_score": round(journalist_score, 4),
        "historical_conversion_score": round(conversion_score, 4),
        "club_specific_score": round(club_score, 4),
        "rumor_stage_score": round(stage_score, 4),
        "article_type_score": round(article_score, 4),
        "time_to_confirmation_score": round(timing_score, 4),
        "article_type": article_kind,
        "historical_support_n": support_n,
        "credibility_notes": notes,
    }


def write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_stats_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_scored_claims_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCORED_CLAIM_FIELDS)
        writer.writeheader()
        for row in rows:
            csv_row = {}
            for field in SCORED_CLAIM_FIELDS:
                value = row.get(field, "")
                if isinstance(value, list):
                    value = "|".join(str(item) for item in value)
                csv_row[field] = value
            writer.writerow(csv_row)


def merge_claim_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    fallback_index = 0
    for path in paths:
        if not path.exists():
            continue
        for row in read_claims(path):
            claim_id = compact_whitespace(str(row.get("claim_id", "")))
            if not claim_id:
                claim_id = f"missing-claim-id::{fallback_index}"
                fallback_index += 1
            if claim_id in merged:
                continue
            merged[claim_id] = dict(row)
    return list(merged.values())


def merge_match_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    fallback_index = 0
    for path in paths:
        if not path.exists():
            continue
        for row in read_matches(path):
            claim_id = compact_whitespace(str(row.get("claim_id", "")))
            if not claim_id:
                claim_id = f"missing-claim-id::{fallback_index}"
                fallback_index += 1
            if claim_id in merged:
                continue
            merged[claim_id] = dict(row)
    return list(merged.values())


def credibility_outputs(
    claims_path: Path,
    matches_path: Path,
    transfers_path: Path,
    output_dir: Path,
    stats_claim_paths: Iterable[Path] | None = None,
    stats_match_paths: Iterable[Path] | None = None,
) -> dict[str, Path]:
    claims = read_claims(claims_path)
    matches = read_matches(matches_path)
    matches_by_claim = {str(row.get("claim_id", "")): row for row in matches}
    config = load_credibility()
    transfers_by_id = transfer_index(transfers_path)

    stats_claim_rows = merge_claim_rows([*(stats_claim_paths or []), claims_path])
    stats_match_rows = merge_match_rows([*(stats_match_paths or []), matches_path])
    stats_matches_by_claim = {str(row.get("claim_id", "")): row for row in stats_match_rows}

    source_stats = aggregate_stats(
        stats_claim_rows,
        stats_matches_by_claim,
        key_fn=lambda row: compact_whitespace(str(row.get("source", ""))),
    )
    journalist_stats = aggregate_stats(
        stats_claim_rows,
        stats_matches_by_claim,
        key_fn=lambda row: journalist_from_source(compact_whitespace(str(row.get("source", ""))), compact_whitespace(str(row.get("journalist", "")))),
    )
    club_journalist_stats = aggregate_stats(
        stats_claim_rows,
        stats_matches_by_claim,
        key_fn=lambda row: f"{compact_whitespace(str(row.get('primary_club', '')))}||{journalist_from_source(compact_whitespace(str(row.get('source', ''))), compact_whitespace(str(row.get('journalist', ''))))}",
    )

    scored_rows = [
        credibility_row(
            claim,
            matches_by_claim.get(str(claim.get("claim_id", "")), {}),
            config,
            source_stats,
            journalist_stats,
            club_journalist_stats,
            transfers_by_id,
        )
        for claim in claims
    ]

    scored_path = output_dir / "scored_claims.jsonl"
    scored_csv_path = output_dir / "scored_claims.csv"
    source_stats_path = output_dir / "source_stats.csv"
    journalist_stats_path = output_dir / "journalist_stats.csv"
    club_journalist_stats_path = output_dir / "club_journalist_stats.csv"

    write_jsonl(scored_path, scored_rows)
    write_scored_claims_csv(scored_csv_path, scored_rows)
    write_stats_csv(
        source_stats_path,
        SOURCE_STATS_FIELDS,
        [
            {
                "source": stat.key,
                "n_claims": stat.n_claims,
                "n_matched": stat.n_matched,
                "match_rate": round(stat.match_rate, 4),
                "smoothed_rate": round(smoothed_rate(stat), 4),
                "avg_match_score": round(stat.avg_match_score, 4),
            }
            for stat in source_stats.values()
        ],
    )
    write_stats_csv(
        journalist_stats_path,
        JOURNALIST_STATS_FIELDS,
        [
            {
                "journalist": stat.key,
                "n_claims": stat.n_claims,
                "n_matched": stat.n_matched,
                "match_rate": round(stat.match_rate, 4),
                "smoothed_rate": round(smoothed_rate(stat), 4),
                "avg_match_score": round(stat.avg_match_score, 4),
            }
            for stat in journalist_stats.values()
        ],
    )
    write_stats_csv(
        club_journalist_stats_path,
        CLUB_JOURNALIST_STATS_FIELDS,
        [
            {
                "club": stat.key.split("||", 1)[0],
                "journalist": stat.key.split("||", 1)[1] if "||" in stat.key else "",
                "n_claims": stat.n_claims,
                "n_matched": stat.n_matched,
                "match_rate": round(stat.match_rate, 4),
                "smoothed_rate": round(smoothed_rate(stat), 4),
                "avg_match_score": round(stat.avg_match_score, 4),
            }
            for stat in club_journalist_stats.values()
        ],
    )

    return {
        "scored_claims": scored_path,
        "scored_claims_csv": scored_csv_path,
        "source_stats": source_stats_path,
        "journalist_stats": journalist_stats_path,
        "club_journalist_stats": club_journalist_stats_path,
    }


def read_scored_claims(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def credibility_stats(rows: Iterable[dict[str, Any]]) -> dict[str, object]:
    total = 0
    by_type: dict[str, int] = {}
    total_score = 0.0
    for row in rows:
        total += 1
        total_score += parse_float(row.get("credibility_score"), 0.0)
        article_kind = compact_whitespace(str(row.get("article_type", ""))) or "unknown"
        by_type[article_kind] = by_type.get(article_kind, 0) + 1
    return {
        "n_rows": total,
        "avg_credibility_score": round(total_score / total, 4) if total else 0.0,
        "article_types": dict(sorted(by_type.items(), key=lambda item: (-item[1], item[0]))),
    }
