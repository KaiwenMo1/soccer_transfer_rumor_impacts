# Match Results Overlay

Optional per-club match result files can be placed here to mark match outcomes on
the club stock path in the dashboard.

Use one CSV per configured club key:

```text
data/raw/matches/manchester_united.csv
data/raw/matches/juventus.csv
data/raw/matches/ajax.csv
```

Expected columns:

```csv
date,club,opponent,competition,venue,result,goals_for,goals_against,score,source,source_url
2026-05-17,Manchester United,Chelsea,E0,A,W,2,1,2-1,football-data.co.uk,https://example.com/match-report
```

Notes:

- `date` should be the match date.
- `club` and `source` are useful for generated files but the dashboard can also
  read manually created files without them.
- `result` can be `W`, `D`, or `L`.
- If `result` is blank, the dashboard infers it from `goals_for` and
  `goals_against`.
- Weekend match dates are mapped to the next available trading date on the stock
  path.

Fetch/update the generated files with:

```bash
PYTHONPATH=src python3 -m transfer_stock.cli fetch-match-results --seasons 2025-26 --resume
```
