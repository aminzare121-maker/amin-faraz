@echo off
setlocal
cd /d "%~dp0"
echo ARTIN Automatic PDF Teacher Motor - EPLANET DEMO OBSERVE ONLY
python artin_mt5_demo_autostart.py
if errorlevel 1 echo BLOCKED: Inspect message above - no order sent by observer.
pause