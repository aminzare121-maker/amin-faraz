@echo off
setlocal
cd /d "%~dp0"
echo ARTIN V13 V6: compile V2 read-only collector and stage EX5 for manual DEMO chart attachment.
echo No auto-attach, no trading, no orders.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0compile_artin_v13_shadow.ps1"
if errorlevel 1 (
 echo COMPILATION FAILED. See receipt under LOCALAPPDATA\ArtinV13\compile-check-v3
 pause
 exit /b 1
)
where py >nul 2>&1
if errorlevel 1 (
 python "%~dp0artin_mt5_demo_stage_v6.py"
) else (
 py -3 "%~dp0artin_mt5_demo_stage_v6.py"
)
set "ARTIN_CODE=%ERRORLEVEL%"
echo.
if "%ARTIN_CODE%"=="0" (
 echo EX5 staged only. You must still attach it MANUALLY to an XAUUSD M15 DEMO chart.
 echo Next: after CSV appears in the MT5 Common Files folder, run run_artin_mt5_demo_observer.cmd
) else (
 echo STAGING BLOCKED. No original MT5 program or existing EA was modified.
)
pause
exit /b %ARTIN_CODE%