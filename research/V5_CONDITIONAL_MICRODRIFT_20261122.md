# V5 conditional microdrift: strict no-trade result (2026-11-22)

Hypothesis: directional persistence over the next M15 bar depends on the preceding candle direction and 4-hour UTC liquidity bucket. Training data only determines admissible cells. A separate high-ATR guard was evaluated.

Dataset: private Eplanet M15 CSV (NOT committed), 23643 rows; train valid rows 8469; OOS valid rows 5799; OOS from 2026-06-15, 104 observed trading dates. Start capital $1000, variable lots (1% ATR sizing, .01 increments, max .30), assumed round-trip cost $0.56/oz, 100oz/lot. No tick-level execution or guaranteed stop loss.

Eligibility: prior candle body between 0.25 and 1.5 ATR(20), next-bar continuous 900 seconds. Cells are UTC 4-hour bucket x candle direction. Minimum 80 training observations and training expected net > $0.25/oz. **None of 12 cells passed**: training net expectation ranges from -$0.1289/oz to -$0.9883/oz. ATR guard training 75th percentile = 13.0935.

OOS baseline: 0 eligible opportunities, 0 trades, gross profit $0, gross loss $0, costs $0, net $0, max closed DD $0, days >= $50: 0/104. Independent ATR guard: identical (no eligible trades). This is not a profitable strategy: it is a correctly rejected hypothesis. No MT5 demo or live trades.

Local executable and JSON output: v5_conditional_microdrift_20261122.py / .json (not uploaded to GitHub). Limitations: fixed estimated costs, M15 bars, no verified fills or intrabar drawdown; data is private. Never infer success from zero drawdown with zero trades.
