# Operations Guide

This is the full command, pipeline, live-refresh, modeling, and deployment
reference for Transfer Stock Analyst.

Start with the concise [project README](../README.md) for the five-minute demo
and [architecture guide](architecture.md) for system boundaries and data
contracts.

An open-source football-finance intelligence operator that turns noisy transfer
coverage into a daily, evidence-backed brief for publicly listed clubs.

It collects transfer news, turns articles into structured claims, scores
journalist/source credibility, links rumors to public football-club tickers, and
shows the evidence in a static dashboard plus local agent tools.

The product goal is simple: a user opens the site and learns **what changed,
what is credible, which listed club is exposed, what else could explain the
stock move, and what deserves inspection next**. See
[PRODUCT_VISION.md](PRODUCT_VISION.md) for the complete product framing.

Demo page after GitHub Pages is enabled:

- `https://kaiwenmo1.github.io/soccer_transfer_rumor_impacts/`

![Dashboard preview](docs/dashboard-preview.svg)

![Pipeline overview](docs/pipeline-overview.svg)

![Demo walkthrough storyboard](docs/demo-walkthrough.svg)

> Launch polish TODO: record `docs/demo-walkthrough.gif` from this storyboard
> before the first public push.

## Quick Demo

- **Live dashboard:** open the static market-intelligence view.
- **Ask The Analyst:** query the local payload in plain English.
- **Evidence RAG:** attach cited local evidence to answers.
- **Agent Run:** give the system a research goal and get plan, trace, evidence, and report files.
- **Data Quality Audit:** grade freshness, source coverage, market context, matching, model reliability, and date hygiene.
- **Scenario Swarm:** run role-based agents over one rumor.
- **Club comparison:** compare public clubs side by side.
- **Reporter profiles:** inspect journalist/source credibility.
- **Daily briefing:** generate a Markdown research brief from the latest data.
- **One-click research operator:** refresh when permitted, audit, retrieve
  evidence, run the analyst, and publish one decision queue.
- **Research runbooks:** choose a purpose-built workflow instead of memorizing
  the CLI.
- **NLWeb-style Agent Access:** expose the website as a natural-language JSON
  endpoint for local AI agents.
- **Temporal Rumor Graph:** inspect evolving relationships between reporters,
  sources, players, clubs, rumor stages, and market reads.

```bash
python3 -m http.server 8000 --directory app/static
```

Open `http://127.0.0.1:8000`.

Run the complete local research package without fetching new data:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli research-cycle --mode research
```

List the workflow gallery that powers the dashboard runbook cards:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli list-runbooks
```

Publish the static runbook snapshot for GitHub Pages:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli list-runbooks --publish
```

Publish the static agent manifest:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli publish-agent-manifest
```

Ask through the NLWeb-style local website endpoint:

```bash
curl -X POST http://127.0.0.1:8011/nlweb/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What changed today?"}'
```

Build the temporal rumor graph:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-rumor-graph
```

Run a supported runbook from CLI:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli run-runbook daily_research_cycle
```

Run the smart cycle, allowing a bounded live-news refresh when the current
payload is stale:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli research-cycle \
  --mode smart \
  --allow-network
```

For the website's **Run today's cycle** button, install the optional API server
and open the workbench:

```bash
pip install -e '.[api_server]'
PYTHONPATH=src python3 -m transfer_stock.cli serve-api --port 8010
```

Open `http://127.0.0.1:8010`.

Ask the local analyst:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "Compare Manchester United and Juventus"

PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "What is the current signal for Casemiro?"
```

Build a local evidence index and ask with citations:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-evidence-index

PYTHONPATH=src python3 -m transfer_stock.cli ask-rag \
  --question "Why is the Casemiro signal negative?"
```

Run the local agent loop:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-run \
  --goal "Find today's strongest Manchester United transfer-stock watch item"
```

Run a scenario simulation:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli simulate-scenario \
  --player Casemiro \
  --club "Manchester United" \
  --rounds 2
```

Generate a daily briefing:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli generate-briefing
```

Audit whether the current payload is fresh and research-ready:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli audit-data-quality
```

## Why This Exists

Confirmed transfers are usually late. The more interesting signal is often the
rumor path before confirmation: who reported it, how credible the source is, how
big the transfer is for the buying/selling club, and whether similar past events
lined up with stock movement.

The hard part is that football club stocks are noisy. Match results, European
qualification, ownership news, earnings, liquidity, legal issues, sponsorships,
and broader markets can all move the same ticker. This project makes that
messiness visible instead of pretending one article explains one price move.

Use it for research, triage, and evidence. It is not a trading advisor and does
not produce guaranteed buy/sell signals.

