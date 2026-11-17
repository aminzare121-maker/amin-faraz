# V5 EMA48 pullback continuation — 2026-11-17

New hypothesis: after two countertrend M15 candles, a confirming candle breaking the preceding high/low in direction of EMA48 slope may capture trend resumption. Signals only use completed candles; entry next bar open. Historical Eplanet CSV (private) 23643 rows; 60/40 chronological split; OOS 2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC. Initial $1000; 0.01–0.02 lot; 100 oz/lot; risk target 1% equity; stop max(0.9 * lagged median 32-bar range, $2), target 1.8R, nine-bar timeout; conservative stop-first collision and gap fills. Assumed round-trip cost $1.46/oz (unverified broker pricing).

| OOS | Base | Range/body risk filter |
|---|---:|---:|
| Qualifying opportunities | 200 | 202 |
| Trades | 177 | 96 |
| Gross USD | -70.01 | -67.76 |
| Estimated costs USD | 277.40 | 148.92 |
| Net USD | -347.41 | -216.68 |
| Max closed equity drawdown USD | 366.23 | 216.68 |
| Active days | 85 | 65 |
| Days net >= $50 | 0 | 0 |
| Losing days | 56 | 41 |

Opportunity counts differ because the simulator skips bars during active trades. The risk filter is a separate loss-reduction role, not a profitable strategy. Intrabar mark-to-market drawdown and actual broker execution are unverified. No demo/live orders. Full executable Python script and JSON ledger generated locally; code upload to repository pending.
