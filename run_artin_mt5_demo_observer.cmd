@echo off
setlocal
cd /d "%~dp0"
echo ARTIN V13: MT5 DEMO read-only CSV observer (V2 collector to V5 archive)
echo No trading, no MetaEditor compilation, no broker login performed by this launcher.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 artin_mt5_local_observer_launcher.py --watch %*
) else (
    python artin_mt5_local_observer_launcher.py --watch %*
)
set "ARTIN_EXIT=%ERRORLEVEL%"
if not "%ARTIN_EXIT%"=="0" (
    echo ARTIN STOPPED with error code %ARTIN_EXIT%.
    echo Check the reported reason. Existing V5 receipts and checkpoint are preserved.
    pause
)
exit /b %ARTIN_EXIT%