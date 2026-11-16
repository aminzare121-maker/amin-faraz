# V5 conditional hourly persistence — 2026-11-16

Research only; no orders. Private Eplanet M15 CSV (23,643 rows) was analyzed locally, not uploaded.

Hypothesis: the final completed 15-minute candle of a UTC hour predicts continuation during the next hour, conditional on hour. Select best hour from first 60% only (minimum 12 filled trades, positive net); hold at most four bars, 1.5x median true range stop. Stop-first OHLC, entry next open. Risk target 1% equity with 0.01 lot floor; skip unaffordable trades. Cost estimate: 0.26 USD/oz spread + 0.60 USD/oz round-trip slippage; 100 oz/lot. Commissions and actual broker fills unverified.

Training 14,185 bars: best hour 17 UTC; 154 signal opportunities, 36 fills; gross +158.60, costs 31.58, net +127.02 USD; closed-equity drawdown 32.74.

Out-of-sample 9,458 bars / 104 trading days: 103 opportunities, 17 fills; gross -34.04, costs 15.59, net -49.63 USD; max closed-equity drawdown 57.14; zero days >= +50 net. Protective filter (signal body <=1.1 median TR and bar range <=1.8 median TR): 103 opportunities, 16 fills; gross -8.38, costs 14.68, net -23.06 USD; drawdown 43.87; zero days >= +50. Lots were 0.01 in both cases despite variable sizing code.

Conclusion: rejected for demo. Protective filter lowers loss but does not create positive edge. Historical OHLC cannot measure intrabar equity drawdown, broker tick execution, or unmodeled commission. Code and JSON generated locally; this report does not assert their GitHub publication.
