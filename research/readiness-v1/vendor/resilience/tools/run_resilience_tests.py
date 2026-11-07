"""Run the frozen 142 baseline tests plus independent isolated lab acceptance."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from faraz_lab import __version__, BASELINE_COMMIT


def identities(phase):
    excluded = ({'broker_contract.py', 'authority.py', 'test_broker_contract.py', 'test_authority.py'}
                if phase == 'd1' else set())
    files = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for folder in ('faraz_core', 'tests', 'tools', 'faraz_lab', 'lab_tests')
             for path in sorted((ROOT / folder).glob('*.py')) if path.name not in excluded}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return digest, files


def baseline_unchanged():
    manifest = json.loads((ROOT / 'reports/resilience-lab/baseline-manifest.json').read_text('utf-8'))
    return (manifest['remote_commit'] == BASELINE_COMMIT and len(manifest['files']) == 32
            and all((ROOT / row['path']).stat().st_size == row['bytes']
                    and hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
                    for row in manifest['files']))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('d1', 'all'), default='all')
    args = parser.parse_args()
    reports = ROOT / 'reports/resilience-lab'
    before, sources = identities(args.phase)
    unchanged_before = baseline_unchanged()
    names = {'D1': ['test_journal', 'test_durable', 'test_process_recovery', 'test_lab_boundaries']}
    if args.phase == 'all':
        names.update(D2=['test_broker_contract'], D3=['test_authority'])
    output = io.StringIO()
    groups = {}
    started = time.monotonic()
    baseline = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(baseline)
    def counts(result):
        return {'tests_run': result.testsRun, 'failures': len(result.failures),
                'errors': len(result.errors), 'skipped': len(result.skipped),
                'expected_failures': len(result.expectedFailures),
                'unexpected_successes': len(result.unexpectedSuccesses),
                'success': result.wasSuccessful() and not result.skipped
                           and not result.expectedFailures}
    groups['baseline'] = counts(result)
    evidence = {}
    for group, modules in names.items():
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('lab_tests.' + name)
                                   for name in modules)
        groups[group] = counts(unittest.TextTestRunner(stream=output, verbosity=2).run(suite))
        for name in modules:
            module = sys.modules.get('lab_tests.' + name)
            for key in ('PROCESS_EVIDENCE', 'DURABLE_EVIDENCE', 'CONTRACT_EVIDENCE',
                        'AUTHORITY_EVIDENCE', 'JOURNAL_EVIDENCE'):
                if module is not None and hasattr(module, key):
                    evidence[name + '.' + key] = getattr(module, key)
    after, _ = identities(args.phase)
    report = {'project': 'Faraz offline resilience lab', 'lab_version': __version__,
              'baseline_commit': BASELINE_COMMIT, 'phase': args.phase,
              'python': platform.python_version(), 'groups': groups,
              'tests_run': sum(row['tests_run'] for row in groups.values()),
              'failures': sum(row['failures'] for row in groups.values()),
              'errors': sum(row['errors'] for row in groups.values()),
              'skipped': sum(row['skipped'] for row in groups.values()),
              'source_sha256': before, 'source_hashes': sources,
              'source_domain': 'baseline plus D1' if args.phase == 'd1' else 'baseline plus all lab phases',
              'inputs_unchanged': before == after,
              'baseline_32_files_unchanged': unchanged_before and baseline_unchanged(),
              'duration_seconds': round(time.monotonic() - started, 6),
              'scenario_evidence': evidence,
              'real_process_termination_tested': bool(evidence.get('test_process_recovery.PROCESS_EVIDENCE')),
              'physical_power_loss_tested': False,
              'broker_or_mt5_connection': False, 'private_or_historical_data_used': False,
              'limitations': ['Synthetic effects only; no broker exactly-once guarantee.',
                              'Process kill and modeled storage faults are not physical power-loss validation.',
                              'Checksums detect corruption, not hostile modification or broker provenance.']}
    report['success'] = (all(row['success'] for row in groups.values())
                         and groups['baseline']['tests_run'] == 142 and before == after
                         and report['baseline_32_files_unchanged']
                         and report['real_process_termination_tested'])
    prefix = 'd1-' if args.phase == 'd1' else ''
    (reports / (prefix + 'unit-tests.log')).write_text(output.getvalue(), 'utf-8')
    (reports / (prefix + 'results.json')).write_text(json.dumps(report, indent=2, ensure_ascii=False)
                                                   + '\n', 'utf-8')
    print(json.dumps({key: report[key] for key in ('phase', 'groups', 'tests_run', 'failures',
                     'errors', 'skipped', 'success', 'source_sha256', 'baseline_32_files_unchanged')}, indent=2))
    if not report['success']:
        print(output.getvalue()[-16000:])
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
