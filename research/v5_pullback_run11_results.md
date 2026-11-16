# V5 pullback experiment — 2026-11-16

Private input: Eplanet_M15_20251105_20261105_merged.csv (23,643 bars). No private market data committed.

Hypothesis: an 8-bar directional trend followed by a countertrend candle that tests the prior extreme may yield a short-term continuation; reverse side is independent control. Lagged 48-bar moving average and 20-bar median high-low range used. Enter next M15 open, stop 1.2x median range, target 1.8x, max six bars, stop-first OHLC. Sizing floor(1% current equity/(stop*100)) to 0.01 lot, max 0.10, skip below 0.01. Spread points x $0.01/oz, $0.20/oz slippage and $7/lot commission. Chronological 65/35 split, starting $1000 separately per period. Independent filter: signal candle range <=1.4x lagged median and spread <=30 points.

Local Python execution (not yet independently reproduced from GitHub):

| Period | Side | Filter | Trades | Gross wins | Gross losses | Costs | Net | Closed DD | Days >= $50 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Train | Follow | No | 298 | 1230.58 | -1072.75 | 176.89 | -19.06 | 177.10 | 0 |
| Train | Follow | Yes | 107 | 464.57 | -349.22 | 59.53 | +55.81 | 73.28 | 0 |
| Train | Fade | No | 274 | 985.92 | -1067.78 | 163.70 | -245.56 | 337.99 | 0 |
| Train | Fade | Yes | 97 | 308.66 | -370.98 | 53.37 | -115.69 | 126.85 | 0 |
| Test | Follow | No | 352 | 1700.96 | -1343.63 | 252.43 | +104.91 | 136.33 | 1 |
| Test | Follow | Yes | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Test | Fade | No | 225 | 659.51 | -865.06 | 144.38 | -349.93 | 406.36 | 0 |
| Test | Fade | Yes | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Out-of-sample spans 91 distinct trading dates. **REJECT**: $50 net/day condition failed; risk filter did not transfer to holdout. Filtered zero-trade result does not establish low risk. No demo activation.

Caveats: OHLC stop-first approximation, no tick replay, margin/stop-out or swaps. This commit records results, not executable source; local code must be copied and exact commit independently rerun before any promotion.
