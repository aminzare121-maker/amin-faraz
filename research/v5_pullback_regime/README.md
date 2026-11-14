# V5 causal M15 pullback experiment — 2026-11-14

Research-only. No demo or live trading orders. Historical Eplanet data remain private and excluded from this branch.

## Exact rule
Original independent pullback signal preserved: EMA(21)>EMA(100), wick touches EMA(21), candle closes above it and body/range >0.25 (mirror for short); buy/sell only on next M15 open. Gate allows a signal only if ATR(14) on closed bar >= rolling median of previous 96 closed ATR observations. Signals and gate are calculated at candle close, never from future bars.

Capital $1000; position size rounded to 0.01 lot, 1% risk/position, max 0.10 lot; SL 1.1 ATR minimum $2/oz, TP 2R, max 8 M15 bars; stop first on same-bar ambiguity, Eplanet spread + hypothetical $10/lot round-trip commission + slippage on both sides.

## Experiment results — net USD, $0.10/oz each-side slippage

| period | no gate | ATR gate |
|---|---:|---:|
| Jan–Apr train | -69.60 | +35.32 |
| May–Jun validation | -110.12 | +19.40 |
| Jul–Oct later | +85.92 | +4.81 |
| May–Oct continuous equity | -301.78 | +12.73 |

The ATR gate was selected on BOTH Jan–Apr train and May–Jun validation: positive net, >=20 trades, DD <=20% each. Jul–Oct has previously been analyzed in other V5 experiments, so this is NOT a pristine held-out dataset.

May–Oct continuous sensitivity net:
- 0.10 slippage: no gate -301.78, gate +12.73
- 0.30 slippage: no gate -332.25, gate -62.80
- 0.50 slippage: no gate -372.55, gate -222.80

**Decision: NOT APPROVED for MT5 demo.** The rule reduces losses but fails to provide $50 net/day and fails execution-cost robustness. 5/5 local software checks passed. Full exact Python runner and trade ledger were produced as `AMIN_PULLBACK_REGIME_CAUSAL_TEST_20261114.zip` in the ChatGPT conversation artifact, NOT committed to this GitHub branch. This repo page is a provenance receipt, not an assertion of full engine delivery.
