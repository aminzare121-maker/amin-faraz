# Compression-release independent hypothesis (2026-11-14)

Hypothesis: after eight M15 candles compressed relative to trailing 96-bar mean true range, a directional close outside the previous range can produce continuation. Signal uses closed bar only, entry next bar; costs and risk inherited from earlier rejection_engine replay: historical spread, slippage each way, $10/lot round trip commission, 1% risk cap, 0.01 minimum lot, 1.6R target, six-bar timeout, pessimistic intrabar stop priority.

| Period | Slippage/side | Net USD | Trades | Closed equity DD | Days >= $50 |
|---|---|---|---|---|---|
| Jan-Mar 2026 | 0.10 | -6.93 | 118 | 10.56% | 0 |
| Jan-Mar 2026 | 0.30 | -70.55 | 86 | 13.49% | 0 |
| Jan-Mar 2026 | 0.50 | -70.25 | 83 | 13.31% | 0 |
| Apr-Nov 5 2026 | 0.10 | -406.30 | 255 | 46.43% | 1 |
| Apr-Nov 5 2026 | 0.30 | -400.59 | 202 | 45.22% | 0 |
| Apr-Nov 5 2026 | 0.50 | -392.35 | 132 | 41.68% | 0 |

At 0.30 in later period: 1652 raw signals; 1423 size skips; 17 daily risk skips. This is chronological testing but **not pristine out-of-sample**, because later 2026 months have been used in prior research. No parameter tuning after viewing results. Rejected for demo. The research script depends on the previously existing `rejection_engine.py`; no private Eplanet history is committed. No live or demo trades executed.
