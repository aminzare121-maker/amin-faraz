# V5 hourly directional drift — 2026-11-18

Hypothesis: dealer inventory unwind could produce directional drift during a fixed UTC hour. Different from previous price-pattern signals.

Data: private Eplanet M15 CSV, 23,643 bars, never committed. Chronological split 60% train / 40% OOS (index 14,185). Choose best of 24 hours × 2 directions using train net PnL, minimum 40 train trades. Selected 14:00 UTC long, training net +$37.88 on 155 trades.

Execution simulation: first bar of hour at its open, max four M15 bars, stop $8/oz, target $12/oz; if SL and TP both touched in one bar, assume SL first. Variable lots in 0.01 increments, 1% equity risk and 0.10 lot cap, 100oz per lot. Costs: observed spread points × $0.01/oz + $0.30/oz roundtrip slippage + $7/lot commission. Cost assumptions not broker-confirmed. No lookahead in selection, but intrabar ordering is unknown.

OOS 104 trading days: 103 opportunities / 103 trades; gross +$11.66, costs $70.90, net -$59.24; max closed-equity drawdown $82.68, estimated intrabar drawdown $90.24; 0/104 days net >=$50.

Independent risk-control filter: skip if observed spread >26 points. 103 opportunities, 0 trades, net $0. Not an edge; the filter removes all opportunities.

Decision: REJECT, do not activate MT5 demo. The local reproducibility script and JSON trade log are held as conversation artifacts, not committed here. No private Eplanet data published; no live orders placed.
