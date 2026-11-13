"""Batch validation must complete before evaluating any classroom case."""
import unittest
from unittest.mock import patch
from entry_engine import RULE_IDS
from run_engine import run_document

class ObservationPreflightTests(unittest.TestCase):
    def test_late_invalid_fact_never_evaluates_earlier_case(self):
        doc = {'mode':'ANNOTATED_OFFLINE','plan_id':'preflight-facts',
               'allowed_rules':[RULE_IDS[0]],'cases':[
                   {'case_id':'valid-first','rule_id':RULE_IDS[0],'side':'BUY','at':10,'facts':{}},
                   {'case_id':'bad-later','rule_id':RULE_IDS[0],'side':'BUY','at':11,
                    'facts':{'current_setup':{'value':True,'known_at':-1,'source':'lesson'}}}]}
        with patch('run_engine.Engine.evaluate',side_effect=AssertionError('partial evaluation')) as evaluate:
            with self.assertRaisesRegex(ValueError,'known_at'):
                run_document(doc)
            evaluate.assert_not_called()

    def test_late_unknown_rule_never_evaluates_earlier_case(self):
        doc = {'mode':'ANNOTATED_OFFLINE','plan_id':'preflight-rule',
               'allowed_rules':[RULE_IDS[0]],'cases':[
                   {'case_id':'valid-first','rule_id':RULE_IDS[0],'side':'BUY','at':10,'facts':{}},
                   {'case_id':'unknown-later','rule_id':'UNSOURCED_ROUTE','side':'SELL','at':11,'facts':{}}]}
        with patch('run_engine.Engine.evaluate',side_effect=AssertionError('partial evaluation')) as evaluate:
            with self.assertRaisesRegex(ValueError,'fixed plan'):
                run_document(doc)
            evaluate.assert_not_called()

if __name__=='__main__':
    unittest.main()
