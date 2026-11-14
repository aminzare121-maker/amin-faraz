# Session-drift hypothesis: result of executed historical replay (2026-11-14)

Hypothesis: A directional 4-bar displacement in 13:00–16:00 UTC when ATR14 exceeds the preceding 96-bar median may persist for the next 1–5 M15 bars because London/New York overlap increases directional order flow.

**Predeclared signal:** closed bar at i, direction sign(close[i]-close[i-4]); abs(displacement)>0.65*ATR14; ATR14>rolling median of previous 96 ATRs; spread<=0.80 USD/oz. Entry next M15 open with 0.30 USD/oz assumed slippage each side. SL=max(1.5,0.75 ATR), TP=1.5 SL, timeout 5 bars. Bid OHLC/Ask=Bid+spread; pessimistic stop-first on ambiguous bars. 100 oz/lot, commission $10/lot roundtrip, volume step .01, min .01; strict 1% risk sizing includes two slippage legs and $0.15 extra spread cushion. Capital reset to $1000 at each split. One position at a time. No live orders.

Data: user's PRIVATE `Eplanet_M15_20251105_20261105_merged.csv` (23,643 M15 rows). **Data not committed.** Development: 2025-11-05 to 2026-04-30; chronological diagnostic holdout: 2026-05-01 to 2026-11-05. Holdout is not pristine because other V5 studies have already inspected overlapping dates.

| Metric | Development | Chronological holdout |
|---|---:|---:|
| Raw signals | 178 | 207 |
| Risk-rejected | 95 | 47 |
| Executed trades | 83 | 160 |
| Net USD (after costs) | -73.73 | -145.22 |
| Closed-equity peak drawdown | 10.58% | 18.69% |
| Winning trades | 30 | 60 |
| Active trading days | 48 | 80 |
| Days net >= $50 | 0 | 0 |
| Worst active day USD | -25.48 | -23.75 |

**Decision: reject as profit-generating edge; no demo activation.** This test explores a distinct time-of-day liquidity/continuation mechanism rather than retuning the eight failed signals. These are historical simulation figures, not executable MT5 fill guarantees. Overnight gap, intrabar ordering and historical spread representation remain modeling limitations.

Local executable artifact `session_drift.py` and separate development/holdout trade ledgers are included in the conversation's research folder. The strategy requires `strict_risk.py` from the previous V5 execution audit. Reproduce: `python session_drift.py PRIVATE_M15_CSV OUTPUT_DIR`.
