from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from typing import Any

from .agent_reach import build_agent_reach_report
from .analyst import ask_analyst
from .config import ROOT
from .nlweb import build_agent_manifest, nlweb_ask
from .operator import DEFAULT_DASHBOARD_OPERATOR, run_research_cycle
from .rumor_graph import DEFAULT_DASHBOARD_RUMOR_GRAPH
from .runbooks import get_runbook, list_runbooks, runbook_operator_kwargs

try:
    from fastapi import FastAPI, HTTPException, Query
    from pydantic import BaseModel
    from fastapi.staticfiles import StaticFiles
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    Query = None  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment,misc]
    StaticFiles = None  # type: ignore[assignment]


DEFAULT_PAYLOAD = ROOT / "app" / "static" / "data" / "dashboard_data.json"


class AskRequest(BaseModel):  # type: ignore[misc]
    question: str


class ResearchCycleRequest(BaseModel):  # type: ignore[misc]
    mode: str = "smart"
    allow_network: bool = True
    source_preset: str = "fast_no_api"
    max_records: int = 20
    clubs: list[str] = []


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


def operator_snapshot_response(path: str | Path = DEFAULT_DASHBOARD_OPERATOR) -> dict[str, Any]:
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        return {"available": False, "status": "not_run", "path": str(snapshot_path)}
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"available": False, "status": "invalid_snapshot", "path": str(snapshot_path)}
    return payload if isinstance(payload, dict) else {"available": False, "status": "invalid_snapshot", "path": str(snapshot_path)}


def rumor_graph_response(path: str | Path = DEFAULT_DASHBOARD_RUMOR_GRAPH) -> dict[str, Any]:
    graph_path = Path(path)
    if not graph_path.exists():
        return {"available": False, "status": "not_built", "path": str(graph_path)}
    try:
        payload = json.loads(graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"available": False, "status": "invalid_snapshot", "path": str(graph_path)}
    if not isinstance(payload, dict):
        return {"available": False, "status": "invalid_snapshot", "path": str(graph_path)}
    return {"available": True, **payload}


def create_app(
    payload_path: str | Path = DEFAULT_PAYLOAD,
    *,
    static_dir: str | Path | None = ROOT / "app" / "static",
) -> Any:
    if FastAPI is None:  # pragma: no cover - optional dependency
        raise RuntimeError("FastAPI is not installed. Install it with: pip install -e '.[api_server]'")

    payload_file = Path(payload_path)
    app = FastAPI(
        title="Transfer Stock Research API",
        version="0.3.0",
        description="Research operator and API for transfer intelligence, credibility, and listed-club market context.",
    )
    operator_runtime: dict[str, Any] = {
        "status": "idle",
        "started_at": "",
        "completed_at": "",
        "mode": "",
        "runbook_id": "",
        "error": "",
    }

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

    @app.get("/nlweb/manifest")
    def nlweb_manifest() -> dict[str, Any]:
        return build_agent_manifest()

    @app.get("/.well-known/transfer-stock-agent.json")
    def well_known_agent_manifest() -> dict[str, Any]:
        return build_agent_manifest()

    @app.get("/agent/reach")
    def agent_reach() -> dict[str, Any]:
        return build_agent_reach_report(payload_path=payload_file)

    @app.post("/nlweb/ask")
    def nlweb_ask_route(request: AskRequest) -> dict[str, Any]:
        try:
            return nlweb_ask(request.question, payload_path=payload_file)
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

    def start_operator_job(
        *,
        mode: str,
        allow_network: bool,
        source_preset: str = "fast_no_api",
        max_records: int = 20,
        clubs: list[str] | None = None,
        runbook_id: str = "",
    ) -> dict[str, Any]:
        if operator_runtime["status"] == "running":
            raise HTTPException(status_code=409, detail="A research cycle is already running.")
        if mode not in {"research", "smart", "refresh"}:
            raise HTTPException(status_code=400, detail="Mode must be research, smart, or refresh.")

        operator_runtime.update(
            {
                "status": "running",
                "started_at": datetime.now(tz=UTC).isoformat(),
                "completed_at": "",
                "mode": mode,
                "runbook_id": runbook_id,
                "error": "",
            }
        )

        def run_job() -> None:
            try:
                result = run_research_cycle(
                    payload_path=payload_file,
                    mode=mode,
                    allow_network=allow_network,
                    source_preset=source_preset,
                    max_records=max_records,
                    clubs=clubs or [],
                )
                operator_runtime.update(
                    {
                        "status": result.get("status", "completed"),
                        "completed_at": datetime.now(tz=UTC).isoformat(),
                        "error": "",
                    }
                )
            except Exception as exc:  # pragma: no cover - runtime boundary
                operator_runtime.update(
                    {
                        "status": "failed",
                        "completed_at": datetime.now(tz=UTC).isoformat(),
                        "error": str(exc),
                    }
                )

        Thread(target=run_job, daemon=True).start()
        return {
            "accepted": True,
            "status": "running",
            "mode": mode,
            "allow_network": allow_network,
            "source_preset": source_preset,
            "max_records": max_records,
            "clubs": clubs or [],
            "runbook_id": runbook_id,
        }

    @app.get("/operator/latest")
    def operator_latest() -> dict[str, Any]:
        return operator_snapshot_response()

    @app.get("/operator/status")
    def operator_status() -> dict[str, Any]:
        return {
            **operator_runtime,
            "latest": operator_snapshot_response(),
        }

    @app.post("/operator/run", status_code=202)
    def operator_run(request: ResearchCycleRequest) -> dict[str, Any]:
        return start_operator_job(
            mode=request.mode,
            allow_network=request.allow_network,
            source_preset=request.source_preset,
            max_records=request.max_records,
            clubs=request.clubs,
        )

    @app.get("/runbooks")
    def runbooks() -> dict[str, Any]:
        return list_runbooks()

    @app.get("/graphs/rumors")
    def rumor_graph() -> dict[str, Any]:
        return rumor_graph_response()

    @app.get("/runbooks/{runbook_id}")
    def runbook(runbook_id: str) -> dict[str, Any]:
        try:
            return get_runbook(runbook_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/runbooks/{runbook_id}/run", status_code=202)
    def runbook_run(runbook_id: str) -> dict[str, Any]:
        try:
            request = runbook_operator_kwargs(runbook_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return start_operator_job(runbook_id=runbook_id, **request)

    if static_dir is not None and StaticFiles is not None:
        static_path = Path(static_dir)
        if static_path.exists():
            app.mount("/", StaticFiles(directory=str(static_path), html=True), name="dashboard")

    return app