## What You Can Do

- Track live transfer rumors around listed clubs.
- Collapse duplicate articles into stronger rumor clusters.
- Score reporter/source credibility from historical claim outcomes.
- Ask RAG-backed analyst questions with cited local evidence.
- Run an agentic research loop that writes a plan, trace, answer, evidence, and report.
- Audit data freshness, source diversity, date hygiene, and model readiness before trusting current signals.
- Inspect target-aware predictions for buyer and seller sides.
- Open club dossiers with stock paths, match markers, transfers, and reporters.
- Compare clubs on live rumor volume, transfer quality, and realized returns.
- View reporter profiles and a reporter -> source -> club trust graph.
- Link rumored deals to closest confirmed historical transfers.
- Test hypothetical deals in the Scenario Simulator.
- Generate deterministic daily briefings for the current payload.

## Public Club Universe

The starter config tracks these listed clubs:

| Club | Default stock symbol | Notes |
| --- | --- | --- |
| Manchester United | `MANU` | NYSE ticker |
| Borussia Dortmund | `BVB.DE` | German listing |
| Juventus | `JUVE.MI` | Italian listing |
| Lazio | `SSL.MI` | Italian listing |
| Ajax NV | `AJAX.AS` | Dutch listing |
| Sporting CP SAD | `SCP.LS` | Portuguese listing |
| FC Porto SAD | `FCP.LS` | Portuguese listing |
| Celtic plc | `CCP.L` | London listing |
| Benfica SAD | `SLBEN.LS` | Portuguese listing |
| Eagle Football Group | `EFG.PA` | Lyon-linked French listing |

If a rumor does not target a public club ticker, the system can still report
credibility and transfer intelligence. It should not invent a stock-impact
prediction where no listed target exists.

## Start Here

If you already have `data/raw/articles/current_fast.jsonl`, rebuild the demo
payload and serve the dashboard:

```bash
source .venv/bin/activate

PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-analyze \
  --input data/raw/articles/current_fast.jsonl \
  --clubs manchester_united juventus ajax \
  --slug current_fast \
  --dashboard-output app/static/data/dashboard_data.json

python3 -m http.server 8000 --directory app/static
```

The website reads:

- `app/static/data/dashboard_data.json`

Scenario runs write `scenario.json`, `agents.json`, `trace.jsonl`, and
`report.md` under `data/simulations/<simulation_id>/`, then publish the latest
snapshot to:

- `app/static/data/scenario_latest.json`
- `app/static/data/scenario_latest_report.md`

Briefings write:

- `data/reports/daily_briefing.md`
- `data/reports/daily_briefing.json`

Data-quality audits write:

- `app/static/data/data_quality_latest.json`
- `data/reports/data_quality_audit.md`

Evidence RAG writes:

- `data/processed/evidence/evidence_index.json`

Agent runs write:

- `data/agents/<run_id>/goal.json`
- `data/agents/<run_id>/plan.json`
- `data/agents/<run_id>/trace.jsonl`
- `data/agents/<run_id>/answer.json`
- `data/agents/<run_id>/evidence.json`
- `data/agents/<run_id>/agent_report.md`

The latest run is also published for the static dashboard:

- `app/static/data/agent_latest.json`
- `app/static/data/agent_latest_report.md`

If you enable the included GitHub Actions workflow, the Pages demo can refresh
itself automatically once per day and redeploy the site with the newest payload.

## Local Agent Run

`agent-run` is the deterministic agent loop that ties the project together. It
does not need an LLM key. Given a goal, it:

1. chooses a grounded analyst question
2. checks dashboard freshness
3. rebuilds the local Evidence RAG index
4. asks the analyst with citations
5. retrieves top supporting evidence
6. optionally runs Scenario Swarm when a concrete rumor is found
7. compares against the previous agent run
8. writes a traceable research report
9. publishes the latest run to the dashboard

```bash
PYTHONPATH=src python3 -m transfer_stock.cli agent-run \
  --goal "Explain the strongest current Juventus rumor and whether the stock signal is credible"
```

Useful options:

```bash
--scenario auto     # default: run Scenario Swarm when a concrete player signal is found
--scenario never    # skip simulation and only produce RAG-backed analyst output
--top-k 8           # retrieve more evidence citations
--no-rebuild-index  # reuse data/processed/evidence/evidence_index.json
```

The dashboard reads `app/static/data/agent_latest.json` and shows the latest
agent goal, plan summary, citations, Scenario Swarm status, and "what changed
since last run" notes.

## Demo Recording Checklist

Before publishing, record a short GIF and save it as
`docs/demo-walkthrough.gif`:

