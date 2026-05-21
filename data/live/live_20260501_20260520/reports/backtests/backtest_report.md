# Backtest Report

Trade convention:
- Signal observed on rumor/event date.
- Entry occurs on the next available trading day close.
- Position holds for 3 trading days.
- Portfolio daily return is the equal-weight average of active trade returns across clubs.

## Strategy Summary

| Strategy | Trades | Win Rate | Avg Trade | Avg Abnormal | Total Return | Sharpe | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| model_short_negative | 1 | 1.0 | 0.015385 | 0.03791 | 0.015193 | 7.385419 | -0.004778 |
| model_long_short_strong_stage | 1 | 1.0 | 0.015385 | 0.03791 | 0.015193 | 7.385419 | -0.004778 |
| heuristic_long_short | 12 | 0.3333 | -0.001182 | -0.005279 | 0.005817 | 0.366554 | -0.058497 |
| journalist_long_short | 12 | 0.3333 | -0.001182 | -0.005279 | 0.005817 | 0.366554 | -0.058497 |
| model_long_short | 3 | 0.3333 | -0.013191 | -0.01204 | -0.039914 | -6.770664 | -0.058801 |
| model_long_positive | 2 | 0.0 | -0.02748 | -0.037015 | -0.054283 | -17.580471 | -0.051015 |
| blended_long_short | 27 | 0.1852 | -0.011293 | -0.016496 | -0.184323 | -4.319171 | -0.196508 |

## Biggest Trades

| Strategy | Club | Player | Side | Entry | Exit | Return | Abnormal | Reason |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| blended_long_short | Lazio | Edoardo Motta | long | 2026-01-16 | 2026-01-20 | -0.050209 | -0.05417 | blended_positive |
| heuristic_long_short | Manchester United | Alejandro Garnacho | short | 2025-08-28 | 2025-09-02 | 0.045641 | 0.03813 | heuristic_outgoing |
| journalist_long_short | Manchester United | Alejandro Garnacho | short | 2025-08-28 | 2025-09-02 | 0.045641 | 0.03813 | journalist_outgoing |
| blended_long_short | Lazio | Edoardo Motta | long | 2026-01-23 | 2026-01-27 | -0.036364 | -0.045764 | blended_positive |
| model_long_positive | Lazio | Edoardo Motta | long | 2026-01-23 | 2026-01-27 | -0.036364 | -0.045764 | model_positive |
| model_long_short | Lazio | Edoardo Motta | long | 2026-01-23 | 2026-01-27 | -0.036364 | -0.045764 | model_positive |
| blended_long_short | Juventus | Edon Zhegrova | long | 2025-08-26 | 2025-08-28 | -0.028815 | -0.017014 | blended_positive |
| blended_long_short | Juventus | Edon Zhegrova | long | 2025-08-25 | 2025-08-27 | -0.028664 | -0.015047 | blended_positive |
| blended_long_short | Lazio | Marcos Antônio | long | 2026-02-05 | 2026-02-09 | 0.028302 | 0.022874 | blended_positive |
| blended_long_short | Manchester United | Bryan Mbeumo | long | 2025-07-21 | 2025-07-23 | 0.028297 | 0.018346 | blended_positive |
