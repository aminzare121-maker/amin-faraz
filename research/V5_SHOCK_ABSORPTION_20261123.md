# V5 shock absorption — 2026-11-23

New hypothesis: shock candle range > 2.3 previous ATR20, tick volume > 1.5x preceding 40-bar median; next candle inside shock range with <85% shock tick volume. Fade shock direction at next bar open. Stop 1.2 ATR, target 1.6 ATR, max eight bars; ambiguous OHLC stop-first. No overlapping positions. Variable lot 0.01 increments, risk 1% equity, cap 0.10 lots, 100oz/lot assumed. Spread points * 0.01 USD/oz plus 0.30 USD/oz roundtrip assumed.

Private Eplanet dataset 23643 M15 candles SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Training before 2026-06-15 UTC, independent $1000 starting equity per partition. No private candles committed.

| Metric | Train | Train guard | OOS diagnostic | OOS guard diagnostic |
|---|---:|---:|---:|---:|
| Opportunities | 51 | 51 | 24 | 24 |
| Executable diagnostic trades | 24 | 24 | 15 | 15 |
| Blocked by minimum lot/risk | 27 | 27 | 9 | 9 |
| Gross profit USD | 96.23 | 96.23 | 73.99 | 73.99 |
| Gross loss USD | -96.77 | -96.77 | -45.91 | -45.91 |
| Estimated costs USD | 14.73 | 14.73 | 9.41 | 9.41 |
| Net USD | -15.27 | -15.27 | +18.67 | +18.67 |
| Max closed drawdown USD | 36.83 | 36.83 | 21.97 | 21.97 |
| Days net >= $50 | 0 | 0 | 0 | 0 |

Guard rejects gaps >15 minutes and spread >35 points. It excluded no additional entries; no risk-reduction evidence. Training negative, OOS sample small and 0 days >= $50. REJECTED. OOS only diagnostic; no demo or live trades authorized.

Limitations: OHLC intrabar ambiguity, contract size and spread conversion not verified, commissions approximated, no swap or tick-level drawdown. Local reproducibility code and JSON exist outside repository; GitHub code publication and independent CI not completed.
