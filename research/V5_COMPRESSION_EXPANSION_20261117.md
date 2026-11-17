# V5 compression-expansion — 2026-11-17
New hypothesis: an eight-candle narrow range followed by a closing breakout may represent accumulated orders and short-term continuation. No COT/sentiment input.

Source: private Eplanet_M15_20251105_20261105_merged.csv (23,643 M15 rows); NOT committed. Split: first 60% development, last 40% out-of-sample, 2026-06-15 05:45 UTC to 2026-11-05 10:45 UTC. No parameter optimization in this run.

Rules: median previous 32 ranges as volatility reference, prior 8-bar high/low, width 0.5 to 2.0 times reference; breakout by completed close, entry next open, stop max(0.8*reference, $2/oz), target 1.6x stop, max 7 bars. Gap stops use open, simultaneous stop/target resolved stop first. Equity starts $1,000; volume 0.01–0.02 lots, position sizing ~1% equity; 100 oz/lot. Roundtrip cost assumption $1.46/oz (not broker verified). No concurrent positions.

Out-of-sample baseline: 340 signals, 269 executed, gross -$45.55, estimated costs $417.56, net -$463.11, closed-equity drawdown $506.30, 101 active days, zero days >=$50 net.
Independent loss-control filter (reject breakout candle range >1.5x reference or body >1.2x reference): 331 signals, 221 executed, gross -$5.54, costs $350.40, net -$355.94, closed-equity drawdown $368.55, 94 active days, zero days >=$50 net.

Caveats: spread is constant 26 in CSV; point-size and Eplanet actual execution costs unverified. No tick-level intrabar drawdown or execution fidelity established. These are OHLC simulation results, NOT MT5 forward results. The filter reduces losses but does not establish profitability. Both variants REJECTED for demo activation. No real trades.
Local reproducible code: v5_compression_expansion.py and result JSON generated during this run; code not yet committed.