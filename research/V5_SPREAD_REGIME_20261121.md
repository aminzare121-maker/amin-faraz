# V5 — spread regime (2026-11-21)

Hypothesis: spreads observed on completed signal bars proxy execution/liquidity risk. Skip elevated-spread signals. Data: private Eplanet M15, 23,643 rows, 60/40 chronological split, 104 holdout trading days. No private CSV committed.

## Holdout USD

| Variant | Opportunities | Trades | Gross | Estimated roundtrip costs | Net | Max closed-equity DD | Days >= $50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline |1517|165|276.95|143.55|133.40|54.11|0|
| Spread <=35 |1517|150|307.90|130.50|177.40|69.63|0|
| Spread <=32 |1517|116|149.24|100.92|48.32|56.19|0|
| Spread <=1.1x trailing median |1517|150|307.90|130.50|177.40|69.63|0|

## Training net USD / DD USD
Baseline 46.17 / 128.41; <=35 37.99 / 129.07; <=32 -9.95 / 122.85; relative -0.66 / 110.20.

## Decision
All variants fail >=$50 net on every trading day. <=35 improves holdout net by $44 but worsens drawdown and training net; not accepted. The spread of the *next* entry bar is unknown at signal time, so the completed-bar spread is only a proxy. Intrabar ordering uses stop-first assumption. Transaction cost $87 per 1 lot roundtrip is an estimate; tick replay, floating DD and broker-real execution not validated. No demo/live trading enabled.

Reproduce: `python research/v5_spread_regime_20261121.py --csv /private/path/Eplanet_M15_20251105_20261105_merged.csv --out results.json`. Results JSON kept local, not committed because it contains the private input hash.
