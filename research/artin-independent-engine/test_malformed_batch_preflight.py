"""Malformed batch inputs fail closed before strategy evaluation."""
import unittest
from unittest.mock import patch
from run_engine import run_document

class MalformedBatchPreflightTests(unittest.TestCase):
    def test_malformed_cases_fail_before_engine(self):
        for cases in (None, {}, ['not-a-case'], [None]):
            with self.subTest(cases=cases):
                with patch('run_engine.Engine.evaluate',side_effect=AssertionError('evaluated')) as evaluate:
                    with self.assertRaisesRegex(ValueError,'Cases must be a list of objects'):
                        run_document({'mode':'ANNOTATED_OFFLINE','cases':cases,'allowed_rules':[]})
                    evaluate.assert_not_called()

    def test_invalid_allowed_rules_fail_before_engine(self):
        with patch('run_engine.Engine.evaluate',side_effect=AssertionError('evaluated')) as evaluate:
            with self.assertRaisesRegex(ValueError,'Allowed rules must be a list'):
                run_document({'mode':'ANNOTATED_OFFLINE','cases':[],'allowed_rules':None})
            evaluate.assert_not_called()

if __name__=='__main__':
    unittest.main()
