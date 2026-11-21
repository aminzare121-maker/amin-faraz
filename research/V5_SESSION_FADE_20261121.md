# V5 session-conditioned extreme candle fade — 2026-11-21

Research-only. Private Eplanet M15 data (23,643 candles) never committed. Chronological day split: train 155 days, holdout 104 days. Starting capital USD 1000; 1% equity risk, 0.01 minimum lot, 100 oz per lot. Signal uses body >1.6 lagged 24-bar ATR, fade at next open, 1.5 ATR stop, three-bar exit. Estimated roundtrip fee USD 0.45/oz. Conservative OHLC stop; intrabar drawdown and tick execution unknown.

**New hypothesis:** 12:00–16:00 UTC overlap repricing makes reversal less reliable; test session exclusion as independent loss control versus profit signal. This is not a retest of the unchanged baseline: session-conditioned execution is new.

| Split | Variant | Trades | Gross profit | Gross loss | Est costs | Net | Closed DD | Days >=50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | All | 88 | 388.01 | -307.74 | 40.05 | 40.22 | 106.55 | 0 |
| Train | 12–16 UTC | 18 | 64.62 | -79.50 | 8.10 | -22.98 | 36.49 | 0 |
| Train | Outside | 73 | 324.05 | -247.73 | 33.30 | 43.01 | 87.10 | 0 |
| Holdout | All | 159 | 830.56 | -588.60 | 72.90 | 169.06 | 170.71 | 1 |
| Holdout | 12–16 UTC | 22 | 138.44 | -115.60 | 9.90 | 12.94 | 57.03 | 1 |
| Holdout | Outside | 136 | 700.83 | -449.50 | 62.55 | 188.78 | 93.95 | 0 |

Holdout candidate opportunity counts: all 329, overlap 367, outside 338 (counts differ due to position lockout). Outside trades on 76 days of 104. Train outside trades on 51 days. All variants fail mandatory USD 50 net EVERY trading day. Do not enable MT5 demo or live. Code and full JSON were executed locally, not yet committed; this markdown is a research record. No independent GitHub CI execution verified. No guarantee. The daily target is economically extreme (5% starting capital/day).
