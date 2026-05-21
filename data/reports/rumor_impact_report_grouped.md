# Transfer Stock Impact Report

Source model table: `data/processed/rumor_events_grouped.csv`

- Total transfer rows: 134
- Rows with observed CAR labels: 134
- Observed labels: 40 positive, 55 neutral, 39 negative
- Date warning: some transfer rows may still use source/proxy dates rather than first market-moving rumor dates.
- ML status: this report uses event-study labels plus a transparent heuristic, not a trained ML model.

## Top Rows By Observed/Predicted Impact

| Rank | Date | Club | Player | Type | Rumors | Observed CAR | Observed | Heuristic CAR | Heuristic | Note |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| 1 | 2025-06-08 | Manchester United | Matheus Cunha | permanent | 1 | 0.219926 | positive | 0.0196 | neutral | exact or source-provided date |
| 2 | 2023-08-05 | Manchester United | Rasmus Højlund | permanent | 1 | 0.16173 | positive | 0.01 | neutral | exact or source-provided date |
| 3 | 2022-01-25 | Juventus | Dušan Vlahović | permanent | 1 | 0.107563 | positive | 0.0339 | positive | exact or source-provided date |
| 4 | 2025-06-23 | Manchester United | Bryan Mbeumo | permanent | 1 | 0.104338 | positive | 0.0194 | neutral | exact or source-provided date |
| 5 | 2024-08-28 | Juventus | Teun Koopmeiners | permanent | 3 | 0.103188 | positive | 0.0205 | positive | exact or source-provided date |
| 6 | 2023-06-28 | Manchester United | Mason Mount | permanent | 1 | 0.096448 | neutral | 0.0241 | positive | exact or source-provided date |
| 7 | 2022-06-17 | Juventus | Federico Chiesa | permanent | 1 | 0.093337 | positive | 0.03 | positive | exact or source-provided date |
| 8 | 2022-08-17 | Manchester United | Casemiro | permanent | 1 | 0.092357 | positive | 0.01 | neutral | exact or source-provided date |
| 9 | 2023-08-01 | Manchester United | Rasmus Højlund | permanent | 1 | -0.090789 | negative | 0.0094 | neutral | exact or source-provided date |
| 10 | 2023-07-20 | Manchester United | André Onana | permanent | 1 | -0.089424 | neutral | 0.0154 | neutral | exact or source-provided date |
| 11 | 2023-07-29 | Manchester United | Rasmus Højlund | permanent | 2 | -0.081609 | negative | 0.01 | neutral | exact or source-provided date |
| 12 | 2022-07-12 | Juventus | Bremer | permanent | 1 | -0.08073 | negative | 0.0285 | positive | exact or source-provided date |
| 13 | 2022-01-27 | Juventus | Dušan Vlahović | permanent | 1 | 0.07937 | neutral | 0.0234 | positive | exact or source-provided date |
| 14 | 2024-06-12 | Juventus | Douglas Luiz | permanent | 1 | 0.071525 | positive | 0.0264 | positive | exact or source-provided date |
| 15 | 2024-07-11 | Manchester United | Joshua Zirkzee | permanent | 1 | 0.061909 | positive | 0.0263 | positive | exact or source-provided date |
| 16 | 2024-08-15 | Manchester United | Matthijs de Ligt | permanent | 1 | 0.057544 | positive | 0.0285 | positive | exact or source-provided date |
| 17 | 2024-08-16 | Manchester United | Matthijs de Ligt | permanent | 1 | 0.056319 | positive | 0.039 | positive | exact or source-provided date |
| 18 | 2025-06-25 | Manchester United | Matheus Cunha | permanent | 1 | -0.054004 | negative | 0.0196 | neutral | exact or source-provided date |
| 19 | 2025-06-25 | Manchester United | Bryan Mbeumo | permanent | 1 | -0.054004 | negative | 0.0194 | neutral | exact or source-provided date |
| 20 | 2023-07-07 | Manchester United | André Onana | permanent | 1 | -0.051302 | negative | 0.0154 | neutral | exact or source-provided date |
| 21 | 2023-07-07 | Manchester United | Rasmus Højlund | permanent | 1 | -0.051302 | negative | 0.01 | neutral | exact or source-provided date |
| 22 | 2024-08-20 | Juventus | Teun Koopmeiners | permanent | 1 | -0.045792 | negative | 0.0205 | positive | exact or source-provided date |
| 23 | 2024-07-02 | Juventus | Douglas Luiz | permanent | 1 | 0.045199 | positive | 0.0369 | positive | exact or source-provided date |
| 24 | 2025-08-07 | Manchester United | Benjamin Sesko | permanent | 2 | -0.042431 | negative | 0.032 | positive | exact or source-provided date |
| 25 | 2022-08-30 | Manchester United | Antony | permanent | 1 | 0.04138 | positive | 0.0198 | neutral | exact or source-provided date |

## Rows Using Inferred News Dates

No rows currently use inferred news dates. Run `fetch-event-news`, `score-news`, and `infer-event-dates` to populate this section.
