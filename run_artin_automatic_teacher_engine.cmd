@echo off
setlocal
cd /d "%~dp0"
echo [1/3] Automatic teacher rule tests - no trades
python -m unittest -q test_artin_automatic_teacher_engine test_artin_automatic_demo_integration
if errorlevel 1 ( echo TEST_FAILED & pause & exit /b 1 )
echo [2/3] Original teacher PDFs SHA256 validation
python -c "from artin_mt5_demo_automatic import verify_teacher_pdf_sources; from pathlib import Path; verify_teacher_pdf_sources(Path('.')); print('ORIGINAL_TEACHER_PDFS_MATCH')"
if errorlevel 1 ( echo PDF_INTEGRITY_FAILED & pause & exit /b 1 )
if exist "private\ARTIN_EPLANET_REAL_23643_M15_OBSERVATIONS_PRIVATE.jsonl" (
  echo [3/3] Autonomous real-history scan (no simulated trades)
  python -c "import sys,json; from pathlib import Path;sys.path.insert(0,'.');from artin_automatic_teacher_recognizer import parse_bars,run_scan,report; p=Path('private/ARTIN_EPLANET_REAL_23643_M15_OBSERVATIONS_PRIVATE.jsonl');bars,h=parse_bars(p);d,s=run_scan(bars);Path('private/AUTO_SCAN_CURRENT.json').write_text(json.dumps(report(bars,h,d,s),ensure_ascii=False,indent=2),encoding='utf8');print('CANDIDATES_FOUND',len(s),'BRANCH_COUNTS',d.counts)"
) else (
  echo PRIVATE_BARS_NOT_PRESENT: raw scan skipped; original data stays private.
)
echo FINISHED - no MT5 orders were sent
pause