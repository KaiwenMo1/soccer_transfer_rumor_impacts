# Architecture

## Purpose

Transfer Stock Analyst is a research system for connecting football transfer
information, source credibility, and publicly listed club market context. It is
not an automated trading system.

The architecture favors inspectable intermediate files and deterministic
fallbacks. Each stage can be run independently, audited, and rebuilt without
requiring an LLM or live API key.

## Component Map

| Boundary | Main modules | Responsibility |
| --- | --- | --- |
| Configuration | `config.py`, `config/*.yml` | Public clubs, aliases, tickers, sources, credibility priors |
| Ingestion | `ingestion_v2.py`, `provider_news.py`, `news_sources.py`, adapters | Discover, fetch, normalize, and deduplicate articles |
| Transfer data | `transfers.py`, `ewenme.py`, `dcaribou.py` | Normalize confirmed transfers, dates, directions, and loan types |
| Claims | `claims.py` | Convert article text into structured transfer claims |
| Entity resolution | `matching.py`, `targets.py` | Match claims to transfers and map buyer/seller exposure to listed clubs |
| Credibility | `credibility_engine.py` | Score sources, journalists, stages, and historical conversion rates |
| Market research | `stock.py`, `market_features.py`, `event_study.py` | Build pre-event context and post-event evaluation windows |
| Modeling | `ml_v2.py`, `backtesting.py` | Train time-aware models and evaluate signal strategies |
| Research intelligence | `analyst.py`, `evidence_rag.py`, `agent.py`, `scenario_swarm.py` | Answer grounded questions and produce inspectable research traces |
| Product orchestration | `operator.py`, `autopilot.py`, `runbooks.py`, `cli.py` | Run bounded workflows and publish outputs |
| Interfaces | `api.py`, `demo.py`, `app/static/` | Build the dashboard payload and expose CLI/API/browser interfaces |

## Data Flow

```text
External sources
  -> normalized article rows
  -> structured claims
  -> matched claims + ambiguity
  -> credibility features
  -> public buyer/seller target rows
  -> pre-event market features
  -> temporal model predictions
  -> post-event evaluation/backtests
  -> dashboard payload, analyst answers, and reports
```

## Important Data Contracts

### Normalized Article

Canonical fields include article ID, source, journalist, title, URL,
publication time, body text, candidate clubs/players, crawl method, and
extraction confidence.

Default location:

```text
data/raw/articles/
```

### Structured Claim

A claim records the primary player and club, direction, rumor stage, fee,
wage, transfer type, journalist, transfer relevance, and extraction
confidence.

Default location:

```text
data/processed/claims/
```

### Matched Claim

Entity resolution adds a stable transfer candidate ID, match score, match
reason, and ambiguity flag. The matcher prefers leaving uncertain claims
unmatched over forcing a false positive.

Default location:

```text
data/processed/matched_claims/
```

### Public Target Row

One rumor may expand into a listed buyer row, a listed seller row, both, or an
intelligence-only row. Stock-impact predictions are only valid for rows with a
direct listed-club target.

### Dashboard Payload

`app/static/data/dashboard_data.json` is the stable browser-facing contract. It
contains signals, transfers, club dossiers, stock paths, match markers,
leaderboards, backtests, and model summaries.

## Leakage Boundary

The project deliberately separates:

- **live/model inputs:** credibility, transfer context, match confidence,
  rumor stage, and pre-event market features
- **evaluation labels:** post-rumor raw/abnormal returns, volatility shifts,
  and realized impact classes

Temporal splits are required. Current-season rows should remain live/test-like
unless explicitly promoted into historical training data.

## Agent Boundary

The analyst and agent layers retrieve from local evidence and return citations,
warnings, confidence, and source paths. They do not execute trades.

The bounded operator follows this pattern:

```text
check freshness -> optionally refresh -> audit -> retrieve -> analyze -> publish
```

Scenario Swarm agents receive the same evidence bundle and run a fixed number
of rounds. Their output is a research scenario report, not a recommendation.

## Runtime Surfaces

### Static Dashboard

The browser reads committed JSON snapshots under `app/static/data/`. GitHub
Pages can host it without a backend.

### CLI

`python -m transfer_stock.cli` exposes ingestion, pipeline, research, and
inspection commands. The CLI is the primary reproducible automation surface.

### FastAPI Workbench

The local API exposes read endpoints plus optional research-operator endpoints.
It defaults to `127.0.0.1`; mutation endpoints should not be exposed publicly
without adding authentication and rate limits.

## Testing Strategy

`tests/test_core.py` currently exercises deterministic behavior across
ingestion normalization, matching, credibility, market features, modeling
guardrails, RAG, agents, scenarios, API helper responses, and dashboard payload
construction.

CI adds four repository-level checks:

1. Python unit tests
2. Python CLI compilation
3. dashboard JavaScript syntax
4. committed dashboard payload inspection

Future test decomposition should split the single core suite by subsystem and
add FastAPI integration and browser smoke tests.

## Extension Points

- Add a listed club in `config/clubs.yml`.
- Add source presets in `config/news_sources.yml`.
- Implement a new ingestion adapter behind the normalized article contract.
- Add extraction backends without changing downstream claim fields.
- Add models while preserving temporal evaluation and the public-target rule.
- Add dashboard views by extending the dashboard payload contract rather than
  coupling the browser directly to pipeline files.

