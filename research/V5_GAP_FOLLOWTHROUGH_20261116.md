# V5 gap follow-through | 2026-11-16
Data: Eplanet M15, 23643 rows, 60/40 chronological split (14185/9458). Private data NOT uploaded.
Hypothesis: gap after >=30min inactivity, 0.35-2.0x preceding 32-bar median range; enter at next open in gap direction. Stop 1x range, target 1.5x range, maximum 5 bars. Worst-case stop first when both touched. Equity-based lot 1% risk rounded down to 0.01; skip below minimum. Contract 100oz/lot; assumed roundtrip cost 0.86 USD/oz (spread .26 + slippage .30 each way).
Independent risk filter: preceding candle range <=1.8x reference and gap <=4 hours.
TRAIN baseline: 101 signals, 50 trades, gross -12.91, costs 46.44, net -59.35, max closed drawdown 83.00, days >=$50 0/156. Filter: 40 trades, gross -31.70, costs 37.84, net -69.54, DD 88.14.
OUT-OF-SAMPLE baseline: 46 signals, 41 trades, gross -71.85, costs 38.70, net -110.55, DD 110.67, days >=$50 0/104. Filter: 32 trades, gross -71.15, costs 31.82, net -102.97, DD 103.09. Lots .01-.02.
Result: rejected for demo. Risk filter reduces OOS loss but not profitable. Candle-based model; no measured execution, no intrabar DD. No live or demo orders.
