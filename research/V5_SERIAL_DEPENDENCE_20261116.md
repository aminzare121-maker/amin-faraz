# V5 serial dependence — 2026-11-16
Data: private Eplanet M15 23643 rows; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604.
Hypothesis: lag-one return autocorrelation over 64 historical candles indicates momentum when >0.18 and reversal when <-0.18. Signal after closed candle; enter next open, exit 4 candles later. Independent risk guard: relative tick volume >=0.65 median, range <1.8 ATR, ATR<12.
Train rows 0:14185; OOS rows 14185:23643. Initial capital $1000, theoretical variable lot sizing, minimum 0.01; actual lots 0.01 throughout. Cost 0.86 USD/oz round trip, 100 oz/lot. No intrabar SL simulation or verified broker execution. Closed-equity drawdown only.
| sample | method | opportunities | trades | gross USD | costs USD | net USD | max closed DD USD | days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| train | signal | 1299 | 74 | -76.32 | 63.64 | -139.96 | 161.79 | 0 |
| train | guard | 1322 | 59 | -85.46 | 50.74 | -136.20 | 160.19 | 0 |
| OOS (104 UTC days) | signal | 975 | 65 | -131.53 | 55.90 | -187.43 | 230.56 | 0 |
| OOS (104 UTC days) | guard | 929 | 94 | 27.68 | 80.84 | -53.16 | 89.11 | 0 |
Opportunities are counted along each strategy's separate execution path, not unique universal market signals.
Decision: REJECT for demo. Risk guard reduces net losses in OOS but fails profitability and $50/day. No trades placed. Source dataset not committed.
Reproduce: python research/v5_serial_dependence.py /path/to/Eplanet_M15_20251105_20261105_merged.csv
