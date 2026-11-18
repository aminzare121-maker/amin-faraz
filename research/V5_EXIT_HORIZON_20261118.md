# V5 exit-horizon research — 2026-11-18

Hypothesis: a fixed time-stop after a persistent 8-bar move changes exposure to reversal and transaction costs. This is an execution/holding-period experiment, not a new entry signal.

Private Eplanet M15 data (23,643 rows) were tested locally. 60% chronological training / 40% held-out evaluation. Initial equity $1,000; dynamic 0.01-lot increments, 1% nominal risk, 0.05 lot cap; 100 oz/lot; estimated spread (26 points / 100), $0.30/oz slippage, $7/lot commission. Conservative stop-first when stop and target both touch in one bar. No real or demo orders.

Training selected horizon=3 bars by train net - 0.5*closed-equity drawdown, BEFORE examining held-out result.

| Horizon bars | Training net USD | Held-out trades | Held-out gross USD | Held-out costs USD | Held-out net USD | Closed DD USD | Days >= $50 |
|---|---:|---:|---:|---:|---:|---:|---:|
|2|133.36|389|216.24|280.12|-63.88|216.93|1|
|3 (selected)|273.36|413|289.10|309.90|-20.80|171.99|0|
|5|95.21|294|284.02|214.39|69.63|155.32|0|
|8|137.51|310|342.03|228.16|113.87|149.43|1|

The independent ATR risk guard (0.5x–2x trailing median ATR) did not change any executed trades; it has no demonstrated incremental value. Counts represent strategy-specific eligible executed entries, not unique underlying market events. Equity carries over from training into held-out segment; the held-out drawdown is recomputed from its first close and is NOT intrabar drawdown. Real broker fills and spread remain unverified. Training-selected variant failed financial target. 8-bar held-out positive result is exploratory and MUST NOT be promoted after looking at held-out results.

Status: REJECT for MT5 demo activation. Private data not committed. Locally executed source: v5_exit_horizon_20261118.py; result: v5_exit_horizon_20261118_results.json.