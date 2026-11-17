# V5 multihorizon drift / 2026-11-18

New hypothesis: 16-bar (4h) directional efficiency >0.35, move >2 prior median true ranges, and 2-bar countertrend pullback. Signal after close; next open fill; stop 2x median TR, target 3x, maximum 13 bars. 1% equity risk with 0.01 lot increments, assumed 100 oz/lot, assumed $1.46 roundtrip per 0.01 lot; **fees not broker verified**. Stop-first when both touched. 60/40 chronological split of 23,643 private Eplanet M15 candles. No private market data committed.

|Segment|Variant|Opportunities|Trades|Gross USD|Estimated cost|Net USD|Closed DD|Days >=$50|
|---|---|---:|---:|---:|---:|---:|---:|---:|
|Train|Base|994|24|9.06|35.04|-25.98|69.49|0/156|
|Train|Execution guard|996|23|-4.11|33.58|-37.69|69.49|0/156|
|OOS|Base|697|36|72.10|52.56|19.54|45.21|0/104|
|OOS|Execution guard|734|0|0|0|0|0|0/104|

Guard: opening gap <=0.25 prior median TR and spread <=30 raw units. The guard removes all OOS trades; no evidence of risk reduction with usable returns. Base OOS gain is only $19.54 over 104 days, far short of required $50 net each trading day. All filled trades were 0.01 lots due to risk constraint. Closed-equity DD only, intrabar floating DD and actual Eplanet costs unverified. Research-only, no MT5 demo or live orders. Executed local source: v5_multihorizon_drift_20261118.py; detailed ledger local only, not committed.