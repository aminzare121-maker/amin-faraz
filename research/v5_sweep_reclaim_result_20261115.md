# Research result: sweep/reclaim candidate, NOT approved for demo
Data: private Eplanet_M15_20251105_20261105_merged.csv, 23643 rows. No private data uploaded.
Signal: low < prior 16-bar low - 0.1*ATR20, close reclaims low and bullish candle => BUY next open; symmetric high sweep => SELL. ATR uses previous bars only. SL=max(1.5,1.1*ATR), TP=1.5*SL, timeout 8 bars, adverse-first same-bar fill. 1% equity risk, 0.01 lot increments. Cost: broker spread points*0.01 plus 0.60 USD slippage and 7 USD commission per lot. XAUUSD 100 oz/lot.
Split: first 70% development, last 30% holdout beginning 2026-07-21 06:30 UTC. Each split reset to 1000 USD.
Development: 671 raw signals; 153 executed; 58 wins; 95 losses; net -233.90 USD; cost 148.38 USD; max drawdown 24.35%; 73 trade days, zero days >=50 USD.
Holdout: 318 raw signals; 138 executed; 51 wins; 87 losses; net -230.50 USD; cost 142.98 USD; max drawdown 23.05%; 60 trade days, zero days >=50 USD.
Caveat: costs are modeled, not broker-confirmed. M15 intrabar ordering unknown; stop-first conservative. 0.01-lot minimum prevents execution of many signals.
Decision: REJECT as standalone profit engine. Do not activate on MT5 demo. Potential loss-filter role requires independent paired-signal evaluation, not established here.
