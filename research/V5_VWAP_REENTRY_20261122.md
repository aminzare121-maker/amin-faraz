# V5 rolling VWAP reentry — 2026-11-22

Hypothesis: price displacement >1.2 previous ATR from 32-bar lagged tick-volume weighted close, followed by reentry toward fair value. Signal on closed M15 bar; entry at next open. Stop 1 ATR, target 1.25 ATR, maximum 8 bars, conservative stop-first ordering. No COT or delayed data.

Eplanet M15 23643 rows, chronological 60/40 split, OOS 2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC. Initial capital USD1000, 1% risk, dynamic lots 0.01 steps capped 0.10, assumed 100 oz/lot; estimated roundtrip costs USD0.63/oz. These broker assumptions need verification.

| OOS | Base | Range guard |
|---|---:|---:|
| Opportunities | 2761 | 2730 |
| Rejected (incl. min lot) | 2413 | 2404 |
| Trades | 348 | 326 |
| Gross profit | 948.46 | 899.92 |
| Gross loss | -1233.81 | -1158.86 |
| Estimated costs | 221.76 | 205.38 |
| Net USD | -507.12 | -464.32 |
| Max closed drawdown | 549.99 | 486.30 |
| Days >= USD50 | 0 | 0 |

Independent risk guard rejects signal candles with range >1.4 previous ATR; improves net loss by USD42.80 and closed drawdown by USD63.69, but does not produce an edge. Both configurations rejected; no demo or live trades. OHLC-only, no intrabar drawdown or actual execution costs. Local executable: v5_vwap_reentry_20261122.py; code upload pending.