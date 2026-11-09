@echo off
setlocal
if "%~1"=="" (
  echo Drag your local prices-only CSV onto this RUN_LOCAL.bat.
  echo Historical CSV stays on this computer; do not upload it.
  pause
  exit /b 2
)
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
%PY% "%~dp0faraz_offline_lab.py" --csv "%~1" --out "%~dp0faraz_aggregate_result.json"
if errorlevel 1 (
  echo Research run failed. No trade or broker request was made.
  pause
  exit /b 1
)
echo Local aggregate report created: %~dp0faraz_aggregate_result.json
pause
