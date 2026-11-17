# V5 shock drift — 2026-11-17

Hypothesis: after a directional M15 shock (body >=1.8x prior 48-bar median range, body/range >=0.72) aligned with prior 16-bar price trend, urgent repricing may persist. Enter next candle open; SL=max(1.2x reference,$2/oz), TP=1.5R, max 5 bars. Stop-first intrabar; adverse gap opens honored. Independent cost guard: reject if assumed roundtrip $1.46/oz exceeds 15% of stop distance. No late data.

Private Eplanet CSV 23,643 rows SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604 (NOT committed). Chronological last 40% OOS 2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC. $1,000 start; risk-sized lot floor to 0.01; 100 oz/lot; assumed $1.46/oz roundtrip (not verified Eplanet).

Baseline: 136 opportunities, 105 simulated trades, gross -$16.43, cost $153.30, net -$169.73, closed drawdown $193.59, 61 active days, 0 days >=$50, lot 0.01.

Independent cost guard: 144 opportunities observed while scanning (different occupied bars), 3 simulated trades, gross +$16.10, costs $4.38, net +$11.72, closed drawdown $11.44, 3 active days, 0 days >=$50, lot 0.01. Tiny sample, not proof of positive edge. No MT5 activation.

Implementation run locally: v5_shock_drift_20261117.py; detailed results v5_shock_drift_results.json. Neither private CSV nor trade ledger published. The code itself is not yet committed. OHLC intrabar ambiguity, fixed assumed cost, and unverified contract specs limit validity. Both configurations FAIL required $50 net/day gate.
