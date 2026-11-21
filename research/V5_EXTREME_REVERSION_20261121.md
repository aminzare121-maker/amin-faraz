# V5 impulsive candle fade — 2026-11-21

Research only. Source data: private Eplanet M15 CSV, 23,643 candles; not committed.

Hypothesis: after a candle body exceeding 1.6 times the prior 24-bar ATR, fade direction at next bar open. Exit after 3 bars or stop 1.5 ATR. Risk budget 1% of current equity, 100 oz/lot, 0.01 minimum lot, $0.45/oz estimated round-trip fees. Optional gap guard rejects next-open gap above 0.12 ATR. 60% chronological trading days training, 40% holdout. OHLC conservative stop assumption, no tick data.

Train (155 days): base and guard 479 opportunities, 88 trades, gross gains 388.01, gross losses -307.74, costs 40.05, net +40.22, max closed drawdown 106.55, zero days >= $50.

Holdout (104 days): base 329 opportunities, 159 trades, gross gains 830.56, gross losses -588.60, costs 72.90, net +169.06, max closed drawdown 170.71, 1 day >= $50. Guard: 328 opportunities, 159 trades, gross gains 830.56, gross losses -589.27, costs 72.90, net +168.39, max closed drawdown 171.38, 1 day >= $50.

**Decision: reject both for MT5 demo.** The 50 USD net on every trading day requirement fails. No live or demo orders. Code and JSON remain local artifacts, not yet pushed to GitHub. This commit is a research record only; independent GitHub execution not verified.
