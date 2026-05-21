# Transfer Scrape Upgrade Guide

This guide turns the current project into a stronger system:

- better scraping
- real AI-assisted extraction
- cleaner rumor-to-transfer matching
- better credibility scoring
- stronger market research
- more serious ML and backtesting

The idea is simple: do **not** start by throwing more ML at weak data. First upgrade ingestion and structure, then train better models on top.

## How To Use This Guide

For each stage:

1. Read the goal and checklist.
2. Copy the prompt into your AI coding tool.
3. Let it inspect the repo first.
4. Make the upgrade incrementally.
5. Verify the outputs before moving to the next stage.

Use the stages in order. They are designed to reduce rework.

## Global Setup Prompt

Before every stage, give the AI this setup prompt first:

```text
You are upgrading an existing Python project called `transfer_scrape`.

Rules:
- Keep the project in Python.
- Preserve working CLI behavior unless a replacement is clearly better.
- Do not do a full rewrite. Refactor incrementally.
- Reuse existing data folders when possible.
- Add tests for new logic.
- Prefer clean modules over giant scripts.
- When scraping, use reliable sources and a structured article schema.
- When modeling, use time-aware splits and avoid leakage.
- Explain assumptions and list risks before coding.
- After coding, summarize exactly what changed, what commands to run, and where outputs are written.
```

## Recommended Upgrade Stack

Use these tools as the backbone of the next version:

- `Fundus`: bulk publisher/news extraction
- `Scrapy` + `scrapy-playwright`: scalable crawling and scheduling
- `Crawl4AI`: fallback for hard pages and structured extraction
- `DSPy`: structured AI extraction and prompt optimization
- `FinGPT`: finance/news understanding tasks and ideas
- `vectorbt`: event study, signal testing, and backtesting
- `Qlib`: later-stage quant research workflow if the project grows

## Roadmap Overview

| Stage | Focus | Main Output |
| --- | --- | --- |
| 1 | News ingestion rebuild | reliable, scalable article collection |
| 2 | AI claim extraction | structured rumor/transfer claims |
| 3 | Entity resolution | article claims matched to the correct transfer |
| 4 | Credibility engine | source and journalist quality scores |
| 5 | Market analysis upgrade | richer stock/event-study features |
| 6 | ML upgrade | better time-aware predictive models |
| 7 | Backtesting | real signal evaluation |
| 8 | Demo/dashboard | polished analysis interface |

## Stage 1: Rebuild The Scraping Layer

### Goal

Replace the thin, event-by-event news collection with a proper ingestion pipeline.

### Why This Matters

Right now the project is constrained by weak news coverage and noisy article matching. If the article layer is weak, everything downstream stays weak.

### Target Architecture

- `Fundus` for direct publisher extraction where possible
- `Scrapy` + `scrapy-playwright` for scalable crawling
- `Crawl4AI` as fallback on messy pages
- unified article schema
- dedupe by URL, title, and published time
- raw article store under `data/raw/articles/`

### Checklist

- add a new article-ingestion module
- create a single article schema
- support multiple crawl methods
- add caching and dedupe
- keep existing CLI working
- add a new v2 CLI path

### Prompt

```text
Upgrade the current news ingestion layer of my Python repo.

Task:
1. Inspect the existing scraping/news pipeline.
2. Design a new ingestion architecture using:
   - Fundus for publisher extraction
   - Scrapy + scrapy-playwright for scalable crawling
   - Crawl4AI only as fallback for difficult pages
3. Keep the project in Python and integrate with the current CLI style.
4. Create a unified article schema with fields like:
   article_id, source, journalist, title, url, published_at, body_text, snippet, club_candidates, player_candidates, language, crawl_method, extraction_confidence
5. Add deduplication and caching.
6. Write outputs to a new raw article dataset under data/raw/articles/.
7. Do not break the current pipeline; add this as a v2 path.
8. Add tests for schema normalization and dedupe behavior.

First give me:
- the proposed module structure
- the exact files you will add/change
- the CLI commands you will introduce
Then implement it.
```

### Done When

- the project can ingest hundreds of articles efficiently
- raw article rows are normalized
- duplicates are removed consistently

## Stage 2: Add AI Claim Extraction

### Goal

Turn raw articles into structured transfer claims.

### Why This Matters

This is where the project starts to feel like an AI system instead of a keyword pipeline.

### Extract These Fields

- primary player
- primary club
- transfer direction
- rumor stage
- fee if present
- wage if present
- loan/permanent/option
- journalist
- whether the article is actually transfer-related
- extraction confidence

### Checklist

- build a claim schema
- use structured outputs
- keep uncertain cases explicit
- store extracted claims under `data/processed/claims/`
- add sample-based tests

### Prompt

