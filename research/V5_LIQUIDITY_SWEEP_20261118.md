# V5 liquidity sweep reversal — 2026-11-18
Research only. Private Eplanet M15 23643 bars; chronological 60% train / 40% holdout (104 trading dates).
Hypothesis: failed break of previous 12-bar high/low reverses on next bar. Completed OHLC only. Variable lot 1% equity risk, min 0.01 max 0.15, 1.7R target, six bars max hold, stop-first. Cost estimate: spread*0.01 USD/oz + 0.30 USD/oz slippage + 7 USD/lot.
Training wick ratios 0.25: -459.48 USD (706 trades), 0.40: -463.84 (526), 0.55: -329.93 (408); all negative. Selected 0.55 by train net.
Holdout base: 915 signal opportunities, 361 executed, gross -267.01 USD, costs 292.20, net -559.21, max closed-equity drawdown 565.67, 0/104 days >= +50 USD.
Independent volatility guard rejects signal bar range >2 ATR: 915 signal opportunities, 363 executed, gross -254.58, costs 293.57, net -548.15, max closed-equity drawdown 554.62, 0/104 days >= +50 USD. Guard changes trade sequencing, so trade counts can increase.
FAIL: no edge, no demo activation. No tick-level verification, broker fees estimated. Local reproduction script and JSON generated, NOT committed in this report. No private market data committed.
