@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0compile_artin_v13_shadow.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
echo This compile-only tool does not connect to any account or send any orders.
echo Exit code: %EXITCODE%
pause
exit /b %EXITCODE%