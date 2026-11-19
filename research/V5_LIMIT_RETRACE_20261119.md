# V5 passive retracement experiment — 2026-11-19

Data: eplanet_m15_requested_year.csv extracted from private Library archive eplanet_twin_native_year_after_restart.zip. 23,551 unique M15 bars. SHA256 f1d9f84a60f3f025dbe8d0e63b8520cdc4ebfa5b64d7617ac5f551813f7695d3. Not the previously cited 23,643-bar merged file; this run used a separately identified real Eplanet dataset.

Hypothesis: after a strong directional M15 candle, passive entry on 50% body retracement may improve entry cost and reduce chase/slippage. Signal: body >= threshold * trailing ATR32 and >=65% of candle range. Buy/sell limit at 50% body retrace; expires after two M15 bars; stop=max($2,0.85*ATR); target=1.8R; maximum 8-bar hold. Chronological 60/40 split, thresholds 1.0,1.3,1.6,2.0 trained; 2.0 selected by training net. $1,000 initial equity, variable 0.01–0.10 lot, 100oz/lot, $10 nominal risk, assumed $0.65/oz round-trip costs, conservative stop-first rule.

Out of sample (103 trading days): 170 opportunities; 66 simulated limit fills/trades; gross +$152.74; assumed costs $54.60; net +$98.14; closed-equity max drawdown $78.07; approximate intrabar drawdown $83.09; 0/103 days >= $50 net.

Independent volatility guard (exclude ATR>15 or ATR<2.5): same 66 trades, +$98.14 net, no risk reduction. This filter was not beneficial.

Important caveat: M15 OHLC cannot establish order of limit fill, stop and take-profit within the same bar. No real broker spread, commission, swap, margin, tick sequence, or MT5 execution validation. These are research simulations only. Data and trade ledger were not published. Code was executed locally but is not included in this commit.

Decision: financial target failed; do not enable demo or live trades.
