# V5 inside-bar release — 2026-11-20

New hypothesis: after an unusually large M15 impulse, a fully inside candle may signal temporary order absorption; enter only after the next completed candle closes beyond the inside candle in the impulse direction. Enter at next open. This is distinct from 8-bar compression breakout.

Data: private Eplanet M15 merged CSV, 23,643 rows, SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`. Chronological 60/40 train/holdout split (14,185 rows train). Historical CSV NOT committed.

Assumptions: ATR proxy = median true range over previous 64 bars, shifted one bar; impulse body > 1.25x ATR; release candle range <2.5x ATR; stop distance clipped to $2.5–$12; 1.6R target; six-bar maximum hold; stop-first if OHLC ambiguous; contract 100 oz/lot; variable lots 0.01–0.10; max risk $10 or 1% equity; estimated round-trip costs $0.80/oz + $7/lot = $87/lot. Guard: stop new entries when realized daily P&L <= -$15. No lookahead at entry, but OHLC does not prove tick execution.

| Segment | Variant | Opportunities | Trades | Gross USD | Costs USD | Net USD | Closed DD USD | Days >= $50 / total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Base | 50 | 29 | +91.59 | 27.84 | +63.75 | 67.66 | 0/156 |
| Train | Guard | 50 | 29 | +91.59 | 27.84 | +63.75 | 67.66 | 0/156 |
| Holdout | Base | 34 | 30 | -7.81 | 27.84 | -35.65 | 71.27 | 0/104 |
| Holdout | Guard | 34 | 30 | -7.81 | 27.84 | -35.65 | 71.27 | 0/104 |

Result: REJECTED. Risk guard did not activate; the number of skipped trades includes position-size ineligibility. 50 USD net per trading day is not met. No demo or real trades.

The executable local script and JSON output are generated in the automation runtime; GitHub reproduction code is tracked separately on this branch.