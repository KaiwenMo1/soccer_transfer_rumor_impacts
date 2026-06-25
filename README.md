# Transfer Stock Analyst

An open-source football-finance intelligence system that turns noisy transfer
coverage into evidence-backed research for publicly listed clubs.

[Live dashboard](https://kaiwenmo1.github.io/soccer_transfer_rumor_impacts/) |
[Architecture](docs/architecture.md) |
[Full operations guide](docs/operations.md) |
[Product vision](PRODUCT_VISION.md)

![Dashboard preview](docs/dashboard-preview.svg)

## What It Does

Transfer Stock Analyst connects three datasets that are usually analyzed
separately:

1. transfer rumors, confirmed deals, players, fees, and clubs
2. journalist and publisher credibility history
3. listed-club stock paths, match results, and market context

The system collects and clusters articles, extracts structured claims, resolves
players and clubs, scores credibility, builds time-aware market features, and
publishes the results through a static dashboard, CLI, and FastAPI interface.

It is designed for research and triage, not automated trading. A rumor without
a direct listed-club target receives transfer and credibility analysis only; the
system does not invent a stock-impact prediction.

## Why This Is Technically Interesting

- **End-to-end data product:** ingestion, normalization, entity matching,
  feature engineering, temporal ML evaluation, backtesting, and presentation.
- **Grounded AI workflows:** a deterministic analyst, local Evidence RAG,
  bounded scenario agents, agent reachability checks, citations, uncertainty,
  and persistent run traces.
- **Honest financial research:** temporal splits, anti-leakage rules, abnormal
  return windows, match-result context, and explicit data-quality warnings.
- **Resilient ingestion:** API, RSS, multilingual sources, Google News URL
  decoding, and optional Scrapling/Fundus/Crawl4AI enrichment.
- **Multiple product surfaces:** static GitHub Pages dashboard, local workbench,
  JSON API, CLI, and agent-friendly tool contract.

## Five-Minute Local Demo

Requirements: Python 3.10+ and Node.js for the JavaScript syntax check.

```bash
git clone https://github.com/kaiwenmo1/soccer_transfer_rumor_impacts.git
cd soccer_transfer_rumor_impacts

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[api_server]"
```

Verify the project:

```bash
PYTHONPATH=src python -m unittest tests.test_core
node --check app/static/dashboard.js
PYTHONPATH=src python -m transfer_stock.cli inspect-demo-data \
  --input app/static/data/dashboard_data.json
```

Start the bundled dashboard:

```bash
python -m http.server 8000 --directory app/static
```

Open `http://127.0.0.1:8000`. This path uses the committed demo payload and
does not require API keys or a live scrape.

## Try The Analyst

Ask a grounded question from the bundled dataset:

```bash
PYTHONPATH=src python -m transfer_stock.cli ask \
  --question "Compare Manchester United and Juventus"
```

Publish the agent-reach report so external tools can discover safe commands,
endpoints, readiness checks, and local data boundaries:

```bash
PYTHONPATH=src python -m transfer_stock.cli agent-reach
```

Optional: install [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach)
as an upstream internet capability layer for wider web/RSS/GitHub/social
research. This project detects it when available and keeps cookie-based social
channels local.

```bash
pipx install https://github.com/Panniantong/agent-reach/archive/main.zip
agent-reach install --env=auto --safe
PYTHONPATH=src python -m transfer_stock.cli agent-reach --external-doctor
```

Run the bounded research operator without fetching new data:

```bash
PYTHONPATH=src python -m transfer_stock.cli research-cycle --mode research
```

Refresh live news and republish all dashboard snapshots locally:

```bash
bash scripts/auto_update_local.sh
```

Use a wider but slower source pass when you want more coverage:

```bash
SOURCE_PRESET=wide_no_api MAX_RECORDS=30 bash scripts/auto_update_local.sh
```

Start the local dashboard and JSON API together:

```bash
PYTHONPATH=src python -m transfer_stock.cli serve-api --port 8010
```

Then open `http://127.0.0.1:8010` or call:

```bash
curl -X POST http://127.0.0.1:8010/nlweb/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What changed today?"}'
```

## System Pipeline

```text
News/API/RSS sources          Transfer + stock + match datasets
          |                                 |
          v                                 v
 Normalized article store --------> Structured transfer claims
                                             |
                                             v
                               Entity resolution + credibility
                                             |
                                             v
                               Time-aware market/ML features
                                             |
                            +----------------+----------------+
                            |                                 |
                            v                                 v
                  Evidence RAG + agents              Backtests + reports
                            |                                 |
                            +----------------+----------------+
                                             |
                                             v
                                  Static dashboard + API
```

See [docs/architecture.md](docs/architecture.md) for component ownership,
data contracts, guardrails, and extension points.

## Main Capabilities

| Area | Implementation |
| --- | --- |
| News ingestion | Provider APIs, RSS, GDELT, multilingual feeds, optional Scrapling/Fundus/Crawl4AI |
| Claim intelligence | Structured extraction, rumor stage classification, duplicate clustering |
| Entity resolution | Player and club aliases, direction consistency, ambiguity flags |
| Credibility | Source, journalist, club-specific, stage, and historical conversion features |
| Market research | Raw and abnormal returns, volatility, pre-event drift, match-result overlays |
| Modeling | Logistic/XGBoost paths, temporal holdouts, leakage controls, feature importance |
| Agent workflows | Local analyst, Evidence RAG, Scenario Swarm, daily briefing, research operator |
| Agent readiness | Agent-reach report with capability catalog, safe commands, endpoints, setup checks, and optional Panniantong/Agent-Reach detection |
| Interfaces | Premium static dashboard, CLI, FastAPI, NLWeb-style manifest, agent-reach JSON |

## Repository Map

```text
src/transfer_stock/      Python ingestion, research, ML, agent, API, and CLI modules
app/static/              Static dashboard and committed demo snapshots
config/                  Club, source, and credibility configuration
tests/                   Deterministic core behavior and pipeline tests
docs/architecture.md     System design and engineering decisions
docs/operations.md       Full command and pipeline reference
docs/mcp_tools.md        Agent/MCP-style tool contract
.github/workflows/       PR validation, Pages deployment, and nightly refresh
```

## Validation And CI

Pull requests and pushes to `main` run:

```bash
PYTHONPATH=src python -m unittest tests.test_core
python -m py_compile src/transfer_stock/cli.py
node --check app/static/dashboard.js
PYTHONPATH=src python -m transfer_stock.cli inspect-demo-data \
  --input app/static/data/dashboard_data.json
```

The nightly workflow refreshes live evidence, republishes the GitHub Pages
dashboard, and commits the refreshed static snapshots back to `main` on
scheduled runs. That means your local machine can pick up the latest public
dashboard package with:

```bash
git pull
```

You can also run the workflow manually from GitHub Actions:

1. Open **Actions**.
2. Choose **Nightly Live Refresh**.
3. Click **Run workflow**.
4. Pick `fast_no_api`, `balanced_no_api`, `wide_no_api`, or
   `scrapling_wide_no_api`.
5. For manual runs, enable `commit_refreshed_data` if you want the refreshed
   static snapshots committed back to `main`. Scheduled runs commit them
   automatically.

To refresh automatically on your own machine, add a cron entry like:

```cron
15 7 */2 * * cd /path/to/transfer_scrape && /bin/bash scripts/auto_update_local.sh >> data/operators/local_auto_update.log 2>&1
```

## Data And Modeling Guardrails

- Use temporal train/test splits only.
- Never use post-rumor stock-return windows as live input features.
- Report credibility and transfer intelligence without stock impact when no
  public target ticker is mapped.
- Surface stale data, thin source coverage, weak entity matches, and low model
  confidence.
- Treat match results, ownership news, liquidity, earnings, European
  qualification, and broader markets as alternative explanations.
- Do not interpret outputs as investment advice.

## Public Club Universe

The bundled configuration includes Manchester United, Borussia Dortmund,
Juventus, Lazio, Ajax, Sporting CP, FC Porto, Celtic, Benfica, and Eagle
Football Group. Add or update clubs in `config/clubs.yml`.

## Resume-Friendly Project Summary

> Built an end-to-end football-finance intelligence platform that ingests and
> clusters multilingual transfer news, extracts and resolves structured rumor
> claims, learns reporter credibility, and evaluates listed-club stock reactions
> with temporal ML and event studies. Added grounded RAG/agent workflows,
> backtesting, data-quality audits, a FastAPI interface, automated refreshes,
> and a public interactive dashboard.

Strong engineering themes to discuss:

- designed explicit data contracts across ingestion, claims, matching,
  credibility, modeling, and presentation
- prevented target leakage with temporal splits and separated pre-event
  features from post-event evaluation labels
- built resilient source fallbacks and inspectable agent traces instead of
  relying on opaque end-to-end predictions
- exposed agent-reach and MCP-style contracts so AI tools can discover safe
  local capabilities without guessing commands
- translated a research pipeline into a usable dashboard, API, CLI, and
  scheduled deployment

## Documentation

- [Architecture and engineering decisions](docs/architecture.md)
- [Full setup, live refresh, modeling, and deployment commands](docs/operations.md)
- [Agent/API tool contract](docs/mcp_tools.md)
- [Product vision and guardrails](PRODUCT_VISION.md)
- [Upgrade history and roadmap](UPGRADE_GUIDE.md)
