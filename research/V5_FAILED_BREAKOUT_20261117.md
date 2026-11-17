# V5 failed breakout reversal — 2026-11-17

Hypothesis: a sweep of the previous 24-bar high/low followed by a close back inside the range predicts mean reversion. Entry next bar open, opposite sweep. ATR20 lagged, stop max($3,1.2 ATR), take profit 1.5R, 9-bar horizon, stop-first ambiguity, gaps at open, sequential non-overlapping trades. Risk 1% equity, lots rounded DOWN to 0.01; capital $1000. Separate risk filter excludes signal candle range >1.5 ATR. Estimated cost $1.46 per ounce round trip, broker-unverified.

Private Eplanet 23643 M15 candles. Chronological last 9458 bars held out: 2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC. No fitting performed; exploratory hypothesis only.

| OOS | Alpha | Risk filter |
|---|---:|---:|
| Sequential opportunities | 625 | 627 |
| Trades | 163 | 113 |
| Wins/losses | 60/103 | 39/74 |
| Gross USD | -114.23 | -127.02 |
| Estimated costs USD | 239.44 | 164.98 |
| Net USD | -353.67 | -292.00 |
| Max closed equity drawdown USD | 364.67 | 307.94 |
| Days >= $50 net | 0 | 0 |
| Active days | 71 | 59 |
| Lots | 0.01–0.02 | 0.01 |

Risk filter reduces net losses but does not produce positive alpha. Counts are sequential, not independent opportunity counts. Intrabar portfolio drawdown, Eplanet execution costs, and spread units are not verified. Reject for MT5 demo. No orders placed. Reproduction script generated locally as v5_failed_breakout.py, not yet committed; no private data published.
