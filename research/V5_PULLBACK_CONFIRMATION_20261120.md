# V5 pullback confirmation — 2026-11-20

Research-only. Eplanet 23,643 M15 bars; 60/40 chronological split (14,185/9,458).

Hypothesis: after a 12-bar trend, a two-bar countertrend pullback followed by a confirmation candle may create continuation opportunities. Entry at next candle open, median previous 32 ranges as stop, 1.5x target, eight-bar timeout. Dynamic risk max $8, minimum 0.01 lot; 100 oz/lot assumed. Conservative same-bar stop priority. Assumed cost $0.26 spread plus $0.20 slippage per ounce and $7/lot round trip; actual broker fees unverified.

| Metric | Training baseline | OOS baseline | OOS daily -$20 guard |
|---|---:|---:|---:|
| Opportunities | 427 | 307 | 307 |
| Trades | 192 | 191 | 190 |
| Gross USD | -6.95 | 77.57 | 84.77 |
| Costs USD | 103.35 | 101.23 | 100.70 |
| Net USD | -110.30 | -23.67 | -15.94 |
| Closed equity max drawdown USD | 168.14 | 96.79 | 92.30 |
| Days net >= $50 | 0/156 | 0/104 | 0/104 |

Guard training net -$112.30 vs baseline -$110.30, so protection is not independently validated. Strategy rejected. No demo or live execution. Private data and trade ledger deliberately excluded. Local executable script: v5_pullback_20261120.py (not yet committed). M15 OHLC cannot verify intrabar order, bid/ask fills, or broker margin.
