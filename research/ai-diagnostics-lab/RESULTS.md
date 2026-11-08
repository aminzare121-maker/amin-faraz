# Actual phase-two offline diagnostic results — 2026-11-05

Two complete executions; 252 portfolios each, 720 probability records each, 38 synthetic QA tests passed. 45 original portfolios replayed exactly; 72 frozen artifact/gate/probability comparisons passed. No new model/calibrator fit. Full numeric summaries and private output hashes identical across both runs.

Result SHA256: `0c80601b3ba0d9b8b0d8f61391ff8d3cee417b90d752b5bcde48ce0459338311`.

All results are hypothetical USD, retrospective and already seen. No independent future test, demonstrated profitability, account connection or deployment. Provenance, redistribution rights, session calendar, Ask/spread and real broker contract/cost remain unverified. Private data, scores, weights and trade rows are not included.

## Primary strict/base probability diagnostics

Weighted by available label count within V or E separately. T/C diagnostics are in-sample (BASE_C on T is descriptive, not a past-only T forecast). V/E are not pooled; their dates overlap across folds.

| Phase | Target | Labels | Brier | Log-loss |
|---|---|---:|---:|---:|
| V | M1_raw | 201 | 0.260045 | 0.719231 |
| V | M1_cal | 201 | 0.289364 | 0.784798 |
| V | M2_raw | 201 | 0.264805 | 0.730062 |
| V | M2_cal | 201 | 0.290910 | 0.786698 |
| V | BASE_C | 201 | 0.286387 | 0.775280 |
| E | M1_raw | 200 | 0.236536 | 0.667361 |
| E | M1_cal | 200 | 0.228333 | 0.648565 |
| E | M2_raw | 200 | 0.257767 | 0.714603 |
| E | M2_cal | 200 | 0.227341 | 0.646473 |
| E | BASE_C | 200 | 0.228098 | 0.647950 |

## Fold-by-fold primary diagnostics

| Fold | Phase | Target | Positive/labels | Gate/candidates | Brier | Log-loss |
|---|---|---|---:|---:|---:|---:|
| WF1 | V | M1_raw | 29/54 | 1/54 | 0.332563 | 0.881776 |
| WF1 | E | M1_raw | 10/39 | 1/40 | 0.221564 | 0.634449 |
| WF1 | V | M1_cal | 29/54 | 0/54 | 0.343622 | 0.912929 |
| WF1 | E | M1_cal | 10/39 | 0/40 | 0.193295 | 0.576049 |
| WF1 | V | M2_raw | 29/54 | 7/54 | 0.339699 | 0.905103 |
| WF1 | E | M2_raw | 10/39 | 12/40 | 0.241639 | 0.679695 |
| WF1 | V | M2_cal | 29/54 | 0/54 | 0.334145 | 0.886232 |
| WF1 | E | M2_cal | 10/39 | 0/40 | 0.192312 | 0.573604 |
| WF1 | V | BASE_C | 29/54 | 0/54 | 0.327715 | 0.868934 |
| WF1 | E | BASE_C | 10/39 | 0/40 | 0.190664 | 0.569270 |
| WF2 | V | M1_raw | 10/38 | 0/38 | 0.215263 | 0.621800 |
| WF2 | E | M1_raw | 28/60 | 0/62 | 0.260663 | 0.719831 |
| WF2 | V | M1_cal | 10/38 | 15/38 | 0.255456 | 0.704134 |
| WF2 | E | M1_cal | 28/60 | 18/62 | 0.256385 | 0.706055 |
| WF2 | V | M2_raw | 10/38 | 6/38 | 0.210662 | 0.610669 |
| WF2 | E | M2_raw | 28/60 | 14/62 | 0.299187 | 0.810135 |
| WF2 | V | M2_cal | 10/38 | 10/38 | 0.277379 | 0.750062 |
| WF2 | E | M2_cal | 28/60 | 14/62 | 0.250889 | 0.694973 |
| WF2 | V | BASE_C | 10/38 | 0/38 | 0.268916 | 0.731050 |
| WF2 | E | BASE_C | 28/60 | 0/62 | 0.253841 | 0.700846 |
| WF3 | V | M1_raw | 28/58 | 0/58 | 0.249355 | 0.691314 |
| WF3 | E | M1_raw | 16/53 | 0/53 | 0.238005 | 0.670064 |
| WF3 | V | M1_cal | 28/58 | 0/58 | 0.299616 | 0.806823 |
| WF3 | E | M1_cal | 16/53 | 0/53 | 0.211065 | 0.613152 |
| WF3 | V | M2_raw | 28/58 | 23/58 | 0.263157 | 0.719775 |
| WF3 | E | M2_raw | 16/53 | 15/53 | 0.244692 | 0.680364 |
| WF3 | V | M2_cal | 28/58 | 0/58 | 0.301822 | 0.812948 |
| WF3 | E | M2_cal | 16/53 | 0/53 | 0.211367 | 0.613780 |
| WF3 | V | BASE_C | 28/58 | 0/58 | 0.297927 | 0.802439 |
| WF3 | E | BASE_C | 16/53 | 0/53 | 0.212251 | 0.616210 |
| WF4 | V | M1_raw | 14/51 | 0/51 | 0.228786 | 0.651469 |
| WF4 | E | M1_raw | 15/48 | 0/52 | 0.216919 | 0.625531 |
| WF4 | V | M1_cal | 14/51 | 0/51 | 0.245520 | 0.684185 |
| WF4 | E | M1_cal | 15/48 | 0/52 | 0.240800 | 0.674723 |
| WF4 | V | M2_raw | 14/51 | 9/51 | 0.227721 | 0.645384 |
| WF4 | E | M2_raw | 15/48 | 7/52 | 0.233533 | 0.661358 |
| WF4 | V | M2_cal | 14/51 | 0/51 | 0.242805 | 0.678752 |
| WF4 | E | M2_cal | 15/48 | 0/52 | 0.244005 | 0.681152 |
| WF4 | V | BASE_C | 14/51 | 0/51 | 0.242522 | 0.678185 |
| WF4 | E | BASE_C | 15/48 | 0/52 | 0.243832 | 0.680806 |

