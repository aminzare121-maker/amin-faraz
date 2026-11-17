# V5 hour-conditioned continuation — 2026-11-18

Hypothesis: 2-bar momentum continuation is economically useful only at certain UTC hours, due to session liquidity. Train first 60%, test last 40% of 23,643 Eplanet M15 candles. No late-arriving signals.

Training gate: at least 80 examples per (UTC hour, direction), and mean next-bar return net of $1.46/oz cost > $0.50/oz. **Zero combinations qualified.** Therefore OOS strategy and risk-filter strategy both take zero trades, net $0, drawdown $0, 0 days above $50. This is abstention, not profitability.

Diagnostic only, without training gate: 9,348 candidate opportunities; 225 risk-affordable simulated trades (0.01 lot); gross -$169.07; assumed costs $328.50; net -$497.57; closed-equity drawdown $500.86; 27 traded dates; 0 dates >= $50. Initial equity $1,000; 1% risk cap; lot rounded down to 0.01; $100/oz/lot. The diagnostic is NOT an approved trading strategy.

Limitations: $1.46/oz roundtrip costs assumed, not confirmed broker execution; next-bar OHLC cannot prove intrabar ordering or live fills. No demo/live order. The exact executable local source and JSON were produced in this run; private Eplanet CSV not committed.
