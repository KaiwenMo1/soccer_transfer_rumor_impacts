from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyst import ask_analyst
from .config import ROOT

try:
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]


DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"


class AskRequest(BaseModel):  # type: ignore[misc]
    question: str


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Dashboard payload not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def club_dossier_response(data: dict[str, Any], club: str) -> dict[str, Any]:
    dossiers = data.get("club_dossiers", {})
    if club not in dossiers:
        raise KeyError(f"Unknown club dossier: {club}")
    return {
        "club": club,
        "dossier": dossiers[club],
        "stock_path": data.get("club_stock_paths", {}).get(club, {}),
        "media": data.get("club_media", {}).get(club, {}),
    }


def reporter_profile_response(data: dict[str, Any], reporter: str) -> dict[str, Any]:
    profiles = data.get("reporter_profiles", {})
    if reporter not in profiles:
        raise KeyError(f"Unknown reporter profile: {reporter}")
    return {
        "reporter": reporter,
        "profile": profiles[reporter],
    }


def compare_response(data: dict[str, Any], club_a: str, club_b: str) -> dict[str, Any]:
    dossiers = data.get("club_dossiers", {})
    missing = [club for club in (club_a, club_b) if club not in dossiers]
    if missing:
        raise KeyError(f"Unknown club dossier: {', '.join(missing)}")
    return ask_analyst(f"Compare {club_a} and {club_b}", payload=data)


def ask_response(data: dict[str, Any], question: str) -> dict[str, Any]:
    normalized = question.strip()
    if not normalized:
        raise ValueError("Question is required")
    return ask_analyst(normalized, payload=data)


def create_app(payload_path: str | Path = DEFAULT_PAYLOAD) -> Any:
    if FastAPI is None:  # pragma: no cover - optional dependency
        raise RuntimeError("FastAPI is not installed. Install it with: pip install -e '.[api_server]'")

    payload_file = Path(payload_path)
    app = FastAPI(
        title="Transfer Stock Research API",
        version="0.1.0",
        description="Small API for current signals, transfer history, and credibility leaderboards.",
    )

    def payload() -> dict[str, Any]:
        return load_payload(payload_file)

    @app.get("/health")
    def health() -> dict[str, Any]:
        data = payload()
        return {
            "status": "ok",
            "generated_at": data.get("generated_at", ""),
            "latest_season": data.get("latest_season", ""),
        }

    @app.get("/meta")
    def meta() -> dict[str, Any]:
        data = payload()
        return {
            "generated_at": data.get("generated_at", ""),
            "latest_season": data.get("latest_season", ""),
            "available_seasons": data.get("available_seasons", []),
            "overview": data.get("overview", {}),
            "watchlist_meta": data.get("live_watchlist_meta", {}),
        }

    @app.get("/signals/current")
    def signals_current(
        season: str | None = Query(default=None),
        club: str | None = Query(default=None),
        limit: int = Query(default=25, ge=1, le=250),
    ) -> dict[str, Any]:
        data = payload()
        chosen_season = season or data.get("latest_season", "")
        rows = list(data.get("signals_by_season", {}).get(chosen_season, []))
        if club:
            rows = [row for row in rows if row.get("club") == club or row.get("target_club") == club]
        return {
            "season": chosen_season,
            "count": len(rows),
            "rows": rows[:limit],
        }

    @app.get("/clubs/{club}/dossier")
    def club_dossier(club: str) -> dict[str, Any]:
        try:
            return club_dossier_response(payload(), club)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/reporters/{reporter}")
    def reporter_profile(reporter: str) -> dict[str, Any]:
        try:
            return reporter_profile_response(payload(), reporter)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/compare")
    def compare_clubs(
        club_a: str = Query(...),
        club_b: str = Query(...),
    ) -> dict[str, Any]:
        try:
            return compare_response(payload(), club_a, club_b)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/ask")
    def ask(request: AskRequest) -> dict[str, Any]:
        try:
            return ask_response(payload(), request.question)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/signals/watchlist")
    def signals_watchlist(limit: int = Query(default=10, ge=1, le=100)) -> dict[str, Any]:
        data = payload()
        rows = list(data.get("live_watchlist", []))
        return {
            "meta": data.get("live_watchlist_meta", {}),
            "count": len(rows),
            "rows": rows[:limit],
        }

    @app.get("/transfers/history")
    def transfers_history(
        season: str | None = Query(default=None),
        club: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict[str, Any]:
        data = payload()
        chosen_season = season or data.get("latest_season", "")
        rows = list(data.get("transfers_by_season", {}).get(chosen_season, []))
        if club:
            rows = [row for row in rows if row.get("club") == club or row.get("subject_club") == club]
        return {
            "season": chosen_season,
            "count": len(rows),
            "rows": rows[:limit],
        }

    @app.get("/leaderboards/{kind}")
    def leaderboard(kind: str, limit: int = Query(default=20, ge=1, le=200)) -> dict[str, Any]:
        data = payload()
        valid = {"journalists", "sources", "club_journalists"}
        if kind not in valid:
            raise HTTPException(status_code=404, detail=f"Unknown leaderboard kind: {kind}")
        rows = list(data.get("leaderboards", {}).get(kind, []))
        return {
            "kind": kind,
            "count": len(rows),
            "rows": rows[:limit],
        }

    return app
