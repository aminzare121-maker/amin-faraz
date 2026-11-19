# V5 — Gap reversion audit, 2026-11-19
Hypothesis: abnormal interbar opening gaps are temporary repricing and may reverse by the same bar close. Signal uses current open, previous close, and lagged rolling baseline; no COT/sentiment.
Data: private Eplanet merged M15 CSV (23643 bars); do NOT commit data. Chronological 60/40 split. Capital $1000. Variable lots (0.01–0.10, $5 ATR proxy sizing), one-bar holding. Cost assumption $0.46 per 0.01 lot roundtrip (NOT broker verified). No intra-bar stop, no margin/tick execution simulation.
| Out-of-sample (104 trading days) | Base | Prior-ATR risk guard |
|---|---:|---:|
| Raw signals |293|293|
| Executed candidates |6|6|
| Gross USD |-2.65|-2.65|
| Costs USD |2.76|2.76|
| Net USD |-5.41|-5.41|
| Max closed-equity DD USD |10.08|10.08|
| Days net >= $50 |0|0|
Train: 522 raw signals, 3 eligible trades, +$6.25 net. Guard changes nothing. Rejected: insufficient opportunities and negative OOS net. No demo/live orders. Reproduce: python research/v5_gap_reversion_audit.py /private/path/Eplanet_M15_20251105_20261105_merged.csv.
