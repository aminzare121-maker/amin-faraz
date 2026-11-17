# V5 spread-conditioned 24-bar breakout — 2026-11-17

Hypothesis: an expansion candle closing outside the prior 24-bar range has continuation potential. The separate spread gate attempts to reduce execution drag; it is NOT an alpha signal.

Data: private Eplanet M15 CSV, 23643 bars, 9458 chronological out-of-sample bars (2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC). No private dataset committed.

Model: enter next bar open; 20-bar ATR, stop 1.2 ATR (min $3/oz), target 2R, max 8 bars, no overlap, stop-first ambiguous bars, gap stop at open; variable lots floor to 0.01 with 1% equity risk and 0.1 cap. Fixed hypothetical roundtrip cost $1.46/oz, 100 oz per lot. Spread units not verified with broker. Gate requires signal-bar spread <= prior 96-bar median and <=40 units. No forward-looking signals.

| OOS | Baseline | Spread gate |
|---|---:|---:|
| Opportunities (sequential scan) | 558 | 594 |
| Simulated trades | 212 | 114 |
| Gross USD | -33.20 | -103.98 |
| Costs USD | 312.44 | 166.44 |
| Net USD | -345.64 | -270.42 |
| Max closed-equity drawdown USD | 383.70 | 294.93 |
| Maximum single-trade intrabar adverse excursion USD | 44.17 | 44.17 |
| Days net >= $50 | 0 | 0 |
| Active days | 78 | 61 |

Opportunity counts differ because the sequential scan skips bars during open trades. This is a model limitation, not independent market opportunity counts. Costs are assumptions, not confirmed broker charges. Intrabar portfolio drawdown not calculated. The gate reduces loss but has no independent profitability. Reject for MT5 demo; no orders placed.
