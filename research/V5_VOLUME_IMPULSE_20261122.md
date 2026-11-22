# V5 high-participation impulse — 2026-11-22

Research only. OOS: 2026-06-15 05:45 UTC onward; Eplanet M15, 23643 bars total; split 60/40. Hypothesis: a large directional candle with tick volume >1.8x prior 48-bar median and body >0.75x prior ATR24, body/range >0.7 predicts continuation. Entry next open, stop 0.8 ATR (min $2/oz), target 1.6R, timeout 8 bars. Dynamic 1% equity risk, 100 oz/lot, 0.01 lot step. Conservative stop-first OHLC. Assumed spread points *0.01, slippage $0.10/oz per side, commission $0.07 per 0.01 lot roundtrip; broker contract specifications not verified.

| OOS | Baseline | High-volatility risk veto |
|---|---:|---:|
| Opportunities |59|65|
| Executed |51|1|
| Blocked |0|64|
| Lot rejected |8|0|
| Gross gain USD |165.80|0|
| Gross loss USD |234.93|6.63|
| Costs USD |33.04|0.59|
| Net USD |-102.16|-7.22|
| Closed drawdown USD |102.16|7.22|
| Days >= $50 |0|0|

Risk veto nearly suppresses all trades; cannot be called effective risk control from one trade. No demo deployment. Code and full JSON generated locally but not yet committed; GitHub report is not an independently reproducible CI test. Private price data excluded.