```text
Build an AI-based claim extraction layer on top of the new article ingestion pipeline.

Task:
1. Inspect the current article schema and repo structure.
2. Add a claim extraction module using DSPy-style structured outputs.
3. For each article, extract:
   - primary player
   - primary club
   - transfer direction
   - rumor stage (linked, talks, bid, advanced, agreed, medical, official, unclear)
   - transfer fee if present
   - wage if present
   - loan/permanent/option if present
   - journalist name
   - whether this is genuinely transfer-related
   - extraction confidence
4. Save outputs under data/processed/claims/.
5. Add validation rules and fallback behavior when extraction is uncertain.
6. Add tests using a few real sample articles.

First show me the structured output schema and extraction flow, then implement it.
```

### Done When

- raw text becomes structured rumor rows
- non-transfer junk is filtered out better
- the extracted output is inspectable and testable

## Stage 3: Build Entity Resolution And Transfer Matching

### Goal

Link extracted claims to the correct player, club, and transfer candidate.

### Why This Matters

This is the current weak spot in many rows. Good extraction without good matching still produces bad labels.

### Matching Signals

- exact and fuzzy player-name matching
- club alias matching
- season/window filtering
- direction consistency
- optional AI tie-breaker only for ambiguous cases

### Checklist

- create a transfer ID or stable candidate ID
- generate match score and match reason
- flag ambiguity instead of guessing
- store outputs under `data/processed/matched_claims/`

### Prompt

```text
Build an entity resolution layer for my transfer project.

Task:
1. Inspect the current transfer datasets and extracted claim outputs.
2. Create a matching system that links each claim to the most likely transfer candidate.
3. Use a hybrid approach:
   - exact and fuzzy name matching
   - club alias matching
   - season/window filtering
   - transfer direction consistency
   - optional AI-assisted disambiguation only when rules are ambiguous
4. Output:
   match_id, matched_transfer_id, match_score, match_reason, ambiguity_flag
5. Keep false positives low even if recall drops slightly.
6. Write outputs to data/processed/matched_claims/.
7. Add tests for common ambiguity cases.

First explain the matching strategy and error cases, then implement it.
```

### Done When

- one rumor usually maps to one plausible transfer
- false matches are reduced
- ambiguous cases are clearly surfaced

## Stage 4: Upgrade The Credibility Engine

### Goal

Replace simple keyword/source heuristics with a richer credibility framework.

### Why This Matters

The project becomes more interesting if it learns which journalists and source types are actually predictive.

### Credibility Features

- source reputation
- journalist reputation
- historical rumor conversion rate
- club-specific hit rate
- rumor stage reliability
- official vs aggregate vs live blog vs exclusive
- time-to-confirmation

### Checklist

- keep the score interpretable
- store subcomponents separately
- update source/journalist stats from history
- write outputs under `data/processed/credibility/`

### Prompt

```text
Upgrade the rumor credibility system in my project.

Task:
1. Inspect the current credibility config and scoring logic.
2. Replace the simple heuristic with a structured credibility engine.
3. Build features for:
   - source reputation
   - journalist reputation
   - historical rumor conversion rate
   - club-specific hit rate
   - rumor stage reliability
   - whether the article is exclusive, aggregate, live blog, or official
4. Create a credibility score and also store the subcomponents separately.
5. Add a pipeline that updates journalist/source stats from historical labeled outcomes.
6. Save outputs under data/processed/credibility/.
7. Keep the system transparent and debuggable.

First propose the scoring formula and storage format, then implement it.
```

### Done When

- credibility scores can be explained
- journalist/source performance is learned from data
- the project can rank rumors more meaningfully

## Stage 5: Upgrade The Market Analysis Layer

### Goal

Make the stock side feel like real research instead of a small event-window helper.

### Why This Matters

If the target is weak or too narrow, the model can only learn weak signals.

### Add These Features

- abnormal return windows `t+1`, `t+3`, `t+5`, `t+10`
- volatility shift
- rolling z-scores
- relative volume if available
- pre-rumor drift
- post-rumor drift
- market-adjusted and raw returns

### Checklist

- rebuild the market layer around `vectorbt`
- keep alignment to rumor-event rows
- add anti-leakage checks
- store outputs under `data/processed/market_features/`

### Prompt

```text
Upgrade the market analysis part of my transfer-stock project.

Task:
1. Inspect the current event-study and stock feature pipeline.
2. Rebuild the market analysis around vectorbt.
3. Add features for:
   - abnormal return windows t+1, t+3, t+5, t+10
   - volatility changes
   - rolling z-scores
   - relative volume if available
   - pre-rumor drift and post-rumor drift
   - market-adjusted and club-only returns
4. Keep the outputs aligned to the rumor-event rows.
5. Save processed market features under data/processed/market_features/.
6. Add tests for event window calculations and alignment.

First explain the event-study design and anti-leakage safeguards, then implement it.
```

### Done When

- rumor rows have richer market context
- event windows are reproducible
- the market side becomes research-grade

