# V5 session opening-range breakout — 2026-11-23
Research only; NO DEMO OR LIVE ORDERS.
Dataset: private Eplanet M15 2025-11-05 to 2026-11-05 (23,643 bars). No private data committed.
New hypothesis: price breaking the 07:00–09:00 UTC range on a completed 09:00–12:00 UTC candle may continue due to session liquidity and order-flow clustering. Enter next candle open, stop 0.9 x trailing ATR20 (min $2/oz), target 1.8R, exit after 8 bars, stop-first intrabar. One attempt/day.
Risk: 1% balance, variable lots rounded down to 0.01 (max 0.10), $100/oz per lot assumed. Spread from historical points * $0.01/oz; round-trip slippage $0.20/oz; commission $7/lot. Assumptions require broker verification.
Train before 2026-06-15 UTC; out-of-sample from 2026-06-15. Independent $1,000 equity per split.
| metric | base train | base OOS | guard train | guard OOS |
|---|---:|---:|---:|---:|
| opportunities |116|91|116|91|
| trades |87|85|49|68|
| gross profit USD |385.05|486.08|221.63|351.89|
| gross loss USD |-364.54|-314.45|-195.92|-260.48|
| costs USD |56.11|55.33|32.02|42.95|
| net USD |-35.60|+116.30|-6.32|+48.46|
| max closed DD USD |63.17|63.22|60.65|57.74|
| days net >= $50 |0|0|0|0|
Guard excludes ranges <0.65 or >3.5 ATR, spread >35 points, or breakout candle >2 ATR. Guard reduces OOS drawdown $5.48 but reduces net $67.84. Neither qualifies for $50 net/day. OOS gain cannot validate negative train expectancy.
Caveats: OHLC stop-first, not tick path; no independently verified Eplanet contract or actual slippage. Local full simulator and trade logs: v5_session_range_20261123.py and .json, not yet committed. This repo contains a reproducible SIGNAL AUDIT script, not the full backtest. Do not enable demo.
