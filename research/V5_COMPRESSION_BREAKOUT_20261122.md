# V5 compression breakout research — 2026-11-22

Private Eplanet M15 dataset: 23,643 rows, NOT committed. Hypothesis: after the prior 8-bar high-low range is at most 2.5 times lagged 20-bar true-range ATR, trade in direction of a close beyond the prior 8-bar extreme. Enter next bar open; exit open four bars later. Exclude gaps. Protective variant additionally excludes signal bars whose true range is >=1.25 times ATR. This filter is a separate risk-control role.

Train before 2026-06-15 UTC; OOS from 2026-06-15. Gate: at least 100 training observations and mean net per ounce > $0.30. Baseline train 1059 observations, -$0.7090/oz; guarded 574, -$0.8680/oz. BOTH FAIL.

OOS diagnostics ONLY, reset capital $1000, 1% ATR-based sizing proxy, 0.01 lot increments, 0.10 cap, 100 oz/lot assumed. Roundtrip costs: recorded spread points * $0.01 plus $0.30/oz. Baseline: 803 opportunities, 32 non-overlap trades, gross profit $85.76, gross loss -$134.83, estimated costs $24.29, net -$73.36, max closed drawdown $109.64, 0 days >=$50. Guard: 483 opportunities, 15 trades, gross profit $50.95, gross loss -$39.76, estimated costs $11.62, net -$0.43, max closed drawdown $34.74, 0 days >=$50. Authorized trades ZERO.

The guard reduced diagnostic loss but has no positive demonstrated edge. Costs and contract size assumed; no intrabar stops or tick-level drawdown. No MT5 demo or live orders. Reproduction script remains local until its full source is committed and independently tested.
