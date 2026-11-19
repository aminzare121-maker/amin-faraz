# V5 compression-breakout research — 2026-11-19
Hypothesis: a completed M15 close outside the prior eight-bar compressed range could reveal fresh directional order flow. Entry is next bar open; no COT/sentiment. Prior 40-bar ATR (shifted one bar), compression range between 0.35 and selected ratio times ATR; breakout buffer 0.08 ATR. Stop 1 ATR, target 2 ATR, maximum eight bars. Stop-first for ambiguous OHLC. Equity $1,000; risk 1% of current equity, 0.01 lot increments, cap 0.15, 100 oz/lot.

Private input: Eplanet_M15_20251105_20261105_merged.csv, 23,643 candles, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Never commit CSV.

Chronological first 60% train: ratio .9: 6 opportunities/2 trades, +$14.45 net; ratio 1.2: 60 opportunities/27 trades, +$34.74 net; ratio 1.5: 203/83, -$62.23; ratio 1.8: 410/136, -$210.88. Selected 1.2 without examining holdout.

Last 40% holdout, 104 trading days: 55 opportunities, 34 trades; gross -$108.05, estimated costs $31.62, **net -$139.67**, maximum closed-equity drawdown $139.67, 0/104 days reaching $50 net.

Separate risk guard excludes trigger candles >2.5 ATR or spread >30 points: 58 raw opportunities, 0 trades, $0 net. Zero exposure is not an edge. Guard's opportunity count differs because skipped entries do not block later signals.

Costs: $7/lot roundtrip commission, $0.26/oz spread, $0.30/oz slippage each side. Swap excluded; no broker cost verification, margin test, or tick-level execution. Intrabar drawdown not established. OHLC execution assumptions may overstate performance. Full private trade ledger retained locally, not published.

**Decision: reject trading method; no demo/live activation.** Research code: research/v5_compression_breakout_repro.py. Reproduce using python research/v5_compression_breakout_repro.py --csv /path/to/private.csv.