1. Start the dashboard with `python3 -m http.server 8000 --directory app/static`.
2. Show the overview, Ask The Analyst, and Latest Agent Run panels.
3. Run `agent-run --goal "Explain Casemiro"` in the terminal.
4. Refresh the dashboard and show the new agent memory/citation panel.
5. Open the generated `agent_report.md`.

## Evidence RAG

The Evidence RAG layer builds a local index over the dashboard payload, current
article stores, scenario reports, daily briefings, club dossiers, reporter
profiles, transfer rows, stock paths, and match markers. It is intentionally
local and deterministic: no API key, vector database, or hosted model is needed.

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-evidence-index \
  --payload app/static/data/dashboard_data.json \
  --output data/processed/evidence/evidence_index.json

PYTHONPATH=src python3 -m transfer_stock.cli query-evidence \
  --question "Casemiro Manchester United credibility"

PYTHONPATH=src python3 -m transfer_stock.cli ask \
  --question "Explain Casemiro" \
  --with-evidence
```

Use `ask-rag --rebuild-index` when you want one command to rebuild the index and
answer the question:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli ask-rag \
  --question "Compare Manchester United and Juventus" \
  --rebuild-index
```

RAG citations are evidence context, not proof of causality. They show which
local rows, articles, reports, and market context support the answer.

## Agent-Ready Interfaces

This repo includes practical local agent instructions at:

- `skills/transfer-impact-analyst/SKILL.md`
- `AGENTS.md`
- [`docs/mcp_tools.md`](docs/mcp_tools.md)

These files teach Codex/Claude/Cursor-style tools how to refresh live news,
fetch match results, rebuild the dashboard, query the analyst CLI, run Scenario
Swarm simulations, generate the daily briefing, and avoid leakage or
overclaiming. They are local operating docs, not marketplace claims.

Everything below is the fuller pipeline and publishing reference.

## Recommended Data Sources

Use these in this order:

- Historical transfers: public Transfermarkt-derived datasets, or exports from
  `worldfootballR` functions such as `tm_team_transfers()` and
  `tm_player_transfer_history()`. Direct scraping Transfermarkt pages can be
  fragile and may violate site restrictions, so this project treats it as an
  ingestion source rather than hard-coding aggressive scraping.
- Wages: FBref/Capology via `worldfootballR::fb_squad_wages()` where available.
  Treat wages as estimates.
- Stock prices: Yahoo chart endpoint by default, with Stooq CSV support when
  you provide an API key.
- News and rumors: Guardian/GNews provider APIs, no-key RSS presets, GDELT for
  broad discovery, optional Fundus publisher crawling, optional Scrapling
  article-body enrichment, and Crawl4AI only for heavier fallback extraction.

## Club Config

The public-club universe is listed near the top of this README. If a symbol
does not return data, or you want to add another listed club, edit
`config/clubs.yml`.

## Install

This first version uses Python standard library plus `requests` and `PyYAML`,
which are already available in the current environment.

```bash
python3 -m transfer_stock.cli --help
```

Stage 1 of the upgrade guide adds a v2 ingestion path with optional extras:

```bash
pip install -e ".[scrape_v2]"
pip install -e ".[google_news_decode]"
pip install -e ".[scrapling_scrape]"
pip install -e ".[ai_scrape]"
pip install -e ".[claim_ai]"
pip install -e ".[market_research]"
pip install -e ".[ml_pipeline]"
pip install -e ".[api_server]"
```

These extras are optional. The repo still works without them and will fall back
to provider APIs, RSS ingestion, and a pure-Python market engine where
possible. For the stronger current-news path, the most useful no-key install
right now is:

```bash
pip install -e ".[scrapling_scrape,api_server]"
```

Then you can add:

```bash
pip install -e ".[scrape_v2]"
pip install -e ".[scrapling_scrape]"
pip install -e ".[ai_scrape]"
```

if you want stronger article-body enrichment. Scrapling is the lighter first
choice for resolving and parsing article pages; Crawl4AI is the heavier fallback
for pages that need AI/browser extraction.

Note: current Scrapling releases depend on `lxml >= 6`, while the installed
Fundus/Crawl4AI versions in this environment expect `lxml < 6` or `~5.3`.
Treat Scrapling mode as a separate enrichment lane from Fundus/Crawl4AI until
those dependency ranges converge.

## Quick Start

Run the demo pipeline with bundled sample transfers:

```bash
python3 -m transfer_stock.cli demo
```

Clean raw transfer files into one season-aware table:

```bash
python3 -m transfer_stock.cli clean-transfers
```

Expand the dataset with public Transfermarkt-derived league CSVs from
`ewenme/transfers`:

