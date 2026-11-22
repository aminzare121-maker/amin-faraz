@echo off
cd /d "%~dp0"
where node.exe >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Use official https://nodejs.org/en/download
  pause
  exit /b 1
)
node "%~dp0Setup-Amin-Cloudflare.mjs"
echo.
echo If setup stopped, review the error above. Do not share private keys.
pause
