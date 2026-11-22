# V5: Reopen gap mean-reversion research (2026-11-22)
Dataset: private Library `Eplanet_M15_20251105_20261105_merged.csv` (not committed).
Local executable: `v5_gap_dislocation_20261122.py` (available as conversation artifact; not yet committed).
Hypothesis: price gaps after at least 30 minutes without a candle reverse after the first M15 bar. Entry next bar open, exit close of fourth bar after gap.
Filter: gap size 0.2–3.0 of lagged 20-bar ATR, next bar contiguous, four-bar exit contiguous. Train before 2026-06-15; holdout on/after.
Training: 124 opportunities; mean gross minus estimated $0.56/oz roundtrip = **-$3.8979/oz**. Gate requires >=30 opportunities and mean net >$0.20/oz; FAILED.
Holdout: 69 qualifying raw opportunities across 104 days. Gate rejected trading: **0 trades**, gross profit 0, gross loss 0, costs 0, net 0, max closed drawdown 0, days with >=$50 net 0. Independent spread/gap-size guard was not activated because baseline failed training.
Sizing if gate passed: variable 0.01-lot steps, 1% equity divided by 20-bar ATR times 100 oz/lot, max 0.30 lot. This is not a true stop-loss and must not be used live.
Assumptions: $0.56/oz all-in estimated cost; M15 cannot verify fills or intra-candle drawdown. No MT5 demo/live order submitted. Research REJECTED.
