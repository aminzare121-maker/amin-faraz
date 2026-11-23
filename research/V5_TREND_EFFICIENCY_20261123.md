# V5 trend-efficiency research — 2026-11-23

Status: REJECTED; no demo trading enabled.

Hypothesis: a directionally efficient 12-bar trend that briefly pulls back and resumes may reflect persistent order flow. Signal uses only completed OHLC bars; enter at next M15 open.

Data: Eplanet_M15_20251105_20261105_merged.csv (private; NOT committed). 15-minute OHLC, 2025-11 to 2026-11. Chronological holdout starts 2026-06-15.

Rules: prior 12-bar absolute displacement / sum absolute close changes >0.42; prior-bar pullback >0.12*ATR20; current candle resumes >0.25*ATR20 in trend direction and above/below prior MA48. ATR20 and MA48 lagged. SL 1.2 ATR; TP 1.8 ATR; max hold 8 bars. Conservative stop-first on ambiguous OHLC bars. 0.5% risk/equity, 0.01 minimum lot, 0.05 cap; reject signals if minimum lot exceeds risk. Assume 100 oz per lot. Round-trip cost = recorded spread points * 0.01 + $0.20/oz slippage, multiplied by ounces. This is an assumption, not verified Eplanet execution pricing.

TRAIN (155 dates): 247 raw opportunities, 3 executable trades, gross gain $7.15, gross loss -$8.65, costs $1.42, net -$2.92, closed DD $4.89, zero days >=$50.

HOLDOUT (104 dates): 190 raw opportunities, 1 executable trade, gross gain $7.19, gross loss $0, costs $0.54, net +$6.65, closed DD $0, zero days >=$50.

Independent risk guard (skip ATR >1.6x trailing 96-bar ATR median or spread >$0.35) changes no executable trades in either partition. It does NOT demonstrate drawdown improvement.

Major finding: with realistic minimum-lot sizing and 0.5% risk, nearly all nominal signals are untradeable for a $1000 account. Positive holdout P&L on ONE trade is statistically meaningless. Financial gate FAIL. No demo or live orders.

Reproduction script and detailed JSON generated locally as v5_trend_efficiency_20261123.py / .json. They have not been uploaded to this branch; GitHub CI not run. Do not claim independent reproducibility from this report alone. No private price data published.
