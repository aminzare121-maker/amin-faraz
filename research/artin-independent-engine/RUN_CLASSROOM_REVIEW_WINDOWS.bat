@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "ASR_DIR=%~1"
set "TIMEBASE=%~2"
if "%TIMEBASE%"=="" set "TIMEBASE=relative"
echo.
echo ARTIN - PRIVATE CLASSROOM REVIEW / بازبینی محلی کلاس‌های آرتین
echo This script does not trade or upload any video/audio.
echo.
if "%ASR_DIR%"=="" (
  echo Please drag the parent folder of speech-*.json files onto this BAT file,
  echo or type its complete path:
  set /p "ASR_DIR=ASR folder: "
)
if not exist "%ASR_DIR%\" (
  echo ERROR: Folder does not exist. No processing performed.
  pause
  exit /b 2
)
if not "%TIMEBASE%"=="relative" if not "%TIMEBASE%"=="absolute" (
  echo ERROR: Timebase must be relative or absolute.
  pause
  exit /b 3
)
set "OUT=%ROOT%PRIVATE_CLASSROOM_AUDIT"
if not exist "%OUT%" mkdir "%OUT%"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py -3 -B "%ROOT%classroom_dialogue_pipeline.py" --asr-root "%ASR_DIR%" --timebase %TIMEBASE% --report "%OUT%\PRIVATE_asr_coverage.json" --private-review-queue "%OUT%\PRIVATE_qa_review_queue.json"
) else (
  python -B "%ROOT%classroom_dialogue_pipeline.py" --asr-root "%ASR_DIR%" --timebase %TIMEBASE% --report "%OUT%\PRIVATE_asr_coverage.json" --private-review-queue "%OUT%\PRIVATE_qa_review_queue.json"
)
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Local ASR review failed. No trading program was changed.
  pause
  exit /b 4
)
echo.
echo Reports are LOCAL and PRIVATE:
echo %OUT%\PRIVATE_asr_coverage.json
echo %OUT%\PRIVATE_qa_review_queue.json
echo Speaker roles and teacher rules still need audiovisual verification.
pause
endlocal
