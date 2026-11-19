# V5 session volatility experiment — 2026-11-19

Source: private Eplanet M15 merged CSV, 23,643 bars; private data NOT committed. Chronological 60/40 split, 156 train days and 104 OOS days.

Hypothesis: an unusually large trailing one-hour displacement may continue or mean-revert differently by UTC liquidity session. Signal uses only closed bars. Candidate sessions: 07–12 UTC, 13–18 UTC, all hours; continuation and reversal. Training selected European-session reversal, despite training being unprofitable (-$280.53 net). No trading authorization.

OOS: 715 opportunities, 343 simulated trades, gross -$213.17, estimated execution cost $239.85, net -$453.02, maximum closed-equity drawdown $526.84, approximate bar-level floating drawdown $531.99; 0/104 days >= $50 net. Independent risk-guard role (exclude ATR/base >1.5 or ATR<3): 339 trades, gross -$235.40, cost $237.25, net -$472.65, closed drawdown $556.62; worse than baseline.

Model: $1,000 initial balance; 100 oz/lot; variable lot floored to 0.01; max 0.1; nominal $10 stop risk; stop = max($3,0.9*ATR32); target 1.5R; 5-bar timeout; estimated $0.65/oz roundtrip costs. If both TP and SL hit same bar, SL wins. All results are bar-based research simulations, NOT MT5 execution. Broker commissions, swaps, tick sequencing, slippage, and margin are not verified.

Decision: REJECT both strategies, NO DEMO OR LIVE TRADING. Private dataset and trade ledger remain outside GitHub.
