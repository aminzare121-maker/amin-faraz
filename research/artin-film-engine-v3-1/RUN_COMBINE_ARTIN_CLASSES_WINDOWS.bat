@echo off
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "PY=python"
where py >nul 2>&1
if not errorlevel 1 set "PY=py -3"
echo.
echo ARTIN V3 - combine lesson result folders by session number
set /p "FOLDER=Parent folder of session_01, session_02 ...: "
if not exist "%FOLDER%\" goto missing
if not exist "%ROOT%PRIVATE_CLASS_COURSE" mkdir "%ROOT%PRIVATE_CLASS_COURSE"
%PY% "%ROOT%artin_course_compiler.py" --course-root "%FOLDER%" --expected-sessions 26 --out "%ROOT%PRIVATE_CLASS_COURSE\CANDIDATE_SYLLABUS.json"
if errorlevel 1 goto failed
echo Candidate syllabus created. All speaker roles and teacher rules remain UNVERIFIED.
echo No code changes, no MT5, no transactions.
pause
exit /b 0
:missing
echo Course folder not found.
pause
exit /b 2
:failed
echo One or more session folders contain missing/untrusted files.
pause
exit /b 3