```bash
python3 -m transfer_stock.cli import-ewenme-transfers --start-season 2021-22 --end-season 2025-26
python3 -m transfer_stock.cli clean-transfers
```

This pulls Premier League, Bundesliga, and Serie A by default, then filters to
the configured public clubs. The source has season/window-level timing rather
than exact announcement dates, so imported rows use proxy dates: July 1 for
summer moves and January 1 for winter moves.

Loans are kept by default but marked with `transfer_type` and `is_loan`. To
exclude them from event/model data:

```bash
python3 -m transfer_stock.cli clean-transfers --loan-policy exclude
```

Fetch stock data:

```bash
python3 -m transfer_stock.cli fetch-stocks --start 2023-01-01 --end 2026-04-19

# Fetch only a subset when you do not want the full public-club universe.
python3 -m transfer_stock.cli fetch-stocks \
  --source yahoo \
  --start 2021-01-01 \
  --end 2026-05-01 \
  --clubs manchester_united ajax fc_porto
```

Stooq currently asks for an API key on direct CSV downloads. To use it, set:

```bash
export STOOQ_API_KEY=your_key_here
python3 -m transfer_stock.cli fetch-stocks --source stooq
```

Fetch match results for each public club and mark them on club stock paths:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli fetch-match-results \
  --seasons 2025-26 \
  --resume
```

This writes one CSV per club under `data/raw/matches/`. Rebuild the dashboard
afterward so the markers appear:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-analyze \
  --input data/raw/articles/current_fast.jsonl \
  --clubs manchester_united juventus ajax \
  --slug current_fast \
  --dashboard-output app/static/data/dashboard_data.json
```

Fetch current transfer news:

```bash
python3 -m transfer_stock.cli fetch-news --days 14
```

Fetch normalized articles into the v2 article store:

```bash
python3 -m transfer_stock.cli fetch-news-v2 --start 2026-04-01 --end 2026-05-19
python3 -m transfer_stock.cli inspect-ingestion --input data/raw/articles/articles_v2.jsonl
```

Normalize an existing raw JSONL file into the v2 article schema:

```bash
python3 -m transfer_stock.cli normalize-articles \
  --input data/raw/news/provider_club_news_2025_26_combined.jsonl \
  --output data/raw/articles/provider_club_news_2025_26_normalized.jsonl
```

Extract structured transfer claims from normalized articles:

```bash
python3 -m transfer_stock.cli extract-claims \
  --input data/raw/articles/provider_club_news_2025_26_normalized.jsonl \
  --output data/processed/claims/provider_club_news_2025_26_claims.jsonl

python3 -m transfer_stock.cli inspect-claims \
  --input data/processed/claims/provider_club_news_2025_26_claims.jsonl
```

The default claim extractor is a tested heuristic backend. If you install
`dspy` and configure a model, you can request the DSPy backend explicitly:

```bash
export DSPY_MODEL=openai/gpt-5-mini
python3 -m transfer_stock.cli extract-claims --backend dspy
```

Match extracted claims to likely transfer records:

```bash
python3 -m transfer_stock.cli match-claims \
  --claims data/processed/claims/provider_event_news_2025_26_top50_claims.jsonl \
  --transfers data/processed/transfers_exact_dates.csv \
  --output data/processed/matched_claims/provider_event_news_2025_26_top50_matches.csv

python3 -m transfer_stock.cli inspect-matches \
  --input data/processed/matched_claims/provider_event_news_2025_26_top50_matches.csv
```

Build richer credibility features from the claim and match history:

```bash
python3 -m transfer_stock.cli score-credibility \
  --claims data/processed/claims/provider_event_news_2025_26_top50_claims.jsonl \
  --matches data/processed/matched_claims/provider_event_news_2025_26_top50_matches.csv \
  --transfers data/processed/transfers_exact_dates.csv \
  --output-dir data/processed/credibility/provider_event_news_2025_26_top50

python3 -m transfer_stock.cli inspect-credibility \
  --input data/processed/credibility/provider_event_news_2025_26_top50/scored_claims.jsonl
```

This writes:

- `scored_claims.jsonl`: claim-level credibility scores and subcomponents
- `scored_claims.csv`: same scored claims in table form
- `source_stats.csv`: source-level historical match rates
- `journalist_stats.csv`: journalist-level historical match rates
- `club_journalist_stats.csv`: club-specific journalist hit rates

Run the same credibility pipeline over the larger historical 2021-25 event-news
set:

