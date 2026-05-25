# Agent Instructions

This repo is a Python research project for football transfer rumors, confirmed transfers, and publicly traded club stock reactions. It also has a static dashboard in `app/static/`.

## Work Style

- Inspect the existing pipeline before editing.
- Keep changes incremental and compatible with current CLI commands.
- Prefer small modules under `src/transfer_stock/`.
- Use existing data folders and schemas where possible.
- Do not make unsupported trading claims. Phrase outputs as research, ranking, triage, or context.
- Preserve user data and generated files unless explicitly asked to clean them.

## Commands

Use `PYTHONPATH=src` for local CLI commands:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask --question "Compare Manchester United and Juventus"
PYTHONPATH=src python3 -m transfer_stock.cli build-evidence-index
PYTHONPATH=src python3 -m transfer_stock.cli ask-rag --question "Explain Casemiro"
PYTHONPATH=src python3 -m transfer_stock.cli agent-run --goal "Explain the strongest current Juventus rumor"
PYTHONPATH=src python3 -m transfer_stock.cli simulate-scenario --player Casemiro --club "Manchester United"
PYTHONPATH=src python3 -m transfer_stock.cli generate-briefing
python3 -m http.server 8000 --directory app/static
```

If the virtualenv is active in the task, `.venv/bin/python` is also acceptable.

## Important Outputs

- Dashboard: `app/static/data/dashboard_data.json`
- Scenario dashboard snapshot: `app/static/data/scenario_latest.json`
- Scenario report: `app/static/data/scenario_latest_report.md`
- Full scenario run: `data/simulations/<simulation_id>/`
- Daily briefing: `data/reports/daily_briefing.md`
- Evidence RAG index: `data/processed/evidence/evidence_index.json`
- Agent run reports: `data/agents/<run_id>/agent_report.md`
- Match results: `data/raw/matches/<club_key>.csv`
- Agent/MCP-style contract: `docs/mcp_tools.md`

## Leakage And Claims

- Use temporal splits only for modeling.
- Do not use future stock-return windows as input features.
- Keep 2025-26/current rows as live or test-like data unless the user asks otherwise.
- If a rumor has no public target club ticker, report credibility and transfer intelligence only.
- Always mention that football club stocks can move because of match results, ownership news, liquidity, earnings, European qualification, and broader markets.

## Validation

Run focused checks after edits:

```bash
python3 -m py_compile src/transfer_stock/cli.py
PYTHONPATH=src python3 -m unittest tests.test_core
node --check app/static/dashboard.js
```

Only run `node --check` when dashboard JavaScript changed.
