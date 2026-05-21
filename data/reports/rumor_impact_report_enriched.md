# Transfer Stock Impact Report

Source model table: `data/processed/rumor_events_enriched.csv`

- Total transfer rows: 64
- Rows with observed CAR labels: 64
- Observed labels: 18 positive, 37 neutral, 9 negative
- Date warning: some transfer rows may still use source/proxy dates rather than first market-moving rumor dates.
- ML status: this report uses event-study labels plus a transparent heuristic, not a trained ML model.

## Top Rows By Observed/Predicted Impact

| Rank | Date | Club | Player | Type | Rumors | Observed CAR | Observed | Heuristic CAR | Heuristic | Note |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| 1 | 2022-01-25 | Juventus | Dušan Vlahović | permanent | 1 | 0.107563 | positive | 0.0339 | positive | exact or source-provided date |
| 2 | 2023-08-01 | Manchester United | Rasmus Højlund | permanent | 1 | -0.090789 | negative | 0.0094 | neutral | exact or source-provided date |
| 3 | 2023-07-29 | Manchester United | Rasmus Højlund | permanent | 1 | -0.081609 | negative | -0.0011 | neutral | exact or source-provided date |
| 4 | 2022-01-27 | Juventus | Dušan Vlahović | permanent | 1 | 0.07937 | positive | 0.0234 | positive | exact or source-provided date |
| 5 | 2025-08-07 | Manchester United | Benjamin Sesko | permanent | 1 | -0.042431 | negative | 0.0251 | positive | exact or source-provided date |
| 6 | 2022-08-30 | Manchester United | Antony | permanent | 1 | 0.04138 | positive | 0.0198 | neutral | exact or source-provided date |
| 7 | 2024-06-14 | Juventus | Douglas Luiz | permanent | 1 | 0.04007 | positive | 0.0299 | positive | exact or source-provided date |
| 8 | 2023-06-08 | Borussia Dortmund | Jude Bellingham | permanent | 1 | 0.035965 | positive | 0.0164 | neutral | exact or source-provided date |
| 9 | 2022-07-15 | Manchester United | Lisandro Martínez | permanent | 1 | 0.034835 | positive | 0.004 | neutral | exact or source-provided date |
| 10 | 2021-06-23 | Borussia Dortmund | Jadon Sancho | permanent | 1 | -0.032513 | negative | 0.0182 | neutral | exact or source-provided date |
| 11 | 2024-06-30 | Juventus | Douglas Luiz | permanent | 1 | 0.031302 | positive | 0.0153 | neutral | exact or source-provided date |
| 12 | 2024-06-22 | Juventus | Douglas Luiz | permanent | 1 | 0.028573 | positive | 0.0153 | neutral | exact or source-provided date |
| 13 | 2022-01-30 | Juventus | Dušan Vlahović | permanent | 1 | -0.028485 | negative | 0.0234 | positive | exact or source-provided date |
| 14 | 2022-01-31 | Juventus | Dušan Vlahović | permanent | 1 | -0.028485 | negative | 0.0198 | neutral | exact or source-provided date |
| 15 | 2024-07-18 | Manchester United | Leny Yoro | permanent | 1 | -0.027537 | negative | 0.013 | neutral | exact or source-provided date |
| 16 | 2024-07-18 | Manchester United | Leny Yoro | permanent | 1 | -0.027537 | negative | 0.0025 | neutral | exact or source-provided date |
| 17 | 2022-09-01 | Manchester United | Antony | permanent | 1 | 0.025905 | positive | 0.0093 | neutral | exact or source-provided date |
| 18 | 2023-07-14 | Manchester United | André Onana | permanent | 1 | 0.025313 | positive | 0.019 | neutral | exact or source-provided date |
| 19 | 2023-07-14 | Manchester United | André Onana | permanent | 1 | 0.025313 | positive | 0.0044 | neutral | exact or source-provided date |
| 20 | 2022-07-05 | Juventus | Matthijs de Ligt | permanent | 1 | 0.024903 | positive | 0.0045 | neutral | exact or source-provided date |
| 21 | 2023-07-17 | Manchester United | André Onana | permanent | 1 | 0.024344 | positive | 0.019 | neutral | exact or source-provided date |
| 22 | 2025-06-11 | Borussia Dortmund | Jamie Gittens | permanent | 1 | -0.023022 | negative | 0.0059 | neutral | exact or source-provided date |
| 23 | 2023-06-14 | Borussia Dortmund | Jude Bellingham | permanent | 1 | 0.021127 | positive | 0.0164 | neutral | exact or source-provided date |
| 24 | 2023-06-14 | Borussia Dortmund | Jude Bellingham | permanent | 1 | 0.021127 | positive | 0.0054 | neutral | exact or source-provided date |
| 25 | 2025-06-01 | Manchester United | Matheus Cunha | permanent | 1 | 0.020295 | positive | 0.0086 | neutral | exact or source-provided date |

## Rows Using Inferred News Dates

No rows currently use inferred news dates. Run `fetch-event-news`, `score-news`, and `infer-event-dates` to populate this section.
