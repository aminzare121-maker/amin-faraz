@echo off
setlocal
cd /d "%~dp0"
if not exist "FXM.pdf" (echo ERROR: FXM original handout not present & exit /b 2)
if not exist "core\LEGACY_SHA_MANIFEST.json" (echo ERROR: pinned 13-route engine missing & exit /b 2)
if not exist "private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json" (echo ERROR: private classroom cases missing & exit /b 2)
set "OUT=private\FXM_MOTOR_REPLAY_%RANDOM%_%RANDOM%.json"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 artin_fxm_teacher_motor.py --private-citations "private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json" --classroom-cases "private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json" --pinned-core core --fxm-pdf FXM.pdf --balance 1000 --reference-balance 1000 --risk-percent 1 --style DAY_TRADE --teacher-action-events "private\ARTIN_SOURCE_GROUNDED_ENTRY_EXIT_EVENTS.json" --original-25-sessions-dir "private\source_sessions" --out "%OUT%"
) else (
  python artin_fxm_teacher_motor.py --private-citations "private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json" --classroom-cases "private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json" --pinned-core core --fxm-pdf FXM.pdf --balance 1000 --reference-balance 1000 --risk-percent 1 --style DAY_TRADE --teacher-action-events "private\ARTIN_SOURCE_GROUNDED_ENTRY_EXIT_EVENTS.json" --original-25-sessions-dir "private\source_sessions" --out "%OUT%"
)
if errorlevel 1 (echo FXM MOTOR FAILED & exit /b 1)
echo FXM paper-only result: %OUT%
exit /b 0