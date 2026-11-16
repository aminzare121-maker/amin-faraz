# V5 volatility compression breakout — 2026-11-17

Research-only. No MT5 orders. Hypothesis: four low-range bars relative to 40-bar median precede directional expansion beyond prior eight-bar extreme. Next-open execution; stop 1.2 ATR, target 2.4 ATR, time exit 8 bars; conservative stop-first OHLC. 60/40 chronological split of 23,643 private Eplanet M15 bars, OOS 2026-06-15 to 2026-11-05. 0.86 USD/oz assumed round-trip cost; risk 0.5% of equity with 0.01 lot floor, 0.1 lot cap. Independent risk guard rejects >1.5 ATR signal candle or hours 21–23 UTC.

| OOS metric | Baseline | Risk guard |
|---|---:|---:|
| Scanned opportunities (path dependent) | 166 | 170 |
| Trades | 11 | 7 |
| Gross USD | 1.05 | -3.64 |
| Costs USD | 9.46 | 6.02 |
| Net USD | -8.41 | -9.66 |
| Closed-equity max drawdown USD | 21.62 | 12.40 |
| Active days | 11 | 7 |
| Days >=50 USD net | 0 | 0 |

**Rejected for demo.** Risk guard reduces drawdown but worsens net return. Executed lot 0.01 only. Intrabar drawdown, variable spread, broker commission and live fills unverified. Private market data must not be committed. Local executable source and JSON results retained outside repository; source upload pending.