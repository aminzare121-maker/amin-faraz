# V5 session VWAP reentry — 2026-11-17

Research hypothesis: after an intraday XAUUSD deviation >1.6 prior ATR units from a tick-volume weighted UTC-session VWAP, a move back toward the VWAP may revert further. Signal confirmed on closed M15 bar; enter next open; exit at VWAP, 1.25 ATR stop, or after 9 bars. Conservative stop-first OHLC.

Private Eplanet CSV: 23,643 rows; SHA256 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. Chronological split 60/40, OOS 2026-06-15 05:45 UTC through 2026-11-05 10:45 UTC. Starting capital USD 1,000; 0.5% risk-based variable lot formula, floor 0.01 lot, cap 0.1 lot; actual lots 0.01. Costs assumed USD 0.86 per ounce per round trip (0.86 USD at 0.01 lot). Stop trading after equity depletion.

Independent guard rejects signal bar range >1.7 prior ATR or tick volume <45% of previous 40-bar median.

| OOS | Baseline | Guard |
|---|---:|---:|
| opportunities | 860 | 935 |
| trades | 860 | 780 |
| gross USD | -267.72 | -203.38 |
| estimated costs USD | 739.60 | 670.80 |
| net USD | -1007.32 | -874.18 |
| ending equity USD | -7.32 | 125.82 |
| max closed equity drawdown USD | 1097.83 | 947.11 |
| active days | 103 | 104 |
| days >=50 USD net | 3 | 4 |

**Rejected**: risk guard reduces losses but cannot produce an edge. Baseline depletes capital; slight negative ending equity reflects stop-fill loss exceeding remaining capital in an OHLC simulation, not allowed account overdraft. No demo or live orders.

Research source and machine-readable results were generated locally but not committed to GitHub in this commit. Caveats: UTC session proxy; no broker variable spread/commission or intrabar equity DD; no actual broker fills. No private CSV committed.