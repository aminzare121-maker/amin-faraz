@echo off
setlocal
cd /d "%~dp0"
echo Amin Windows Bridge - one-time, limited connection test
set /p WORKSPACE=Enter the full folder path of the APPROVED project workspace: 
if "%WORKSPACE%"=="" (
 echo No workspace selected. Exiting.
 pause
 exit /b 2
)
where py >nul 2>&1
if not errorlevel 1 (
 py -3 "%~dp0bridge_agent.py" --repo aminzare121-maker/amin-faraz --issue 38 --workspace "%WORKSPACE%"
) else (
 python "%~dp0bridge_agent.py" --repo aminzare121-maker/amin-faraz --issue 38 --workspace "%WORKSPACE%"
)
echo Bridge session ended. No service was installed.
pause
