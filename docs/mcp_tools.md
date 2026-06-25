# MCP-Friendly Tool Contract

This repo is not shipping a real MCP server yet. The best next step is a
stable MCP-compatible contract over the local CLI and FastAPI surfaces that
already exist. A real MCP server can later wrap these same functions without
changing tool names or response shapes.

Use this document when connecting Codex, Claude, Cursor, or another local agent
to the transfer-stock research project.

## Recommendation

Build the real MCP server later. For now, use the documented contract below.

Why:

- the project already has deterministic local tools
- the FastAPI layer exposes JSON for the most common read-only queries
- scenario simulations and briefings intentionally write research artifacts to
  disk, which is safer to keep as explicit CLI commands for now
- no new dependency is needed just to let agents use the project correctly

## Local Data Boundary

All tools are grounded in local project files. The default source payload is:

```text
app/static/data/dashboard_data.json
```

Important outputs:

```text
app/static/data/scenario_latest.json
app/static/data/scenario_latest_report.md
app/static/data/rumor_graph.json
data/simulations/<simulation_id>/
data/reports/daily_briefing.md
data/reports/daily_briefing.json
```

If live refresh commands need provider credentials, pass them through
environment variables. Do not store API keys in repo config files.

Common env vars:

```text
GUARDIAN_API_KEY
GNEWS_API_KEY
STOOQ_API_KEY
```

## Start The JSON API

Install the optional API dependency once:

```bash
pip install -e '.[api_server]'
```

Run the local API:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli serve-api \
  --payload app/static/data/dashboard_data.json \
  --host 127.0.0.1 \
  --port 8010
```

Health check:

```bash
curl http://127.0.0.1:8010/health
```

## Agent Reachability Report

The project includes an AgentReach-style readiness report. It is a compact
machine-readable entrypoint for external agents: what tools exist, which ones
are read-only, which files must exist, what setup is missing, and what safety
rules apply.

This report can also detect the optional upstream
[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) CLI.
That external project is useful as an internet capability router for web, RSS,
GitHub, YouTube, and optional social channels. This repo uses it only as an
optional upstream discovery layer; transfer normalization, credibility,
matching, modeling, and market research stay inside `transfer_stock`.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-reach
```

Print the full report without writing it:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-reach --print-only
```

Run the external Agent-Reach doctor when installed:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-reach --external-doctor --print-only
```

HTTP:

```http
GET /agent/reach
```

Static output:

```text
app/static/data/agent_reach.json
```

Core response fields:

```json
{
  "schema_version": "0.1",
  "status": "ready|partial|blocked",
  "readiness_score": 0.0,
  "summary": {
    "latest_season": "2025-26",
    "signal_count": 0,
    "watchlist_count": 0,
    "club_count": 0
  },
  "capabilities": [
    {
      "id": "ask_transfer_analyst",
      "risk": "read_only",
      "cli": "PYTHONPATH=src python -m transfer_stock.cli ask --question ...",
      "http": "/ask"
    }
  ],
  "readiness_checks": [],
  "external_agent_reach": {
    "available": false,
    "useful_channels": []
  },
  "recommended_next_actions": [],
  "agent_rules": []
}
```

This is intentionally lighter than a full MCP server. A real MCP wrapper can
consume this report to decide which local command or HTTP endpoint to call.
Keep social/cookie channels local and out of GitHub Actions unless you are
deliberately managing those credentials.

## NLWeb-Style Website Endpoint

The project also exposes a lightweight NLWeb-inspired contract so the dashboard
can behave like an AI-readable website.

Static manifest:

```text
app/static/.well-known/transfer-stock-agent.json
```

Publish it:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli publish-agent-manifest
```

HTTP:

```http
GET  /nlweb/manifest
POST /nlweb/ask
GET  /.well-known/transfer-stock-agent.json
```

Example:

```bash
curl -X POST http://127.0.0.1:8010/nlweb/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What changed today?"}'
```

This endpoint is intentionally research-only. It wraps the local analyst and
Evidence RAG layers; it does not execute trades or fetch private credentials.

## Temporal Rumor Graph

The project includes a lightweight Graphiti-inspired temporal graph over local
rumor evidence.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-rumor-graph
```

HTTP:

```http
GET /graphs/rumors
```

Output includes:

```json
{
  "summary": {
    "node_count": 0,
    "edge_count": 0,
    "timeline_count": 0,
    "top_clubs": [],
    "top_sources": [],
    "stage_mix": []
  },
  "nodes": [],
  "edges": [],
  "timelines": []
}
```

Use it to inspect evidence paths such as:

```text
Reporter -> Source -> Player -> Club -> Rumor Stage -> Market Read
```

This is relationship context, not causal market proof.

## Response Style

Agent-facing answers should prefer structured JSON over prose. When a tool uses
predictions, include confidence and uncertainty. When the target club is not a
publicly traded club in the payload, return credibility and transfer context
without claiming stock impact.

Never phrase outputs as trading advice. Use language like research context,
triage, watch item, historical comparison, and uncertainty.

