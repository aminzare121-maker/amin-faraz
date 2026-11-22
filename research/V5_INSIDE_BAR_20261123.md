# V5 inside-bar breakout — 2026-11-23

New hypothesis: after an unusually wide mother candle and a fully contained inside bar, a subsequent confirmed close beyond the mother range predicts directional continuation. Entry at next candle open. This is distinct from prior compression breakout.

Dataset: private Eplanet M15 CSV, 23643 rows (verify locally with script); split 2026-06-15 UTC, OOS ends 2026-11-06. No private market data uploaded.

Risk: initial equity $1000; dynamic lots floor(1% equity/(stop distance * 100 oz), 0.01), capped 0.10; 0.01 minimum. Stop=max(0.9 ATR20, distance to prior inside bar extreme), TP=1.6R; 8-candle time exit; stop wins simultaneous stop/target. Cost: spread * $0.01/oz + $0.30/oz roundtrip, multiplied by ounces. This is assumed, not broker-verified.

| Split | Mode | Opportunities | Trades | Gross profit | Gross loss | Costs | Net | Max closed DD | Days >=$50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | base |205|33|100.71|-155.62|22.13|-77.05|90.62|0|
| Train | guard |207|17|33.60|-92.06|10.80|-69.26|69.26|0|
| OOS | base |132|38|136.46|-193.13|25.59|-82.26|98.13|0|
| OOS | guard |136|0|0|0|0|0|0|0|

Guard excludes breakout candles >1.8 ATR or spread >30. Opportunities count depends on skipped holding intervals, so counts are not identical across modes. Both training modes negative; guard OOS has no trades. No demo activation. No live trades.

Limitations: OHLC intrabar ordering unknown, no tick-level floating drawdown, assumptions about broker point and contract size unverified, no independent GitHub CI. Full executable local script and JSON were produced in the automation workspace, but are not included in this commit.
