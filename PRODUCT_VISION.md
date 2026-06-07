# Product Vision

## One-Sentence Purpose

Transfer Stock Analyst is a football-finance intelligence operator that turns
noisy transfer coverage into a daily, evidence-backed brief for publicly listed
clubs.

## The User Job

A user should be able to open the website and answer:

1. What changed since the last update?
2. Which rumors are credible enough to inspect?
3. Is a publicly listed club directly exposed as buyer or seller?
4. What does the model estimate, and how uncertain is it?
5. Could matches, ownership news, liquidity, earnings, or the broader market
   explain the same stock movement?
6. What should I verify next?

The user should not need to understand scraping, entity resolution, RAG,
event studies, or model commands to get those answers.

## Product Promise

**One click, one current research package:**

- refresh current evidence when permitted
- structure and cluster transfer claims
- rank rumor credibility
- map only direct listed-club exposure to stock context
- audit freshness and data quality
- run a grounded analyst agent
- publish a decision queue, evidence, uncertainty, and next-best action

The package is research context, not an automated trading recommendation.

## Main Audience

- football-finance researchers
- fans and investors following listed clubs
- sports-business journalists
- students studying event-driven markets, data engineering, RAG, and agents

## Core Product Surface

The default website should prioritize six outputs:

1. **Today in one read** - the strongest current item and why it matters.
2. **Research runbooks** - named workflows that turn internal commands into
   one-click or copy-paste actions.
3. **Decision queue** - monitor, verify, credibility-only, and background items.
4. **Evidence and trust** - source breadth, reporter history, citations, and
   freshness.
5. **Market context** - stock path, match markers, and alternative explanations.
6. **What changed** - differences from the previous research cycle.

Everything else is a drill-down view.

## One-Click Modes

### Hosted Website

GitHub Actions refreshes the data and publishes the latest research package.
Visitors only open the website.

### Local Workbench

The FastAPI workbench exposes a **Run today's cycle** button. It starts a
bounded background operator that may refresh news, then runs audit, RAG,
briefing, and analyst steps.

### CLI

```bash
PYTHONPATH=src python3 -m transfer_stock.cli research-cycle --mode research

PYTHONPATH=src python3 -m transfer_stock.cli research-cycle \
  --mode smart \
  --allow-network

PYTHONPATH=src python3 -m transfer_stock.cli list-runbooks
```

## GitHub-Inspired Product Pattern

The project should feel less like a command catalog and more like a small
research operating system:

- **OpenBB pattern:** expose financial research workflows with clear outputs.
- **Dify pattern:** present reusable workflows as cards that normal users can
  choose.
- **LangGraph pattern:** keep long-running work bounded, stateful, and
  inspectable.
- **FinRobot pattern:** use analyst-style agents for explanation and evidence,
  while keeping final claims grounded in structured data.

## Guardrails

- Never create a stock-impact prediction without a direct listed-club mapping.
- Never execute trades.
- Never hide stale data, thin source coverage, or low model confidence.
- Treat post-rumor returns as labels/evaluation, not live input features.
- Always show that football stocks have multiple possible drivers.
