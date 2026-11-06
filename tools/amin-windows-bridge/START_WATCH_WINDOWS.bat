@echo off
setlocal
cd /d "%~dp0"
echo Amin Windows Bridge - stays running ONLY while this window is open
set /p WORKSPACE=Enter the full folder path of the APPROVED project workspace: 
if "%WORKSPACE%"=="" (
 echo No workspace selected. Exiting.
 pause
 exit /b 2
)
echo This will periodically check Issue 38. Press Ctrl+C to stop.
where py >nul 2>&1
if not errorlevel 1 (
 py -3 "%~dp0bridge_agent.py" --repo aminzare121-maker/amin-faraz --issue 38 --workspace "%WORKSPACE%" --watch
) else (
 python "%~dp0bridge_agent.py" --repo aminzare121-maker/amin-faraz --issue 38 --workspace "%WORKSPACE%" --watch
)
echo Bridge stopped. No Windows service installed.
pause
