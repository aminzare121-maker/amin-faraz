# V5 volatility transition — 2026-11-17

Hypothesis: after six quiet M15 candles, a strong expansion candle may continue for four candles. Only completed candle information; next-bar open entry. Fixed 1.6R target, 1.1x prior 24-bar median true range stop; stop-first ambiguous bars. Initial equity $1000, 0.01 lot steps, risk 1.5% base and 0.75% guard. Costs proxy $1.46/oz round trip, 100oz/lot; NOT broker verified.

Data: private Eplanet merged M15, 23643 rows, chronological 60/40 split; out-of-sample begins 2026-06-15 05:45 UTC. Private data not uploaded.

| metric | base | guard |
|---|---:|---:|
| raw opportunities | 99 | 99 |
| simulated trades | 88 | 28 |
| gross USD | -185.00 | -97.83 |
| proxy costs USD | 169.36 | 40.88 |
| net USD | -354.36 | -138.71 |
| max closed drawdown USD | 354.36 | 140.84 |
| conservative intrabar drawdown proxy USD | 370.15 | 157.14 |
| days net >= $50 | 0 | 0 |
| active days | 59 | 26 |
| lots | .01-.03 | .01 |

Guard excludes high spread relative to trailing median and stop distance >$12. This reduces losses but does not create edge. REJECTED; no demo activation or real trading. Local executable code: v5_volatility_transition.py and results JSON. Code upload remains pending; GitHub report alone is not reproducible without the local script.