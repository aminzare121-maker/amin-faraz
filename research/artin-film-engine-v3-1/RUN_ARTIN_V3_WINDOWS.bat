@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
echo.
echo ARTIN V3: 18 linked sections, Persian audio and local vision
set "VIDEO=%~1"
if "%VIDEO%"=="" set /p "VIDEO=Original classroom video full path: "
if not exist "%VIDEO%" goto bad_video
set "ASR=%ROOT%PRIVATE_MODELS\whisper-small"
set "MODEL=qwen2.5vl:3b"
echo.
echo A 90-minute video is split into numbered 01..18 chunks FIRST.
echo Local model availability is checked AFTER saving and verifying all clips.
set "OUTPUT=%ROOT%PRIVATE_ARTIN_RESULT"
echo.
echo Preparing clips, then local ASR + vision + neighbor-aware analysis.
echo Contents and reports remain local. Time depends heavily on your PC / model.
%PY% "%ROOT%artin_film_pipeline.py" all --video "%VIDEO%" --out "%OUTPUT%" --asr-model "%ASR%" --ollama-model "%MODEL%" --workers 2 --visual-sample-seconds 20
if errorlevel 1 goto failed
@echo.
echo Local result: "%OUTPUT%\artin_engine_handoff.json"
echo Teacher video still requires independent checking; NO orders generated.
pause
exit /b 0
:bad_video
echo Input video not found.
pause
exit /b 3
:failed
echo A step failed. Check chunk_order_verified.json for saved numbered clips.
echo If local models were missing, run SETUP_ARTIN_MODELS_WINDOWS.bat separately.
echo Do not interpret partial analysis as a verified lesson.
pause
exit /b 4
