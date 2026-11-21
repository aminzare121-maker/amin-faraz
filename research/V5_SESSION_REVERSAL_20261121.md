# V5 Session Reversal — 2026-11-21

Hypothesis: fade extreme 8-bar returns in UTC 16–20, next-bar open entry, 4-bar holding horizon. Signal uses only closed bar information. Independent risk role: stop distance 1.0 ATR versus 1.5 ATR. ATR32 lagged one bar.

Data: Eplanet M15 23643 bars; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological 60/40 split, 104 out-of-sample trading dates. Private candles NOT committed.

Assumptions: $1000 initial, 1% equity risk, 100oz/lot, min 0.01 lot, 0.01 step, $45/lot round-trip estimated total cost. OHLC stop-first, no tick validation. Thresholds exploratory, NOT independently tuned in train: this is a provisional OOS screen, not an unbiased final validation.

|Threshold ATR|Stop ATR|Opportunities|Rejected min lot|Trades|Gross profit|Gross loss|Cost|Net|Closed DD|Days >=$50|
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|1.5|1.5|834|802|32|178.86|-130.79|14.40|33.67|45.77|0|
|1.5|1.0|472|282|190|812.15|-771.44|85.50|-44.79|247.20|0|
|2.0|1.5|619|604|15|58.48|-83.13|6.75|-31.40|40.12|0|
|2.0|1.0|341|190|151|630.91|-640.03|67.95|-77.07|251.03|0|
|2.5|1.5|433|422|11|47.80|-59.38|4.95|-16.53|45.62|0|
|2.5|1.0|254|151|103|438.57|-429.60|46.35|-37.38|132.11|0|

None meet required $50 net each trading day. No demo activation. The apparent +$33.67 variant is inadequate and sensitive to cost assumptions. Local executable code and JSON outputs were produced, but source code is not yet committed to GitHub. Intrabar DD, actual spread and commission not verified.
