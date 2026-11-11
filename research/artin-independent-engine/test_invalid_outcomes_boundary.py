"""Regression tests: invalid collections must never authorize an Artin decision."""
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("artin_decision_boundary.py")
spec = importlib.util.spec_from_file_location("artin_decision_boundary", MODULE_PATH)
engine = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)


class InvalidOutcomesTests(unittest.TestCase):
    def test_non_iterable_outcomes_fail_closed(self):
        for value in (None, 42, True):
            with self.subTest(value=value):
                self.assertEqual(
                    engine.decide(value),
                    {"decision": "BLOCKED", "reason": "INVALID_RULE_OUTCOMES", "executable": False},
                )

    def test_invalid_iterator_fail_closed(self):
        def invalid():
            yield from ()
            raise ValueError("invalid input stream")
        self.assertEqual(
            engine.decide(invalid()),
            {"decision": "BLOCKED", "reason": "INVALID_RULE_OUTCOMES", "executable": False},
        )


if __name__ == "__main__":
    unittest.main()
