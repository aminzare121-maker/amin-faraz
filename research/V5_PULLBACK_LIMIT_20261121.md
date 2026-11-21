# V5 passive pullback limit — 2026-11-21

New hypothesis: submit a one-candle passive limit at 0.10 or 0.20 of prior ATR in favorable direction rather than buying/selling at next open. Economic rationale: reduce adverse entry price, at the cost of missed fills.

Data: private Eplanet M15 CSV, 23,643 candles; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split. Capital $1,000; lot 0.01–0.10; estimated $87 per lot round trip; stop-first OHLC; no tick confirmation.

| Holdout (104 trading days) | Market | Limit 0.10 ATR | Limit 0.20 ATR |
|---|---:|---:|---:|
| Signal opportunities | 1517 | 1517 | 1517 |
| Unfilled orders | 0 | 120 | 248 |
| Trades | 165 | 159 | 157 |
| Gross USD | 276.95 | 131.34 | 131.13 |
| Costs USD | 143.55 | 138.33 | 136.59 |
| Net USD | 133.40 | -6.99 | -5.46 |
| Closed drawdown USD | 54.11 | 92.04 | 120.53 |
| Days net >= $50 | 0 | 0 | 0 |

Training net: market $46.17; 0.10 ATR -$41.76; 0.20 ATR $43.01.

**Decision: reject both limit-entry variants.** Neither profitability nor loss reduction survives holdout. No MT5 orders.

**Execution caveat:** The limit fill is inferred from an OHLC touch. The fill candle is not checked for stop/target before the following bar, potentially overstating performance; therefore negative holdout results are especially unfavorable, not proof of exact realized loss. Intrabar floating drawdown is unmeasured. Estimated costs are not verified live spreads/commissions. Research implementation executed locally; independent GitHub CI and upload of the executable source are not yet verified. No private data uploaded.
