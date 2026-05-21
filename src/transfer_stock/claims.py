from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .article_store import compact_whitespace, parse_list
from .config import Club
from .http import FetchError
from .io import ensure_parent, read_jsonl, write_jsonl
from .transfers import load_transfers


CLAIM_FIELDS = [
    "claim_id",
    "article_id",
    "published_at",
    "source",
    "journalist",
    "title",
    "url",
    "primary_player",
    "primary_club",
    "transfer_direction",
    "rumor_stage",
    "transfer_fee_raw",
    "transfer_fee_eur_estimate",
    "wage_raw",
    "wage_eur_annual_estimate",
    "transfer_type",
    "is_transfer_related",
    "extraction_confidence",
    "extractor_backend",
    "validation_notes",
    "club_candidates",
    "player_candidates",
]

RUMOR_STAGES = ("linked", "talks", "bid", "advanced", "agreed", "medical", "official", "unclear")
TRANSFER_DIRECTIONS = ("in", "out", "unclear")
TRANSFER_TYPES = ("permanent", "loan", "loan_with_option", "option", "unclear")

NON_TRANSFER_PATTERNS = (
    "as it happened",
    "live",
    "match report",
    "player ratings",
    "preview",
    "minute by minute",
    "relegation",
    "title race",
)

TRANSFER_CONTEXT_REGEXES = (
    r"\btransfer\b",
    r"\btransfer window\b",
    r"\bsigning\b",
    r"\bin talks\b",
    r"\btalks with\b",
    r"\btalks over\b",
    r"\bbid for\b",
    r"\boffer for\b",
    r"\bmove for\b",
    r"\bdeal for\b",
    r"\bdeal to sign\b",
    r"\bagreement to sign\b",
    r"\bagree(?:d)? deal\b",
    r"\bclose on\b",
    r"\bclose in on\b",
    r"\bclosing in\b",
    r"\bset to join\b",
    r"\bpoised to join\b",
    r"\bjoins? from\b",
    r"\bsign\b.*\bfrom\b",
    r"\bsigns? from\b",
    r"\bsigned for\b",
    r"\bsigns for\b",
    r"\bloan\b",
    r"\bmedical\b",
    r"\bsale of\b",
    r"\bsell\b",
    r"\bexit\b",
)

STAGE_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "official",
        (
            "confirm agreement to sign",
            "confirm signing",
            "confirmed signing",
            "official",
            "signs for",
            "signed for",
            "completes move",
            "completes transfer",
            "seals move",
            "announced signing",
            "seal deal",
            "joins from",
        ),
    ),
    ("medical", ("medical",)),
    ("agreed", ("deal agreed", "agreement", "agreed", "seal deal", "seals deal")),
    ("advanced", ("close on", "close in on", "closing in", "set to join", "poised to join", "edges closer")),
    ("bid", ("bid for", "offer for", "improved offer", "improved bid")),
    ("talks", ("in talks", "talks with", "talks over", "negotiations for", "discussions over")),
    ("linked", ("interested", "interest", "linked", "rumours", "rumor", "eyeing", "monitoring")),
]

IN_PATTERNS = (
    "sign",
    "signing",
    "buy",
    "bid for",
    "move for",
    "agree deal for",
    "close on",
    "join",
    "to ",
)

OUT_PATTERNS = (
    "sale",
    "sell",
    "selling",
    "leave",
    "leaving",
    "exit",
    "departure",
    "to sign",
    "close in on deal for",
)

MONEY_PATTERN = re.compile(
    r"(?P<currency>[€£$])\s?(?P<amount>\d+(?:\.\d+)?)\s?(?P<suffix>m|million|k|thousand)?(?:-|\s)?(?P<weekly>a week|per week|weekly)?",
    flags=re.IGNORECASE,
)

