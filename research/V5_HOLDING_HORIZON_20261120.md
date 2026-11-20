# V5 holding horizon test — 2026-11-20

Private Eplanet M15 SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604; 23,643 bars; chronological 60/40 split. New hypothesis: a shorter 6-bar holding horizon can reduce exposure to reversal and execution costs, compared with 12 bars; 24 bars is a control for opportunity cost. Same prior completed-bar signal, 45% adverse-wick exclusion, three-bar stagnation exit, variable lots, stop-first OHLC, 1% risk cap and estimated $87/lot roundtrip. **Code was executed locally; not yet committed.**

| Metric | Train 6 | Train 12 | Train 24 | Holdout 6 | Holdout 12 | Holdout 24 |
|---|---:|---:|---:|---:|---:|---:|
| Opportunities |2059|2059|2059|1517|1517|1517|
| Trades |155|137|145|184|165|160|
| Gross USD |194.32|168.84|262.60|248.64|276.95|246.75|
| Costs USD |138.33|122.67|129.63|160.08|143.55|139.20|
| Net USD |55.99|46.17|132.97|88.56|133.40|107.55|
| Max closed drawdown USD |77.50|128.41|83.65|68.56|54.11|62.11|
| Days net >= $50 |0/156|1/156|1/156|0/104|0/104|1/104|

**Decision: reject 6- and 24-bar variants.** Both reduce holdout net and increase holdout drawdown relative to 12-bar baseline. The 24-bar variant improved training only. No demo trades. $50 net per trading day not met.

Reproducibility limitations: historical OHLC cannot resolve tick ordering; execution costs estimated; open-trade drawdown and margin stress not measured. Input CSV is private and not committed. Source remains local pending upload.
