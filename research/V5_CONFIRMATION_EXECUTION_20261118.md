# V5: one-bar confirmation execution (2026-11-18)

Data: private Eplanet M15 CSV, 23,643 rows. No private price data committed. Chronological 60/40 split, test starts 2026-06-15 05:45 UTC; 104 trading dates.

Hypothesis: wait for one directionally favorable M15 confirmation candle before entering an efficient eight-bar trend, reducing false starts. Independent role: execution/risk filter, not a new alpha claim. Entry at next bar open, no future prices in signal.

Parameters fixed for this comparison: eight-bar efficiency >=0.72, displacement >=1.1 ATR, impulse <=1.4 ATR; stop 1.3 ATR, target 2 ATR, time exit after up to six candles; 1% equity risk, lots 0.01-0.05. Confirm candle direction favorable, close not below signal close in direction, range <=1.5 ATR. OHLC stop-first conservative collision. Assumed 100 oz/lot, spread points /100, $0.30/oz round-trip slippage, $7/lot commission; actual Eplanet costs not verified.

| OOS metric | Immediate entry | Confirmed entry |
|---|---:|---:|
| opportunities | 512 | 615 |
| trades | 267 | 100 |
| gross USD | +322.41 | +41.05 |
| cost USD | 193.20 | 72.77 |
| net USD | +129.21 | -31.72 |
| max closed-equity drawdown USD | 141.53 | 111.45 |
| trading days net >= $50 | 2/104 | 0/104 |

Different opportunity counts reflect position occupancy and skipped entries. Worst single-trade observed adverse excursion was $28.78 vs $18.72, not portfolio intrabar max drawdown. Confirmation reduced drawdown but destroyed net profitability. Reject confirmation filter; neither configuration meets $50 net every trading day. Do not activate demo or live orders. Code: research/v5_confirmation_execution.py. Local JSON contains full ledger and is not committed because it contains private-derived trade timestamps.
