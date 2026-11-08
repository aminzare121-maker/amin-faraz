@echo off
setlocal
rem Requires preexisting local Python and ephemeral local AMIN_BRIDGE_GH_TOKEN.
rem Exactly one locally owner-approved workspace argument. No arbitrary forwarded args.
if "%~1"=="" (
  echo Usage: START_ONCE_WINDOWS.bat "APPROVED_ISOLATED_WORKSPACE"
  exit /b 2
)
if not "%~2"=="" (
  echo Only the approved workspace argument is accepted.
  exit /b 2
)
set "BRIDGE_PY=python"
if defined AMIN_BRIDGE_PYTHON set "BRIDGE_PY=%AMIN_BRIDGE_PYTHON%"
"%BRIDGE_PY%" "%~dp0bridge_agent.py" --workspace "%~1" --live-handshake --owner-approved-workspace
exit /b %errorlevel%
