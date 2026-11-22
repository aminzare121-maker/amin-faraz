# V5 failed breakout — 2026-11-22
Data: private Eplanet M15 CSV, 23,643 rows. Data is NOT committed.
Hypothesis: price breaks previous 20-bar extreme intrabar but closes back inside, suggesting failed liquidity sweep. Trade opposite direction at next bar open.
Out-of-sample chronological split 60/40, starts 2026-06-15 05:45 UTC. No fitted parameters. 1% risk cap, 0.01 lot minimum, 100 oz/lot assumption, stop-first OHLC convention. Cost estimate $0.63 per ounce round trip.
Base: opportunities 312, trades 183, gross gains $597.98, gross losses -$619.60, costs $119.07, net -$140.69, max closed drawdown $196.73, 0 days >= $50.
Independent volatility guard: opportunities 318 (candidate count differs because sequential trade blocking), trades 130, gross gains $439.12, gross losses -$392.51, costs $84.42, net -$37.81, max closed drawdown $117.21, 0 days >= $50.
Both rejected. Guard reduces loss but not to profitability. Intrabar drawdown and broker-specific contract/costs unverified. No live or demo orders.
Run: put private CSV alongside script and execute python research/v5_failed_breakout_20261122.py from repository root.
