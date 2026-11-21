# V5 hourly boundary inventory fade — 2026-11-22

New hypothesis: fade the preceding completed hour's directional displacement (0.65–2.2x lagged ATR) for up to 30 minutes. Separate risk filter excludes ATR > 1.2x prior rolling ATR median. No COT/sentiment or future candle used for signal.

Input: private Eplanet M15 CSV, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604, 23643 bars. Chronological 60/40 split at row 14185. Private input not committed.

Assumptions: $1000 start, 1% equity risk, 0.01 lot step, max 0.05 lots, 100 oz/lot, $0.45/oz estimated round-trip cost, stop-first OHLC; not tick/broker verified.

| Metric OOS | Base | Risk filter |
|---|---:|---:|
| Opportunities | 1093 | 1093 |
| Trades | 670 | 607 |
| Gross profit USD | 1373.11 | 1196.01 |
| Gross loss USD | -1584.11 | -1436.52 |
| Estimated cost USD | 315.45 | 286.20 |
| Net USD | -526.44 | -526.71 |
| Max closed drawdown USD | 546.43 | 546.70 |
| Days net >= $50 | 0 | 0 |

Training base: 842 trades, -$319.70 net; training filtered: 733 trades, -$318.25 net. Both rejected. No demo or live trades. The locally executed Python and JSON were generated separately and have not been committed here. Reproduction requires the private CSV and those files; GitHub CI not run.