## Tool Schemas

### get_agent_reachability()

Discover safe local commands, HTTP endpoints, readiness checks, and missing
setup before an external agent operates the project.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-reach --print-only
```

HTTP:

```http
GET /agent/reach
```

Output schema:

```json
{
  "schema_version": "string",
  "status": "ready|partial|blocked",
  "readiness_score": 0.0,
  "capabilities": [
    {
      "id": "string",
      "label": "string",
      "risk": "read_only|writes_local_reports|writes_static_manifest",
      "cli": "string",
      "http": "string"
    }
  ],
  "readiness_checks": [
    {"id": "string", "status": "pass|warn|fail", "message": "string"}
  ],
  "recommended_next_actions": ["string"],
  "agent_rules": ["string"]
}
```

### ask_transfer_analyst(question)

General local analyst query over the dashboard payload.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "Compare Manchester United and Juventus"
```

HTTP:

```http
POST /ask
Content-Type: application/json

{"question":"Compare Manchester United and Juventus"}
```

Input schema:

```json
{
  "question": "string"
}
```

Output schema:

```json
{
  "question": "string",
  "intent": "string",
  "short_answer": "string",
  "evidence_cards": [
    {"title": "string", "value": "string|number", "detail": "string"}
  ],
  "tables": [
    {"title": "string", "columns": ["string"], "rows": [{"key": "value"}]}
  ],
  "warnings": ["string"],
  "confidence": 0.0,
  "source_paths": {"dashboard_payload": "app/static/data/dashboard_data.json"}
}
```

Example:

```bash
curl -X POST http://127.0.0.1:8010/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the current signal for Casemiro?"}'
```

CLI with local Evidence RAG citations:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-evidence-index

PYTHONPATH=src python3 -m transfer_stock.cli ask-rag \
  --question "What is the current signal for Casemiro?"
```

When Evidence RAG is enabled, the answer includes extra fields:

```json
{
  "evidence_citations": [
    {
      "doc_id": "string",
      "doc_type": "signal|article|transfer|club_dossier|reporter_profile|stock_path|match_result|scenario|briefing",
      "title": "string",
      "snippet": "string",
      "source_path": "string",
      "url": "string",
      "score": 0.0
    }
  ],
  "what_would_change_mind": ["string"],
  "rag": {
    "retriever": "local_lexical",
    "index": "data/processed/evidence/evidence_index.json",
    "top_k": 5,
    "citation_count": 0
  }
}
```

### get_current_signals(club = null, season = null, limit = 25)

Read current or season-filtered rumor signals.

HTTP:

```http
GET /signals/current?club=Manchester%20United&season=2025-26&limit=25
```

Input schema:

```json
{
  "club": "string|null",
  "season": "string|null",
  "limit": 25
}
```

Output schema:

```json
{
  "season": "string",
  "count": 0,
  "rows": [
    {
      "club": "string",
      "target_club": "string",
      "player": "string",
      "rumor_stage": "string",
      "credibility_score": 0.0,
      "prediction_scope": "direct|indirect|none",
      "predicted_label": "positive|negative|neutral|unknown",
      "prediction_confidence": 0.0
    }
  ]
}
```

### get_club_dossier(club)

Return the club dossier, media, stock path, and match markers for one club.

HTTP:

```http
GET /clubs/Manchester%20United/dossier
```

Input schema:

```json
{"club": "string"}
```

Output schema:

```json
{
  "club": "string",
  "dossier": {"key": "value"},
  "stock_path": {"points": [], "markers": []},
  "media": {"logo": "string"}
}
```

### compare_clubs(club_a, club_b)

Compare two public-club dossiers using the analyst answer format.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "Compare Manchester United and Juventus"
```

HTTP:

```http
GET /compare?club_a=Manchester%20United&club_b=Juventus
```

Input schema:

```json
{
  "club_a": "string",
  "club_b": "string"
}
```

Output schema:

```json
{
  "question": "string",
  "intent": "compare_clubs",
  "short_answer": "string",
  "evidence_cards": [],
  "tables": [],
  "warnings": [],
  "confidence": 0.0,
  "source_paths": {"dashboard_payload": "app/static/data/dashboard_data.json"}
}
```

### get_reporter_profile(reporter)

Return the local credibility profile for a journalist/reporter.

HTTP:

```http
GET /reporters/Fabrizio%20Romano
```

