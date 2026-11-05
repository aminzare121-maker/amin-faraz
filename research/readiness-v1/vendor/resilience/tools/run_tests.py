"""Run synthetic offline acceptance and write exact evidence to this project only."""
from pathlib import Path
import hashlib
import io
import json
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from faraz_core import __version__


def identity():
    files = {}
    for folder in ('faraz_core', 'tests', 'tools'):
        for path in sorted((ROOT / folder).glob('*.py')):
            files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return digest, files


def main():
    before, files = identity()
    output = io.StringIO()
    started = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    elapsed = time.monotonic() - started
    after, _ = identity()
    report = {
        'project': 'Amin MT5 — Faraz', 'scope': 'offline synthetic prototype only',
        'project_version': __version__,
        'python': platform.python_version(), 'code_and_test_sha256': before,
        'source_hashes': files, 'inputs_unchanged': before == after,
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped),
        'expected_failures': len(result.expectedFailures),
        'unexpected_successes': len(result.unexpectedSuccesses),
        'duration_seconds': round(elapsed, 6),
        'success': result.wasSuccessful() and before == after,
        'broker_or_mt5_called': False, 'private_market_data_used': False,
        'market_performance_validated': False,
        'limitations': ['Memory replay is not disk durability.',
                       'Synthetic execution is not a broker execution test.',
                       'No market edge, profitability, or installed deployment is established.'],
    }
    boundary_module = sys.modules.get('tests.test_boundaries')
    probe = getattr(boundary_module, 'LAST_IMPORT_PROBE_REPORT', None)
    report['fresh_process_import_probe'] = probe
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    (reports / 'unit-tests.log').write_text(output.getvalue(), encoding='utf-8')
    (reports / 'test-results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(output.getvalue(), end='')
    print(json.dumps({k: report[k] for k in ('tests_run', 'failures', 'errors', 'skipped', 'success', 'code_and_test_sha256')}, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
