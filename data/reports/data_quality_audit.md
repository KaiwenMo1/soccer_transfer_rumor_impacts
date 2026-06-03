# Data Quality Audit

Generated: `2026-06-02T13:56:47.667964+00:00`
Payload: `app/static/data/dashboard_data.json`

Overall: **usable** (79%)

## Dimensions

| Area | Score | Status | Summary |
| --- | ---: | --- | --- |
| Freshness | 100% | strong | Latest signal date: 2026-06-02 |
| Source Coverage | 53% | watch | 10 live clusters, 12 sources, 0 journalists |
| Market Context | 100% | strong | 10 stock paths, latest stock date 2026-05-20, 353 match markers |
| Entity + Target Matching | 71% | usable | 73 direct public-target rows out of 92 total signals |
| Model Reliability | 42% | watch | Holdout n=68, accuracy=0.471, macro F1=0.306 |
| Date Hygiene | 100% | strong | No future-dated rows found |

## Warnings

- 8 live clusters have only one article/source; consensus is thin.
- 10 live clusters are missing journalist attribution.
- 21 direct signal rows have weak entity-match scores below 0.65.
- Positive class is sparse in holdout data; positive predictions need extra skepticism.
- Macro F1 is low, so the model is more useful for triage than final decisions.

## Recommended Commands

```bash
PYTHONPATH=src python3 -m transfer_stock.cli audit-data-quality
```
