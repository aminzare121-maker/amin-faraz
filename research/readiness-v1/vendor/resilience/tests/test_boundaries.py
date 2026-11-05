"""Independent safety boundary checks for the whole offline core."""
import ast
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import unittest

from faraz_core.numbers import dec, natural


LAST_IMPORT_PROBE_REPORT = None


class BoundaryTests(unittest.TestCase):
    def test_decimal_inputs_are_exact_and_finite(self):
        self.assertEqual(dec('0.08') * dec('550'), Decimal('44.00'))
        for value in [None, True, False, 0.1, 'NaN', '-Infinity', 'Infinity', object()]:
            with self.subTest(kind=type(value).__name__, value=str(value)):
                with self.assertRaises(ValueError):
                    dec(value)

    def test_event_sequences_and_clocks_are_strict_integers(self):
        for value in [-1, '1', 1.0, True, None]:
            with self.assertRaises(ValueError):
                natural(value)
        self.assertEqual(natural(0), 0)

    def test_core_has_no_io_sdk_dynamic_execution_or_old_engine_imports(self):
        allowed = {'dataclasses', 'decimal', 'typing', 'enum', 'hashlib', 'json',
                   'numbers', '__future__', 'collections', 'math', 'functools',
                   'risk', 'money', 'execution', 'temporal', 'exits',
                   'authorization', 'decision'}
        forbidden_calls = {'open', 'exec', 'eval', 'compile', '__import__', 'input',
                           'breakpoint'}
        root = Path(__file__).resolve().parents[1] / 'faraz_core'
        files = sorted(root.glob('*.py'))
        self.assertGreaterEqual(len(files), 8, 'All core modules must exist before acceptance')
        for path in files:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name.split('.')[0], allowed, (path.name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn((node.module or '').split('.')[0], allowed, (path.name, node.module))
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, forbidden_calls, (path.name, node.func.id))

    def test_modules_import_with_broker_network_process_and_legacy_imports_blocked(self):
        global LAST_IMPORT_PROBE_REPORT
        # The suite already imported core modules above. An in-process import
        # would mostly hit sys.modules and would not exercise import-time code.
        root = Path(__file__).resolve().parents[1]
        child = subprocess.run(
            [sys.executable, '-I', '-S', '-B', str(root / 'tools' / 'check_import_boundary.py'), str(root)],
            cwd=root, capture_output=True, text=True, timeout=30, check=False,
        )
        payload = json.loads(child.stdout)
        LAST_IMPORT_PROBE_REPORT = payload
        self.assertEqual(child.returncode, 0, payload)
        self.assertEqual(child.stderr, '')
        self.assertIs(payload['success'], True)
        self.assertIs(payload['isolated'], True)
        self.assertIs(payload['site_disabled'], True)
        self.assertIs(payload['bytecode_disabled'], True)
        self.assertEqual(payload['preloaded_core_modules'], [])
        self.assertIs(payload['all_core_imports_fresh'], True)
        expected = ['faraz_core'] + ['faraz_core.' + name for name in (
            'authorization', 'decision', 'execution', 'exits', 'money', 'numbers', 'risk', 'temporal')]
        self.assertEqual(payload['imported_core_modules'], sorted(expected))
        self.assertEqual(payload['fresh_core_imports'], sorted(expected))
        self.assertEqual(payload['forbidden_attempts_during_core'], [])
        self.assertIs(payload['guard_still_installed'], True)
        self.assertIs(payload['socket_audit_guard_verified'], True)
        self.assertEqual(len(payload['guard_self_checks']), 8)
        self.assertTrue(all(check['blocked'] is True for check in payload['guard_self_checks']))

