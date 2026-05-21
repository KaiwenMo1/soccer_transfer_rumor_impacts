# Transfer Stock Impact Report

Source model table: `data/processed/rumor_events_exact_top.csv`

- Total transfer rows: 36
- Rows with observed CAR labels: 36
- Observed labels: 9 positive, 21 neutral, 6 negative
- Date warning: some transfer rows may still use source/proxy dates rather than first market-moving rumor dates.
- ML status: this report uses event-study labels plus a transparent heuristic, not a trained ML model.

## Top Rows By Observed/Predicted Impact

| Rank | Date | Club | Player | Type | Rumors | Observed CAR | Observed | Heuristic CAR | Heuristic | Note |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| 1 | 2023-08-01 | Manchester United | Rasmus Højlund | permanent | 1 | -0.090789 | negative | 0.0094 | neutral | exact or source-provided date |
| 2 | 2023-07-29 | Manchester United | Rasmus Højlund | permanent | 1 | -0.081609 | negative | -0.0011 | neutral | exact or source-provided date |
| 3 | 2025-08-07 | Manchester United | Benjamin Sesko | permanent | 1 | -0.042431 | negative | 0.0251 | positive | exact or source-provided date |
| 4 | 2024-06-14 | Juventus | Douglas Luiz | permanent | 1 | 0.04007 | positive | 0.0299 | positive | exact or source-provided date |
| 5 | 2022-07-15 | Manchester United | Lisandro Martínez | permanent | 1 | 0.034835 | positive | 0.004 | neutral | exact or source-provided date |
| 6 | 2024-06-30 | Juventus | Douglas Luiz | permanent | 1 | 0.031302 | positive | 0.0153 | neutral | exact or source-provided date |
| 7 | 2024-06-22 | Juventus | Douglas Luiz | permanent | 1 | 0.028573 | positive | 0.0153 | neutral | exact or source-provided date |
| 8 | 2024-07-18 | Manchester United | Leny Yoro | permanent | 1 | -0.027537 | negative | 0.013 | neutral | exact or source-provided date |
| 9 | 2024-07-18 | Manchester United | Leny Yoro | permanent | 1 | -0.027537 | negative | 0.0025 | neutral | exact or source-provided date |
| 10 | 2022-07-05 | Juventus | Matthijs de Ligt | permanent | 1 | 0.024903 | positive | 0.0045 | neutral | exact or source-provided date |
| 11 | 2025-06-11 | Borussia Dortmund | Jamie Gittens | permanent | 1 | -0.023022 | negative | 0.0059 | neutral | exact or source-provided date |
| 12 | 2023-06-14 | Borussia Dortmund | Jude Bellingham | permanent | 1 | 0.021127 | positive | 0.0054 | neutral | exact or source-provided date |
| 13 | 2025-06-01 | Manchester United | Matheus Cunha | permanent | 1 | 0.020295 | positive | 0.0086 | neutral | exact or source-provided date |
| 14 | 2025-06-01 | Manchester United | Matheus Cunha | permanent | 1 | 0.020295 | positive | 0.0086 | neutral | exact or source-provided date |
| 15 | 2025-06-01 | Manchester United | Matheus Cunha | permanent | 1 | 0.020295 | positive | 0.0086 | neutral | exact or source-provided date |
| 16 | 2022-07-18 | Juventus | Matthijs de Ligt | permanent | 1 | 0.019731 | neutral | 0.0045 | neutral | exact or source-provided date |
| 17 | 2022-07-17 | Manchester United | Lisandro Martínez | permanent | 1 | 0.015876 | neutral | 0.0145 | neutral | exact or source-provided date |
| 18 | 2022-07-17 | Manchester United | Lisandro Martínez | permanent | 1 | 0.015876 | neutral | 0.004 | neutral | exact or source-provided date |
| 19 | 2023-06-07 | Borussia Dortmund | Jude Bellingham | permanent | 1 | 0.014634 | neutral | 0.0054 | neutral | exact or source-provided date |
| 20 | 2022-07-19 | Juventus | Bremer | permanent | 1 | 0.011952 | neutral | 0.007 | neutral | exact or source-provided date |
| 21 | 2022-07-19 | Juventus | Bremer | permanent | 1 | 0.011952 | neutral | 0.007 | neutral | exact or source-provided date |
| 22 | 2025-07-20 | Manchester United | Benjamin Sesko | permanent | 1 | 0.011669 | neutral | 0.0251 | positive | exact or source-provided date |
| 23 | 2025-07-19 | Manchester United | Benjamin Sesko | permanent | 1 | 0.011669 | neutral | 0.0105 | neutral | exact or source-provided date |
| 24 | 2025-07-03 | Borussia Dortmund | Jamie Gittens | permanent | 1 | -0.00926 | neutral | 0.0059 | neutral | exact or source-provided date |
| 25 | 2021-07-01 | Manchester United | Jadon Sancho | permanent | 1 | 0.007938 | neutral | 0.0123 | neutral | proxy window date; not exact announcement date |

## Rows Using Inferred News Dates

No rows currently use inferred news dates. Run `fetch-event-news`, `score-news`, and `infer-event-dates` to populate this section.
