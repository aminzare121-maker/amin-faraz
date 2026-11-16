# V5 channel-breakout / execution-risk experiment (2026-11-16)
Research-only, no MT5 order placement. Private Eplanet candles are NOT included.

## Hypothesis
A close outside the prior 20-bar channel after a relatively compact channel (range <= 5 x lagged ATR20), aligned with lagged 20-bar momentum and above median tick activity, may capture continuation. A separate execution/risk gate rejects an opening gap >0.5 lagged ATR or signal bar >2.5 lagged ATR. Both gates use information available at signal close or next-bar open.

## Reproduction
Run the companion Python source `v5_session_breakout.py` (delivered separately in the research run) against the private `Eplanet_M15_20251105_20261105_merged.csv`. 60% chronological train / 40% test, 23643 candles. One position at a time, next open, stop=1.2 ATR, target=2 ATR, time exit=6 bars, stop-first when both touched. Lot floor to .01, risk budget $10 and max .10 lot, skip lot <.01. Proxy $0.86/oz round-trip transaction cost; contract assumed 100oz/lot. No commission beyond that proxy, no live execution. Intrabar equity DD is not measured.

| sample | risk gate | signals | trades | wins | gross USD | cost USD | net USD | closed DD USD | net/day USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| train | off | 543 | 202 | 79 | -74.59 | 182.32 | -256.91 | 357.20 | -1.65 |
| train | on | 552 | 160 | 63 | -79.50 | 143.62 | -223.12 | 301.77 | -1.43 |
| OOS | off | 331 | 226 | 87 | -38.88 | 202.96 | -241.84 | 311.82 | -2.33 |
| OOS | on | 344 | 178 | 72 | 21.12 | 157.38 | -136.26 | 198.67 | -1.31 |

Signals differ because skipping positions changes the occupied-bar state. Gate reduces loss and closed DD but does not make the strategy profitable. **Reject for demo.** Target >=$50 net every trading day not achieved. No guarantee.