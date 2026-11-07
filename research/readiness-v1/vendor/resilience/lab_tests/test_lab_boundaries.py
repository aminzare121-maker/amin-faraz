"""Static boundary for the new IO-enabled offline wrapper, separate from core."""
import ast
from pathlib import Path
import unittest


class LabBoundaries(unittest.TestCase):
    def test_no_broker_network_or_unsafe_deserialization_in_lab(self):
        root = Path(__file__).resolve().parents[1]
        banned = {'socket', 'urllib', 'http', 'requests', 'MetaTrader5', 'pickle',
                  'amin_mt5', 'ctypes', 'subprocess'}
        for path in (root / 'faraz_lab').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text('utf-8'))):
                if isinstance(node, ast.Import):
                    self.assertFalse({alias.name.split('.')[0] for alias in node.names} & banned, path.name)
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module.split('.')[0], banned, path.name)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {'eval', 'exec', 'compile', '__import__'}, path.name)
