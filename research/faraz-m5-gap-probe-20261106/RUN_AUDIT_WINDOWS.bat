@echo off
setlocal
chcp 65001 >nul
set "MT5=%APPDATA%\MetaQuotes\Terminal\Common\Files"
set "SRC=%~dp0faraz_m5_audit.py"
if not exist "%MT5%\FARAZ_probe_M15.csv" (
  echo M15 CSV not found. Run FARAZ_M5_ReadOnly_Export in MT5 first.
  pause
  exit /b 1
)
if not exist "%MT5%\FARAZ_probe_M5.csv" (
  echo M5 CSV not found. Run FARAZ_M5_ReadOnly_Export in MT5 first.
  pause
  exit /b 1
)
py -3 "%SRC%" --m15 "%MT5%\FARAZ_probe_M15.csv" --m5 "%MT5%\FARAZ_probe_M5.csv" --mode probe --out "%~dp0RESULTS"
if errorlevel 1 (
  echo Python launcher unavailable or analysis failed; trying python command.
  python "%SRC%" --m15 "%MT5%\FARAZ_probe_M15.csv" --m5 "%MT5%\FARAZ_probe_M5.csv" --mode probe --out "%~dp0RESULTS"
)
echo.
echo Examine the RESULTS folder. Keep raw CSV files PRIVATE.
pause