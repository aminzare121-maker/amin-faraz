# V5 — Volume-climax wick rejection (2026-11-17)

Independent new hypothesis: elevated broker tick volume and an unusually wide M15 candle with a rejection wick may indicate exhausted aggressive orders, making short-horizon reversal plausible. No COT/sentiment/timezone assumptions.

Dataset: private Eplanet M15 merged CSV, 23,643 bars; chronological 60/40 split; OOS 2026-06-15 05:45 UTC through 2026-11-05 10:45 UTC. Data not committed.

Rules: previous 32-bar median range and tick volume, both lagged one bar; range > 1.5x prior median and tick volume > 1.5x prior median; rejection wick > 55% range; buy lower rejection, sell upper rejection. Next-bar open entry; stop 1x median range, target 1.5x, max 9 bars. Stop-first on same-bar collisions; adverse gaps filled at opening price. Initial equity $1,000; size floor to 0.01 lot based on 1% risk; contract assumption 100 oz/lot. Estimated round-trip execution cost $1.46/oz, not validated broker fees.

| OOS metric | Base | Post-loss cooldown (8 bars) |
|---|---:|---:|
| Raw qualifying signals | 183 | 183 |
| Simulated trades | 148 | 125 |
| Gross P&L USD | -3.82 | -36.11 |
| Estimated costs USD | 230.68 | 195.64 |
| Net P&L USD | -234.50 | -231.75 |
| Max closed-equity drawdown USD | 255.06 | 258.06 |
| Active trade days | 83 | 83 |
| Days net >= $50 | 0 | 0 |

The cooldown reduces trade count but not meaningful drawdown; neither role qualifies for demo. Intrabar drawdown, tick-by-tick fill realism and actual Eplanet charges remain unverified. No live or demo trades placed. Executable research script and JSON trade ledger generated locally; code upload to GitHub pending.