CURRENCY_TO_EUR = {
    "€": 1.0,
    "£": 1.17,
    "$": 0.92,
}


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    article_id: str
    published_at: str
    source: str
    journalist: str
    title: str
    url: str
    primary_player: str
    primary_club: str
    transfer_direction: str
    rumor_stage: str
    transfer_fee_raw: str
    transfer_fee_eur_estimate: float | None
    wage_raw: str
    wage_eur_annual_estimate: float | None
    transfer_type: str
    is_transfer_related: bool
    extraction_confidence: float
    extractor_backend: str
    validation_notes: tuple[str, ...]
    club_candidates: tuple[str, ...]
    player_candidates: tuple[str, ...]

    def to_row(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "article_id": self.article_id,
            "published_at": self.published_at,
            "source": self.source,
            "journalist": self.journalist,
            "title": self.title,
            "url": self.url,
            "primary_player": self.primary_player,
            "primary_club": self.primary_club,
            "transfer_direction": self.transfer_direction,
            "rumor_stage": self.rumor_stage,
            "transfer_fee_raw": self.transfer_fee_raw,
            "transfer_fee_eur_estimate": "" if self.transfer_fee_eur_estimate is None else round(self.transfer_fee_eur_estimate, 2),
            "wage_raw": self.wage_raw,
            "wage_eur_annual_estimate": "" if self.wage_eur_annual_estimate is None else round(self.wage_eur_annual_estimate, 2),
            "transfer_type": self.transfer_type,
            "is_transfer_related": int(self.is_transfer_related),
            "extraction_confidence": round(self.extraction_confidence, 4),
            "extractor_backend": self.extractor_backend,
            "validation_notes": list(self.validation_notes),
            "club_candidates": list(self.club_candidates),
            "player_candidates": list(self.player_candidates),
        }


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return compact_whitespace(text)


def claim_id_from_parts(article_id: str, primary_player: str, primary_club: str, stage: str) -> str:
    digest = hashlib.sha1("||".join([article_id, primary_player, primary_club, stage]).encode("utf-8")).hexdigest()
    return digest[:16]


def player_lexicon(transfers_path: Path | None) -> list[str]:
    if transfers_path is None or not transfers_path.exists():
        return []
    names = []
    for transfer in load_transfers(transfers_path):
        if transfer.player:
            names.append(transfer.player)
    return list(dict.fromkeys(sorted(names, key=lambda item: (-len(item), item))))


def mentioned_players(text: str, candidates: Iterable[str]) -> list[str]:
    haystack = f" {normalize_text(text)} "
    matches = []
    for player in candidates:
        normalized = normalize_text(player)
        if not normalized:
            continue
        if f" {normalized} " in haystack:
            matches.append(player)
            continue
        parts = normalized.split()
        if len(parts) >= 2:
            surname = parts[-1]
            if len(surname) >= 4 and f" {surname} " in haystack:
                matches.append(player)
    return list(dict.fromkeys(matches))


def choose_player(article: dict[str, Any], clubs: dict[str, Club], lexicon: list[str]) -> str:
    explicit = compact_whitespace(str(article.get("player", "")))
    if explicit:
        return explicit
    candidates = parse_list(article.get("player_candidates"))
    text = " ".join([str(article.get("title", "")), str(article.get("snippet", "")), str(article.get("body_text", ""))])
    direct_matches = mentioned_players(text, candidates)
    if direct_matches:
        return direct_matches[0]
    lexicon_matches = mentioned_players(text, lexicon)
    if lexicon_matches:
        return lexicon_matches[0]
    return ""


def choose_club(article: dict[str, Any], clubs: dict[str, Club]) -> str:
    explicit = compact_whitespace(str(article.get("club", "")))
    if explicit:
        return explicit
    candidates = parse_list(article.get("club_candidates"))
    if len(candidates) == 1:
        return candidates[0]
    title = normalize_text(str(article.get("title", "")))
    snippet = normalize_text(str(article.get("snippet", "")))
    scores: list[tuple[int, str]] = []
    for candidate in candidates:
        score = 0
        label = normalize_text(candidate)
        if label and label in title:
            score += 2
        if label and label in snippet:
            score += 1
        scores.append((score, candidate))
    scores.sort(key=lambda item: (-item[0], item[1]))
    return scores[0][1] if scores and scores[0][0] > 0 else (candidates[0] if candidates else "")


