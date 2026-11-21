# V5 Wick Absorption — 2026-11-22

New hypothesis: an M15 candle with a rejection wick occupying >=60% of its range, close in the opposite 35% of range, and tick volume >=1.1x preceding 32-bar median reflects absorbed aggressive flow. Enter on next open in rejection direction. This differs from prior range-breakout, opening-dislocation, and session reversal methods.

Private input: Eplanet_M15_20251105_20261105_merged.csv (23,643 bars), chronological 60/40 split at row 14185. Local Python implementation: v5_wick_absorption_20261122.py; JSON: v5_wick_absorption_20261122.json. These two local artifacts are **not yet committed to this branch**. The original Eplanet data are not published.

Rules: prior ATR20, candle range 0.65–2.5 ATR, stop max(0.75 candle range, 0.65 ATR, $1/oz), target 1.3R, max 8 bars, stop-first on ambiguous candles; 1% equity risk, 0.01-lot increments, 0.05 max, 100 oz/lot assumed, $0.45/oz all-in round-trip cost assumed. Independent risk filter: reject signals when ATR20 exceeds the trailing 96-bar 75th percentile.

| Sample | Variant | Opportunities | Min lot rejected | Trades | Gross profit | Gross loss | Cost | Net | Closed DD | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 609 | 320 | 289 | 1043.70 | -1143.65 | 148.50 | -248.45 | 307.63 | 0 |
| Train | ATR filter | 613 | 178 | 243 | 891.92 | -960.15 | 127.35 | -195.59 | 254.66 | 0 |
| OOS | Base | 402 | 69 | 333 | 1370.40 | -1337.66 | 173.70 | -140.96 | 265.91 | 0 |
| OOS | ATR filter | 413 | 34 | 232 | 893.64 | -932.96 | 125.55 | -164.87 | 249.65 | 0 |

**Decision:** reject both. Filter reduces OOS drawdown by $16.26 but worsens net P&L by $23.91; no positive edge. No demo/live orders.

Limitations: costs are modeled, no tick-level spread/slippage validation; max drawdown is closed-equity only; daily $50 criterion is not met. Opportunities differ by variant due to nonoverlapping positions, so they are not a fixed universal signal count.
