# V5 shock-range gate — 2026-11-20
Hypothesis: a signal following an unusually wide completed M15 candle (true range > 2.0 times preceding 32-bar median true range) has unfavorable execution/adverse selection. Exclude these entries; independently test $15 daily-loss guard. No COT/sentiment.
Private CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. 23,643 M15 bars. Chronological 60/40 split (156/104 trading days), no training optimization of threshold. $1,000 initial, 0.01–0.10 variable lots, 100 oz/lot, 1% risk capped $10, estimated roundtrip $87/lot, 1.8R target, 12-bar timeout, stop-first intrabar.
| Split | Variant | Opportunities | Trades | Gross USD | Costs USD | Net USD | Closed DD USD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Baseline | 2061 | 132 | 97.38 | 118.32 | -20.94 | 175.17 | 0/156 |
| Train | Shock gate | 1955 | 130 | 102.53 | 116.58 | -14.05 | 164.41 | 0/156 |
| Train | Shock gate + guard | 1955 | 130 | 103.05 | 116.58 | -13.53 | 158.13 | 0/156 |
| Holdout | Baseline | 1526 | 177 | 169.61 | 153.99 | 15.62 | 138.77 | 1/104 |
| Holdout | Shock gate | 1474 | 173 | 152.98 | 150.51 | 2.47 | 134.62 | 0/104 |
| Holdout | Shock gate + guard | 1474 | 158 | 70.37 | 137.46 | -67.09 | 193.18 | 0/104 |
Conclusion: gate loses $13.15 of holdout net while improving closed DD by $4.15; guard materially worsens both. REJECT. Research only, no demo/real orders.
Reproduce: `python research/v5_shock_gate_20261120.py --csv PRIVATE_EPLANET_CSV --out results.json`. Do not commit CSV or trade-level private data.
Limitations: estimated costs; OHLC stop-first approximation, no verified broker tick sequencing; equity DD excludes intrabar floating DD. Baseline differs from earlier efficiency-pause reports, reconciliation still needed.