def infer_rumor_stage(text: str) -> str:
    lowered = normalize_text(text)
    if not has_transfer_context(lowered):
        return "unclear"
    for stage, patterns in STAGE_PATTERNS:
        for pattern in patterns:
            if normalize_text(pattern) in lowered:
                return stage
    return "unclear"


def infer_transfer_type(text: str) -> str:
    lowered = normalize_text(text)
    if "loan with option" in lowered or "loan option" in lowered:
        return "loan_with_option"
    if "option to buy" in lowered or "buy option" in lowered:
        return "option"
    if "loan" in lowered:
        return "loan"
    if has_transfer_context(lowered):
        return "permanent"
    return "unclear"


def has_transfer_context(text: str) -> bool:
    lowered = normalize_text(text)
    return any(re.search(pattern, lowered) for pattern in TRANSFER_CONTEXT_REGEXES)


def infer_transfer_related(text: str, primary_player: str, primary_club: str, stage: str) -> bool:
    lowered = normalize_text(text)
    if any(pattern in lowered for pattern in NON_TRANSFER_PATTERNS):
        return False
    if not has_transfer_context(lowered):
        return False
    if stage != "unclear":
        return True
    return bool(primary_player or primary_club)


def infer_direction(text: str, primary_club: str, primary_player: str) -> str:
    lowered = normalize_text(text)
    club = normalize_text(primary_club)
    player = normalize_text(primary_player)
    surname = player.split()[-1] if player else ""
    if club:
        out_signals = [
            "sale",
            "sell",
            "selling",
            "leaving",
            "leave",
            "exit",
            "departure",
            "depart",
            "from " + club,
        ]
        if surname:
            out_signals.extend(
                [
                    f"{club} s {surname}",
                    f"replace {surname}",
                    f"replacement for {surname}",
                    f"{surname} replacement",
                    f"{surname} exit",
                    f"{surname} departure",
                    f"{surname} final game",
                ]
            )
        if any(phrase in lowered for phrase in out_signals):
            return "out"
        if surname and f" s {surname}" in lowered and any(
            phrase in lowered for phrase in ["signing", "deal for", "bid for", "move for", "close in on", "transfer"]
        ):
            return "out"
    if club and any(phrase in lowered for phrase in ["close in on deal for"]):
        return "out"
    if club:
        in_signals = [
            club + " confirm agreement to sign",
            club + " confirm signing",
            club + " confirmed agreement to sign",
            club + " confirmed signing",
            "agree deal for " + club,
            "to " + club,
            "join " + club,
            "joins " + club,
            "sign for " + club,
            "signs for " + club,
            "signed for " + club,
            club + " sign",
            club + " signs",
            club + " signing",
            club + " move for",
            club + " bid for",
            club + " close on",
            club + " close in on",
        ]
        if any(phrase in lowered for phrase in in_signals):
            return "in"
        if surname:
            player_in_signals = [
                f"agreement to sign {surname}",
                f"deal to sign {surname}",
                f"sign {surname}",
                f"signing {surname}",
                f"deal for {surname}",
                f"bid for {surname}",
                f"move for {surname}",
            ]
            if any(phrase in lowered for phrase in player_in_signals) and f"{club} s {surname}" not in lowered:
                return "in"
    return "unclear"


def scale_money(amount: float, suffix: str) -> float:
    normalized = suffix.lower() if suffix else ""
    if normalized in {"m", "million"}:
        return amount * 1_000_000
    if normalized in {"k", "thousand"}:
        return amount * 1_000
    return amount


