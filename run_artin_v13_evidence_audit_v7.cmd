@echo off
setlocal
cd /d "%~dp0"
echo ARTIN V13 V7 - local file evidence audit (NO ORDERS)
echo V5 will read the existing V2 CSV once; then ALL V5 receipts will be replayed.
echo This cannot verify real MetaEditor compilation or the broker account.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0artin_mt5_evidence_audit_v7.py" --capture-new %*
) else (
  python "%~dp0artin_mt5_evidence_audit_v7.py" --capture-new %*
)
set "ARTIN_CODE=%ERRORLEVEL%"
if not "%ARTIN_CODE%"=="0" (
  echo V7 BLOCKED - see the reported reason. No trades.
) else (
  echo V7 LOCAL FILE AUDIT complete. NOT a live broker certification.
)
pause
exit /b %ARTIN_CODE%