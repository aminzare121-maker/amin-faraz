@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
echo.
echo ARTIN V3 - optional LOCAL models setup. No broker trades.
echo Model download needs internet and several gigabytes of free storage.
echo This program will only download/install after your separate YES answers.
echo.
where ffmpeg >nul 2>&1
if errorlevel 1 echo WARNING: Install FFmpeg and add it to PATH, plus ffprobe.
where ollama >nul 2>&1
if errorlevel 1 echo WARNING: Install Ollama separately from its official website.
echo.
set /p "APPROVE=Install the Python faster-whisper package? (YES/no): "
if /I not "%APPROVE%"=="YES" goto next_asr
%PY% -m pip install faster-whisper
if errorlevel 1 goto failed
:next_asr
set /p "APPROVE=Download LOCAL Whisper-small ASR model (hundreds of MB)? (YES/no): "
if /I not "%APPROVE%"=="YES" goto next_vision
%PY% "%ROOT%artin_setup_models.py" --download-asr small --target "%ROOT%PRIVATE_MODELS\whisper-small"
if errorlevel 1 goto failed
:next_vision
where ollama >nul 2>&1
if errorlevel 1 goto skip_vision
set /p "APPROVE=Download LOCAL Qwen2.5-VL 3B vision model (about 3.2 GB)? (YES/no): "
if /I not "%APPROVE%"=="YES" goto skip_vision
ollama pull qwen2.5vl:3b
if errorlevel 1 goto failed
:skip_vision
%PY% "%ROOT%artin_model_preflight.py" --asr-model "%ROOT%PRIVATE_MODELS\whisper-small" --ollama-model "qwen2.5vl:3b"
echo.
echo Models are optional. Nothing was connected to MT5 or Codex.
pause
exit /b 0
:failed
echo Setup failed. Check connectivity, disk space, and Python/Ollama version.
pause
exit /b 1
