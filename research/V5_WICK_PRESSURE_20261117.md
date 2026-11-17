# V5 wick-pressure holdout — 2026-11-17
Private dataset: Eplanet M15 23,643 bars, chronological 60/40 split at 14,185. Not committed.
Hypothesis: candle close in outer 20% with opposing rejection wick; enter next bar open, stop at 1.15x prior 32-bar median range, exit after two bars. Independent spread/range/risk guard. No delayed signals.
Train: 676 opportunities; 287 trades; gross +21.39; estimated cost 502.24; net -480.85; closed DD 507.08.
Holdout baseline: 441 opportunities; 355 trades; gross +116.21; estimated cost 589.84; net -473.63; closed DD 524.43; intrabar DD estimate 533.71; 1 day >= $50.
Holdout guard: 441 opportunities; 82 trades; gross -55.93; cost 119.72; net -175.65; closed DD 189.02; intrabar DD estimate 193.11; 0 days >= $50.
Assumptions: initial equity $1,000; variable 0.01-0.02 lots baseline, 0.01 guarded; $1.46/oz roundtrip assumed; 100oz/lot; stop-first OHLC. Guard risk 0.75% versus baseline 1.5%. No broker fill validation.
Decision: REJECT both for MT5 demo. Risk guard reduced losses but has no standalone positive edge. No real orders.
Reproduce: python research/v5_wick_pressure.py --csv /private/path/Eplanet_M15_20251105_20261105_merged.csv
