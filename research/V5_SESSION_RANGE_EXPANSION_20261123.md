# V5 session-range expansion — 2026-11-23
Research-only; no MT5 orders.

## Hypothesis
Between 07:00–09:00 UTC, a price range forms. A 09:00–15:00 UTC close outside that range, with candle body >= 0.35 * lagged ATR20 and tick volume >= 1.15 * lagged 32-bar median, may indicate persistent price discovery. Range width must be 0.7–5 times lagged ATR. Enter at next bar open, ATR/structure stop, 1.8R target, maximum 8 bars. Max one filled trade/day. 1% equity risk, dynamic 0.01-lot increments, 0.15 cap. Assumed 100 oz/lot and roundtrip costs 0.01 USD per spread point plus 0.60 USD/oz. Stop takes precedence if stop and target occur in same candle. Initial equity resets to USD 1000 at train/test split 2026-06-15 UTC.

## Reproduced local run on Eplanet_M15_20251105_20261105_merged.csv
| Variant | Split | Opportunities | Risk blocked | Trades | Gross wins | Gross losses | Costs | Net | Closed DD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Base | Train | 81 | 24 | 57 | 243.61 | -240.87 | 60.20 | -57.46 | 82.06 | 0 |
| Base | Test | 57 | 5 | 52 | 247.31 | -207.82 | 55.10 | -15.60 | 48.00 | 0 |
| Guard | Train | 89 | 2 | 18 | 94.19 | -62.35 | 20.26 | +11.58 | 25.27 | 0 |
| Guard | Test | 66 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Guard excludes spread >30 points, signal true range >2.2 lagged ATR, or hour >=13 UTC. Opportunity counts vary because filled days are removed from future consideration; these counts are not comparable raw-signal totals. Guard zero trades in test is not a successful strategy.

## Limitations
Local run produced detailed JSON ledger, not committed because private dataset-derived trade timestamps remain local. Broker contract size, spread-unit conversion, slippage, tick-by-tick drawdown, and actual fill quality remain unverified. GitHub CI not run. This method fails the daily USD 50 net target and is **not authorized for demo or live orders**. Local executable: v5_session_range_expansion_20261123.py (not yet uploaded to this branch).
