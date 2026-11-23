# V5 — Two-bar acceptance after volatility contraction (2026-11-23)

Research-only; NO MT5 orders. Data: private Eplanet M15 merged CSV (not committed), 2025-11-05 to 2026-11-05. UTC split 2026-06-15. Hypothesis: after an eight-bar quiet interval relative to prior 48 bars, two aligned candles closing toward their directional extremes can indicate directional price acceptance. This is a distinct signal from previous one-bar reversal / Donchian breakout tests.

## Reproduction
`python research/v5_two_bar_acceptance.py /private/path/Eplanet_M15_20251105_20261105_merged.csv`

Closed-bar features only; next-bar open entry, stop 0.8 prior ATR, target 1.6 ATR, 8-bar expiry; both touched in same bar => stop first. Lot size floored to 0.01 with 1% equity risk, capped at 0.15 lot, assumed 100 oz/lot. Cost = $0.60/oz round-trip friction plus recorded spread points × $0.01/point, times ounces. Guard independently rejects unusually high spread, >2 ATR signal bar, hours 21-23 UTC. No tick execution proof. Risk cap does not include trading costs.

| Split | Variant | Raw opportunities | Risk-blocked | Trades | Gross profit $ | Gross loss $ | Costs $ | Net $ | Max closed DD $ | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 681 | 197 | 350 | 1637.83 | -1434.27 | 404.96 | -201.40 | 351.68 | 1 |
| Train | Guard | 681 | 150 | 250 | 1079.48 | -1026.92 | 275.56 | -223.00 | 314.81 | 0 |
| Test | Base | 551 | 205 | 246 | 735.39 | -813.45 | 262.17 | -340.23 | 361.43 | 0 |
| Test | Guard | 551 | 38 | 185 | 650.83 | -604.40 | 185.33 | -138.90 | 154.41 | 0 |

Guard reduces test net loss by $201.33 and max closed drawdown by $207.02 but still loses money. Guard is a risk-reduction hypothesis only, not a profit engine. Neither variant qualifies for demo. The $50 net profit *each trading day* target fails. Costs are estimated; no intrabar tick-level equity drawdown or real broker execution verification. Raw opportunities include overlaps and are not executable trades. Training/test equity sizing is continuous from start of history, not reset at test split.

No private market data or account credentials committed.