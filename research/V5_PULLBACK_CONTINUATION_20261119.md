# V5 — 2026-11-19: trend pullback continuation
Research only; no demo/live orders. Private Eplanet CSV excluded from repository.

Hypothesis: after a 40-bar directional move, two countertrend candles followed by a confirmation candle may create a continuation entry. Signal uses only closed M15 candles; next-bar open entry. Stop-first conservative OHLC simulation, 1.2x 20-bar mean range stop (clamped $2–12), 1.8R target, max 8 bars, variable lots 0.01–0.15, 0.75% sizing. Cost proxy $0.60 per ounce traded roundtrip; not verified with Eplanet execution.

23,643 unique M15 bars; first 14,185 training, remaining 9,458 OOS. No optimization of parameters on OOS. Guard excludes mean candle range >$8 or price distance >3x mean range.

| Metric | Train | OOS primary | OOS guard |
|---|---:|---:|---:|
| Opportunities | 273 | 203 | 209 |
| Trades | 273 | 203 | 84 |
| Wins | 113 | 80 | 34 |
| Gross USD | 125.00 | -20.57 | 51.51 |
| Cost USD | 163.80 | 121.80 | 51.00 |
| Net USD | -38.80 | -142.37 | +0.51 |
| Closed equity max drawdown USD | 349.64 | 207.46 | 68.34 |
| Active days | 134 | 91 | 57 |
| Days net >= $50 | 2 | 1 | 0 |

Guard's +$0.51 is not an independently validated edge, and was evaluated on the same OOS period. Both fail target $50 net per trading day. No demo activation. Limitations: tick execution, swap, real commissions/spreads, floating intrabar drawdown and margin not verified. Code: research/v5_pullback_continuation_repro.py.
