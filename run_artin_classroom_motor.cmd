@echo off
setlocal
cd /d "%~dp0"
if not exist "core\LEGACY_SHA_MANIFEST.json" (echo ERROR: pinned engine core not found & exit /b 2)
if not exist "private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json" (echo ERROR: classroom citation source missing & exit /b 2)
if not exist "private\source_sessions\session_24_all_machine_speech_review.jsonl" (echo ERROR: original lesson text missing & exit /b 2)
set "OUT=private\CLASSROOM_MOTOR_EXECUTION_%RANDOM%_%RANDOM%.json"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 artin_classroom_motor.py --private-citations "private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json" --classroom-cases "private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json" --pinned-core "core" --teacher-action-events "private\ARTIN_SOURCE_GROUNDED_ENTRY_EXIT_EVENTS.json" --original-25-sessions-dir "private\source_sessions" --out "%OUT%"
) else (
    python artin_classroom_motor.py --private-citations "private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json" --classroom-cases "private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json" --pinned-core "core" --teacher-action-events "private\ARTIN_SOURCE_GROUNDED_ENTRY_EXIT_EVENTS.json" --original-25-sessions-dir "private\source_sessions" --out "%OUT%"
)
if errorlevel 1 (echo MOTOR EXECUTION FAILED & exit /b 1)
echo Motor report: %OUT%
echo This is an OFFLINE CLASSROOM MOTOR, not a trading EA.
exit /b 0