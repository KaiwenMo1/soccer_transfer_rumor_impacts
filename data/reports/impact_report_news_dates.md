# Transfer Stock Impact Report

Source model table: `data/processed/model_dataset_news_dates.csv`

- Total transfer rows: 270
- Rows with observed CAR labels: 261
- Observed labels: 40 positive, 191 neutral, 30 negative
- Date warning: imported ewenme rows mostly use July 1 / January 1 proxy dates, not exact announcement dates.
- ML status: this report uses event-study labels plus a transparent heuristic, not a trained ML model.

## Top Rows By Observed/Predicted Impact

| Rank | Date | Club | Player | Type | Rumors | Observed CAR | Observed | Heuristic CAR | Heuristic | Note |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |
| 1 | 2023-01-01 | Juventus FC | Samuel Iling Junior | permanent | 0 | 0.11521 | positive | 0.009 | neutral | proxy window date; not exact announcement date |
| 2 | 2023-01-01 | Juventus FC | Luca Pellegrini | loan | 0 | 0.11521 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 3 | 2023-01-01 | Juventus FC | Marley Aké | loan | 0 | 0.11521 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 4 | 2023-01-01 | Juventus FC | Weston McKennie | loan | 0 | 0.11521 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 5 | 2022-01-01 | Juventus FC | Denis Zakaria | permanent | 0 | 0.101436 | positive | 0.015 | neutral | proxy window date; not exact announcement date |
| 6 | 2022-01-01 | Juventus FC | Federico Gatti | permanent | 0 | 0.101436 | positive | 0.015 | neutral | proxy window date; not exact announcement date |
| 7 | 2022-01-01 | Juventus FC | Dušan Vlahović | permanent | 0 | 0.101436 | positive | 0.0135 | neutral | proxy window date; not exact announcement date |
| 8 | 2022-01-01 | Juventus FC | Marley Aké | permanent | 0 | 0.101436 | positive | 0.012 | neutral | proxy window date; not exact announcement date |
| 9 | 2022-01-01 | Juventus FC | Aaron Ramsey | loan | 0 | 0.101436 | positive | 0.0105 | neutral | proxy window date; not exact announcement date |
| 10 | 2022-01-01 | Juventus FC | Dejan Kulusevski | loan | 0 | 0.101436 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 11 | 2022-01-01 | Juventus FC | Federico Gatti | loan | 0 | 0.101436 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 12 | 2022-01-01 | Juventus FC | Mohamed Ihattaren | loan | 0 | 0.101436 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 13 | 2022-01-01 | Juventus FC | Radu Dragusin | loan | 0 | 0.101436 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 14 | 2022-01-01 | Juventus FC | Rodrigo Bentancur | permanent | 0 | 0.101436 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 15 | 2022-01-01 | Manchester United | Amad Diallo | loan | 0 | 0.029213 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 16 | 2022-01-01 | Manchester United | Anthony Martial | loan | 0 | 0.029213 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 17 | 2022-01-01 | Manchester United | Axel Tuanzebe | loan | 0 | 0.029213 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 18 | 2022-01-01 | Manchester United | Donny van de Beek | loan | 0 | 0.029213 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 19 | 2022-01-01 | Manchester United | Teden Mengi | loan | 0 | 0.029213 | positive | 0.0066 | neutral | proxy window date; not exact announcement date |
| 20 | 2022-07-01 | Borussia Dortmund | Salih Özcan | permanent | 0 | 0.029094 | positive | 0.0165 | neutral | proxy window date; not exact announcement date |
| 21 | 2022-07-01 | Borussia Dortmund | Nico Schlotterbeck | permanent | 0 | 0.029094 | positive | 0.0135 | neutral | proxy window date; not exact announcement date |
| 22 | 2022-07-01 | Borussia Dortmund | Niklas Süle | permanent | 0 | 0.029094 | positive | 0.0135 | neutral | proxy window date; not exact announcement date |
| 23 | 2022-07-01 | Borussia Dortmund | Marcel Lotka | permanent | 0 | 0.029094 | positive | 0.012 | neutral | proxy window date; not exact announcement date |
| 24 | 2022-07-01 | Borussia Dortmund | Axel Witsel | permanent | 0 | 0.029094 | positive | 0.0107 | neutral | proxy window date; not exact announcement date |
| 25 | 2022-07-01 | Borussia Dortmund | Marcel Schmelzer | permanent | 0 | 0.029094 | positive | 0.0107 | neutral | proxy window date; not exact announcement date |

## Rows Using Inferred News Dates

| Date | Original Transfer Date | Club | Player | Rumors | Observed CAR | Observed | Heuristic | Note |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| 2021-08-27 | 2021-08-27 | Manchester United | Cristiano Ronaldo | 2 | 0.013844 | neutral | neutral | earliest credible news/article date |
| 2021-06-26 | 2021-07-01 | Manchester United | Sergio Romero | 2 | -0.012027 | neutral | neutral | earliest credible news/article date |
| 2021-06-27 | 2021-07-01 | Borussia Dortmund | Donyell Malen | 2 | -0.01057 | neutral | neutral | earliest credible news/article date |
| 2021-06-26 | 2021-07-01 | Borussia Dortmund | Lukasz Piszczek | 2 | -0.01057 | neutral | neutral | earliest credible news/article date |
| 2021-07-01 | 2021-07-01 | Manchester United | Jadon Sancho | 2 | 0.007938 | neutral | positive | earliest credible news/article date |
| 2021-06-01 | 2021-07-01 | Borussia Dortmund | Gregor Kobel | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-06 | 2021-07-01 | Borussia Dortmund | Leonardo Balerdi | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-06 | 2021-07-01 | Borussia Dortmund | Ansgar Knauff | 1 |  |  | neutral | earliest credible news/article date |
| 2021-06-15 | 2021-07-01 | Borussia Dortmund | Immanuel Pherai | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-04 | 2021-07-01 | Manchester United | Joel Pereira | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-09 | 2021-07-01 | Manchester United | Anthony Elanga | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-14 | 2021-07-01 | Borussia Dortmund | Thomas Delaney | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-15 | 2021-07-01 | Borussia Dortmund | Immanuel Pherai | 2 |  |  | neutral | earliest credible news/article date |
| 2021-06-06 | 2021-07-01 | Borussia Dortmund | Leonardo Balerdi | 2 |  |  | neutral | earliest credible news/article date |
