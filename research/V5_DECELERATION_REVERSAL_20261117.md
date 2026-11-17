# V5 — Decelerating impulse reversal (2026-11-17)

Research-only, no MT5 orders. New hypothesis: three consecutive same-direction candles with sequentially declining real bodies may indicate exhausted aggressive order flow, followed by a 3-bar mean-reversion opportunity.

Dataset: private Eplanet M15 merged CSV, 23,643 bars. Chronological 60/40 split; holdout starts 2026-06-15 05:45 UTC. Private dataset is NOT committed.

Signals use only completed candle OHLC and lagged 32-bar median range. Enter at next bar open, stop at 0.9x prior median range (minimum $2), target at 1.3R, maximum 3 bars. Ambiguous OHLC exits assume stop first. Position size: 1% equity risk baseline, 0.5% guard; floor to 0.01 lot, cap 0.10 lot; 100oz/lot. Guard rejects oversized last bar and relatively elevated spread. Estimated all-in roundtrip costs: $1.46 per ounce traded, not verified broker costs.

| Holdout metric | Base | Risk guard |
|---|---:|---:|
| Opportunities | 131 | 131 |
| Trades | 124 | 16 |
| Gross USD | -17.08 | -10.25 |
| Estimated costs USD | 202.94 | 23.36 |
| Net USD | **-220.02** | **-33.61** |
| Max closed drawdown USD | 235.37 | 45.84 |
| Estimated intrabar drawdown USD | 240.81 | 53.28 |
| Days net >= $50 | 0 | 0 |
| Lot range | 0.01–0.02 | 0.01 |

Training baseline: 188 opportunities, 115 trades, gross +$10.03, costs $201.48, net -$191.45. Holdout baseline 48 wins / 76 losses. Guard 6 wins / 10 losses.

**Decision: REJECT for demo.** The guard is a loss-reduction mechanism, not an independent profit engine. Estimated intrabar drawdown is approximate; no tick-level path, verified broker fill, or real execution. Research implementation and JSON results were executed locally; this commit records the evidence summary only. No private bars uploaded.
