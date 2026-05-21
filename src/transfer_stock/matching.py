from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

from .article_store import compact_whitespace, parse_list
from .claims import read_claims
from .config import Club
from .io import ensure_parent
from .transfers import Transfer, infer_season, load_transfers


MATCH_FIELDS = [
    "match_id",
    "claim_id",
    "article_id",
    "published_at",
    "primary_player",
    "primary_club",
    "transfer_direction",
    "rumor_stage",
    "is_transfer_related",
    "matched_transfer_id",
    "match_score",
    "match_reason",
    "ambiguity_flag",
    "candidate_count",
    "matched_season",
    "matched_club",
    "matched_player",
    "matched_direction",
    "matched_transfer_type",
    "matched_transfer_date",
]


@dataclass(frozen=True)
class TransferCandidate:
    transfer_id: str
    transfer: Transfer


@dataclass(frozen=True)
class MatchResult:
    match_id: str
    claim_id: str
    article_id: str
    published_at: str
    primary_player: str
    primary_club: str
    transfer_direction: str
    rumor_stage: str
    is_transfer_related: bool
    matched_transfer_id: str
    match_score: float
    match_reason: str
    ambiguity_flag: int
    candidate_count: int
    matched_season: str
    matched_club: str
    matched_player: str
    matched_direction: str
    matched_transfer_type: str
    matched_transfer_date: str

    def to_row(self) -> dict[str, object]:
        return {
            "match_id": self.match_id,
            "claim_id": self.claim_id,
            "article_id": self.article_id,
            "published_at": self.published_at,
            "primary_player": self.primary_player,
            "primary_club": self.primary_club,
            "transfer_direction": self.transfer_direction,
            "rumor_stage": self.rumor_stage,
            "is_transfer_related": int(self.is_transfer_related),
            "matched_transfer_id": self.matched_transfer_id,
            "match_score": round(self.match_score, 4),
            "match_reason": self.match_reason,
            "ambiguity_flag": self.ambiguity_flag,
            "candidate_count": self.candidate_count,
            "matched_season": self.matched_season,
            "matched_club": self.matched_club,
            "matched_player": self.matched_player,
            "matched_direction": self.matched_direction,
            "matched_transfer_type": self.matched_transfer_type,
            "matched_transfer_date": self.matched_transfer_date,
        }


def normalize_text(value: str) -> str:
    return compact_whitespace(
        "".join(char.lower() if char.isalnum() else " " for char in value or "")
    )


def transfer_id_for(transfer: Transfer) -> str:
    digest = hashlib.sha1(
        "||".join(
            [
                transfer.date.isoformat(),
                transfer.club,
                transfer.player,
                transfer.direction,
                transfer.transfer_type,
            ]
        ).encode("utf-8")
    ).hexdigest()
    return digest[:16]


