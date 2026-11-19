# V5 independent compression participation comparison — 2026-11-19

Private Eplanet CSV SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23643 bars; no private rows committed.

Variant distinct from earlier compression test: prior 8-bar high-low <= selected threshold times lagged ATR32; breakout is candle CLOSE beyond prior range in candle direction, next-bar open execution; stop 0.9 ATR, target 1.6R, time exit after 6 bars. Conservative SL-first intrabar fill; dynamic 0.01-0.10 lots with planned $10 stop risk; initial $1000; assumed 100 oz/lot, estimated $0.65/oz roundtrip friction.

Training first 14185 bars: selected 2.5 threshold from 2.5/3/3.5/4 on training only; best training -$518.46 over 544 trades. Holdout last 9458 bars (104 trading days): BASE 902 opportunities, 543 trades, gross +$3.29, cost $385.45, NET -$382.16, closed DD $420.98, approx intrabar DD $423.34, 0/104 days >= $50. GUARD (trigger tick volume >= prior 32-bar median AND trigger range <=2 ATR): 902 opportunities, 233 trades, gross -$239.18, costs $163.80, NET -$402.98, closed DD $434.65, approx intrabar DD $435.70, 0/104 days >= $50.

Rejected both. Guard worsens net. Costs are estimated; actual Eplanet fills, margin, swaps and tick path unavailable. No demo or real orders. Local executable and ledger created but source code not yet committed to this branch.
