# V5 session opportunity experiment — 2026-11-20

Input: private Eplanet M15 CSV, 23,643 bars; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split. Research-only. No private prices committed.

Hypothesis: trading-session selection changes opportunity economics (signal density, spread-adjusted net return and drawdown). Compare completed-bar signal + 45% adverse-wick exclusion + 3-bar stagnation exit + 12-bar holding period with entry UTC windows: all, 07:00–17:00, 12:00–22:00, 00:00–08:00. Entry decisions use only available candle data. Initial equity $1,000; 1% risk cap, 0.01–0.10 lots; $87/lot estimated roundtrip costs; stop-first OHLC.

| Metric | Train all | Train 07-17 | Train 12-22 | Train 00-08 | Holdout all | Holdout 07-17 | Holdout 12-22 | Holdout 00-08 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Opportunities |2059|2059|2059|2059|1517|1517|1517|1517|
| Trades |137|68|26|78|165|85|46|81|
| Gross USD |168.84|32.99|-28.82|219.75|276.95|204.35|-10.19|181.90|
| Costs USD |122.67|59.16|22.62|71.34|143.55|73.95|40.02|70.47|
| Net USD |46.17|-26.17|-51.44|148.41|133.40|130.40|-50.21|111.43|
| Max closed drawdown USD |128.41|98.40|57.88|43.67|54.11|43.89|65.13|94.66|
| Days >= $50 |1|0|0|0|0|0|0|0|

Decision: no window qualifies. The 00–08 window was best in training but deteriorated in holdout; 07–17 modestly reduced holdout drawdown while also reducing net. Do not activate demo. This is a fixed UTC-hour exploratory comparison, not daylight-saving-aware market session identification. No tick sequencing, real slippage, floating drawdown, or live spread validation. Research code and full JSON generated locally but not included in this commit.