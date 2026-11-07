@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
set "VIDEO=%~1"
if "%VIDEO%"=="" set /p "VIDEO=Original classroom film full path: "
if not exist "%VIDEO%" goto bad_video
set "OUTPUT=%ROOT%PRIVATE_ARTIN_NUMBERED_BATCHES"
echo.
echo ARTIN: First split film into numbered 5-minute parts, no AI model needed.
echo Short last part is accepted. Long films use batch_002/part_01 etc.
echo Parallel processing may finish out of order; final index is always numeric.
echo.
%PY% "%ROOT%artin_film_pipeline.py" prepare --video "%VIDEO%" --out "%OUTPUT%" --workers 4 --frames-per-chunk 0 --chunk-seconds 300
if errorlevel 1 goto failed
%PY% "%ROOT%artin_film_pipeline.py" remux --out "%OUTPUT%" --video-output "%OUTPUT%\original_ordered_chapters.mp4"
if errorlevel 1 goto failed
echo.
echo VERIFIED: "%OUTPUT%\chunk_order_verified.json"
echo CLIPS: "%OUTPUT%\clips"
echo CHAPTER VIDEO: "%OUTPUT%\original_ordered_chapters.mp4"
echo No speech or visual AI understanding has yet been attempted.
pause
exit /b 0
:bad_video
echo Film path does not exist.
pause
exit /b 2
:failed
echo Splitting or verification failed. Check the console. Partial files are not verified.
pause
exit /b 3