## All primary portfolios and all fixed seeds

Expected C-only acceptance budgets, never matched to future realized trade counts or exposure. q unavailable is not an observed zero budget; inspect activity_budgets before interpreting any no-trade result. No seed selected. All 9 conditions are in the aggregate JSON files.

| Arm | Net | Trades | Planned risk | Exposure hours | Net/risk | Net/hour |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 0.00 | 0 | 0.00 | 0.00 | undefined | undefined |
| B1 | -602.15 | 89 | 1693.69 | 327.25 | -0.355526 | -1.840031 |
| B2 | -428.36 | 113 | 2230.56 | 513.00 | -0.192041 | -0.835010 |
| M1_raw | -24.36 | 1 | 24.36 | 0.25 | -1.000000 | -97.440000 |
| M1_cal | -73.00 | 6 | 110.07 | 12.25 | -0.663214 | -5.959184 |
| M2_raw | -289.05 | 30 | 576.95 | 97.75 | -0.500997 | -2.957033 |
| M2_cal | -10.18 | 4 | 75.98 | 40.75 | -0.133983 | -0.249816 |
| BASE_C | 0.00 | 0 | 0.00 | 0.00 | undefined | undefined |
| R_M1_raw_seed1729 | 52.71 | 2 | 33.78 | 4.75 | 1.560391 | 11.096842 |
| R_M1_raw_seed2718 | -6.74 | 1 | 20.17 | 4.00 | -0.334160 | -1.685000 |
| R_M1_raw_seed31415 | -38.27 | 2 | 38.27 | 0.75 | -1.000000 | -51.026667 |
| R_M1_raw_seed42017 | 0.00 | 0 | 0.00 | 0.00 | undefined | undefined |
| R_M1_raw_seed65537 | -21.24 | 2 | 40.16 | 4.25 | -0.528884 | -4.997647 |
| R_M1_cal_seed1729 | -47.32 | 15 | 284.59 | 66.00 | -0.166274 | -0.716970 |
| R_M1_cal_seed2718 | -81.86 | 15 | 275.53 | 66.75 | -0.297100 | -1.226367 |
| R_M1_cal_seed31415 | -72.34 | 20 | 387.36 | 108.75 | -0.186751 | -0.665195 |
| R_M1_cal_seed42017 | -104.50 | 13 | 228.96 | 35.50 | -0.456412 | -2.943662 |
| R_M1_cal_seed65537 | 14.07 | 13 | 255.73 | 44.00 | 0.055019 | 0.319773 |
| R_M2_raw_seed1729 | -261.71 | 32 | 607.16 | 67.75 | -0.431040 | -3.862878 |
| R_M2_raw_seed2718 | -442.11 | 39 | 780.87 | 110.75 | -0.566176 | -3.991964 |
| R_M2_raw_seed31415 | -374.06 | 34 | 660.44 | 77.25 | -0.566380 | -4.842201 |
| R_M2_raw_seed42017 | -172.93 | 28 | 506.63 | 65.50 | -0.341334 | -2.640153 |
| R_M2_raw_seed65537 | -91.25 | 25 | 463.77 | 96.25 | -0.196757 | -0.948052 |
| R_M2_cal_seed1729 | -73.70 | 13 | 255.17 | 67.25 | -0.288827 | -1.095911 |
| R_M2_cal_seed2718 | -3.27 | 10 | 188.07 | 53.00 | -0.017387 | -0.061698 |
| R_M2_cal_seed31415 | -103.20 | 10 | 182.01 | 59.50 | -0.567002 | -1.734454 |
| R_M2_cal_seed42017 | -58.08 | 6 | 105.76 | 15.25 | -0.549168 | -3.808525 |
| R_M2_cal_seed65537 | -18.83 | 6 | 101.48 | 23.50 | -0.185554 | -0.801277 |

