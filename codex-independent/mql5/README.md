# Independent read-only capture script

`ArtinIndependentCapture.mq5` is a **script**, not an EA. It runs once and has
no trading, account-login, WebRequest, indicator-install, or order APIs. It does
not change a chart's current timeframe or enable automated trading. Do not
replace an existing chart EA to run it: use a separate disposable chart if the
owner's existing terminal is used.

Inputs: `InpSymbol` defaults to `XAUUSD.st` and accepts only that name or
`XAUUSD`; `InpClosedBars` defaults to 512, bounded to 1..100000. Timeframe is
fixed at `PERIOD_M15`. The account must be DEMO, server exactly `ePlanet-MT5`,
company contain `eplanet`, and terminal be connected. Guards fail closed.

`CopyRates(symbol, PERIOD_M15, 1, count, rates)` excludes the current candle.
Data are in physical oldest-to-newest order (`ArraySetAsSeries(false)`), checked
for strictly increasing timestamps, finite positive OHLC, consistent ranges,
and nonnegative volumes/spread. The current-bar boundary is captured before
the copy and checked again after it. Each exported candle must end no later
than that boundary. Native server integers are preserved; no UTC/local-time
conversion or assumption about the broker's timezone is applied. Gaps between
bars are preserved and are **not** classified as market closures, missing data,
or teacher FVGs by the script.

Output is a unique UTF-8 JSON file under the MT5 `FILE_COMMON` sandbox:
`ArtinCodexIndependent/capture_<server_seconds>_<tickcount>.json`. A temporary
file is written as explicit UTF-8 bytes in binary mode, flushed, then renamed
without replacing previous captures. Binary mode prevents the text writer from
expanding LF to CRLF and invalidating exact byte-count comparisons.
Header includes schema/magic, symbol, timeframe, closure boundary, requested
and received counts, partial-history flag, and no login/account identifiers.
`bars` contain `time, open, high, low, close, tick_volume, spread, real_volume`.
Short history is explicitly marked `partial_history=true`; it is never called
complete history. Runtime timings are printed in microseconds; JSON includes
receive and validation timings. Python archive ingestion supplies SHA-256,
full-file validation, persisted timings, deduplication, recovery, and chain
verification. MQL reopens the published file and compares its bytes to the
ASCII-only JSON document; that readback is not a SHA integrity claim.

This implementation does not auto-attach to MT5, modify installed files, change
security settings, switch accounts, log in, or submit orders. Compile and actual
DEMO execution evidence must be recorded separately; source existence is not
proof of either.
