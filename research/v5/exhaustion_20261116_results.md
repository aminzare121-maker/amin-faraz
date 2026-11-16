# V5 exhaustion hypothesis — 2026-11-16
Dataset: private Eplanet_M15_20251105_20261105_merged.csv (NOT committed), 23,643 M15 bars.
Signal: closed candle range > 2 * rolling ATR32, tick volume above preceding 32-bar median, close in top/bottom 15% of range. Fade next bar at open, exit next bar close or intrabar stop 1 ATR; skip time gaps.
Risk: starting 1000 USD, 0.5% equity target, minimum .01 lot and maximum .10 lot, 100 oz/lot assumption.
Costs: recorded spread points * .01 USD + .30 USD each side slippage; commission UNKNOWN, assumed zero. Conservative intrabar stop priority. Bar-based backtest, not tick execution.
Chronological split 70/30 at 2026-07-21 06:30 UTC; NO parameter optimization.
Training: 380 trades, net -80.70 USD, 177 wins, 203 losses, closed-trade max drawdown 320.32 USD; 3 days >=50 USD.
Out-of-sample: 202 trades, net -142.85 USD, 85 wins, 117 losses, closed-trade max drawdown 238.11 USD; ZERO days >=50 USD.
Rejected: does not meet required >=50 USD net per trading day. Do not activate in MT5 demo.
Limitations: broker contract size/commission and true tick fills not independently verified; stop/gap handling simplified. This is an exploratory historical backtest, not observed demo performance.
