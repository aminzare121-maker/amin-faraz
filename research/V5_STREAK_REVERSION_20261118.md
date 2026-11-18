# V5 streak reversion — 2026-11-18

Hypothesis: reversal after 4 same-direction M15 closes, holding at most 2 bars; independent volatility/spread guard.
Dataset: private Eplanet M15, 23643 bars, chronological 60/40 split, 104 OOS days. Private bars NOT uploaded.
Model: 100oz/lot; spread points/100 + $0.30/oz slippage + $7/lot commission. Variable lot 0.01-0.05; 1% stop-risk sizing; OHLC stop-first assumption.
Selection on training only: maximize net minus 0.5 * closed drawdown over streak 2/3/4 and holding 2/4, without guard.

| OOS | Base | Independent guard |
|---|---:|---:|
| opportunities | 639 | 677 |
| trades | 95 | 0 |
| gross USD | +1.45 | 0 |
| costs USD | 69.73 | 0 |
| net USD | -68.28 | 0 |
| closed drawdown USD | 79.31 | 0 |
| estimated intrabar drawdown USD | 80.93 | 0 |
| days >= $50 | 0/104 | 0/104 |

Guard rejects ATR >1.6x rolling median or spread >30 points; OOS it admits no trades. Different opportunity counts reflect blocking and overlapping positions.
Training base net -192.38 USD, guard net -179.34 USD. Hypothesis rejected; not eligible for demo.

Local executable: v5_streak_reversion_20261118.py; local JSON: v5_streak_reversion_20261118_results.json. These files are not yet committed to this branch; this commit documents actual local execution only. Tick-by-tick execution, real Eplanet fees and exact intrabar drawdown not verified.
