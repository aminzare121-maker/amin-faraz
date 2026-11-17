# V5 London opening range — 2026-11-17
Dataset: Eplanet M15, 23643 rows, private and NOT committed. 60/40 chronological split at index 14185.
Hypothesis: first London hour (07:00 UTC) defines liquidity boundary; a crossing candle 08:00–10:59 UTC predicts continuation over next five bars. Enter next bar open, exit fifth bar close; one trade/day.
Costs assumed: $1.46 per 0.01 lot roundtrip, including $0.86 fees/spread and $0.60 modeled slippage; NOT broker verified.
Train: 135 trades, gross +276.03, cost 197.10, net +78.93, closed-equity drawdown 311.88, 4 days >= $50.
Holdout: 100 trades, gross -80.78, cost 146.00, net -226.78, drawdown 286.06, 0 days >= $50.
Independent risk filter: opening-range/ATR <= training median 1.509654, sizing 1% of equity / (2 ATR), rounded down to 0.01-lot increments; holdout 69 candidate opportunities but ZERO tradable under risk cap. Zero trades is NOT profitability.
Limitations: no intrabar stop execution, no broker fill validation, no tick-based intrabar drawdown; cost is scenario. REJECT for demo. No live orders.
Local executable artifact: v5_opening_range.py; local result JSON: v5_opening_range_results.json. Neither private dataset nor credentials are published.