```bash
python3 -m transfer_stock.cli merge-jsonl \
  --output data/raw/news/historical_event_news_2021_25.jsonl \
  --inputs data/raw/news/combined_event_news_top.jsonl data/raw/news/event_news.jsonl \
  --dedupe

python3 -m transfer_stock.cli normalize-articles \
  --input data/raw/news/historical_event_news_2021_25.jsonl \
  --output data/raw/articles/historical_event_news_2021_25_normalized.jsonl

python3 -m transfer_stock.cli extract-claims \
  --input data/raw/articles/historical_event_news_2021_25_normalized.jsonl \
  --output data/processed/claims/historical_event_news_2021_25_claims.jsonl

python3 -m transfer_stock.cli match-claims \
  --claims data/processed/claims/historical_event_news_2021_25_claims.jsonl \
  --transfers data/processed/transfers_exact_dates.csv \
  --output data/processed/matched_claims/historical_event_news_2021_25_matches.csv

python3 -m transfer_stock.cli score-credibility \
  --claims data/processed/claims/historical_event_news_2021_25_claims.jsonl \
  --matches data/processed/matched_claims/historical_event_news_2021_25_matches.csv \
  --transfers data/processed/transfers_exact_dates.csv \
  --output-dir data/processed/credibility/historical_event_news_2021_25
```

Build richer market research features aligned to rumor rows:

```bash
python3 -m transfer_stock.cli build-market-features \
  --input data/processed/rumor_events_grouped.csv \
  --output data/processed/market_features/rumor_events_grouped_market.csv

python3 -m transfer_stock.cli inspect-market-features \
  --input data/processed/market_features/rumor_events_grouped_market.csv
```

The market-feature layer keeps pre-rumor context separate from post-rumor
evaluation windows. Safe pre-event columns include fields such as
`pre_raw_return_m10`, `pre_abnormal_return_m10`, `pre_volatility_20d`, and
`pre_close_zscore_20d`. Post-event evaluation columns include
`abnormal_return_0_p3`, `abnormal_return_0_p10`, `volatility_shift_20d`, and
`target_label_p3`.

Build the Stage 6 claim-level ML dataset from the historical and 2025-26
scored-claim files:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-stage6-dataset
```

The Stage 6 base dataset is now target-aware:

- one matched rumor can expand into a public `buyer` row, a public `seller`
  row, or both if both clubs are listed
- rows without any public target stay in the dataset with
  `prediction_scope = none`
- those intelligence-only rows keep credibility and transfer context, but the
  market-label and ML path do not assign them fake stock-impact predictions

Train the stronger temporal tabular models:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli train-model-v2 \
  --dataset data/processed/modeling/stage6_claims_market.csv \
  --predictions-dir data/models/stage6 \
  --metrics data/models/stage6/metrics_stage6.json \
  --train-end-season 2024-25
```

The Stage 6 trainer now keeps the same CLI but does a small validation-based
model selection pass for XGBoost. It compares a full feature set against a
pruned core feature set and picks the better validation configuration before
writing the final prediction files.

This writes:

- `data/processed/modeling/stage6_claims_market.csv`
- `data/models/stage6/stage6_logistic_predictions.csv`
- `data/models/stage6/stage6_xgboost_predictions.csv`
- `data/models/stage6/metrics_stage6.json`

Run Stage 7 backtests on the XGBoost predictions:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli run-backtests \
  --predictions data/models/stage6/stage6_xgboost_predictions.csv \
  --output-dir data/reports/backtests \
  --holding-days 3 \
  --positive-threshold 0.55 \
  --negative-threshold 0.55 \
  --credibility-threshold 0.65

PYTHONPATH=src python3 -m transfer_stock.cli inspect-backtests \
  --input data/reports/backtests/backtest_summary.csv
```

This writes:

- `data/reports/backtests/backtest_summary.csv`
- `data/reports/backtests/backtest_trades.csv`
- `data/reports/backtests/backtest_daily_returns.csv`
- `data/reports/backtests/backtest_report.md`

Build the Stage 8 dashboard payload from the main Stage 6/7 outputs:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli build-demo-data \
  --predictions data/models/stage6/stage6_xgboost_predictions.csv \
  --metrics data/models/stage6/metrics_stage6.json \
  --backtest-summary data/reports/backtests/backtest_summary.csv \
  --backtest-trades data/reports/backtests/backtest_trades.csv \
  --transfers data/processed/transfers_exact_dates.csv \
  --journalist-stats data/processed/credibility/historical_event_news_2021_25/journalist_stats.csv \
  --source-stats data/processed/credibility/historical_event_news_2021_25/source_stats.csv \
  --club-journalist-stats data/processed/credibility/historical_event_news_2021_25/club_journalist_stats.csv \
  --output app/static/data/dashboard_data.json

PYTHONPATH=src python3 -m transfer_stock.cli inspect-demo-data \
  --input app/static/data/dashboard_data.json
```

