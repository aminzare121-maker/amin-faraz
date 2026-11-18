# V5 — Session VWAP overextension reversal (2026-11-18)

Status: REJECTED. No demo or live trades.

Hypothesis: intraday price deviations >1.8 times trailing median true range from same-day tick-volume weighted VWAP, followed by a completed 15-minute candle turning toward VWAP, may revert over five bars. This is distinct from impulse continuation and breakout signals. VWAP uses completed bars only. Entry at next bar open.

Data: private Eplanet_M15_20251105_20261105_merged.csv, 23,643 M15 rows. Chronological 60/40 split; test begins 2026-06-15 05:45 UTC, 104 trading days. Thresholds predeclared; not tuned on test.

| OOS | Base | Independent risk guard |
|---|---:|---:|
| Opportunities | 883 | 1100 |
| Executed simulations | 249 | 0 |
| Gross P/L USD | -102.26 | 0 |
| Estimated costs USD | 172.29 | 0 |
| Net USD | -274.55 | 0 |
| Closed equity drawdown USD | 309.09 | 0 |
| Approx conservative intratrade drawdown USD | 316.53 | 0 |
| Days net >= $50 | 0/104 | 0/104 |

Capital $1,000, variable lot in 0.01 increments, max 0.05 lot, 1% risk base and 0.5% guard. Guard rejects spread/ATR >0.055 or ATR>10. Stop 1.3 ATR; target 1.6 ATR; time exit after five M15 bars. 100oz per lot, spread column assumed points/100, slippage $0.30/oz roundtrip, commission $7/lot. OHLC stop-first where ambiguous, one open trade at a time. Guard made zero trades due to sizing/filter constraints; zero P/L is NOT evidence of an edge. Intratrade DD is an OHLC proxy, not tick-verified.

No private data committed. Reproduction script and trade ledger are local artifacts, not yet pushed to GitHub. Contract size, spread semantics, slippage and broker execution need validation before any MT5 demo. Goal $50 net EVERY trading day not met.