def money_mentions(text: str) -> list[dict[str, object]]:
    mentions: list[dict[str, object]] = []
    for match in MONEY_PATTERN.finditer(text):
        currency = match.group("currency")
        amount = float(match.group("amount"))
        scaled = scale_money(amount, match.group("suffix") or "")
        weekly = bool(match.group("weekly"))
        raw = compact_whitespace(match.group(0))
        eur = scaled * CURRENCY_TO_EUR.get(currency, 1.0)
        mentions.append(
            {
                "raw": raw,
                "eur": eur,
                "weekly": weekly,
                "currency": currency,
            }
        )
    return mentions


def choose_fee_and_wage(text: str) -> tuple[str, float | None, str, float | None]:
    mentions = money_mentions(text)
    fees = [item for item in mentions if not bool(item["weekly"])]
    wages = [item for item in mentions if bool(item["weekly"])]
    fee_raw = ""
    fee_eur = None
    if fees:
        best_fee = max(fees, key=lambda item: float(item["eur"]))
        fee_raw = str(best_fee["raw"])
        fee_eur = float(best_fee["eur"])
    wage_raw = ""
    wage_eur = None
    if wages:
        best_wage = max(wages, key=lambda item: float(item["eur"]))
        wage_raw = str(best_wage["raw"])
        wage_eur = float(best_wage["eur"]) * 52
    return fee_raw, fee_eur, wage_raw, wage_eur


def note_list_to_tuple(notes: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(note for note in notes if note))


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def validate_claim(raw: dict[str, Any], article: dict[str, Any]) -> dict[str, object]:
    notes = list(parse_list(raw.get("validation_notes")))
    direction = compact_whitespace(str(raw.get("transfer_direction", "unclear"))).lower() or "unclear"
    stage = compact_whitespace(str(raw.get("rumor_stage", "unclear"))).lower() or "unclear"
    transfer_type = compact_whitespace(str(raw.get("transfer_type", "unclear"))).lower() or "unclear"
    if direction not in TRANSFER_DIRECTIONS:
        direction = "unclear"
        notes.append("invalid_direction")
    if stage not in RUMOR_STAGES:
        stage = "unclear"
        notes.append("invalid_stage")
    if transfer_type not in TRANSFER_TYPES:
        transfer_type = "unclear"
        notes.append("invalid_transfer_type")
    related = bool(int(raw.get("is_transfer_related"))) if str(raw.get("is_transfer_related", "")).isdigit() else bool(raw.get("is_transfer_related"))
    if not related:
        stage = "unclear"
        direction = "unclear"
        notes.append("not_transfer_related")
    primary_player = compact_whitespace(str(raw.get("primary_player", "")))
    primary_club = compact_whitespace(str(raw.get("primary_club", "")))
    if not primary_player:
        notes.append("missing_player")
    if not primary_club:
        notes.append("missing_club")
    confidence = float(raw.get("extraction_confidence") or 0.0)
    if not primary_player or not primary_club:
        confidence *= 0.7
    if not related:
        confidence *= 0.4
    if article.get("title") and "live" in normalize_text(str(article["title"])):
        confidence *= 0.6
    return {
        **raw,
        "primary_player": primary_player,
        "primary_club": primary_club,
        "transfer_direction": direction,
        "rumor_stage": stage,
        "transfer_type": transfer_type,
        "is_transfer_related": related,
        "extraction_confidence": clamp_confidence(confidence),
        "validation_notes": note_list_to_tuple(notes),
    }


