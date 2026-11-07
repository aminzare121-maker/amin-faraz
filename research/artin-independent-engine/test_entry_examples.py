import unittest
from examples import demo_document
from run_engine import run_document
from entry_engine import RULE_IDS

class SourceConditionExamples(unittest.TestCase):
    def test_all_twelve_distinct_teacher_branches_execute_on_explicit_synthetic_inputs(self):
        result=run_document(demo_document())
        self.assertEqual({d['rule_id'] for d in result['decisions']},set(RULE_IDS))
        self.assertTrue(all(d['status']=='ELIGIBLE' and not d['order_created'] and d['sources'] for d in result['decisions']))
        self.assertFalse(result['broker_connected']);self.assertEqual(result['orders_sent'],0)
        lifecycle=result['paper_trades'][0]
        self.assertEqual(lifecycle['final_state'],'CLOSED')
        trace=lifecycle['trace']
        self.assertEqual(trace[-2]['state'],'CLOSED_PENDING_COST')
        self.assertEqual(trace[-2]['status'],'UNKNOWN')
        self.assertEqual(trace[-1]['status'],'CLOSED')
    def test_same_input_same_decisions_and_missing_condition_is_not_a_signal(self):
        doc=demo_document();first=run_document(doc);self.assertEqual(first,run_document(doc))
        del doc['cases'][0]['facts']['post_break_pivot_confirmed']
        changed=run_document(doc)
        self.assertEqual(changed['decisions'][0]['status'],'REVIEW')
        self.assertEqual(changed['decisions'][1:],first['decisions'][1:])

if __name__=='__main__':unittest.main(verbosity=2)
