# V5 spread shock recovery — research log (2026-11-16)
Input (private, not committed): Eplanet_M15_20251105_20261105_merged.csv; 23643 M15 bars.
New hypothesis: after abnormal bid/ask spread expansion, normalization may cause reversal or continuation of the shock candle.
Signal: prior spread > 1.7x prior 48-bar median; current spread <1.15x prior median and <=40 points; prior candle body >0.5x lagged 48-bar median range; adjacent timestamps exactly 900s.
Entry next bar open, 5-bar maximum hold, stop=1.5x lagged median range, target=1.5x stop, stop-first OHLC resolution.
Sizing floor(5 USD/(stop distance *100 USD/oz per lot)) to 0.01 lot, maximum 0.10; skip below 0.01.
Cost spread points * 0.01 USD/oz + 0.20 USD/oz assumed slippage, plus 7 USD/lot commission.
Risk filter independently requires current spread <=0.85x prior median.
65/35 chronological split at row 15367.
Results:
train fade 1 trade: gross win 7.47, costs 0.54, net +6.93, closed DD 0.
train follow 1 trade: gross loss -4.98, costs 0.54, net -5.52, closed DD 5.52.
test fade/follow: 0 eligible trades, net 0, drawdown 0, days >=50 USD 0.
filtered train/test: 0 trades.
REJECT: insufficient frequency and zero OOS trades. No MT5 demo activation.
Limitations: no tick replay, margin, stop-out, or swap. The executable Python script is local, not included in this commit; this record is NOT an independently reproducible code commit.
