@echo off
setlocal
set "FARAZ_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%FARAZ_PY%" (
  echo Python 3.12+ is required. Run: python -B tools/run_offline_demo.py
  exit /b 1
)
"%FARAZ_PY%" -B "%~dp0tools\run_offline_demo.py"
exit /b %errorlevel%
