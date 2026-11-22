# V5 efficiency-horizon, 2026-11-22
Data: private Eplanet M15 23,643 candles, 2025-11-05 to 2026-11-05. Never commit data.
Hypothesis: high 8-bar directional efficiency (>=0.7) may persist long enough to overcome transaction costs. Entry next bar open, 2/4/8/12 bar exit horizons; training before 2026-06-15; OOS >=2026-06-15 (104 days). No late data.
Training edge per oz after assumed $0.56/oz cost: 2 bars -0.01376 (n=1168); 4 bars -0.01224 (n=1134); 8 bars -0.58543 (n=1068); 12 bars -0.42610 (n=1033).
Gate: at least 150 training observations AND >$0.30/oz average training edge. NONE PASS. Authorized demo: zero trades.
OOS diagnostic only, best TRAIN horizon 4 bars, $1000 reset, variable lots, 1% equity ATR risk proxy, 100oz/lot, 0.01 lot increment, conservative stop-first OHLC:
Baseline: 875 opportunities, 290 trades, gross profits $1098.95, gross losses -$889.54, estimated costs $169.68, net +$39.73, max closed DD $129.47, 1/104 days >=$50.
Independent range/spread guard (range/ATR <=1.5, spread<=35): 875 opportunities, 213 trades, gross profits $721.71, gross losses -$658.52, estimated costs $120.40, net -$57.21, max closed DD $228.94, 1/104 days >=$50.
Guard worsens net and drawdown. Diagnostic positive net is NOT authorization; training edge fails and daily objective fails.
Limitations: M15 bar stop ordering uncertain, gap slippage not modeled, cost estimated, broker point value/contract size must be verified. Full local simulator and JSON were generated in the run, not committed; repository source is training-only reproduction. No live or demo trades.
