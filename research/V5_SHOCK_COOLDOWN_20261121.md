# V5 shock cooldown — 2026-11-21

Research-only. Eplanet M15 CSV (23,643 candles), chronological 60/40 split. No private OHLC committed.

Hypothesis: immediately after an unusually large completed candle, execution uncertainty and adverse price excursions rise; exclude entries for the next 4 or 8 completed bars when a recent true range exceeds 2x or 3x prior ATR(32 median). Signals use only completed OHLC. Baseline includes adverse-wick filter and three-bar stagnation exit. Initial capital $1000; 0.01–0.10 variable lots, 1% risk cap, estimated roundtrip cost $87/lot, stop-first OHLC. No live or demo trades.

| Holdout metric | Baseline | 2x / 4 bars | 3x / 4 bars | 2x / 8 bars |
|---|---:|---:|---:|---:|
| Opportunities |1517|1517|1517|1517|
| Trades |165|136|160|108|
| Gross USD |276.95|109.13|207.98|27.40|
| Estimated costs USD |143.55|118.32|139.20|93.96|
| Net USD |133.40|-9.19|68.78|-66.56|
| Max closed drawdown USD |54.11|134.31|81.93|147.02|
| Days >= $50 |0|0|0|0|

All shock-cooldown variants worsen holdout performance; reject. Important: OHLC intrabar sequence unknown; no actual slippage or floating drawdown validation. The research code was run locally but is not yet committed to this branch; reproducibility is incomplete until code is committed and independently rerun. Do not enable demo trading.