# V5 — cost-aware trend pullback, independent research branch

## Experiment
On the existing EMA(21/100) pullback, retain only closed-M15-candle conditions with ATR(14) above median ATR of 96 prior bars. Compare `stop_distance/(closed_bar_spread+0.30)` thresholds 6, 9, 12, 15, where stop distance = max(2 USD/oz, 1.1×ATR). Source: private Eplanet XAUUSD M15 (never commit private dataset). Initial equity $1000, dynamic lot sizes, one position at a time, conservative stop priority, commission/slippage as in prior engine.

## Continuous May–October results, dollars net, slippage each side

| Method | 0.10 | 0.30 | 0.50 |
|---|---:|---:|---:|
| ATR gate only | +12.73 | -62.80 | -222.80 |
| ATR gate + cost ratio >=9 | +42.03 | -31.94 | -214.22 |
| ATR gate + cost ratio >=12 | +204.10 | +53.41 | -45.76 |
| ATR gate + cost ratio >=15 | +60.25 | -46.31 | -49.12 |

The 12-threshold exploratory result at 0.10 slippage had 141 trades and 6.25% drawdown marked after closing transactions, not continuous floating-equity drawdown.

**Critical selection leakage warning:** the threshold chosen for highest May–June validation PnL among candidates with >=20 trades would be **15**, which then lost **$82.74 in July–October**. Choosing 12 after seeing the later data is exploratory/post-hoc, not an independent holdout success. July–October was reused in earlier V5 experiments. No strategy passed $50 net/day, or cost stress at 0.50. No demo trades placed.

Full runnable Python source, tests, and CSV reports were created in the conversation artifact named `AMIN_V5_COST_TO_RISK_EXPERIMENT_20261114.zip`. This GitHub file is a continuity receipt, not the complete runnable code. The original Eplanet zip and all private history are deliberately excluded.
