# V5 - M15 cross-feed audit

This is a research-only module for XAUUSD. NOT the original V5 trading strategy, an MT5 expert advisor, a trading signal, or evidence of $50/day profits.

## Data and measured result

- Eplanet input: Eplanet_History(3).zip, M15.
- Public external candidate: GitHub Gen144-D/EA-Gold-for-backtesting-and-Strategy-, file XAUUSD_2026_03.csv. Underlying broker UNKNOWN.
- Clock calibration: March 2 and March 9, 2026; offsets 0 and +60 minutes respectively.
- Held-out pairs: March 3-6 and March 10-20, 2026 (13 market dates).
- Same completed M15 candle direction matched 1116 of 1127 pairs, or 99.02%.
- Predicting NEXT M15 direction with external previous candle direction: 47.94% on 1114 pairs, versus 47.49% for Eplanet previous direction.
- Predicting NEXT contiguous 60 minutes: 48.98% on 1078 pairs, versus 48.42% for Eplanet previous direction.
- Only 11 feed disagreements were eligible for next-M15 comparison. No statistically established incremental prediction.
- Historical dates were already inspected in prior research. The test is NOT pristine forward proof.

## Decision

Approved: M15 timestamp alignment, supplementary data-quality audit.
NOT approved: new BUY/SELL signals, lot or stop modification, live execution, claim of independent price feed, claim of profitability.

## Command line

Install pandas and numpy in your Python environment.
1. python research/v5_crossfeed/v5_crossfeed_gate.py --ep Eplanet_History.zip --external external.csv --out research_out
2. python research/v5_crossfeed/v5_incremental_information.py --ep Eplanet_History.zip --holdout research_out/calibrated_holdout.csv --out research_out
3. From research/v5_crossfeed: python -m unittest -v test_crossfeed.py

external.csv columns: time,external_dir (up/down/flat or 1/0/x). Timezone/source timestamp semantics must be verified first.

## Motor constraints

Initial capital USD 1000, dynamic lot based on actual broker specs, demo-only research, no unapproved real orders.
Historical order-flow or traded futures volume would be meaningfully new information. A second copy of completed M15 candle direction is mostly redundant.
Original V5 entry/exit logic must be recovered before claiming improvement to the requested V5 motor.