The dashboard reads from:

- `app/static/data/dashboard_data.json`
- `data/models/stage6/stage6_xgboost_predictions.csv`
- `data/models/stage6/metrics_stage6.json`
- `data/reports/backtests/backtest_summary.csv`
- `data/reports/backtests/backtest_trades.csv`

The payload now carries all available seasons (`2021-22` through `2025-26` in
the bundled demo data), so the dashboard can switch between past seasons and
show how the realized market impact changed over time. It also exposes
`target_club`, `target_ticker`, `target_role`, and `prediction_scope` so the
UI can distinguish direct public-club predictions from rows that would only be
credibility/transfer-quality assessments in a broader future pipeline.

The current dashboard also includes:

- a `Rumor Signals` view for target-aware rumor predictions
- a `Past Transfers` view for confirmed transfer quality and realized impact
- a `Live Watchlist` panel for the latest direct-target rumors
- journalist, source, and club-journalist credibility leaderboards
- club stock paths with optional match result markers from `data/raw/matches/<club_key>.csv`

Match-result overlay CSVs use this shape:

```csv
date,opponent,competition,venue,result,goals_for,goals_against,score,source_url
2026-05-17,Chelsea,Premier League,A,W,2,1,2-1,https://example.com/match-report
```

Weekend match dates are mapped to the next available stock trading date.

Serve the dashboard locally from the repo root:

```bash
python3 -m http.server 8000 --directory app/static
```

Then open `http://127.0.0.1:8000`.

Important:

- the website does **not** read `current_live.jsonl` directly
- the website reads `app/static/data/dashboard_data.json`
- `current_live.jsonl` is a normalized article-store input file
- you update the site by rebuilding `dashboard_data.json`

Recommended two-step workflow for current live data:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-fetch \
  --start "$(python3 -c 'from datetime import date, timedelta; print((date.today() - timedelta(days=21)).isoformat())')" \
  --end "$(python3 -c 'from datetime import date; print(date.today().isoformat())')" \
  --source-preset scrapling_wide_no_api \
  --max-records 10 \
  --pause 0.1 \
  --clubs manchester_united borussia_dortmund juventus lazio ajax sporting_cp fc_porto celtic benfica eagle_football_group \
  --output data/raw/articles/current_live.jsonl

PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-analyze \
  --input data/raw/articles/current_live.jsonl \
  --clubs manchester_united borussia_dortmund juventus lazio ajax sporting_cp fc_porto celtic benfica eagle_football_group \
  --slug current_live \
  --dashboard-output app/static/data/dashboard_data.json

PYTHONPATH=src .venv/bin/python -m transfer_stock.cli audit-data-quality
```

After that, refresh the browser on `http://127.0.0.1:8000`.

This is also the default GitHub Actions refresh lane. It discovers articles
from RSS and Google News feeds, decodes Google News wrapper URLs into real
publisher URLs, then uses Scrapling to pull article bodies. That gives the
claim extractor more context than headline-only RSS.

Refresh the current-news dashboard in one command:

```bash
export GUARDIAN_API_KEY=your_guardian_key
export GNEWS_API_KEY=your_gnews_key

PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-dashboard \
  --start 2026-05-01 \
  --end 2026-05-20 \
  --provider all \
  --methods provider rss fundus \
  --clubs manchester_united borussia_dortmund juventus lazio ajax sporting_cp fc_porto celtic benfica eagle_football_group \
  --dashboard-output app/static/data/dashboard_data.json
```

If you want a much faster run without any API keys, use the new no-API preset:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-dashboard \
  --start 2026-05-01 \
  --end 2026-05-20 \
  --source-preset fast_no_api \
  --max-records 15 \
  --pause 0.1 \
  --no-refresh-stocks \
  --clubs manchester_united borussia_dortmund juventus lazio ajax \
  --dashboard-output app/static/data/dashboard_data.json
```

That preset uses repo-based and feed-based collection only:

- Guardian RSS
- BBC Football RSS
- Google News RSS

No Guardian API key or GNews API key required.

If you want a broader no-API mode and have `fundus` installed:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-dashboard \
  --start 2026-05-01 \
  --end 2026-05-20 \
  --source-preset balanced_no_api \
  --max-records 12 \
  --pause 0.1 \
  --no-refresh-stocks \
  --clubs manchester_united borussia_dortmund juventus lazio ajax sporting_cp fc_porto benfica \
  --dashboard-output app/static/data/dashboard_data.json
```

