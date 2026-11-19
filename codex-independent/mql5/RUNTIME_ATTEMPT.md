# Actual MQL script runtime attempt

Current status: **PASS — ACTUAL v1.01 MQL SCRIPT CAPTURE VALIDATED**,
2026-11-10. Earlier observations below are chronological, not the final result.

The parent recorded actual MetaEditor success separately: EX5 generated,
0 errors / 0 warnings. This record concerns runtime only.

The existing ePlanet DEMO window was selected by exact executable path and
returned window identity. A separate XAUUSD.st H1 chart was opened for the
one-shot script so the existing M15 chart and its AminReadOnlyBridge EA were
not replaced. Existing H4 and Daily charts were preserved. The script itself
always requests M15 independently of the chart timeframe.

Only our two new files were copied into the previously absent dedicated
`MQL5/Scripts/ArtinCodexIndependent/` folder under the exact existing ePlanet
data directory. An initial automatic review rejected that copy based on the
older MT5-preservation restriction. The same direct operation was retried
only after reading the new owner's explicit instruction to run the independent
DEMO test and explaining its narrower scope. That reviewed retry was accepted;
there was no workaround or alternate terminal.

Navigator was displayed. Before its script list could be refreshed and the
script launched, two state-derived UI actions following fresh observations
were blocked by: `user input was detected in this window; call get_window_state
before continuing`. UI work stopped to avoid conflicting with live input.
The script was not attached or run. No runtime success is claimed.

No account/login, global Algo Trading, EA, security setting, existing installed
file, or vendor-test terminal was modified. No terminal restart or order was
performed. The added chart and Navigator remain open; the user can close the
new chart later if desired. Do not close an original chart by title alone,
because duplicate XAUUSD chart titles now exist.

Next runtime attempt: on the separate no-EA chart, refresh the Scripts tree,
locate ArtinCodexIndependent/ArtinIndependentCapture, inspect script properties,
and run only if no security/trading changes are requested. Then independently
verify a new FILE_COMMON capture and its actual contents. A compile pass or
Python SDK capture is not proof that this MQL script ran.

## Resumed after owner explicitly freed the desktop

The owner then explicitly stated that the system was free for desktop work.
Fresh observations succeeded. The main window was maximized only to bring the
floating Navigator inside its capture bounds. Indicators and Expert Advisors
tree groups were collapsed, Scripts was refreshed, and the exact independent
script appeared. The original charts/EA were not removed.

Opening the script reached its actual properties dialog. The Common tab had
`Allow Algo Trading` **checked by default**. No OK action was performed and
the checkbox was not changed. The Computer Use skill's mandatory restriction
against changing in-app security settings or acting on security permission
requests prevents the agent from granting or changing that permission itself.
The dialog remains visible for the owner to personally uncheck this per-script
option. This is not the global Algo Trading toolbar button. After owner action,
the inputs and disabled trading option must be observed afresh before running.

The installed EX5 intended for this attempt remains SHA256
`9689163ee853946e33c5521a88b219e7fb04f05bebf63085ab02ee1da47fd49e`.
Parent recompiled the unchanged source afterward and obtained another EX5 due
to compiler build metadata; it did not overwrite this installed binary. Runtime
proof must identify the binary actually executed, not the later workspace build.

## Actual v1.00 failure and narrowly tested source correction

On a later fresh observation, the original properties dialog had disappeared.
The dedicated Common output folder existed with only
`capture_1794341780_560148984.json.tmp` (94136 bytes). The script-specific log
reported `ARTIN_CAPTURE_BLOCKED: EXPORT_WRITE_FAILED`. The agent had not
clicked OK; nevertheless the log/file prove actual script execution occurred.
Do not call this execution successful or say it never ran.

The temporary file ended in CRLF, while the intended document ended in LF.
MQL's FILE_TXT writer expanded the newline, so a strict comparison of its byte
count with StringLen rejected the export. The failed temporary file was left
untouched. The installed v1.00 MQ5 and EX5 were preserved locally as
`failed-v100.mq5` and `failed-v100.ex5` before replacing only our own dedicated
installed files. No other installed files were overwritten.

v1.01 uses StringToCharArray(..., CP_UTF8), excludes its trailing NUL via
ArrayResize(encoded-1), writes uchar bytes with FileWriteArray in FILE_BIN,
and compares exact byte count plus complete readback. A relative 900-second
grid check against the captured current-bar boundary was also added, without
assuming a UTC broker epoch or converting timestamps.

Actual MetaEditor compile after these changes: 0 errors / 0 warnings,
compiler 5.0.0.6230, UTC 2026-11-10T18:19:24.4774249Z. Current source SHA256:
`732f550fa1125144bc79fbe55098a7e158d8ccd67cdadf9ed98a4979fa8d77fd`;
compiled and installed EX5 SHA256:
`4a75afb83008348f159fc69abbb76d6c499f3bc8580b3385f184359116e749bd`.
The sanitized actual compile report is maintained by compile.ps1 in reports/.

The v1.01 properties dialog was opened afresh and its titlebar clicked to bring
it to the foreground. `Allow Algo Trading` is again checked by default, so the
agent has not clicked OK or changed that option. Owner must personally remove
the tick and leave this dialog open for observation before the corrected
runtime test. Runtime v1.01 is **not yet verified** at this checkpoint.

## Successful v1.01 execution after owner action

The owner personally removed the per-script Algo Trading tick and clicked OK.
The new published capture appeared; the agent did not launch a duplicate run.
`reports/actual-mql-runtime.json` records independent checks against actual
installed source/EX5 bytes, the complete JSON payload and the script's own
sanitized result line. No raw account log was exported.

Actual output: `capture_1794342061_560429578.json`, 94133 bytes, SHA256
`45a640021693d9f180c3575c9bba0ec2d974a523af8697204016efe718732318`.
It contains 512 unique closed XAUUSD.st M15 bars, no partial-history flag,
valid finite OHLC, nonnegative volume/spread and native timestamp grid.
First bar native1793690100; last1794340800; current-bar fence1794341700.
The last captured candle ends exactly at the excluded current-bar boundary.
Five timestamp discontinuities are preserved without classifying them as
missing data, session closure or teacher FVG.

The output is LF-terminated exact binary UTF-8, no NUL/BOM or CRLF expansion.
The old failed temporary file remains preserved. Actual runtime timings in
microseconds: receive13, validation2, processing34358, storage1599,
verification5269, total41369 (41.369 ms). These are one MQL candle snapshot's
timings, not an Artin video-extraction time or a sustained throughput result.

Orders submitted0. This pass does not certify semantic rules, network-disconnect
recovery, Windows reboot persistence, complete market history or trading.
