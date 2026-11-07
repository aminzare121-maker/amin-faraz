@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "VIDEO=%~1"
if "%VIDEO%"=="" (
 echo Drag a 90-minute video onto this file, or paste its full file path.
 set /p "VIDEO=Original classroom video: "
)
if not exist "%VIDEO%" (
 echo ERROR: Video file not found.
 pause
 exit /b 2
)
set /p "WHISPER_MODEL=Previously installed local faster-whisper model FOLDER path: "
if not exist "%WHISPER_MODEL%\" (
 echo ERROR: Local Whisper model not found. No fake transcription will be produced.
 pause
 exit /b 3
)
set /p "OLLAMA_MODEL=Installed local Ollama multilingual vision model name: "
if "%OLLAMA_MODEL%"=="" (
 echo ERROR: Ollama model name required. No unverified trading rules will be created.
 pause
 exit /b 4
)
set "RESULTS=%~dp0PRIVATE_ARTIN_CLASSROOM_RESULT"
if not exist "%RESULTS%" mkdir "%RESULTS%"
python -B "%~dp0artin_film_pipeline.py" all --video "%VIDEO%" --out "%RESULTS%" --asr-model "%WHISPER_MODEL%" --ollama-model "%OLLAMA_MODEL%" --workers 2 --with-frames
if errorlevel 1 (
 echo.
 echo Processing is incomplete. Inspect PRIVATE_ARTIN_CLASSROOM_RESULT for existing evidence and logs.
 echo Original video was NOT changed. No trade was placed.
 pause
 exit /b 5
)
echo.
echo Completed candidate timeline: %RESULTS%\unified_timeline.json
echo Teacher rules are NOT approved without direct audiovisual checking.
pause
endlocal
