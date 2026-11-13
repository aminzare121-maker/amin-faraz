"""Regression: route approval alone must never authorize another classroom case."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).with_name("artin_classroom_motor.py")

class CaseAcceptanceScopeTests(unittest.TestCase):
    def test_case_level_membership_is_required(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        source = ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), tree)
        self.assertIn("proof['route_id'], proof['case_id']", source)
        self.assertIn("not in accepted_cases", source)
        self.assertNotIn("proof['route_id'] not in accepted_routes", source)

if __name__ == "__main__":
    unittest.main()
