# V5 directional path efficiency — 2026-11-16
Research only; **rejected for MT5 demo**. Input: private Eplanet M15 CSV (not committed), 23,643 candles, 60/40 chronological split (14,185/9,458).
Data SHA256: `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`.
Hypothesis: unusually efficient directional movement over six completed M15 bars indicates order-flow persistence. Enter next bar open, exit two bars later at open. Gate independently excludes atypical median ranges and recorded spread >26.
Assumptions: 100 oz per lot; $0.86/oz estimated round-trip execution cost; variable lot sizing with risk budget and minimum .01 lot; no tick-level execution or intrabar drawdown; no realized broker fills.
| Segment | Variant | Trades | Gross USD | Estimated cost USD | Net USD | Max closed-equity DD USD | Days >=$50 | Days |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Signal | 124 | 89.55 | 106.64 | -17.09 | 59.83 | 0 | 156 |
| Train | Risk gate | 96 | 65.09 | 82.56 | -17.47 | 42.84 | 0 | 156 |
| OOS | Signal | 110 | -53.66 | 94.60 | **-148.26** | 183.00 | 0 | 104 |
| OOS | Risk gate | 0 | 0 | 0 | 0 | 0 | 0 | 104 |
OOS opportunity days: signal 48, gate 0. All filled simulated positions 0.01 lot; dynamic sizing rule did not result in variation. The gate's zero loss reflects zero trades, not success. OOS gross is negative before fees. No trading authorization. Code: `research/v5_path_efficiency.py`; run locally with CSV path as positional argument. The gate and signal are evaluated separately. No private data published.
