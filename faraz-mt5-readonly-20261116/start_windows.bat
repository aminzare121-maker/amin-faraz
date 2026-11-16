@echo off
setlocal
cd /d "%~dp0"
title Faraz Amin MT5 Read Only
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 (
 echo Python 3.12 x64 is needed. Trying winget...
 where winget >nul 2>&1
 if errorlevel 1 goto missing
 winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements
 if errorlevel 1 goto missing
)
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 goto missing
if not exist ".venv\Scripts\python.exe" (
 py -3.12 -m venv .venv
 if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install MetaTrader5
if errorlevel 1 goto failed
".venv\Scripts\python.exe" bridge.py
goto failed
:missing
echo Python 3.12 x64 not found. Install from python.org and retry.
:failed
echo Please send a screenshot of this window if an error appears.
pause
