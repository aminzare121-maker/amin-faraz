# Eplanet M15 | V4 loss diagnosis — final GitHub receipt (2026-11-14)

GitHub Actions run: https://github.com/aminzare121-maker/amin-faraz/actions/runs/43630981734  
Run conclusion: **success** (successful technical execution of a negative/failed strategy result).  
Branch: `research/amin-m15-v4-diagnostic-20261114`  
Code commit: `75faba0333e094a003646070c0a0e30037ce7100`  
Data provenance: 23,643 M15 Eplanet candles; SHA256 `06b60768cc6179d1985ce7ab173d421edb3adcacf62d781ca733adc331bc2604`.

## Frozen research setup
- V3 classifier, `h4_sl1_r2`, BUY only, cutoff = 90th calibration percentile
- Fixed filter: decision UTC hour 07-19; 24-bar positive price trend; spread-to-ATR <= 70th calibration percentile; no gap in previous 20 closed bars
- Filter thresholds defined without holdout outcomes; holdout used once and is now considered **consumed** for this line of research.
- Assumed 0.01 lot, commission/slippage and spread conversion are **not independently verified against Eplanet real execution**.
- Rebuilt historical CSV before execution and verified SHA256.
- Pinned CI numerical versions: Python 3.11, scikit-learn 1.9.1, NumPy 2.4.6, pandas 2.3.3.
- The local run under scikit-learn 1.8.0 produced different numeric outcomes; do **not** conflate them with this pinned CI run.

## Actual pinned GitHub results

| Dataset block | Reference trades | Reference net USD | Filter trades | Filter net USD | Filter profit factor |
| --- | ---: | ---: | ---: | ---: | ---: |
| Calibration | 238 | -236.286 | 65 | +46.689 | 1.1492 |
| Validation | 265 | -47.301 | 65 | +26.705 | 1.0852 |
| Untouched, one-time holdout | 239 | -338.677 | 45 | -192.612 | 0.3359 |

Holdout filter win rate: **17.778%**.  
Holdout filter hypothetical average trading-day profit: **-4.815 USD** (40 historical trading days in block).
Holdout split chronology: independent block relative to the train/calibration/validation split.

## Final outcome
**FILTER_REJECTED_BY_UNSEEN_HOLDOUT.**
No profitable signal has been established. No live or demo order was placed; no modification to the main trading bot. Target 50 USD net per day from 1000 USD NOT achieved.

Artifact `eplanet-m15-v4-diagnostics-23643` ID `14127384563`: https://github.com/aminzare121-maker/amin-faraz/actions/runs/43630981734/artifacts/14127384563  
Artifact retention until about 2026-11-21 (may expire). It contains report and per-trade CSVs.

**Do not select another filter using the consumed holdout.** Any subsequent independent signal claim needs fresh Eplanet data outside these observation periods and verified broker costs, then MT5 demo forward testing.