CLI equivalent:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "Show Fabrizio Romano profile"
```

Input schema:

```json
{"reporter": "string"}
```

Output schema:

```json
{
  "reporter": "string",
  "profile": {
    "claim_count": 0,
    "avg_credibility": 0.0,
    "club_breakdown": []
  }
}
```

### get_transfer_history(club = null, season = null, limit = 50)

Read confirmed transfer rows from the dashboard payload.

HTTP:

```http
GET /transfers/history?club=Manchester%20United&season=2025-26&limit=50
```

Input schema:

```json
{
  "club": "string|null",
  "season": "string|null",
  "limit": 50
}
```

Output schema:

```json
{
  "season": "string",
  "count": 0,
  "rows": [
    {
      "date": "YYYY-MM-DD",
      "club": "string",
      "player": "string",
      "role": "buyer|seller|unknown",
      "transfer_fee_eur": 0.0,
      "market_value_eur": 0.0,
      "transfer_indicator": 0.0
    }
  ]
}
```

### get_leaderboard(kind, limit = 20)

Read journalist, source, or club-journalist leaderboards.

HTTP:

```http
GET /leaderboards/journalists?limit=20
GET /leaderboards/sources?limit=20
GET /leaderboards/club_journalists?limit=20
```

Input schema:

```json
{
  "kind": "journalists|sources|club_journalists",
  "limit": 20
}
```

Output schema:

```json
{
  "kind": "string",
  "count": 0,
  "rows": [{"key": "value"}]
}
```

### run_scenario_swarm(question = "", player = "", club = "", rounds = 2)

Run a bounded deterministic scenario simulation and write artifacts.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli simulate-scenario \
  --player Casemiro \
  --club "Manchester United" \
  --rounds 2
```

Input schema:

```json
{
  "question": "string",
  "player": "string",
  "club": "string",
  "rounds": 2,
  "payload": "app/static/data/dashboard_data.json",
  "output_dir": "data/simulations",
  "publish_dashboard": true
}
```

Output files:

```text
data/simulations/<simulation_id>/scenario.json
data/simulations/<simulation_id>/agents.json
data/simulations/<simulation_id>/trace.jsonl
data/simulations/<simulation_id>/report.md
app/static/data/scenario_latest.json
app/static/data/scenario_latest_report.md
```

Output JSON shape:

```json
{
  "simulation_id": "string",
  "scenario": "data/simulations/<simulation_id>/scenario.json",
  "agents": "data/simulations/<simulation_id>/agents.json",
  "trace": "data/simulations/<simulation_id>/trace.jsonl",
  "report": "data/simulations/<simulation_id>/report.md",
  "dashboard_scenario": "app/static/data/scenario_latest.json",
  "dashboard_report": "app/static/data/scenario_latest_report.md"
}
```

### generate_daily_briefing(payload = default, scenario = latest)

Generate a deterministic Markdown and JSON daily briefing from local data.

CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli generate-briefing
```

Input schema:

```json
{
  "payload": "app/static/data/dashboard_data.json",
  "scenario": "app/static/data/scenario_latest.json",
  "output": "data/reports/daily_briefing.md",
  "json_output": "data/reports/daily_briefing.json"
}
```

Output files:

```text
data/reports/daily_briefing.md
data/reports/daily_briefing.json
```

## Error Conventions

- HTTP `404`: unknown club, reporter, or leaderboard kind
- HTTP `400`: missing or empty question
- CLI non-zero exit: missing payload, missing scenario seed, or invalid args
- Empty but valid payload result: return `count: 0`, empty rows, and warnings when
  the command supports warnings

## Security Notes

- Run the API on `127.0.0.1` unless you intentionally place it behind your own
  auth layer.
- Do not expose provider API keys through endpoints, checked-in config, or
  static dashboard payloads.
- Treat all outputs as research context. This project is not a trading advisor.
- Football club stocks can move for many reasons outside transfer rumors:
  match results, ownership news, earnings, European qualification, liquidity,
  legal issues, sponsorship, and broader markets.
- For live/news refresh, keep credentials in environment variables and avoid
  writing raw secrets to logs.

## Future Real MCP Server Shape

When the repo is ready for a real MCP server, add a thin adapter such as:

```text
src/transfer_stock/mcp_server.py
```

It should call the existing Python functions instead of reimplementing logic:

```text
get_agent_reachability -> transfer_stock.agent_reach.build_agent_reach_report
ask_transfer_analyst -> transfer_stock.analyst.ask_analyst
get_current_signals -> transfer_stock.api.signals_current behavior
get_club_dossier -> transfer_stock.api.club_dossier_response
compare_clubs -> transfer_stock.api.compare_response
get_reporter_profile -> transfer_stock.api.reporter_profile_response
run_scenario_swarm -> transfer_stock.scenario_swarm.run_scenario_swarm
generate_daily_briefing -> transfer_stock.briefing.generate_daily_briefing
```

Keep the same tool names and schemas from this document so external agents do
not need to relearn the project later.

## Local Agent Loop

The repo also exposes a higher-level deterministic agent command:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-run \
  --goal "Find today's strongest Manchester United transfer-stock watch item"
```

This command is the best wrapper for general AI-agent use. It writes:

```text
data/agents/<run_id>/goal.json
data/agents/<run_id>/plan.json
data/agents/<run_id>/trace.jsonl
data/agents/<run_id>/answer.json
data/agents/<run_id>/evidence.json
data/agents/<run_id>/agent_report.md
```

The loop is:

```text
goal -> plan -> freshness check -> evidence index -> analyst answer -> evidence retrieval -> optional Scenario Swarm -> report
```

Use this when an external agent should delegate the whole research workflow to
the repo rather than manually calling each lower-level tool.
