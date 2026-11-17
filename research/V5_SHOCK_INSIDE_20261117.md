# V5 shock / inside-bar continuation — 2026-11-17
New hypothesis: an unusually directional bar (>2.2x preceding 48-bar median range, body >65% range) followed by an inside bar (<65% prior range) may continue after temporary inventory rebalancing. Entry next open in shock direction, stop=1x pre-signal median range, take profit=1.5x, exit after 4 bars. Stop-first if both levels touched. Strictly completed candles and 900-second continuity.

Eplanet M15 merged CSV: 23,643 rows; holdout final 40% (2026-06-15 05:45 UTC through 2026-11-05 10:45 UTC). Starting equity $1,000. Variable lots 0.01–0.03 in baseline, risk budget 1.5%, 100 oz per lot. Assumed round-trip all-in cost $1.46 per oz (not broker-validated).

| Holdout metric | Baseline | Risk guard (0.75% risk, additional volatility/spread constraints) |
|---|---:|---:|
| Signal opportunities | 67 | 67 |
| Executed backtest trades | 67 | 0 |
| Gross P&L | -$27.32 | $0 |
| Estimated costs | $157.68 | $0 |
| Net P&L | -$185.00 | $0 |
| Closed-equity max drawdown | $213.68 | $0 |
| Estimated intrabar drawdown | $225.26 | $0 |
| Wins/losses | 26/41 | 0/0 |
| Active days | 48 | 0 |
| Days net >= $50 | 0 | 0 |

Guard rejects all 67 opportunities due to size/risk/volatility constraints, not profitable. Baseline rejected for demo. Intrabar DD estimated from OHLC; execution, broker fees, spread variability, and slippage unverified. No real or demo trades. Reproduction code generated locally: v5_shock_inside.py; CSV remains private. This report alone is NOT a code commit or a production-ready engine.