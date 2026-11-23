# V5 gap repricing — 2026-11-23
Data: private Eplanet M15, 23643 rows, training before 2026-06-15 UTC, OOS 2026-06-15 through 2026-11-05. No private data committed.
Hypothesis: after >=30min market data gap, initial 15m candle reverses gap; trade next open toward pre-gap close, stop 1.2x previous 20-bar mean range, max 12 bars. Base versus independent guard (gap <=1.8 ATR, spread <=35, bar range <=2.5 ATR). Risk 1% equity, dynamic 0.01-0.10 lot, assumed 100oz/lot; fee spread points x $0.01/oz plus $0.30/oz. Pessimistic stop first if both touched.
| sample | arm | opportunities | trades | gross gain | gross loss | fees | net | closed DD | days >= $50 |
| train | base | 98 | 20 | 33.27 | -54.22 | 14.42 | -35.37 | 51.30 | 0 |
| train | guard | 98 | 6 | 13.23 | 0 | 3.36 | +9.87 | 0.17 | 0 |
| OOS | base | 48 | 23 | 31.90 | -42.91 | 24.78 | -35.79 | 35.90 | 0 |
| OOS | guard | 48 | 1 | 2.08 | 0 | 1.28 | +0.80 | 0 | 0 |
Guard suppresses losses by eliminating almost all trades; cannot establish a profitable strategy with one OOS trade. REJECT. No demo or real orders. Costs assumed, not verified with broker. OHLC cannot measure tick intrabar drawdown. Reproduce with the local Python script v5_gap_repricing_20261123.py and private CSV; source file should be committed in subsequent step.