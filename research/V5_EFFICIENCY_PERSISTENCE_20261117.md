# V5 directional-efficiency persistence — 2026-11-17
Data: private Eplanet M15 CSV, 23,643 rows; 60/40 chronological split (index 14185). No private candles committed.
Hypothesis: persistent directional displacement relative to traveled path predicts continuation. Efficiency=(close-close.shift(12))/sum(abs(close.diff()),12). Signal .62<abs(eff)<.94; median 20-bar range lagged, 1<range<25, current range<1.8x median. Enter next open in efficiency direction. Stop 1.4x median range; target 1.8R; max four bars. Stop first on ambiguous bars. Equity 1000, variable lot 0.01-0.10 with 1.5% risk, 0.75% for guard. Cost estimated $1.46 per ounce roundtrip, 100oz/lot.

| Holdout | Base | Guard |
|---|---:|---:|
| Signal opportunities |633|633|
| Executed trades |237|22|
| Gross USD |163.12|-14.36|
| Estimated costs USD |378.14|32.12|
| Net USD |-215.02|-46.48|
| Max closed-equity DD USD |260.87|60.40|
| Approx intrabar DD USD |262.87|63.55|
| Active days |83|16|
| Days >= $50 net |0|0|
| Lot range |.01-.02|.01|

Training base: 237 trades, net -117.97, closed DD 252.03. Guard excludes high spread (>1.15x trailing 96-bar median) and large bar (>1.2x lagged median range). No optimization on holdout. Guard reduces loss but is not profitable. No demo authorization. OHLC execution approximation, unknown actual broker fees/spread unit, no tick-level intrabar reconstruction. Research only; no orders.