If you want the widest no-API discovery pass, use the region-expanded preset:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-dashboard \
  --start 2026-05-01 \
  --end 2026-05-20 \
  --source-preset wide_no_api \
  --max-records 10 \
  --pause 0.1 \
  --no-refresh-stocks \
  --clubs manchester_united borussia_dortmund juventus lazio ajax sporting_cp fc_porto celtic benfica eagle_football_group \
  --dashboard-output app/static/data/dashboard_data.json
```

`wide_no_api` expands the feed mix with localized Google News queries for:

- Germany / Borussia Dortmund
- Italy / Juventus and Lazio
- France / Eagle Football Group
- Scotland / Celtic
- Portugal / Sporting, Porto, Benfica
- Netherlands / Ajax

If you already fetched into `current_live.jsonl`, you do **not** need to fetch
again. Just run:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-analyze \
  --input data/raw/articles/current_live.jsonl \
  --clubs manchester_united borussia_dortmund juventus lazio ajax sporting_cp fc_porto celtic benfica eagle_football_group \
  --slug current_live \
  --dashboard-output app/static/data/dashboard_data.json
```

This command will:

1. fetch current provider club-news articles
2. normalize and dedupe them into the v2 article store
3. extract structured claims
4. match claims to likely transfers
5. score credibility using historical claim/match history as context
6. rebuild the Stage 6 dataset with the fresh live rows included
7. retrain the Stage 6 models
8. rerun the Stage 7 backtests
9. rebuild the Stage 8 dashboard payload

Artifacts for each refresh run are written under `data/live/<run_slug>/`, so
you can inspect a full run without overwriting older ones.

The source layer now includes multilingual RSS coverage for:

- Ajax in Dutch
- Sporting CP in Portuguese
- FC Porto in Portuguese
- Benfica in Portuguese

Those sources are additive to the Guardian/GNews flow and are intended to help
current-news refreshes pull better local coverage for clubs outside the
English-language bubble.

If `fundus` is installed, the same command can also pull directly from regional
publisher collections for:

- UK / Ireland coverage around Manchester United and Celtic
- Germany for Borussia Dortmund
- Italy for Juventus and Lazio
- Netherlands for Ajax
- Portugal for Sporting, Porto, and Benfica
- France for Eagle Football Group / Lyon

If `crawl4ai` is installed and you add `crawl4ai` to `--methods`, the v2
ingestion path will also try to enrich thin article bodies from article URLs
after the initial provider/RSS/Fundus collection.

If `scrapling` is installed, you can use the Scrapling-enhanced no-API preset:

```bash
pip install -e ".[scrapling_scrape]"

PYTHONPATH=src .venv/bin/python -m transfer_stock.cli refresh-live-fetch \
  --source-preset scrapling_wide_no_api \
  --max-records 20 \
  --pause 0.1 \
  --resume
```

This keeps discovery cheap through RSS, decodes Google News wrapper links into
real publisher URLs, then uses Scrapling's browser-like HTTP fetcher to enrich
thin article bodies. It is usually a better first fallback than opening full
browser/AI crawlers for every article.

In the latest local benchmark, this turned 13 Google News RSS rows from
headline-only entries into 13 decoded publisher URLs with article bodies. See
`data/reports/scrapling_benchmark.md` after running the benchmark or a live
refresh.

Serve the same dashboard payload through a small FastAPI layer:

```bash
PYTHONPATH=src .venv/bin/python -m transfer_stock.cli serve-api \
  --payload app/static/data/dashboard_data.json \
  --host 127.0.0.1 \
  --port 8010
```

Useful endpoints:

- `GET /health`
- `GET /meta`
- `GET /signals/current?season=2025-26&club=Manchester%20United`
- `GET /signals/watchlist`
- `GET /clubs/Manchester%20United/dossier`
- `GET /reporters/Fabrizio%20Romano`
- `GET /compare?club_a=Manchester%20United&club_b=Juventus`
- `POST /ask` with JSON body `{"question":"Compare Manchester United and Juventus"}`
- `GET /transfers/history?season=2025-26`
- `GET /leaderboards/journalists`

The agent-oriented command and schema contract is documented in
[`docs/mcp_tools.md`](docs/mcp_tools.md).

Example analyst API call:

```bash
curl -X POST http://127.0.0.1:8010/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the current signal for Casemiro?"}'
```

## GitHub Demo

Yes, it is worth publishing a click-through demo page. This repo now includes:

- `.github/workflows/deploy-pages.yml` to deploy `app/static` to GitHub Pages
- `.github/workflows/nightly-refresh.yml` to refresh the live dashboard data on
  a nightly schedule and redeploy the Pages site

If your first deploy fails with a `Get Pages site failed` or `Not Found` error,
the usual fix is:

