@echo off
cd /d "%~dp0"
where node >nul 2>&1 || (echo Node.js is required: https://nodejs.org/ & pause & exit /b 1)
where py >nul 2>&1 || (echo Python is required: https://python.org/ & pause & exit /b 1)
call npx --yes dukascopy-node -i xauusd -from 2025-11-04 -to 2026-11-03 -t m15 -f csv
if errorlevel 1 (echo DOWNLOAD FAILED & pause & exit /b 1)
py -m pip install pandas numpy
py analyze.py
pause
