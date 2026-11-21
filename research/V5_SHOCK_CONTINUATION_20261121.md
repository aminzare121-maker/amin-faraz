# V5 shock continuation — 2026-11-21
New hypothesis: a large directional M15 real body with small opposing wick represents persistent order flow; enter at next bar open in the same direction. Independent risk guard: 1.5 ATR stop. No delayed sentiment/COT. No MT5 orders.

Private Eplanet merged CSV (23,643 bars) used locally, NOT committed. Chronological split by UTC trading date: 155 training days, 104 held-out days. 1000 USD initial equity, 100oz/lot, variable lot with 1% target risk and minimum 0.01 lot; 4 bars holding. Round-trip cost PROXY 0.45 USD/oz. OHLC does not prove tick execution or floating drawdown.

| Body / ATR | Guard | Opportunities | Trades | Gross gain | Gross loss | Estimated costs | Net USD | Closed DD | Days >= 50 USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.0 | no | 809 | 115 | 393.40 | -559.01 | 51.75 | -217.36 | 278.74 | 0 |
| 1.0 | yes | 818 | 126 | 361.55 | -538.57 | 56.70 | -233.72 | 297.95 | 0 |
| 1.5 | no | 362 | 42 | 64.12 | -340.79 | 18.90 | -295.57 | 299.10 | 0 |
| 1.5 | yes | 359 | 57 | 82.29 | -299.75 | 25.65 | -243.11 | 246.64 | 0 |
| 2.0 | no | 150 | 28 | 38.15 | -231.06 | 12.60 | -205.51 | 221.30 | 0 |
| 2.0 | yes | 152 | 34 | 46.84 | -211.53 | 15.30 | -179.99 | 183.65 | 0 |

All variants rejected for demo: none positive OOS or meet $50/day. Guard helps only some thresholds, not reliably. Many opportunities fail minimum lot sizing, highlighting capital constraint. Costs are assumed, not broker-confirmed. Intrabar stop ordering and open gaps require tick validation. No data uploaded, no live trades.
