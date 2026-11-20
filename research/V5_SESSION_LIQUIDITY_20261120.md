# V5 session liquidity gate — 2026-11-20

New predeclared hypothesis: restricting existing 16-bar efficiency/3-bar pause signals to 12:00–20:00 UTC may improve fills/edge through more liquid London/US hours. Tested independently of the daily-loss guard. Signal is calculated from completed candles; next-bar open entry. No COT/sentiment.

Private Eplanet CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23,643 M15 candles. Chronological 60%/40% split, 156/104 trading days. Initial capital $1,000; 0.01–0.1 variable lots, 100 oz/lot, 1% equity risk capped $10; estimated roundtrip $87/lot, stop-first intrabar, 1.8R target, 12-bar timeout.

| Segment | Variant | Opportunities | Trades | Gross USD | Costs USD | Net USD | Closed-equity DD USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | All sessions | 2061 | 132 | +97.38 | 118.32 | -20.94 | 175.17 | 0/156 |
| Train | 12–20 UTC | 480 | 27 | -78.28 | 23.49 | -101.77 | 106.75 | 0/156 |
| Holdout | All sessions | 1526 | 177 | +169.61 | 153.99 | +15.62 | 138.77 | 1/104 |
| Holdout | 12–20 UTC | 421 | 48 | -4.11 | 41.76 | -45.87 | 98.22 | 0/104 |
| Holdout | 12–20 UTC + $15 daily loss guard | 421 | 48 | -4.11 | 41.76 | -45.87 | 98.22 | 0/104 |

Session filter loses money in both segments; daily guard makes no difference. REJECT for demo. The baseline here is not identical to earlier efficiency-pause reports (different segment-boundary and sizing implementation); do not interpret this as a directly reconciled baseline. Audit/reconcile before promotion.

Reproduction code and JSON generated as conversation artifacts, but are not yet committed in this branch. No private CSV uploaded. Estimates omit verified live spreads, commissions and tick-by-tick sequencing; closed-equity drawdown understates intrabar risk. No orders placed.
