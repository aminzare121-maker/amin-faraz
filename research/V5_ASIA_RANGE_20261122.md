# V5 Asian-range breakout research — 2026-11-22

Hypothesis: breakout of completed 00:00–07:00 UTC range during 07:00–16:00 UTC, confirmed at M15 close, enter next M15 open. Economic rationale: liquidity transfer from Asian consolidation to London/US sessions may cause directional expansion.

Source: private Eplanet M15 CSV, 23,643 bars; SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. Private data NOT uploaded. Chronological 60/40 split; OOS begins 2026-06-15 05:45 UTC. No training optimization was performed in this run; fixed parameters are hypothesis assumptions, not fitted parameters.

Rules: first confirmed breakout per UTC day; next open entry; stop max(0.9 prior ATR20, $2/oz); target 1.8R; maximum 16 M15 bars; stop-first when both levels touched; 1% of current equity risk, 100 oz/lot, 0.01 minimum/step; $0.70/oz estimated round-trip friction; 1,000 USD OOS initial equity. Protective variant blocks breakout signal bars with range >1.8 prior ATR. Sequential positions cannot overlap.

| OOS metric | Base | Shock guard |
|---|---:|---:|
| Opportunities | 91 | 91 |
| Blocked | 0 | 21 |
| Minimum-lot rejected | 3 | 0 |
| Trades | 88 | 70 |
| Gross profit USD | 412.16 | 316.26 |
| Gross loss USD | -382.76 | -307.31 |
| Estimated costs USD | 67.20 | 52.50 |
| Net USD | **-37.80** | **-43.54** |
| Max closed drawdown USD | 112.26 | 102.53 |
| Days >= $50 net | 0/104 | 0/104 |

**Decision: reject both for demo.** Guard lowers closed drawdown by $9.73 but worsens net return by $5.74. It is not a proven profitable guard.

Limitations: bar-only OHLC cannot validate intrabar order sequence, fills, actual Eplanet spread/commission, slippage, margin, tick-level floating drawdown, or whether server timestamps truly represent UTC. Fixed $0.70/oz cost is a scenario, not verified broker pricing. The local executable `v5_asia_range_20261122.py` and trade ledger JSON were created and run in the automation environment; this commit contains only the report, **not the executable source**. Independent GitHub Actions verification has not occurred. No demo/live orders sent.