def heuristic_extract_claim(article: dict[str, Any], clubs: dict[str, Club], lexicon: list[str]) -> dict[str, object]:
    title = compact_whitespace(str(article.get("title", "")))
    snippet = compact_whitespace(str(article.get("snippet", "")))
    body_text = compact_whitespace(str(article.get("body_text", "")))
    text = " ".join([title, snippet, body_text]).strip()
    primary_player = choose_player(article, clubs, lexicon)
    primary_club = choose_club(article, clubs)
    stage = infer_rumor_stage(text)
    transfer_type = infer_transfer_type(text)
    related = infer_transfer_related(text, primary_player, primary_club, stage)
    direction = infer_direction(text, primary_club, primary_player) if related else "unclear"
    fee_raw, fee_eur, wage_raw, wage_eur = choose_fee_and_wage(text)
    notes: list[str] = []
    confidence = 0.45
    if stage != "unclear":
        confidence += 0.15
    if primary_player:
        confidence += 0.15
    if primary_club:
        confidence += 0.1
    if related:
        confidence += 0.1
    if fee_raw or wage_raw:
        confidence += 0.05
    if direction == "unclear":
        notes.append("unclear_direction")
    if stage == "unclear":
        notes.append("unclear_stage")
    raw = {
        "claim_id": claim_id_from_parts(str(article.get("article_id", "")), primary_player, primary_club, stage),
        "article_id": str(article.get("article_id", "")),
        "published_at": str(article.get("published_at", "")),
        "source": str(article.get("source", "")),
        "journalist": compact_whitespace(str(article.get("journalist", ""))),
        "title": title,
        "url": str(article.get("url", "")),
        "primary_player": primary_player,
        "primary_club": primary_club,
        "transfer_direction": direction,
        "rumor_stage": stage,
        "transfer_fee_raw": fee_raw,
        "transfer_fee_eur_estimate": fee_eur,
        "wage_raw": wage_raw,
        "wage_eur_annual_estimate": wage_eur,
        "transfer_type": transfer_type,
        "is_transfer_related": related,
        "extraction_confidence": confidence,
        "extractor_backend": "heuristic",
        "validation_notes": notes,
        "club_candidates": parse_list(article.get("club_candidates")),
        "player_candidates": parse_list(article.get("player_candidates")),
    }
    validated = validate_claim(raw, article)
    record = ClaimRecord(
        claim_id=str(validated["claim_id"]),
        article_id=str(validated["article_id"]),
        published_at=str(validated["published_at"]),
        source=str(validated["source"]),
        journalist=str(validated["journalist"]),
        title=str(validated["title"]),
        url=str(validated["url"]),
        primary_player=str(validated["primary_player"]),
        primary_club=str(validated["primary_club"]),
        transfer_direction=str(validated["transfer_direction"]),
        rumor_stage=str(validated["rumor_stage"]),
        transfer_fee_raw=str(validated["transfer_fee_raw"]),
        transfer_fee_eur_estimate=None if validated.get("transfer_fee_eur_estimate") in {"", None} else float(validated["transfer_fee_eur_estimate"]),
        wage_raw=str(validated["wage_raw"]),
        wage_eur_annual_estimate=None if validated.get("wage_eur_annual_estimate") in {"", None} else float(validated["wage_eur_annual_estimate"]),
        transfer_type=str(validated["transfer_type"]),
        is_transfer_related=bool(validated["is_transfer_related"]),
        extraction_confidence=float(validated["extraction_confidence"]),
        extractor_backend=str(validated["extractor_backend"]),
        validation_notes=tuple(validated["validation_notes"]),
        club_candidates=tuple(parse_list(validated["club_candidates"])),
        player_candidates=tuple(parse_list(validated["player_candidates"])),
    )
    return record.to_row()


