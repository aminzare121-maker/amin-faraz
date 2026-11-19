# V5 — 3-bar exhaustion reversal — 2026-11-19
Source: private Eplanet M15 CSV, SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23643 bars. No private data uploaded.
Hypothesis: 3-bar directional displacement > ATR(32) * threshold, then last candle close-location indicates rejection. Reverse on next open. Exit by 1.2 ATR stop, 1.8 ATR take profit, or 4 bars.
Training first 14185 bars; OOS last 9458 bars (104 trading days). Threshold selected on training only among 1.5, 2, 2.5, 3 ATR: 2.5. Training net -14.04 USD (20 trades).
Initial equity 1000 USD; dynamic lot 0.01-0.10 with $10 planned stop risk; assumed XAUUSD 100 oz/lot, round-trip friction $0.65/oz.
OOS BASE: 60 opportunities, 29 trades, gross -8.78, cost 18.85, net -27.63 USD, closed-equity max drawdown 59.40, 0/104 days >= $50 net.
OOS volatility GUARD (current candle TR/ATR between 0.45 and 1.8): 60 raw opportunities, 16 trades, gross 17.17, cost 10.40, net +6.77 USD, max drawdown 15.55, 0/104 days >= $50.
CAVEAT: guard was not independently selected on training; its OOS improvement is exploratory, not independently validated. Costs estimated; actual broker commissions, swaps, margin and intrabar tick fills unverified. A gap during a position is not fully simulated. Both variants FAIL $50 net per trading day requirement; no demo or real orders.
Local reproducibility script: v5_exhaustion_reversal_20261119.py and results JSON produced during this run; source script is not yet committed to GitHub.
