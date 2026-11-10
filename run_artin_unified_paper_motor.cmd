@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if "%~1"=="" (
    echo [ARTIN] Pass the path to a source-observed event JSON.
    echo [ARTIN] Synthetic test is separate from market performance.
    echo [ARTIN] Example: run_artin_unified_paper_motor.cmd "private\teacher_events.json"
    exit /b 2
)
where py >nul 2>nul
if %errorlevel% EQU 0 (set "PY=py -3") else (set "PY=python")
if not exist "private\paper_runs" mkdir "private\paper_runs"
set "OUT=private\paper_runs\artin_%RANDOM%_%RANDOM%.json"
%PY% "%~dp0artin_unified_paper_motor.py" --events "%~1" --pinned-core "%~dp0core" --out "%OUT%"
if errorlevel 1 (
    echo [ARTIN] Engine failed; no broker orders sent.
    exit /b 1
)
echo [ARTIN] Paper execution report: %OUT%
exit /b 0