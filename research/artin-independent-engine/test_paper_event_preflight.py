"""Reject later unsourced or noncausal events before partial paper replay."""
import unittest
from unittest.mock import patch
from entry_engine import RULE_IDS
from run_engine import run_document

class PaperEventPreflightTests(unittest.TestCase):
    def document(self,events):
        return {'mode':'ANNOTATED_OFFLINE','plan_id':'paper-preflight',
                'allowed_rules':[RULE_IDS[0]],'cases':[
                    {'case_id':'source-case','rule_id':RULE_IDS[0],'side':'BUY','at':10,
                     'facts':{},'paper_trade':{'events':events}}]}

    def test_later_reversed_availability_fails_before_evaluation(self):
        events=[{'event':'fill_entry','at':10,'known_at':12,'source':'broker','lots':'0.01','fill_price':'4000'},
                {'event':'quote','at':11,'known_at':11,'source':'broker','bid':'4001','ask':'4002'}]
        with patch('run_engine.Engine.evaluate',side_effect=AssertionError('partial replay')) as evaluate:
            with self.assertRaisesRegex(ValueError,'causal and nondecreasing'):
                run_document(self.document(events))
            evaluate.assert_not_called()

    def test_unsourced_later_event_fails_before_evaluation(self):
        events=[{'event':'fill_entry','at':10,'known_at':10,'source':'broker'},
                {'event':'quote','at':11,'known_at':11,'source':''}]
        with patch('run_engine.Engine.evaluate',side_effect=AssertionError('partial replay')) as evaluate:
            with self.assertRaisesRegex(ValueError,'provenance'):
                run_document(self.document(events))
            evaluate.assert_not_called()

if __name__=='__main__':
    unittest.main()
