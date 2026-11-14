# AMIN V5: Bid/Ask correctness audit

**Verified code bug:** In original pullback simulation a short-position's unrealized profit used Bid close, whereas closing a short requires buying at Ask = Bid + spread. That can activate trailing protection too early. A quote-aware copy of the engine corrects both closed-bar profit and short trailing-stop quote. The previously frozen original strategy remains untouched.

## Reproduction: Eplanet M15, May–Nov 5 2026, capital $1000

| Assumed slippage each way, USD/oz | Original net USD | Quote-corrected net USD | Corrected trades |
|---|---:|---:|---:|
| 0.10 | +167.35 | +162.61 | 170 |
| 0.30 | +134.09 | +75.32 | 157 |
| 0.50 | +73.85 | +67.93 | 153 |

At 0.30: quote-aware close-to-close trade ledger 157 trades, peak-to-closed-equity drawdown 7.26%, **zero realized trading days at +$50 or above**. Six targeted quote-price regression tests passed and reproducing a fresh patch from the original engine matched the $75.32 net result.

The source used prior-optimized `atr_cost_12`, therefore this is **not pristine out-of-sample performance**, not MT5 execution and not a validated $50/day engine. No trading orders were placed. Data from user's private Eplanet zip is not committed.

## Files
- `quote_math.py`: explicit Bid/Ask close PnL and trailing stop
- `test_quote_math.py`: targeted accounting checks
- `patch_existing_runner.py`: generates a new patched engine from the existing runner rather than mutating frozen source

This branch contains the reproduction patch, not the private historical OHLC data. A full local reproduction package with generated ledgers is available as `AMIN_V5_QUOTE_CORRECTNESS_AUDIT_20261114.zip` in the conversation.
