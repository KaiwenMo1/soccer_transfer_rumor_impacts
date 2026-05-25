---
name: transfer-impact-analyst
description: Use when operating or extending this transfer_scrape football transfer-stock research repo: refresh live news, fetch match results, rebuild the static dashboard, query the analyst CLI, run Scenario Swarm simulations, generate daily briefings, inspect club/reporter outputs, and avoid leakage or unsupported trading claims.
---

# Transfer Impact Analyst

Use this skill inside the `transfer_scrape` repo when asked to operate, debug, or extend the football transfer-stock research pipeline.

## Core Rules

- Keep the project in Python with the existing static dashboard in `app/static/`.
- Prefer incremental changes. Do not rewrite the pipeline.
- Use `PYTHONPATH=src python3 -m transfer_stock.cli ...` unless the repo is already using `.venv/bin/python`.
- Treat outputs as research triage, not investment advice.
- Do not claim causal market impact from a rumor. Mention match results, liquidity, ownership news, and broad markets as confounders.
- Avoid leakage: do not train on future seasons when evaluating current or holdout seasons; do not use future price-window target values as model features.
- If a rumor does not map to a public club ticker, return credibility and transfer intelligence only.
- Validate with focused tests or compile checks after code changes.

## Key Data Contracts

- Dashboard payload: `app/static/data/dashboard_data.json`
- Latest Scenario Swarm snapshot: `app/static/data/scenario_latest.json`
- Latest Scenario Swarm Markdown: `app/static/data/scenario_latest_report.md`
- Daily briefing: `data/reports/daily_briefing.md`
- Full scenario runs: `data/simulations/<simulation_id>/`
- Match overlays: `data/raw/matches/<club_key>.csv`
- Live refresh working files: `data/live/<run_slug>/`

## Common Commands

Serve the static dashboard:

```bash
python3 -m http.server 8000 --directory app/static
```

Fast no-API live fetch/analyze flow, assuming a normalized live article file already exists:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-analyze \
  --input data/raw/articles/current_fast.jsonl \
  --clubs manchester_united juventus ajax \
  --slug current_fast \
  --dashboard-output app/static/data/dashboard_data.json
```

Full live refresh:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-dashboard \
  --clubs manchester_united juventus ajax \
  --source-preset no_api_fast \
  --methods rss \
  --max-records 8 \
  --page-size 8 \
  --max-pages 1 \
  --slug current_fast \
  --dashboard-output app/static/data/dashboard_data.json
```

Fetch match results:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli fetch-match-results \
  --seasons 2025-26 \
  --resume
```

Ask the local analyst:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "Compare Manchester United and Juventus"
```

Run Scenario Swarm:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli simulate-scenario \
  --player Casemiro \
  --club "Manchester United" \
  --rounds 2
```

Generate daily briefing:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli generate-briefing
```

Inspect dashboard payload:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli inspect-demo-data \
  --input app/static/data/dashboard_data.json
```

Serve API, if optional API dependencies are installed:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli serve-api \
  --payload app/static/data/dashboard_data.json \
  --host 127.0.0.1 \
  --port 8010
```

## How To Inspect Club And Reporter Context

For club dossiers, use the dashboard UI first. For CLI/API-style inspection:

- Ask: `Compare Manchester United and Juventus`
- Ask: `What are Manchester United current signals?`
- API endpoint if running: `GET /clubs/Manchester%20United/dossier`

For reporter profiles:

- Ask: `Show Fabrizio Romano profile`
- Ask: `Who are the strongest reporters for Manchester United?`
- API endpoint if running: `GET /reporters/Fabrizio%20Romano`

## Refresh Workflow

1. Fetch or reuse live articles.
2. Analyze live articles into claims, matches, credibility, market features, predictions, and dashboard payload.
3. Optionally fetch match results and rebuild dashboard data so stock charts include match markers.
4. Run Scenario Swarm for the most important signal.
5. Generate the daily briefing.
6. Serve `app/static/` and inspect the dashboard.

## Validation

After code edits, run the smallest meaningful checks:

```bash
python3 -m py_compile src/transfer_stock/cli.py
PYTHONPATH=src python3 -m unittest tests.test_core
node --check app/static/dashboard.js
```

Use `node --check` only when JavaScript changed.

## Output Interpretation

- `positive`, `negative`, and `neutral` labels are model/research labels.
- `watch` from Scenario Swarm means evidence is interesting but not decisive.
- Credibility scores describe local historical/source evidence quality, not truth.
- Match-result markers show timing context only; they do not isolate causality.