## Primary paired block uncertainty

95% exploratory total-P&L difference intervals, 1000 circular paired resamples of 125 common UTC calendar days including zeros; unadjusted for multiple comparisons. Equal weight mean of five fixed random seeds is a descriptive comparator, not equal realized exposure.

| Target | Baseline | Block days | Difference | 95% interval |
|---|---|---:|---:|---|
| M1_raw | B0 | 1 | -24.360 | [-73.080, 0.000] |
| M1_raw | B0 | 5 | -24.360 | [-73.080, 0.000] |
| M1_raw | B0 | 10 | -24.360 | [-73.080, 0.000] |
| M1_raw | B1 | 1 | 577.790 | [257.820, 913.310] |
| M1_raw | B1 | 5 | 577.790 | [261.350, 890.450] |
| M1_raw | B1 | 10 | 577.790 | [240.740, 883.530] |
| M1_raw | R_M1_raw_mean5 | 1 | -21.652 | [-85.256, 18.952] |
| M1_raw | R_M1_raw_mean5 | 5 | -21.652 | [-82.328, 14.192] |
| M1_raw | R_M1_raw_mean5 | 10 | -21.652 | [-77.042, 12.698] |
| M1_cal | B0 | 1 | -73.000 | [-166.120, 7.240] |
| M1_cal | B0 | 5 | -73.000 | [-173.740, 0.000] |
| M1_cal | B0 | 10 | -73.000 | [-192.920, 0.000] |
| M1_cal | B1 | 1 | 529.150 | [224.890, 847.620] |
| M1_cal | B1 | 5 | 529.150 | [197.420, 861.000] |
| M1_cal | B1 | 10 | 529.150 | [193.750, 852.770] |
| M1_cal | R_M1_cal_mean5 | 1 | -14.610 | [-101.116, 65.494] |
| M1_cal | R_M1_cal_mean5 | 5 | -14.610 | [-124.306, 81.422] |
| M1_cal | R_M1_cal_mean5 | 10 | -14.610 | [-118.158, 79.554] |
| M2_raw | B0 | 1 | -289.050 | [-502.690, -95.400] |
| M2_raw | B0 | 5 | -289.050 | [-528.570, -63.470] |
| M2_raw | B0 | 10 | -289.050 | [-552.810, -25.860] |
| M2_raw | B1 | 1 | 313.100 | [10.320, 617.810] |
| M2_raw | B1 | 5 | 313.100 | [-1.570, 621.800] |
| M2_raw | B1 | 10 | 313.100 | [8.200, 619.150] |
| M2_raw | R_M2_raw_mean5 | 1 | -20.638 | [-235.100, 191.512] |
| M2_raw | R_M2_raw_mean5 | 5 | -20.638 | [-256.470, 229.534] |
| M2_raw | R_M2_raw_mean5 | 10 | -20.638 | [-278.132, 258.120] |
| M2_cal | B0 | 1 | -10.180 | [-55.700, 28.460] |
| M2_cal | B0 | 5 | -10.180 | [-46.220, 22.500] |
| M2_cal | B0 | 10 | -10.180 | [-48.780, 22.140] |
| M2_cal | B1 | 1 | 591.970 | [274.160, 926.720] |
| M2_cal | B1 | 5 | 591.970 | [253.540, 923.510] |
| M2_cal | B1 | 10 | 591.970 | [235.700, 914.540] |
| M2_cal | R_M2_cal_mean5 | 1 | 41.236 | [-22.100, 108.754] |
| M2_cal | R_M2_cal_mean5 | 5 | 41.236 | [-10.306, 101.940] |
| M2_cal | R_M2_cal_mean5 | 10 | 41.236 | [-12.688, 113.228] |

