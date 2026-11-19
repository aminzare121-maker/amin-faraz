# V5 wick rejection — 2026-11-19
Source: private Eplanet M15 CSV (not published); SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23643 rows. Train first 14185 rows, OOS remainder (104 trading days).
Hypothesis: after an intrabar breach of prior 20-bar extreme, a long rejection wick and close back inside signals liquidity-sweep reversal. Enter at next candle open, stop 1x rolling median TR(20), target 1.5x, timeout 4 bars; stop wins same-bar ambiguity. Lot floor to 0.01 step, risk 0.5% equity, max 0.10 lot; min 0.01 lot. Assumed roundtrip costs $0.60/oz plus $7/lot, 100 oz/lot; no swap, real broker execution or intrabar tick validation.
Train thresholds 0.55: -55.74 (31 trades); 0.65: -14.05 (21); 0.75: +17.92 (7). Chosen 0.75 on train only.
OOS base: 105 raw opportunities, 13 executed trades, gross -25.02, fees 8.71, net -33.73, closed-equity drawdown 33.73, 0/104 days >= $50.
OOS independent volatility guard (skip signal candle range outside 0.5–2.0 x median TR): 105 raw opportunities, 10 executed, gross -23.51, fees 6.70, net -30.21, closed-equity drawdown 30.21, 0/104 days >= $50.
Decision: REJECT both as trading strategies. Guard reduced losses by $3.52 but does not produce positive expectancy. No demo or real orders. Target $50 net per trading day remains unmet. Private CSV excluded from repository.
