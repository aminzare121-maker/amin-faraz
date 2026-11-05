import unittest
from decimal import Decimal as D
from dataclasses import replace
from readiness import Opportunity,choose,summarize,run_fixture,SEEDS
class BudgetTests(unittest.TestCase):
 def setUp(self): self.u=tuple(Opportunity(str(i),i) for i in range(100))
 def test_reproducible_seeds(self):
  for s in SEEDS:self.assertEqual(choose(self.u,4,s),choose(self.u,4,s))
 def test_equal_budget(self):
  for s in SEEDS:
   r=choose(self.u,1,s);self.assertEqual(sum(x.risk_usd*x.holding_seconds for x in r),D(9000))
 def test_no_outcome_argument(self):
  import inspect
  self.assertEqual(list(inspect.signature(choose).parameters),['universe','quota','seed'])
 def test_future_outcome_changes_do_not_change_selection(self):
  a=choose(self.u,2,1729);outcomes={x.key:D(-1) for x in self.u};outcomes['99']=D(999999);self.assertEqual(a,choose(self.u,2,1729))
 def test_unequal_duration_rejected(self):
  with self.assertRaises(ValueError):choose(self.u+(replace(self.u[0],key='other',holding_seconds=901),),1,1729)
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):choose(self.u+(self.u[0],),1,1729)
 def test_unknown_risk_rejected(self):
  with self.assertRaises(ValueError):choose((replace(self.u[0],risk_usd=D('NaN')),),1,1729)
 def test_boolean_budget_rejected(self):
  with self.assertRaises(ValueError):choose(self.u,True,1729)
 def test_oversized_budget_rejected(self):
  with self.assertRaises(ValueError):choose(self.u,101,1729)
 def test_zero_budget(self):self.assertEqual(choose(self.u,0,1729),())
 def test_one_vs_hundred_does_not_claim_edge(self):
  r=run_fixture();self.assertEqual(r['ai_one']['net_hypothetical_usd'],'-1');self.assertEqual(r['unmatched_100']['net_hypothetical_usd'],'-100');self.assertFalse(r['ai_one']['edge_established'])
 def test_matched_random_has_same_net_and_exposure(self):
  r=run_fixture()
  for c in r['matched_controls']:
   for k in ['exposure_seconds','risk_usd_hours','lot_hours','net_hypothetical_usd']:self.assertEqual(c['metrics'][k],r['ai_one'][k])
 def test_no_trade_has_no_sharpe(self):self.assertIsNone(run_fixture()['no_trade']['per_trade_sharpe_descriptive_not_time_sharpe'])
 def test_ci_is_not_confirmation(self):self.assertFalse(run_fixture()['ci_reused_diagnostic_only']['independent_future_test'])
 def test_nonfinite_outcome_rejected(self):
  with self.assertRaises(ValueError):summarize((self.u[0],),{'0':D('Infinity')},100)
 def test_independent_count_is_not_candidate_count(self):
  r=summarize(tuple(replace(x,block=0) for x in self.u),{x.key:D(-1) for x in self.u},100);self.assertEqual(r['independent_blocks_assumed'],1)
if __name__=='__main__':unittest.main()
