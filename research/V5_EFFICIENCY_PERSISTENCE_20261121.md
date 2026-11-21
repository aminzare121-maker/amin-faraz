# V5 efficiency persistence — 2026-11-21
Research only; NOT approved for MT5 demo.
Hypothesis: directional efficiency over 12 completed M15 candles may proxy persistent order flow; 4-bar holding.
Dataset: Eplanet_M15_20251105_20261105_merged.csv, 23643 bars; chronological 60/40 split; 9458 out-of-sample bars, 104 trading dates.
Rules: absolute 12-bar net change / sum absolute 12 close changes >0.58; absolute net >1.7 ATR20; latest absolute close change <1.4 ATR20. Enter next bar open, stop 2 ATR, 4 bars max; risk 1% of changing equity, lot floored to 0.01 increments, minimum 0.01. Conservative stop collision.
Costs modeled: $0.46 per ounce round trip plus $10 per lot; not verified broker fills.
Baseline OOS: 957 signal opportunities; 910 minimum-lot rejections; 20 executed trades; gross winning +46.25, gross losing -48.83, costs 11.20, net -13.78 USD; max closed drawdown 41.42; 0 of 104 days >= $50.
Independent early adverse-exit variant: 957 opportunities; 919 minimum-lot rejections; 17 trades; gross wins +21.17, gross losses -50.61, costs 9.52, net -38.96; max closed drawdown 50.48; 0 days >= $50.
Both rejected. Note OHLC bars cannot prove tick-level stop order or floating drawdown. Minimum-lot infeasibility dominates.
Local executed script SHA256 012102efc5080ded014c0e7eb20e904682890cf8040a0897fc500132d09a78ab. JSON SHA256 8f5a6dfde457d6b7b451d7c93badae5a02611d0d88503770a6a9bdf81b686321.
Private source data NOT committed.