# V5: quiet-to-moderate volatility acceleration (2026-11-21)

Dataset: private Eplanet M15, 23,643 candles. Chronological 60/40 split, OOS 104 market days. Source data deliberately not committed.

Hypothesis: following low volatility (ATR20 / rolling median ATR20 over 96 bars <0.72 four bars ago), moderate acceleration (current ratio 0.85..1.25 and 4-bar directional displacement 1.0..2.5 ATR) may provide directional drift without chasing extreme price shocks. Enter next candle open; exit at fifth subsequent open or intrabar 1.5 ATR stop. Independent protective exit: adverse close >0.55 ATR after two bars, exit next open. No future indicators.

Risk: starting $1,000, 1% equity per trade, floor lots to 0.01, 100 oz/lot, no overlapping trades. Cost assumed $56/lot round trip (spread + slippage + commission). No actual broker execution or tick validation.

| OOS measure | Base | Protective |
|---|---:|---:|
| Signal opportunities | 20 | 20 |
| Min-lot rejections | 4 | 4 |
| Executed trades | 9 | 9 |
| Gross wins USD | 18.14 | 18.14 |
| Gross losses USD | -35.58 | -32.44 |
| Costs USD | 5.04 | 5.04 |
| Net USD | -22.48 | -19.34 |
| Closed-equity max drawdown USD | 29.05 | 25.91 |
| Days >= $50 net | 0 / 104 | 0 / 104 |

Rejected for MT5 demo. Protective exit reduces loss by $3.14 but does not establish positive expectancy. Intrabar floating drawdown not measured. Local reproducible implementation and JSON were generated; do not infer this markdown file contains executable source.