class DSPyClaimExtractor:
    def __init__(self) -> None:
        try:
            import dspy  # type: ignore
        except ImportError as exc:
            raise FetchError("DSPy backend requested but `dspy` is not installed. Run `pip install dspy`.") from exc
        model_name = os.environ.get("DSPY_MODEL", "").strip()
        if not model_name:
            raise FetchError("DSPy backend requested but `DSPY_MODEL` is not set.")
        self.dspy = dspy
        dspy.configure(lm=dspy.LM(model_name))

        class ClaimSignature(dspy.Signature):  # type: ignore[misc, valid-type]
            """Extract a structured football transfer claim from a news article."""

            article_title: str = dspy.InputField()
            article_snippet: str = dspy.InputField()
            article_body: str = dspy.InputField()
            club_candidates: str = dspy.InputField()
            player_candidates: str = dspy.InputField()

            primary_player: str = dspy.OutputField()
            primary_club: str = dspy.OutputField()
            transfer_direction: str = dspy.OutputField(desc="One of: in, out, unclear")
            rumor_stage: str = dspy.OutputField(desc="One of: linked, talks, bid, advanced, agreed, medical, official, unclear")
            transfer_fee_raw: str = dspy.OutputField()
            wage_raw: str = dspy.OutputField()
            transfer_type: str = dspy.OutputField(desc="One of: permanent, loan, loan_with_option, option, unclear")
            is_transfer_related: str = dspy.OutputField(desc="Return true or false")
            extraction_confidence: str = dspy.OutputField(desc="A number between 0 and 1")
            validation_notes: str = dspy.OutputField(desc="Comma-separated notes, or empty")

        self.predictor = dspy.Predict(ClaimSignature)

    def extract(self, article: dict[str, Any]) -> dict[str, Any]:
        prediction = self.predictor(
            article_title=compact_whitespace(str(article.get("title", ""))),
            article_snippet=compact_whitespace(str(article.get("snippet", ""))),
            article_body=compact_whitespace(str(article.get("body_text", ""))),
            club_candidates=" | ".join(parse_list(article.get("club_candidates"))),
            player_candidates=" | ".join(parse_list(article.get("player_candidates"))),
        )
        return {
            "primary_player": compact_whitespace(str(getattr(prediction, "primary_player", ""))),
            "primary_club": compact_whitespace(str(getattr(prediction, "primary_club", ""))),
            "transfer_direction": compact_whitespace(str(getattr(prediction, "transfer_direction", "unclear"))).lower(),
            "rumor_stage": compact_whitespace(str(getattr(prediction, "rumor_stage", "unclear"))).lower(),
            "transfer_fee_raw": compact_whitespace(str(getattr(prediction, "transfer_fee_raw", ""))),
            "wage_raw": compact_whitespace(str(getattr(prediction, "wage_raw", ""))),
            "transfer_type": compact_whitespace(str(getattr(prediction, "transfer_type", "unclear"))).lower(),
            "is_transfer_related": compact_whitespace(str(getattr(prediction, "is_transfer_related", "false"))).lower() in {"true", "1", "yes"},
            "extraction_confidence": float(getattr(prediction, "extraction_confidence", 0.5) or 0.5),
            "validation_notes": parse_list(getattr(prediction, "validation_notes", "")),
        }


def choose_backend(name: str) -> str:
    backend = name.strip().lower() or "auto"
    if backend not in {"auto", "heuristic", "dspy"}:
        raise ValueError(f"Unsupported claim extractor backend: {backend}")
    return backend


