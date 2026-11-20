# V5 stalled-trade exit — 2026-11-20

New hypothesis: after three completed M15 candles, exit at candle close if maximum favorable excursion is below 0.25 of initial stop distance. Adverse-wick >=45% gate remains fixed. No real or demo orders.

Input: Eplanet merged 23,643 candles; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. 60/40 chronological split, 104 holdout trading days. Initial equity $1000; dynamic 0.01–0.1 lot; estimated roundtrip cost $87/lot; stop-first OHLC execution.

| Holdout | Wick baseline | Stall exit | Stall exit + daily guard |
|---|---:|---:|---:|
| Opportunities | 1526 | 1526 | 1526 |
| Excluded by wick | 350 | 350 | 350 |
| Trades | 159 | 165 | 163 |
| Gross USD | 228.86 | 276.95 | 241.12 |
| Costs USD | 138.33 | 143.55 | 141.81 |
| Net USD | 90.53 | 133.40 | 99.31 |
| Closed-equity drawdown USD | 64.73 | 54.11 | 68.75 |
| Days >= $50 net | 0/104 | 0/104 | 0/104 |

Train: wick baseline -$4.20; stall exit +$46.17; guard +$46.17. Stall exit is a candidate for independent risk-reduction investigation, not approved for MT5. Daily guard worsens holdout. No verified tick execution or broker spread; no claim of $50/day success.

**Reproducibility warning:** The previously committed `research/v5_adverse_wick_20261120.py` on branch `research/v5-adverse-wick-20261120` does not implement adverse wick: it filters true range >2*ATR instead. It therefore does not reproduce its purported wick report. This run used the local corrected wick implementation and independently reproduced baseline $90.53 on the real Eplanet file. Do not use the mismatched GitHub file as the baseline.

Executable research source for this run is currently provided as a conversation attachment `v5_stagnation_exit_20261120.py`; it has not yet been uploaded to this GitHub branch. The private dataset is not committed.
