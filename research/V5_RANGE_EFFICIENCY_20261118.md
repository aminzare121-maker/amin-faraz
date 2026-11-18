# V5 directional efficiency research — 2026-11-18

Hypothesis: a high body/range candle (>=0.8) with range >=0.9 ATR(20) predicts continuation over the next four M15 bars. Direction uses only the completed signal candle; enter at next open. Split first 60% training / last 40% holdout. Initial equity $1000; risk 1% of current equity; lots floored to 0.01 and capped at 0.15; SL 1.2 ATR (minimum $2/oz); TP 1.5R; stop-first if both touched in same OHLC candle. Costs: recorded spread points * 0.01 USD/oz + $0.30/oz slippage + $7/lot round-trip. Guard: suppress range >2.5 ATR or spread >35 points. All numbers simulated, not broker-confirmed.

Training (156 trading days): threshold 0.6 net -$346.97, 0.7 net -$310.08, 0.8 net -$294.41. Threshold 0.8 selected without using holdout.

Holdout (104 trading days): base 785 signals, 222 trades, gross -$192.66, costs $168.49, net -$361.15, max closed-equity drawdown $374.25, 0 days >=$50. Guard 785 signals, 227 trades (suppression changes overlap scheduling), gross -$135.98, costs $159.26, net -$295.24, max closed-equity drawdown $328.63, 0 days >=$50. The guard reduces losses by $65.91 but remains loss-making.

Decision: REJECT. No demo/live execution. Limitations: no tick replay, intra-bar stop-first approximation, approximate fees, no verified broker contract specs, closed-equity rather than exact floating drawdown. Data private; do not commit CSV or trade ledger.

The executable local research script is v5_range_efficiency_20261118.py, not yet committed in this branch.
