# V5 short-horizon shock reversal — 2026-11-23
Hypothesis: unusually large one-bar XAUUSD returns may revert over the following three M15 bars due to temporary liquidity imbalance. Entry uses only completed-bar price and spread.
Data: private Eplanet M15 2025-11-05 to 2026-11-05 (not committed). Train ends 2026-06-15; untouched holdout 2026-06-15 to 2026-11-06.
Signal: abs(close.diff()) >= 3 * prior 96-bar median absolute return; trade against shock at next open; stop=max(2.5*scale,0.6*abs(shock)), target=1.3*stop, max hold 3 bars, stop-first on OHLC ambiguity.
Guard independently rejects spread above previous 96-bar median, shock above 7*scale, range above 8*scale.
Capital $1000, dynamic lots floor(min(0.10, 1% equity/(100*stop+cost_per_lot))*100)/100, reject <0.01 lots. Approximate costs: spread points * $0.01 *100 oz, $0.20/oz per side slippage and $7/lot commission. Assumes 1 lot=100 oz. No broker confirmation, tick replay, or intrabar drawdown. No real trades.
| Holdout | Base | Guard |
|---|---:|---:|
| Opportunities |803|806|
| Trades |287|261|
| Gross gains USD |876.98|840.04|
| Gross losses USD |-919.86|-826.58|
| Costs USD |234.18|205.67|
| Net USD |-277.06|-192.21|
| Max closed drawdown USD |277.06|213.78|
| Days net >= $50 |0|0|
Train net: base -336.90, guard -313.30.
Decision: REJECT both as profit engines. Guard reduces losses but does not establish standalone edge. No MT5 demo deployment.
Local reproducibility script: v5_short_horizon_reversal_20261123.py (not yet committed at time of this report).