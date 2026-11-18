# V5 failed continuation — 2026-11-18
Hypothesis: after a 4-bar displacement above 2x lagged 32-bar median true range, a completed counter-direction candle failing to extend the preceding extreme indicates transient liquidity impact and short-horizon reversion. Enter at next 15-minute open; stop 1.25x ATR proxy, target 1.5x, exit after 3 bars. All signals use completed bars only.
Private Eplanet CSV: 23,643 rows; chronological split 60%/40%; 104 distinct out-of-sample dates. Initial equity USD 1,000; lot rounded to 0.01, capped at 0.05; nominal 1% risk. Cost model: recorded spread (points /100), additional USD 0.30/oz execution penalty, USD 7/lot commission. XAUUSD contract assumed 100oz/lot.
Out-of-sample:
- Baseline: 438 opportunities, 215 trades, gross -$130.87, costs $154.89, net -$285.76, max closed-equity DD $330.13, days >=$50: 0/104.
- Independent volatility guard (reject if latest 8-bar median TR >1.7x preceding 32-bar median): 438 opportunities, 188 trades, gross -$102.38, costs $135.16, net -$237.54, max closed-equity DD $278.92, days >=$50: 0/104.
No optimization on held-out sample. Guard reduces loss but does not create positive edge. Research rejected; no demo or live orders. Bar OHLC cannot establish precise fill order if stop and target both touched; code conservatively prioritizes stop. Intrabar drawdown and actual broker fills not verified. Data must NOT be committed.
Reproduction: put PRIVATE CSV beside research/v5_failed_continuation.py, then python research/v5_failed_continuation.py (pandas/numpy required).
