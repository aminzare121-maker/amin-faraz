@echo off
setlocal
cd /d "%~dp0"
set "TASK_PYTHON=%ARTIN_PYTHON%"
if not defined TASK_PYTHON (
  where py >nul 2>&1
  if not errorlevel 1 set "TASK_PYTHON=py"
)
if not defined TASK_PYTHON (
  where python >nul 2>&1
  if not errorlevel 1 set "TASK_PYTHON=python"
)
if not defined TASK_PYTHON if exist "%~dp0..\..\..\..\Amin-MT5-0.4.1\amin-mt5\.venv-demo-041\Scripts\python.exe" set "TASK_PYTHON=%~dp0..\..\..\..\Amin-MT5-0.4.1\amin-mt5\.venv-demo-041\Scripts\python.exe"
if not defined TASK_PYTHON (
  echo Existing Python not found. Set ARTIN_PYTHON to an existing interpreter. Nothing will be installed.
  exit /b 2
)
"%TASK_PYTHON%" -B run_engine.py --demo --output DEMO_RESULT.json
exit /b %errorlevel%
