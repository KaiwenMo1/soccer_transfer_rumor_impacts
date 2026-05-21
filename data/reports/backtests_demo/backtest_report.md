# Backtest Report

Trade convention:
- Signal observed on rumor/event date.
- Entry occurs on the next available trading day close.
- Position holds for 3 trading days.
- Portfolio daily return is the equal-weight average of active trade returns across clubs.

## Strategy Summary

| Strategy | Trades | Win Rate | Avg Trade | Avg Abnormal | Total Return | Sharpe | Max DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic_long_short | 11 | 0.3636 | 0.001259 | -0.003317 | 0.012193 | 0.547313 | -0.058497 |
| journalist_long_short | 11 | 0.3636 | 0.001259 | -0.003317 | 0.012193 | 0.547313 | -0.058497 |
| model_short_negative | 2 | 0.5 | 0.001818 | 0.013768 | 0.003386 | 1.548325 | -0.008475 |
| model_long_short_strong_stage | 2 | 0.0 | -0.016909 | -0.031665 | -0.033534 | -8.053688 | -0.02765 |
| blended_long_short | 28 | 0.25 | -0.004307 | -0.008418 | -0.048519 | -0.752599 | -0.145141 |
| model_long_short | 6 | 0.1667 | -0.012663 | -0.015384 | -0.052509 | -3.857886 | -0.04908 |
| model_long_positive | 4 | 0.0 | -0.019904 | -0.02996 | -0.055707 | -5.317449 | -0.040952 |

## Biggest Trades

| Strategy | Club | Player | Side | Entry | Exit | Return | Abnormal | Reason |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| blended_long_short | Manchester United | Benjamin Sesko | long | 2026-04-28 | 2026-04-30 | 0.0964 | 0.091121 | blended_positive |
| heuristic_long_short | Manchester United | Alejandro Garnacho | short | 2025-08-28 | 2025-09-02 | 0.045641 | 0.03813 | heuristic_outgoing |
| journalist_long_short | Manchester United | Alejandro Garnacho | short | 2025-08-28 | 2025-09-02 | 0.045641 | 0.03813 | journalist_outgoing |
| blended_long_short | Lazio | Edoardo Motta | long | 2026-01-23 | 2026-01-27 | -0.036364 | -0.045764 | blended_positive |
| model_long_positive | Lazio | Edoardo Motta | long | 2026-01-23 | 2026-01-27 | -0.036364 | -0.045764 | model_positive |
| model_long_short | Lazio | Edoardo Motta | long | 2026-01-23 | 2026-01-27 | -0.036364 | -0.045764 | model_positive |
| blended_long_short | Juventus | Edon Zhegrova | long | 2025-08-26 | 2025-08-28 | -0.028815 | -0.017014 | blended_positive |
| blended_long_short | Juventus | Edon Zhegrova | long | 2025-08-25 | 2025-08-27 | -0.028664 | -0.015047 | blended_positive |
| blended_long_short | Lazio | Marcos Antônio | long | 2026-02-05 | 2026-02-09 | 0.028302 | 0.022874 | blended_positive |
| blended_long_short | Manchester United | Bryan Mbeumo | long | 2025-07-21 | 2025-07-23 | 0.028297 | 0.018346 | blended_positive |
