@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "MEDIA_DIR=%~1"
echo.
echo ARTIN - Private teacher video / audio inventory
echo Files remain on this Windows computer. No upload, trading or installation.
if "%MEDIA_DIR%"=="" (
  echo Enter the folder containing original teacher videos and audio recordings:
  set /p "MEDIA_DIR=Media folder: "
)
if not exist "%MEDIA_DIR%\" (
  echo ERROR: Original media folder not found.
  pause
  exit /b 2
)
set "OUTPUT=%ROOT%PRIVATE_CLASSROOM_AUDIT"
if not exist "%OUTPUT%" mkdir "%OUTPUT%"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py -3 -B "%ROOT%classroom_media_manifest.py" --media-root "%MEDIA_DIR%" --private-out "%OUTPUT%\PRIVATE_media_manifest.json"
) else (
  python -B "%ROOT%classroom_media_manifest.py" --media-root "%MEDIA_DIR%" --private-out "%OUTPUT%\PRIVATE_media_manifest.json"
)
if %ERRORLEVEL% NEQ 0 (
  echo ERROR: Media inventory did not complete.
  pause
  exit /b 3
)
echo.
echo Media hash report (PRIVATE - do not upload this file):
echo %OUTPUT%\PRIVATE_media_manifest.json
echo This report shows files available; it does not verify lessons or answers.
pause
endlocal