## Stage 6: Upgrade The ML Pipeline

### Goal

Move from simple heuristics and toy models to stronger time-aware tabular modeling.

### Important Note

Use AI to improve extraction and feature quality. For the final predictive layer, structured tabular models will usually be stronger and easier to evaluate than a vague LLM end-to-end predictor.

### Models To Add

- logistic baseline
- `LightGBM` or `XGBoost`
- optional regression alongside classification

### Checklist

- use temporal splits only
- compare against current baseline
- report feature importance
- report class balance and calibration
- store outputs under `data/models/`

### Prompt

```text
Upgrade the ML pipeline of my transfer-stock project.

Task:
1. Inspect the current features, labels, and train/test logic.
2. Replace the simple baseline model with a stronger time-aware tabular modeling pipeline.
3. Use interpretable structured features from:
   - transfer quality
   - rumor credibility
   - rumor stage
   - entity match confidence
   - market context
4. Train at least:
   - logistic baseline
   - LightGBM or XGBoost classifier/regressor
5. Use proper temporal splits only.
6. Report:
   accuracy, F1, class balance, calibration, feature importance
7. Save trained outputs and prediction tables under data/models/.
8. Do not use leakage from future news or future price windows.

First show me the modeling plan and evaluation protocol, then implement it.
```

### Done When

- the model is evaluated honestly
- feature importance is meaningful
- results improve over the current baseline

## Stage 7: Add Backtesting And Signal Evaluation

### Goal

Treat predictions as tradable signals and test whether they actually help.

### Why This Matters

Without backtesting, the project still stops at “interesting classifier,” which is not enough for market claims.

### Strategy Ideas

- trade only high-confidence positive rumors
- trade only high-confidence negative rumors
- trade only high-credibility journalist signals
- filter by club, rumor stage, or transfer direction

### Checklist

- implement backtests in `vectorbt`
- compare model vs heuristic signals
- report returns and risk
- store outputs under `data/reports/backtests/`

### Prompt

```text
Build a backtesting and signal evaluation layer for my transfer-stock project.

Task:
1. Inspect the current prediction outputs and market data.
2. Use vectorbt to test simple signal strategies based on predicted rumor impact.
3. Evaluate strategies such as:
   - trade only high-confidence positive rumors
   - trade only high-confidence negative rumors
   - trade only high-credibility journalists
   - filter by club and rumor stage
4. Report:
   win rate, average return, max drawdown, Sharpe-like metrics, turnover
5. Compare model-driven signals vs simple heuristics.
6. Save outputs under data/reports/backtests/.

First propose the backtest design and signal rules, then implement it.
```

### Done When

- signal usefulness is measured directly
- the project has a real research output beyond labels

## Stage 8: Build The Demo Layer

### Goal

Make the project easy to understand and demo.

### What To Show

- latest rumors
- extracted claims
- credibility breakdown
- transfer, rumor, and stock indicators
- predicted stock impact
- similar historical examples
- backtest summary

### Checklist

- use a clean data-dense UI
- avoid a marketing landing page
- make the working dashboard the first screen
- document data flow clearly

### Prompt

```text
Build a clean demo/report interface for my transfer-stock project.

Task:
1. Inspect the current outputs and any existing app/static structure if present.
2. Create a small web dashboard or report view that shows:
   - latest current rumors
   - extracted structured claim fields
   - journalist/source credibility
   - transfer indicator, rumor indicator, stock indicator
   - predicted impact label and confidence
   - past similar cases
   - backtest summary
3. Keep the UI simple, data-dense, and polished.
4. Do not build a marketing landing page; build the working analysis view first.
5. Show exactly where the dashboard reads its data from.

First propose the page structure and data flow, then implement it.
```

### Done When

- someone can open the project and understand it immediately
- the output looks like an AI market-intelligence tool

## Suggested Execution Order

Do the stages in this order:

1. Stage 1: scraping
2. Stage 2: extraction
3. Stage 3: matching
4. Stage 4: credibility
5. Stage 5: market features
6. Stage 6: ML
7. Stage 7: backtesting
8. Stage 8: dashboard

## Common Mistakes To Avoid

- doing a full rewrite before preserving working paths
- adding more ML before fixing ingestion and matching
- using future prices or future articles in training
- trusting broad keyword scraping without entity checks
- letting AI outputs overwrite uncertainty instead of storing confidence
- treating all sources as equally credible

## Fastest High-Impact Path

If time is limited, do these first:

1. Stage 1
2. Stage 2
3. Stage 4
4. Stage 5
5. Stage 6

That sequence gives the biggest upgrade in quality without waiting for a perfect end-state system.

## Final Advice

The project becomes impressive when it does this well:

`article -> structured transfer claim -> credibility -> market context -> prediction -> backtest`

That is the real spine of the upgraded system.
