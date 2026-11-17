# V5 absorption / opportunity-frequency audit (2026-11-17)
Source: private Eplanet M15 CSV (not committed). SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604
Local executable: v5_conditional_autocorr.py; full code and ledger available as run artifacts.

Hypothesis: exceptionally high tick activity in a narrow, directional M15 bar may indicate absorption followed by continuation. Signal uses only completed candles. Entry next candle open, stop 1.5 x previous 96-bar median range, target 1.5R, timeout 4 candles. Size risk 1% equity, floor to 0.01 lots; assumed XAUUSD contract 100 oz/lot. Estimated all-in round-trip cost $1.46/oz. Split first 60% / last 40% (OOS).

OOS 2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC, 23643 total bars.
Base: 1 opportunity, 1 simulated trade, gross +$14.66, cost $1.46, net +$13.20, closed drawdown $0, worst intratrade adverse $0.95; 0 days >=$50.
Independent risk guard (cost/stop <=12%, spread <= preceding 96-bar median): 1 opportunity, 0 trades, $0 gross/cost/net.
Decision: FAIL insufficient opportunity frequency and $50/day target. No demo or real trading. Execution/spread costs are estimates; candle OHLC does not establish tick-level fill accuracy.
