# V5 session VWAP overshoot — 2026-11-22

New hypothesis: after a >=1.5 ATR displacement from the completed-candle, tick-volume-weighted session VWAP, a reversal candle predicts mean reversion over up to 8 M15 candles. Entry next bar open. ATR stop 1.5x, target 2x; if stop and target both touched in a candle, assume stop first. Variable 1%-equity risk, 0.01-0.10 lots, assumed 100 oz/lot. Spread from dataset (points * $0.01/oz) plus $0.30/oz roundtrip. No future candle used for signal.

Split: training before 2026-06-15; independent OOS on/after 2026-06-15; $1000 reset at start of each segment.

| Metric | Train base | Train guard | OOS base | OOS guard |
|---|---:|---:|---:|---:|
| Opportunities | 1800 | 1800 | 1324 | 1324 |
| Executed diagnostic trades | 101 | 86 | 84 | 82 |
| Gross wins $ | 403.85 | 359.44 | 290.93 | 322.99 |
| Gross losses $ | -361.66 | -315.56 | -381.01 | -345.31 |
| Costs $ | 57.66 | 49.01 | 51.95 | 50.66 |
| Net $ | -15.47 | -5.13 | -142.03 | -72.99 |
| Max closed-equity drawdown $ | 69.42 | 79.52 | 223.10 | 156.52 |
| Days >= $50 | 0 | 0 | 0 | 0 |

Guard excludes VWAP displacements >3 ATR and ATR >$18/oz. This reduced OOS loss but failed profitability and daily target. Both strategies REJECTED; zero demo/real orders authorized.

Reproduction input (private, never commit): Eplanet_M15_20251105_20261105_merged.csv (columns time/open/high/low/close/tick_volume/spread). Full local simulator and JSON generated in run, pending GitHub code publication.

Limitations: tick volume is not exchange volume; OHLC stop-first is conservative but does not capture gaps/slippage accurately; contract size and point value must be verified against Eplanet; no swaps; drawdown is closed-equity only. No claim of executable MT5 readiness.