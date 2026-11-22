# V5 session opening-range breakout — 2026-11-22

Hypothesis: the first four M15 candles at 07:00-07:45 UTC establish an opening range; a first close beyond its high/low during 08:00-11:45 UTC can predict continuation over the next six bars. Enter next bar open; exit at open six bars later. Distinct guard: accept only opening-range width / lagged ATR20 between 0.5 and 1.8.

Private Eplanet CSV: 23,643 M15 candles, not committed. Time split 2026-06-15 UTC. Equity resets to $1,000 for each sample. Position size floor to 0.01 lot using 1% current equity divided by max(range width, ATR20, $1) and 100 oz/lot; maximum 0.10 lot. Cost assumption spread points * $0.01/oz + $0.30/oz roundtrip. No stop actually executed: risk sizing is only a proxy. Only complete contiguous bars accepted.

Training: 262 opportunities. Baseline 43 diagnostic trades, gross gains $285.87, gross losses -$135.56, costs $25.91, net +$124.40, max closed DD $34.77, 1 day >= $50. Guard 39 trades, gross gains $256.79, gross losses -$130.67, costs $23.63, net +$102.49, DD $41.03.

OOS diagnostic: 216 opportunities. Baseline 65 trades, gross gains $345.89, gross losses -$353.73, costs $40.20, net -$48.04, max closed DD $179.27, 1 day >= $50. Guard 63 trades, gross gains $339.02, gross losses -$351.53, costs $38.98, net -$51.49, DD $179.27, 1 day >= $50.

Conclusion: OOS negative; guard worsens outcome. Both rejected. Authorized demo trades: zero. This is bar-level research with estimated costs, not executable MT5 validation. Complete executable local Python and JSON are retained as conversation artifacts; source is not yet committed. Do not publish private data or enable live/demo trading.
