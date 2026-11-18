# V5 participation-confirmed impulse — 2026-11-18

**Research only; NO MT5 demo or live trading.**

Hypothesis: an unusually high tick-volume directional M15 candle may have continuation because of elevated participation. Signal requires volume > 1.7 × prior 48-bar median, body > 1.2 × prior 32-bar median true range, and body/range > 0.7. Direction follows candle body. Execute next open, stop 1.2 × volatility (minimum $2/oz), target 2× stop, maximum 9 bars, stop-first intrabar. Capital $1000; risk 1% equity; 0.01 lot steps; 100 oz/lot; estimated $1.46 roundtrip per 0.01 lot. Guard rejects signal when spread > 26 points or next-open gap > 0.15 × volatility.

Input: private Eplanet M15 CSV, 23,643 rows; chronological 60/40 split. SHA256 available in local JSON; raw CSV intentionally excluded.

| Sample | Variant | Opportunities | Trades | Gross USD | Estimated costs USD | Net USD | Max closed DD USD | Trading days ≥ $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 188 | 73 | -99.54 | 108.04 | -207.58 | 220.74 | 0/156 |
| Train | Guard | 191 | 57 | -100.67 | 84.68 | -185.35 | 211.76 | 0/156 |
| OOS | Base | 101 | 75 | +9.73 | 112.42 | -102.69 | 118.79 | 0/104 |
| OOS | Guard | 112 | 0 | 0 | 0 | 0 | 0 | 0/104 |

Different opportunity counts arise because trades lock out subsequent signals; guard variant can inspect more signals.

**Decision:** Reject for demo. Guard reduces losses by rejecting all OOS trades, not by producing profitable trades. The $50 net/day objective is unmet. Commission/spread/slippage are modeled estimates, not verified Eplanet fills; intrabar equity drawdown is not measured. Local runnable script: v5_volume_impulse_20261118.py; local full ledger: v5_volume_impulse_20261118_results.json. These local artifacts are not part of this commit.
