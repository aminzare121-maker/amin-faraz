# V5 failed liquidity sweep — 2026-11-17
Data: private Eplanet M15, 23643 bars; chronological split 14185 (60/40). Not published.
Hypothesis: failure to hold a new 12-bar high/low signals short-term reversal; next-bar open, stop 1.2x previous 24-bar median range, exit fourth bar close. Variable lots by equity risk.
Train base: 1118 candidates, 274 trades, gross +7.39, cost 763.58, net -756.19, closed-equity DD 914.08.
Holdout base: 780 candidates, 308 trades, gross -96.35, cost 725.62, net -821.97, DD 860.74, 2 days >= $50.
Holdout risk guard (spread <=1.3x recent median, range <=2x ATR, 1% risk rather than 2.5%): 780 candidates, 191 trades, gross -95.19, cost 280.32, net -375.51, DD 384.83, 0 days >= $50.
Cost scenario $1.46/oz roundtrip, 100 oz/lot, 0.01-lot minimum. Stop-first OHLC simulation; no tick-based fill validation or broker-specific costs. REJECT for demo. No orders sent.
Local runnable source: v5_liquidity_sweep.py; result: v5_liquidity_sweep_results.json. Source not yet committed; private dataset not published.
