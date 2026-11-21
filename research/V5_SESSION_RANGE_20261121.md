# V5 session-range breakout (2026-11-21)
Private Eplanet M15 CSV: 23,643 rows. No market data committed.

Hypothesis: after 06:00–08:00 UTC range, enter at next open on first confirmed close beyond range during 08:00–12:00 UTC; exit after up to 5 candles. Independent risk guard: ATR/half-range stop. Capital $1,000, variable lot, 1% nominal risk, minimum 0.01 lot, 100 oz/lot, estimated roundtrip $0.45/oz. Chronological 60/40 trading-day split.

| OOS (104 days) | Signal | Risk guard |
|---|---:|---:|
| Opportunities | 93 | 93 |
| Trades | 71 | 70 |
| Gross profit | 378.38 | 356.19 |
| Gross loss | -308.39 | -254.44 |
| Estimated costs | 31.95 | 31.50 |
| Net | +38.04 | +70.25 |
| Max closed drawdown | 59.11 | 42.24 |
| Days >= $50 net | 0 | 0 |

Training (155 days): signal +63.78 net / 84.89 drawdown / 64 trades; guard +69.11 net / 80.14 drawdown / 66 trades.

Guard reduced OOS drawdown and increased net, but neither passed $50 net per trading day. REJECT for MT5 demo. No live or demo orders. Costs estimated; intrabar tick path and floating drawdown unavailable. Session hours interpreted as UTC without independent broker clock verification.

Reproduce: `python research/v5_session_range_20261121.py /path/to/private/Eplanet_M15_20251105_20261105_merged.csv`
