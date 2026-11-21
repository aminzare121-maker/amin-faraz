# V5: directional exhaustion / shrinking third candle (2026-11-21)

Source: private Eplanet M15 merged CSV, 23,643 rows. Private market data NOT committed.

New hypothesis: after three same-direction candle bodies with the third shrinking below 65% of the previous body, enter against the move at next bar open. Exit at fifth subsequent bar open (four bars held). Separate risk-control variant: stop at 1.5x prior 20-bar ATR. No future prices used in signal. Chronological 60/40 split (index 14185).

Assumptions: initial equity $1,000 in each split; variable lots using 1% equity / (1.5 ATR * 100oz), rounded down to 0.01 lot; no trade if below 0.01 lot. Round-trip cost assumed $0.45/oz (unverified); conservative stop fill at threshold; closed-equity drawdown only.

| Segment | Variant | Candidate signals | Executed | Gross wins | Gross losses | Costs | Net | Max closed DD | Days >= $50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | Hold | 991 | 69 | 102.03 | -313.88 | 31.50 | -243.35 | 249.97 | 0 |
| Train | Stop | 991 | 82 | 148.73 | -280.06 | 37.35 | -168.68 | 188.67 | 0 |
| OOS | Hold | 658 | 115 | 397.70 | -524.16 | 51.75 | -178.21 | 287.75 | 1 |
| OOS | Stop | 658 | 209 | 749.42 | -712.57 | 94.95 | -58.10 | 212.47 | 1 |

Decision: REJECT both variants for demo; no $50 net per trading day. Stop is a separate loss-mitigation component, but still loses money. Caution: 1% sizing is based on hypothetical stop distance even in no-stop hold variant, so realized loss may exceed 1%. Broker execution costs, tick ordering and floating drawdown unverified. This report records a local Python test; executable source was generated locally but not committed here. No live or demo trades placed.
