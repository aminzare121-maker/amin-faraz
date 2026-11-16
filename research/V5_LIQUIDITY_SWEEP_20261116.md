# V5 liquidity sweep rejection — 2026-11-16
Research only; NO demo/live orders. Private Eplanet CSV never committed.
Input: Eplanet_M15_20251105_20261105_merged.csv, 23643 M15 candles. Chronological 60/40 split (14185/9458).
Hypothesis: failed sweep of previous 16-candle extreme followed by close back inside signals reversal; entry next candle open, stop=median prior 32 true ranges, target=1.5x stop, exit by fourth candle; stop-first ambiguity.
Risk filter independent: signal candle TR <= 1.5x prior ATR, spread<=30 points.
Sizing: floor(1% equity / (stop distance * 100oz) to 0.01 lots), capped 0.20 lots; skip below 0.01 lots. Estimated spread=spread points*0.01 USD/oz, slippage=0.60 USD/oz roundtrip. Broker contract/point assumptions require MT5 verification.
TRAIN: baseline 172 opportunities,111 trades, gross -32.97, cost 108.10, net -141.07, closed DD 172.06; filter 178 opportunities,25 trades, gross 21.20, cost 25.98, net -4.78, DD 32.35.
OOS (104 dates): baseline 121 opportunities,97 trades, gross 50.65, cost 90.13, net -39.48, closed DD 66.71, 0 days >=$50; filter 128 opportunities,0 trades, net 0, DD 0, 0 days >=$50. Opportunity counts differ because the sequential backtester skips occupied bars.
Decision: REJECT entry strategy; filtered path yields no OOS trades, not evidence of profitability. No intrabar equity DD or verified broker fills.
Execution code and machine-readable results generated locally as v5_liquidity_sweep.py and v5_liquidity_sweep_results.json. These files have NOT been pushed to GitHub; this markdown is an audit note, not a reproducible code commit.