def parse_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: str) -> datetime | None:
    text = compact_whitespace(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None


def claim_season(claim: dict[str, Any]) -> str:
    published = parse_date(str(claim.get("published_at", "")))
    if published is None:
        return ""
    return infer_season(published.date())


def surname(name: str) -> str:
    parts = normalize_text(name).split()
    return parts[-1] if parts else ""


def exact_player_match(claim_player: str, transfer_player: str) -> bool:
    return normalize_text(claim_player) == normalize_text(transfer_player) and bool(claim_player)


def surname_match(claim_player: str, transfer_player: str) -> bool:
    left = surname(claim_player)
    right = surname(transfer_player)
    return bool(left and right and left == right and len(left) >= 4)


def token_overlap(left: str, right: str) -> float:
    a = set(normalize_text(left).split())
    b = set(normalize_text(right).split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def club_lookup(clubs: dict[str, Club]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for club in clubs.values():
        lookup[normalize_text(club.name)] = club.name
        for alias in club.aliases:
            lookup[normalize_text(alias)] = club.name
    return lookup


def canonical_club_name(name: str, clubs: dict[str, Club]) -> str:
    lookup = club_lookup(clubs)
    return lookup.get(normalize_text(name), compact_whitespace(name))


def transfer_rows_with_ids(transfers_path: Path) -> list[TransferCandidate]:
    return [TransferCandidate(transfer_id_for(transfer), transfer) for transfer in load_transfers(transfers_path)]


def candidate_pool(
    claim: dict[str, Any],
    transfers: list[TransferCandidate],
    clubs: dict[str, Club],
) -> list[TransferCandidate]:
    claim_related = bool(int(claim.get("is_transfer_related", 0))) if str(claim.get("is_transfer_related", "")).isdigit() else bool(claim.get("is_transfer_related"))
    if not claim_related:
        return []
    primary_club = canonical_club_name(str(claim.get("primary_club", "")), clubs)
    clubs_from_claim = [canonical_club_name(item, clubs) for item in parse_list(claim.get("club_candidates"))]
    season = claim_season(claim)
    candidates = []
    for candidate in transfers:
        transfer = candidate.transfer
        club_match = transfer.club == primary_club or transfer.club in clubs_from_claim
        season_match = not season or transfer.season == season
        if club_match and season_match:
            candidates.append(candidate)
    if candidates:
        return candidates
    if primary_club and season:
        return []
    for candidate in transfers:
        transfer = candidate.transfer
        if primary_club and transfer.club != primary_club:
            continue
        candidates.append(candidate)
    return candidates


def claim_direction_matches(claim_direction: str, transfer_direction: str) -> bool:
    if claim_direction in {"", "unclear"}:
        return True
    return claim_direction == transfer_direction


def fee_closeness(claim_fee: float | None, transfer_fee: float | None) -> float:
    if claim_fee is None or transfer_fee is None or claim_fee <= 0 or transfer_fee <= 0:
        return 0.0
    gap = abs(claim_fee - transfer_fee) / max(claim_fee, transfer_fee)
    return max(0.0, 1.0 - gap)


def date_proximity_score(claim: dict[str, Any], transfer: Transfer) -> float:
    published = parse_date(str(claim.get("published_at", "")))
    if published is None:
        return 0.0
    distance = abs((transfer.date - published.date()).days)
    if distance <= 7:
        return 1.0
    if distance <= 30:
        return 0.8
    if distance <= 90:
        return 0.5
    if distance <= 180:
        return 0.2
    return 0.0


def score_candidate(claim: dict[str, Any], candidate: TransferCandidate, clubs: dict[str, Club]) -> tuple[float, list[str]]:
    transfer = candidate.transfer
    claim_player = str(claim.get("primary_player", ""))
    claim_club = canonical_club_name(str(claim.get("primary_club", "")), clubs)
    claim_season_value = claim_season(claim)
    claim_direction = compact_whitespace(str(claim.get("transfer_direction", ""))).lower()
    claim_type = compact_whitespace(str(claim.get("transfer_type", ""))).lower()
    claim_fee = parse_float(claim.get("transfer_fee_eur_estimate"))
    reasons: list[str] = []
    score = 0.0

    if exact_player_match(claim_player, transfer.player):
        score += 0.45
        reasons.append("exact_player")
    elif surname_match(claim_player, transfer.player):
        score += 0.25
        reasons.append("surname_player")
    else:
        overlap = token_overlap(claim_player, transfer.player)
        if overlap >= 0.5:
            score += 0.15
            reasons.append("fuzzy_player")

    if transfer.club == claim_club and claim_club:
        score += 0.2
        reasons.append("exact_club")
    elif claim_club and normalize_text(claim_club) in normalize_text(transfer.club):
        score += 0.1
        reasons.append("club_alias")

    if claim_season_value and transfer.season == claim_season_value:
        score += 0.1
        reasons.append("season_match")

    date_score = date_proximity_score(claim, transfer)
    if date_score > 0:
        score += 0.1 * date_score
        reasons.append("date_near")

    if claim_direction_matches(claim_direction, transfer.direction):
        if claim_direction not in {"", "unclear"}:
            score += 0.08
            reasons.append("direction_match")
    else:
        score -= 0.12
        reasons.append("direction_conflict")

    if claim_type and claim_type != "unclear":
        if claim_type == transfer.transfer_type:
            score += 0.05
            reasons.append("type_match")
        elif claim_type == "loan" and transfer.is_loan:
            score += 0.03
            reasons.append("loan_match")
        else:
            score -= 0.05
            reasons.append("type_conflict")

    fee_score = fee_closeness(claim_fee, transfer.transfer_fee_eur)
    if fee_score >= 0.8:
        score += 0.08
        reasons.append("fee_close")
    elif fee_score >= 0.5:
        score += 0.04
        reasons.append("fee_similar")

    return score, reasons


def match_id_for(claim_id: str, transfer_id: str) -> str:
    digest = hashlib.sha1(f"{claim_id}||{transfer_id}".encode("utf-8")).hexdigest()
    return digest[:16]


def empty_match(claim: dict[str, Any], reason: str, candidate_count: int = 0) -> MatchResult:
    claim_id = str(claim.get("claim_id", ""))
    return MatchResult(
        match_id=match_id_for(claim_id, ""),
        claim_id=claim_id,
        article_id=str(claim.get("article_id", "")),
        published_at=str(claim.get("published_at", "")),
        primary_player=str(claim.get("primary_player", "")),
        primary_club=str(claim.get("primary_club", "")),
        transfer_direction=str(claim.get("transfer_direction", "")),
        rumor_stage=str(claim.get("rumor_stage", "")),
        is_transfer_related=bool(int(claim.get("is_transfer_related", 0))) if str(claim.get("is_transfer_related", "")).isdigit() else bool(claim.get("is_transfer_related")),
        matched_transfer_id="",
        match_score=0.0,
        match_reason=reason,
        ambiguity_flag=0,
        candidate_count=candidate_count,
        matched_season="",
        matched_club="",
        matched_player="",
        matched_direction="",
        matched_transfer_type="",
        matched_transfer_date="",
    )


def single_match(
    claim: dict[str, Any],
    transfers: list[TransferCandidate],
    clubs: dict[str, Club],
    min_score: float = 0.45,
    ambiguity_delta: float = 0.07,
) -> MatchResult:
    if not (bool(int(claim.get("is_transfer_related", 0))) if str(claim.get("is_transfer_related", "")).isdigit() else bool(claim.get("is_transfer_related"))):
        return empty_match(claim, "not_transfer_related")
    pool = candidate_pool(claim, transfers, clubs)
    if not pool:
        return empty_match(claim, "no_candidates")
    scored: list[tuple[float, list[str], TransferCandidate]] = []
    for candidate in pool:
        score, reasons = score_candidate(claim, candidate, clubs)
        scored.append((score, reasons, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_reasons, best_candidate = scored[0]
    has_player_signal = any(reason in {"exact_player", "surname_player", "fuzzy_player"} for reason in best_reasons)
    if not has_player_signal:
        return empty_match(claim, "missing_player_signal", candidate_count=len(pool))
    if best_score < min_score:
        return empty_match(claim, "score_below_threshold", candidate_count=len(pool))
    ambiguity_flag = 0
    reason_tokens = list(best_reasons)
    if len(scored) > 1 and best_score - scored[1][0] < ambiguity_delta:
        ambiguity_flag = 1
        reason_tokens.append("ambiguous_close_second")
    transfer = best_candidate.transfer
    return MatchResult(
        match_id=match_id_for(str(claim.get("claim_id", "")), best_candidate.transfer_id),
        claim_id=str(claim.get("claim_id", "")),
        article_id=str(claim.get("article_id", "")),
        published_at=str(claim.get("published_at", "")),
        primary_player=str(claim.get("primary_player", "")),
        primary_club=str(claim.get("primary_club", "")),
        transfer_direction=str(claim.get("transfer_direction", "")),
        rumor_stage=str(claim.get("rumor_stage", "")),
        is_transfer_related=bool(int(claim.get("is_transfer_related", 0))) if str(claim.get("is_transfer_related", "")).isdigit() else bool(claim.get("is_transfer_related")),
        matched_transfer_id=best_candidate.transfer_id,
        match_score=best_score,
        match_reason="|".join(reason_tokens),
        ambiguity_flag=ambiguity_flag,
        candidate_count=len(pool),
        matched_season=transfer.season,
        matched_club=transfer.club,
        matched_player=transfer.player,
        matched_direction=transfer.direction,
        matched_transfer_type=transfer.transfer_type,
        matched_transfer_date=transfer.date.isoformat(),
    )


def write_matches(path: Path, rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATCH_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MATCH_FIELDS})


def read_matches(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def match_claims_file(
    claims_path: Path,
    transfers_path: Path,
    output_path: Path,
    clubs: dict[str, Club],
    min_score: float = 0.45,
    ambiguity_delta: float = 0.07,
) -> list[dict[str, object]]:
    claims = read_claims(claims_path)
    transfers = transfer_rows_with_ids(transfers_path)
    rows = [
        single_match(claim, transfers, clubs, min_score=min_score, ambiguity_delta=ambiguity_delta).to_row()
        for claim in claims
    ]
    write_matches(output_path, rows)
    return rows


def match_stats(rows: Iterable[dict[str, Any]]) -> dict[str, object]:
    total = 0
    matched = 0
    ambiguous = 0
    reasons: dict[str, int] = {}
    for row in rows:
        total += 1
        if row.get("matched_transfer_id"):
            matched += 1
        if str(row.get("ambiguity_flag", "")) in {"1", "true", "True"}:
            ambiguous += 1
        reason = compact_whitespace(str(row.get("match_reason", ""))) or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "n_rows": total,
        "matched": matched,
        "unmatched": total - matched,
        "ambiguous": ambiguous,
        "reasons": dict(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
    }