## Causal quality audit

29234 rows: warmup 63, gap-priority 3402, weekend-priority 1664, past64-flat-priority 16760, eligible 7345 (25.13%). Of the 16760 flat-priority exclusions, 15840 current candles are nonflat and 920 are flat. This directly demonstrates the broad historical-filter effect; it does not establish invalid market data.
History-ready marginal flags overlap: past64-flat 21826, weekend proxy 4940, gaps 3402. Exact masks (gap=1/weekend=2/flat=4): 0=7345, 4=16760, 5=126, 6=1664, 7=3276; masks 1/2/3=0. Actual flat/feed/session cause: UNKNOWN. No original CSV changes.

## Interpretation and next proposed step

All four primary AI arms have negative net. Their differences versus their five-seed random-control means have 5-day intervals spanning zero: no supported incremental selection edge. Reduced activity can reduce losses from the losing B1 baseline, but this design cannot prove that activity is the sole cause. Normalized returns and unequal realized exposure are descriptive; 1/6/30/4 trades do not establish deployment readiness.
Prior-period base rates vary substantially across folds. Use the reported Brier/log-loss and drift tables to compare calibration with the simple BASE_C baseline; calibration fitted in C is not guaranteed to improve V/E. Histogram drift is descriptive, not a causal or significance test.
Positive random-seed outcomes are retained, not selected or promoted. Zero-trade and undefined risk/exposure ratios remain explicit. The old negative PR11 is preserved.
Highest-value proposed next step: independently document provenance/rights, real session calendar and broker symbol/cost specifications, then pre-register an untouched future evaluation and minimum-effect/power plan. No such next stage, download or account connection has been started.

## Reproduction

Python 3.12.14, standard library only. Run `python -I -B verify.py`; then `python -I -B run.py --input <original CSV> --models <PR11 run-003/models.PRIVATE.json> --reference <PR11 run-003/summary.json> --output outputs.PRIVATE/<new-run>`. Run twice with fresh output folders. The exact input/model/reference hashes are checked before execution. Network/process audit guards run in both entry points. Synthetic QA tests exercise fitting only on artificial test data; the real diagnostic performs zero fits.
Contract commit a39fc77 predates new outcomes; implementation commit 8c1f18b was frozen before both runs. `tools/package_results.py` is a post-run checker/exporter and was added after outcomes; it does not modify numerical experiments.
Old 40 external trials and PR11 runs001-004 remain historical/dependent, not independent new evidence. This phase has exactly two full executions with no failed/abandoned numerical trial. Private append-only registry stays local.
