# V5 cost/friction gate — 2026-11-20

Hypothesis: avoid entries when estimated round-trip trading friction is large relative to stop distance. Same previously profitable efficiency-pause entry; this is a NEW execution selection gate, not a retest of the signal alone.

Source Eplanet M15 CSV SHA256: 06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604. 23,643 candles. Chronological train 60% / holdout 40%; 156/104 trading days. Capital $1,000; risk 1% capped at $10, variable lot 0.01-0.1; 100 oz/lot; estimated round-trip cost $87/lot. Next-bar-open entry; stop-first intrabar approximation; 12-bar exit, 1.8R target. Only completed candles used.

Gate: roundtrip cost / initial stop-dollar-risk = 87/(100*stop_distance). Predeclared ceilings: baseline (no gate), 0.35, 0.20.

| Variant | Train net | Holdout opportunities | Holdout trades | Holdout gross | Holdout costs | Holdout net | Holdout closed-equity DD | Holdout days >=$50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | +72.86 | 1526 | 158 | +233.52 | 137.46 | +96.06 | 119.54 | 1/104 |
| Gate 0.35 | +72.86 | 1526 | 158 | +233.52 | 137.46 | +96.06 | 119.54 | 1/104 |
| Gate 0.20 | +99.53 | 1526 | 158 | +233.52 | 137.46 | +96.06 | 119.54 | 1/104 |

Gate 0.20 excluded 9 training candidates, zero holdout candidates. Training net changed due to altered overlapping trade selection; holdout unchanged. Thus **no out-of-sample evidence that the gate improves trading**. No demo activation. Target $50 net every trading day NOT met. Costs estimated; no tick-by-tick execution, verified contract specification, dynamic spread, or slippage stress. Max drawdown is closed equity only.

Reproduction script and JSON were executed locally and are supplied as conversation artifacts; they are not included in this commit. No private market CSV was published. No orders placed.