1. Open the repository on GitHub.
2. Go to `Settings -> Pages`.
3. Under `Build and deployment`, set `Source` to `GitHub Actions`.
4. Re-run the `Deploy Demo Page` workflow.

Before enabling the nightly refresh workflow, add these repository secrets:

- `GUARDIAN_API_KEY`
- `GNEWS_API_KEY`

Optional:

- `PAGES_PAT`

If you add `PAGES_PAT`, the workflow can try to auto-enable Pages for the repo.
Without it, manual enablement in the GitHub Pages settings is the simplest path.

Then enable GitHub Pages in the repository settings and point it at the
GitHub Actions deployment.

## Publish To GitHub

From the project root:

```bash
git init
git add .
git commit -m "Initial transfer-stock dashboard"
git branch -M main
git remote add origin https://github.com/<your-github-username>/transfer_scrape.git
git push -u origin main
```

Then in GitHub:

1. Open the repository.
2. Go to `Settings -> Pages`.
3. Under `Build and deployment`, choose `GitHub Actions`.
4. Go to `Settings -> Secrets and variables -> Actions`.
5. Add these repository secrets if you want API-backed refreshes:
   - `GUARDIAN_API_KEY`
   - `GNEWS_API_KEY`
6. Push again or manually run the `Deploy Demo Page` workflow.

Your Pages URL should become:

- `https://<your-github-username>.github.io/transfer_scrape/`

Once it is live, replace the placeholder URL near the top of this README with
your actual page URL.

Fetch historical news around known transfer events:

```bash
python3 -m transfer_stock.cli fetch-event-news --days-before 30 --days-after 3 --max-records 10 --pause 2
```

Score that historical event news and join it into a model table:

```bash
python3 -m transfer_stock.cli score-news --input data/raw/news/event_news.jsonl --output data/processed/scored_event_news.csv
python3 -m transfer_stock.cli build-model-dataset
```

Build event-study labels after you have transfer and stock data:

```bash
python3 -m transfer_stock.cli build-events --transfers data/processed/transfers_clean.csv --output data/processed/transfer_events.csv
python3 -m transfer_stock.cli build-events --transfers data/processed/transfers_clean_no_loans.csv --output data/processed/transfer_events_no_loans.csv --loan-policy exclude
```

Score current rumors:

```bash
python3 -m transfer_stock.cli score-news
```

## Transfer CSV Schema

Put historical transfers in `data/raw/transfers.csv` with these columns:

```csv
date,club,player,direction,from_club,to_club,age,position,market_value_eur,transfer_fee_eur,wage_eur_annual,transfer_type,is_loan,source,source_url
```

`direction` should be `in` or `out` from the listed club's perspective.
`transfer_type` can be `permanent`, `loan`, `loan_with_option`, or a similar
source label.

## Modeling Plan

The first label should be continuous:

- `car_m1_p1`: cumulative abnormal return from one trading day before to one
  day after the event.
- `car_0_p3`: cumulative abnormal return from event day to three trading days
  after.

Then derive classes only for interpretability:

- `negative`: CAR <= -2%
- `neutral`: -2% < CAR < 2%
- `positive`: CAR >= 2%

This keeps regression and classification both possible.

## Why Rumors Matter

A confirmed transfer date is often not the first market-moving date. A credible
report from a high-reputation journalist may move expectations before the club
announcement. The pipeline therefore stores both:

- confirmed transfer events
- rumor/news events with source credibility and transfer-quality features

## Current Limitations

- The transfer importer expects CSV data. It does not aggressively scrape
  Transfermarkt HTML.
- The exact-date transfer importer now strips future-dated rows and tags likely
  loan / loan-return pairs, but Transfermarkt-style loan semantics are still
  inferred heuristically from the raw dataset.
- The v2 ingestion architecture supports provider APIs, RSS, and Fundus-backed
  publisher crawling. Crawl4AI body enrichment is optional if installed.
- `scrapy-playwright` is still the next heavier crawler path for JS-heavy
  sources; it is installed via `.[scrape_v2]` but not yet the default fetch
  method in the live-refresh command.
- The Stage 2 claim extractor supports a real structured claim schema and a
  DSPy-ready backend, but the default runtime path is still a heuristic
  extractor until you configure an LM backend.
- The Stage 3 matcher favors lower false positives over maximum recall. Claims
  can be left unmatched or marked ambiguous instead of being forced onto the
  nearest transfer candidate.
- The starter model is a transparent heuristic because the repo has no large
  historical labeled dataset yet.
- Stock event studies need enough trading days before each event to estimate a
  baseline.
- News matching is keyword-based in the MVP. Entity resolution is the next big
  improvement.
