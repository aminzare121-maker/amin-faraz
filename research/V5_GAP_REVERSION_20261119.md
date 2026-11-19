# V5 opening-gap mean reversion — 2026-11-19
Economic hypothesis: a large difference between previous M15 close and next open reflects temporary liquidity dislocation and may mean-revert. Only contemporaneous prices are used.
Private Eplanet M15 CSV: 23,643 rows. Chronological 60/40 split. Select threshold on training only.
Selected threshold: 0.5 x prior 96-bar median range.
Training: 21 opportunities, 12 trades, gross +$18.95, cost $7.56, net +$11.39, closed-equity drawdown $40.96.
Holdout: 7 opportunities, 7 trades, gross -$5.05, cost $4.41, net -$9.46, closed-equity drawdown $11.39; 0 days >=$50.
Assumptions: $100/lot per $1 gold move; $0.26/oz spread + $0.30/oz roundtrip slippage + $7/lot commission; 1% risk sizing with minimum 0.01 lot; stop wins same-bar ambiguity; max four bars. No swap/tick replay/broker validation.
Decision: REJECT; insufficient opportunity frequency and negative out-of-sample net. No demo or live activation.
