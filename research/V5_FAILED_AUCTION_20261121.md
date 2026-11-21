# V5 failed-auction fade — 2026-11-21

Independent new alpha: fade a failed break of the preceding 20 M15-bar high/low; the signal requires the completed bar to return inside the range. Prior 32-bar median true range is lagged. Protective variant exits at close of fourth bar if adverse displacement exceeds 0.5 initial risk.

Private Eplanet M15 CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23,643 candles; chronological 60/40 split; 1,000 USD starting equity; variable lot 0.01–0.10; max intended risk $10; estimated $87/lot round trip; stop-first OHLC assumption.

| Metric | Alpha holdout | Alpha + guard holdout |
|---|---:|---:|
| Market days | 104 | 104 |
| Signal opportunities | 376 | 376 |
| Trades | 142 | 142 |
| Blocked by min lot | 191 | 193 |
| Gross before costs USD | 39.97 | 34.97 |
| Estimated costs USD | 123.54 | 123.54 |
| Net USD | -83.57 | -88.57 |
| Max closed drawdown USD | 109.62 | 125.58 |
| Days net >= $50 | 0 | 0 |

Training: alpha -$173.29 net, guard -$164.97 net. Holdout alpha wins 51/142, guard 50/142. Both rejected; no demo or live trading.

Local script SHA256 9b0d60d1bbd4be015b1e773959de76a0673b106ffc7fdbee67b4458fe295778b. Executable code and JSON currently in local session; not uploaded to GitHub in this commit. Reproducibility requires the private dataset and local script. Intrabar floating drawdown, real spread, swap, and tick order are not verified. Gross before costs uses price difference; costs are estimated. Net winning/losing trades in JSON include costs.