def single_claim(
    article: dict[str, Any],
    clubs: dict[str, Club],
    lexicon: list[str],
    backend: str = "auto",
    dspy_extractor: DSPyClaimExtractor | None = None,
) -> dict[str, object]:
    resolved_backend = choose_backend(backend)
    if resolved_backend == "heuristic":
        return heuristic_extract_claim(article, clubs, lexicon)
    if resolved_backend == "dspy":
        extractor = dspy_extractor or DSPyClaimExtractor()
        base = heuristic_extract_claim(article, clubs, lexicon)
        dspy_output = extractor.extract(article)
        raw = {
            **base,
            **dspy_output,
            "claim_id": claim_id_from_parts(str(article.get("article_id", "")), str(dspy_output.get("primary_player", "")), str(dspy_output.get("primary_club", "")), str(dspy_output.get("rumor_stage", "unclear"))),
            "extractor_backend": "dspy",
            "journalist": compact_whitespace(str(article.get("journalist", ""))),
            "title": compact_whitespace(str(article.get("title", ""))),
            "url": str(article.get("url", "")),
            "source": str(article.get("source", "")),
            "published_at": str(article.get("published_at", "")),
            "article_id": str(article.get("article_id", "")),
            "club_candidates": parse_list(article.get("club_candidates")),
            "player_candidates": parse_list(article.get("player_candidates")),
        }
        fee_raw = compact_whitespace(str(raw.get("transfer_fee_raw", "")))
        wage_raw = compact_whitespace(str(raw.get("wage_raw", "")))
        if fee_raw or wage_raw:
            parsed_fee_raw, parsed_fee_eur, parsed_wage_raw, parsed_wage_eur = choose_fee_and_wage(" ".join([fee_raw, wage_raw]))
            raw["transfer_fee_raw"] = fee_raw or parsed_fee_raw
            raw["transfer_fee_eur_estimate"] = parsed_fee_eur
            raw["wage_raw"] = wage_raw or parsed_wage_raw
            raw["wage_eur_annual_estimate"] = parsed_wage_eur
        validated = validate_claim(raw, article)
        return {
            **validated,
            "validation_notes": list(validated["validation_notes"]),
            "club_candidates": parse_list(validated["club_candidates"]),
            "player_candidates": parse_list(validated["player_candidates"]),
        }
    try:
        extractor = dspy_extractor or DSPyClaimExtractor()
    except FetchError:
        return heuristic_extract_claim(article, clubs, lexicon)
    return single_claim(article, clubs, lexicon, backend="dspy", dspy_extractor=extractor)


def extract_claims_from_file(
    input_path: Path,
    output_path: Path,
    clubs: dict[str, Club],
    transfers_path: Path | None = None,
    backend: str = "auto",
) -> list[dict[str, object]]:
    rows = read_jsonl(input_path)
    lexicon = player_lexicon(transfers_path)
    extractor = None
    if choose_backend(backend) == "dspy":
        extractor = DSPyClaimExtractor()
    claims = [single_claim(row, clubs, lexicon, backend=backend, dspy_extractor=extractor) for row in rows]
    write_claims(output_path, claims)
    return claims


def write_claims(path: Path, rows: Iterable[dict[str, object]]) -> None:
    ensure_parent(path)
    normalized = []
    for row in rows:
        item = {field: row.get(field, [] if field.endswith("_candidates") or field == "validation_notes" else "") for field in CLAIM_FIELDS}
        if not isinstance(item["validation_notes"], list):
            item["validation_notes"] = parse_list(item["validation_notes"])
        if not isinstance(item["club_candidates"], list):
            item["club_candidates"] = parse_list(item["club_candidates"])
        if not isinstance(item["player_candidates"], list):
            item["player_candidates"] = parse_list(item["player_candidates"])
        normalized.append(item)
    write_jsonl(path, normalized)


def read_claims(path: Path) -> list[dict[str, object]]:
    return read_jsonl(path)


def claim_stats(rows: Iterable[dict[str, Any]]) -> dict[str, object]:
    total = 0
    related = 0
    stages: dict[str, int] = {}
    directions: dict[str, int] = {}
    backends: dict[str, int] = {}
    for row in rows:
        total += 1
        if bool(int(row.get("is_transfer_related", 0))) if str(row.get("is_transfer_related", "")).isdigit() else bool(row.get("is_transfer_related")):
            related += 1
        stage = compact_whitespace(str(row.get("rumor_stage", ""))) or "unknown"
        direction = compact_whitespace(str(row.get("transfer_direction", ""))) or "unknown"
        backend = compact_whitespace(str(row.get("extractor_backend", ""))) or "unknown"
        stages[stage] = stages.get(stage, 0) + 1
        directions[direction] = directions.get(direction, 0) + 1
        backends[backend] = backends.get(backend, 0) + 1
    return {
        "n_rows": total,
        "transfer_related": related,
        "stages": dict(sorted(stages.items(), key=lambda item: (-item[1], item[0]))),
        "directions": dict(sorted(directions.items(), key=lambda item: (-item[1], item[0]))),
        "backends": dict(sorted(backends.items(), key=lambda item: (-item[1], item[0]))),
    }
