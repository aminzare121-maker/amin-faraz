# V5 close-location experiment — 2026-11-18

Hypothesis: extreme close location in a 15-minute candle predicts one subsequent candle, with direction (follow/fade) and volatility ceiling chosen exclusively on the first 60% of historical Eplanet M15 bars. 40% chronological holdout untouched during selection.

Data: private Eplanet_M15_20251105_20261105_merged.csv, 23,643 rows; never commit raw data.

Training best among eight configurations: follow, close-location threshold 0.90, maximum signal candle range 1.5 times preceding 24-bar mean range; **training net -$360.88**.

Holdout (104 distinct dates): 1,780 opportunities; 565 simulated trades; gross +$13.29; estimated execution costs $421.91; **net -$408.62**; maximum closed equity drawdown $424.32; approximate intrabar drawdown $427.68; zero days with net profit >= $50. Guard: spread <=30 points and signal candle range <=1.5x prior mean; **0 trades** (not evidence of success).

Assumptions: initial equity $1000, variable volume 0.01–0.15 lots; estimated 100 oz per lot; spread points x $0.01/oz, $0.30/oz slippage, $7/lot roundtrip; next-open entry, next-close exit, no SL; no live execution, broker contract unverified. The strategy loses money even in training. Do not activate on MT5 demo or live.

Reproducible local Python and full JSON ledger generated separately; upload to this branch still pending. No private data published.
