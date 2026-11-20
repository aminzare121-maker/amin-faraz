# V5 directional efficiency / pause — 2026-11-20

New hypothesis: directional 16-bar efficiency >0.42, 3-bar range / (3 x 32-bar median TR) <1.1, and close on the appropriate side of prior 16-bar midpoint. Signal at candle close; enter next open. 12-bar horizon, 1.5x TR stop, 1.8R target; stop-first conservative intrabar fill. 60/40 chronological split, 23,643 Eplanet M15 candles. CSV SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. No private CSV committed.

Cost assumption: $87 round trip per 1 lot, 100 oz/lot. Starting $1000, variable lot floor to 0.01, capped 0.1, risk budget min($10,1% equity). Stop-first; costs estimated, not verified tick execution.

TRAIN: 2070 signals; base 136 trades, gross $194.66, costs $121.80, net +$72.86, max closed drawdown $121.80, 0/156 days >=$50. Guard identical.

HOLDOUT: 1526 signals; base 158 trades, gross $233.52, costs $137.46, net +$96.06, max closed drawdown $119.54, 1/104 days >=$50. Daily-loss guard ($15): 156 trades, gross $200.26, costs $135.72, net +$64.54, drawdown $151.07, 1/104 days >=$50.

Interpretation: slight positive out-of-sample aggregate, but fails $50 net on every trading day and guard worsens result. NO DEMO DEPLOYMENT. This report is not evidence of tick-level execution or robustness. Local Python source and JSON produced separately; code upload to GitHub remains outstanding.
