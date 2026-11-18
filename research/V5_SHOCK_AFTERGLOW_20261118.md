# V5 — Post-shock pause continuation (2026-11-18)

Dataset: private Eplanet M15 CSV, 23,643 bars; no private data committed.

## New hypothesis
After a candle with absolute body >1.65 times lagged 32-bar median true range, a small pause candle (<0.65 ATR body) that holds >0.45 ATR beyond shock open may predict directional continuation. Enter next bar open; 4-bar horizon; stop 1.15 ATR, target 1.8 ATR. Stop-first on ambiguous OHLC. Variable lot sized to 1% equity risk, min 0.01, max 0.05 lots.

Out-of-sample: final 40% of chronological bars, from 2026-06-15 05:45 UTC; 104 trading days; $1,000 initial equity. Assumptions: spread points /100, $0.30/oz roundtrip slippage, $7/lot commission, 100oz/lot.

| Metric | Base | Independent volatility/spread guard |
|---|---:|---:|
| Candidate opportunities | 223 | 223 |
| Executed simulated trades | 179 | 95 |
| Gross P&L USD | -128.62 | -102.46 |
| Estimated costs USD | 133.06 | 65.67 |
| Net USD | -261.68 | -168.13 |
| Closed-equity max drawdown USD | 281.08 | 168.13 |
| Winning / losing trades | 69 / 110 | 36 / 59 |
| Days with >= $50 net | 0 / 104 | 0 / 104 |

Guard rejects spread/ATR >0.055 or ATR >11; independently reduces drawdown but does not create profitability. Reject both for MT5 demo. No real trades. OHLC bars cannot validate intrabar floating drawdown or execution. Spread-point conversion and broker fees remain assumptions pending broker validation.

Local reproducible implementation and detailed ledger: v5_shock_afterglow_20261118.py and v5_shock_afterglow_20261118.json; code not yet committed to this branch.
