@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% EQU 0 (set "PY=py -3") else (set "PY=python")
echo ARTIN TEACHER PDF PAPER MOTOR: SELF-CHECK ONLY -- NO BROKER ORDERS
%PY% -m unittest -q test_artin_unified_paper_motor test_artin_teacher_sl_tp_motor test_artin_teacher_pdf_bridge test_technical_teacher_policy test_fxm_teacher_policy test_artin_fxm_teacher_motor
if errorlevel 1 goto fail
%PY% -m unittest discover -s core -p "test_*.py" -q
if errorlevel 1 goto fail
call "%~dp0run_artin_motor_synthetic_test.cmd"
if errorlevel 1 goto fail
echo ARTIN PAPER MOTOR SELF-CHECK SUCCESS. No real MT5 trade has been proven.
exit /b 0
:fail
echo ARTIN PAPER MOTOR SELF-CHECK FAILED. No real MT5 trade was sent.
exit /b 1