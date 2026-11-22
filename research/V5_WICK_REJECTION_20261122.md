# V5 wick rejection — 2026-11-22

Hypothesis: 20-bar extreme sweep and rejection, with wick closing back within prior range; next-open execution, 1.8R target, 9-bar maximum holding, 1% equity risk and variable lot (0.01 increments). Independent session filter: 07:00–17:00 UTC.

Dataset: Eplanet M15, 23,643 rows, private (not committed). OOS from 2026-06-15; training period not used for optimization. Initial OOS equity $1000. Estimated all-in roundtrip friction $0.56 per ounce, 0.01 lot assumed 1 oz. Stop-first intrabar, no tick-level fill confirmation. This is a *research simulation*, not live or demo trading.

| OOS metric | Baseline | Session guard |
|---|---:|---:|
| Signal opportunities | 356 | 361 |
| Trades | 145 | 77 |
| Blocked | 0 | 185 |
| Gross profit USD | 511.43 | 239.09 |
| Gross loss USD | -638.10 | -369.78 |
| Estimated costs USD | 86.80 | 44.24 |
| Net USD | -213.47 | -174.93 |
| Max closed-equity drawdown USD | 225.01 | 202.77 |
| Days >= $50 net | 0 | 0 |

Both variants fail. Guard reduces absolute losses but does not establish an independent profitable edge. No MT5 demo activation. Local script and JSON outputs produced, not yet committed. Limitations: 15m OHLC cannot validate order fills, actual Eplanet contract size and real transaction costs must be confirmed. Do not commit private market data.
