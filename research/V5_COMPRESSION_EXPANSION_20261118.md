# V5 compression-expansion research — 2026-11-18

Hypothesis: after a four-bar price compression, a completed-bar breakout impulse may initiate directional expansion. Entry at next bar open, four-bar hold, 1.5 ATR stop, 1% sizing with 0.01–0.05 lot, 100 oz/lot assumed. The loss guard independently filters extreme ATR regimes. All decisions use completed price bars, no COT or sentiment.

Source: private Eplanet M15 merged CSV, 23,643 bars (NOT committed). 60/40 chronological split. Test UTC 2026-06-15 05:45 to 2026-11-05 10:45. Illustrative cost model 0.26 price spread + 0.30 price slippage each side = 0.86 USD/oz round trip. Broker contract and tick fills NOT verified.

|Metric|Signal|Loss guard|
|---|---:|---:|
|Training trades|638|498|
|Test trades|423|336|
|Gross USD|95.15|76.70|
|Costs USD|365.50|288.96|
|Net USD|-270.35|-212.26|
|Closed-equity drawdown USD|478.51|336.94|
|Max observed trade adverse excursion USD|102.08|68.63|
|Days with >= $50 net|0|0|
|Days traded|102|99|

Decision: REJECT for MT5 demo. Guard reduces loss and drawdown but does not generate positive net edge. No orders placed. Local executable code and detailed JSON were generated separately; neither is represented as committed in this branch. No private data published. Important limitations: OHLC-based stop approximation, no verified spread or commissions, no tick-level sequencing, and the fixed parameters were not validated through a full walk-forward grid.