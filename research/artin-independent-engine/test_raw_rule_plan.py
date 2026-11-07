"""Research route isolation; synthetic input is not a teacher market example."""
import csv,gzip,json,tempfile,unittest
from pathlib import Path
from run_raw import run
from entry_engine import RULE_IDS
from test_monthly_execution import context,execution

class RawRulePlanTests(unittest.TestCase):
    def replay(self,rules):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bars.csv';out=Path(tmp)/'out'
            with p.open('w',newline='',encoding='utf8') as f:
                w=csv.writer(f);w.writerow(['time_raw_epoch','open','high','low','close'])
                w.writerow([0,99,101,99,101])
            s=run(p,out,900,contexts=[context()],execution_document=execution(),allowed_rules=rules)
            with gzip.open(out/'PRIVATE_raw_decisions.jsonl.gz','rt',encoding='utf8') as f:
                trace=json.loads(next(f))
            return s,trace
    def test_personal_routes_do_not_execute_eligible_classic_break(self):
        rules=tuple(r for r in RULE_IDS if r.startswith('STOPPUNCH_'))
        s,t=self.replay(rules)
        self.assertEqual(s['actual_entry_evaluations'],2*len(rules))
        self.assertEqual({d['rule_id'] for d in t['decisions']},set(rules))
        self.assertEqual(s['paper_trades_opened'],0)
        self.assertFalse(s['provenance']['entry_rule_plan']['all_branches_diagnostic'])
    def test_classic_selection_is_explicit_and_bound_into_receipt(self):
        s,t=self.replay(('BREAK_STRONG',))
        self.assertEqual(s['actual_entry_evaluations'],2)
        self.assertEqual(s['paper_trades_opened'],1)
        self.assertEqual(s['provenance']['entry_rule_plan']['allowed_rules'],('BREAK_STRONG',))
        other,_=self.replay(('STOPPUNCH_SAME_COLOUR',))
        self.assertNotEqual(s['provenance']['entry_rule_plan']['fingerprint'],other['provenance']['entry_rule_plan']['fingerprint'])
    def test_empty_duplicate_or_mutable_plan_is_rejected(self):
        for rules in ((),('BREAK_STRONG','BREAK_STRONG'),['BREAK_STRONG']):
            with self.subTest(rules=rules),self.assertRaises(ValueError):self.replay(rules)

if __name__=='__main__':unittest.main()
