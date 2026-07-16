# Data Quality Audit

Generated: `2026-07-16T08:33:18.375606+00:00`
Payload: `app/static/data/dashboard_data.json`

Overall: **watch** (51%)

## Dimensions

| Area | Score | Status | Summary |
| --- | ---: | --- | --- |
| Freshness | 12% | needs refresh | Latest signal date: 2026-06-02 |
| Source Coverage | 53% | watch | 10 live clusters, 12 sources, 0 journalists |
| Market Context | 65% | usable | 10 stock paths, latest stock date 2026-05-20, 353 match markers |
| Entity + Target Matching | 71% | usable | 73 direct public-target rows out of 92 total signals |
| Model Reliability | 42% | watch | Holdout n=68, accuracy=0.471, macro F1=0.306 |
| Date Hygiene | 100% | strong | No future-dated rows found |

## Warnings

- Latest signal is 44 days old; refresh live news before presenting this as current.
- Dashboard payload was generated 44 days ago.
- 8 live clusters have only one article/source; consensus is thin.
- 10 live clusters are missing journalist attribution.
- 10 club stock paths are older than 14 days.
- 21 direct signal rows have weak entity-match scores below 0.65.
- Positive class is sparse in holdout data; positive predictions need extra skepticism.
- Macro F1 is low, so the model is more useful for triage than final decisions.

## Recommended Commands

```bash
PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-fetch --source-preset wide_no_api --max-records 20 --resume
```
```bash
PYTHONPATH=src python3 -m transfer_stock.cli refresh-live-analyze --input data/raw/articles/current_live.jsonl --slug live_manual
```
```bash
PYTHONPATH=src python3 -m transfer_stock.cli audit-data-quality
```
