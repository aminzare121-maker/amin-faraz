# V5 compression/expansion hypothesis — 2026-11-16
Dataset: private Eplanet M15 merged CSV (not committed).
Economic hypothesis: directional range expansion following four quiet bars may persist for one hour.
Signal: previous four mean ranges < 0.65 * previous 96-bar median range; completed signal candle range > 1.35 * median, body > 0.65 * range.
Enter at next M15 open, exit at fourth subsequent close. Direction follows signal candle. Ignore time gaps. Assumed all-in execution cost: 0.80 USD/oz round trip. Contract multiplier 100 oz/lot. Initial equity $1,000; cap nominal risk at 1% equity using twice median range, 0.01 lot minimum. No live trades.
Chronological 70/30 split; no tuning on OOS. 23,643 rows.
Results: train 4 trades, wins $31.87, losses -$8.79, net +$23.08, closed-trade DD $8.79.
OOS 2 trades, wins $0, losses -$22.93, net -$22.93, closed-trade DD $22.93.
REJECTED: fails $50 net/day and sparse opportunities. No tick-level execution, stop simulation, or broker-confirmed fees; do not enable on demo.
