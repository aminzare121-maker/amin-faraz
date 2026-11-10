@echo off
setlocal
cd /d "%~dp0"
if exist "private\ARTIN_13_CLASSROOM_MOTOR_EXECUTION.json" (
    echo Existing private report preserved. Please move it aside to run a new comparison.
    exit /b 1
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 artin_classroom_motor.py --private-citations private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json --classroom-cases private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json --pinned-core core --out private\ARTIN_13_CLASSROOM_MOTOR_EXECUTION.json
) else (
    python artin_classroom_motor.py --private-citations private\ARTIN_13_ROUTE_24_CITATION_PRIVATE_REVIEW_20261110.json --classroom-cases private\ARTIN_13_CLASSROOM_CANDIDATE_CASES.json --pinned-core core --out private\ARTIN_13_CLASSROOM_MOTOR_EXECUTION.json
)
if errorlevel 1 (echo Motor source replay failed & exit /b 1)
echo Result saved: private\ARTIN_13_CLASSROOM_MOTOR_EXECUTION.json
endlocal