@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo =================================================
echo SYNTHETIC SOFTWARE TEST ONLY: NOT REAL TRADE/PERFORMANCE
 echo =================================================
call "%~dp0run_artin_unified_paper_motor.cmd" "examples\SYNTHETIC_TEST_ONLY_FXM_TP_LADDER.json"
exit /b %errorlevel%