# V5 reopening gap fade — 2026-11-17
Data: private Eplanet M15 CSV, 23,643 rows, SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. Data is not committed.
Hypothesis: gaps following >30 min interruption may mean revert after liquidity replenishment. Entry at next candle open, stop at max(prior 96-bar median range, 0.75 gap), time exit after four bars, worst stop gap fill, risk cap 1% and lot rounded down to 0.01. Round-trip cost assumption $1.46/oz, 100 oz/lot; not broker-verified. No lookahead in entry signal.
Train first 60% (ending 2026-06-15 05:30 UTC); OOS remaining 40% (starting 2026-06-15 05:45 UTC).
Training net by threshold gap/ATR: 0.5=-127.69; 1=-30.38; 1.5=-7.73; 2=-7.67 USD. Threshold 2 chosen on train only.
OOS: 104 UTC dates, 5 opportunities, 0 executed trades due to size/risk/continuity constraints. Gross $0, cost $0, net $0, closed-equity drawdown $0, zero days >=$50. Guard requiring gap >= 3x estimated roundtrip cost: also 0 trades.
Decision: reject as income engine; guard cannot be judged on zero executions. No demo or live trading. Need actual broker contract, spread and commission verification before financial acceptance.