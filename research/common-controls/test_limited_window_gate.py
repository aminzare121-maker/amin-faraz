import copy,unittest
from limited_window_gate import evaluate,REQUIRED

def fixture():
    return dict(id='synthetic gate fixture',start=100,end=200,missing_slots=0,engine_ready=True,
                exposure='PREVIOUSLY_OBSERVED_DIAGNOSTIC',rollback='ROLLBACK_PROTECTION_UNVERIFIED',
                evidence={k:dict(status='VERIFIED',receipt_sha256='a'*64,start=100,end=200) for k in REQUIRED})

class LocalWindowTests(unittest.TestCase):
    def test_local_does_not_require_whole_year(self):
        w=fixture();w['annual_gaps_unknown']=260
        self.assertTrue(evaluate(w)['backtest_allowed']);self.assertFalse(evaluate(w)['annual_certified'])
    def test_seen_window_can_be_diagnostic_not_sealed(self):
        w=fixture();self.assertTrue(evaluate(w)['backtest_allowed'])
        self.assertFalse(evaluate(w,mode='SEALED_HOLDOUT')['backtest_allowed'])
    def test_unknown_costs_not_zero(self):
        w=fixture();w['evidence']['costs']['status']='UNKNOWN'
        self.assertEqual(evaluate(w)['result'],'NO_RESULT')
    def test_live_quote_not_historical_clock(self):
        w=fixture();w['evidence']['clock']['start']=150
        self.assertIn('CLOCK_OUTSIDE_EVIDENCE_INTERVAL',evaluate(w)['blockers'])
    def test_evidence_hash_required(self):
        w=fixture();w['evidence']['rights'].pop('receipt_sha256')
        self.assertFalse(evaluate(w)['backtest_allowed'])
    def test_missing_no_fill(self):
        w=fixture();w['missing_slots']=1;self.assertFalse(evaluate(w)['backtest_allowed'])
    def test_engine_capability_separate_from_data(self):
        w=fixture();w['engine_ready']=False;r=evaluate(w)
        self.assertEqual(r['status'],'LOCAL_WINDOW_ELIGIBLE');self.assertFalse(r['backtest_allowed'])
    def test_no_financial_or_trading_permission(self):
        r=evaluate(fixture());self.assertFalse(r['profitability_verified']);self.assertFalse(r['trade_allowed'])
    def test_bounded_cost_evidence_not_unlabeled_zero(self):
        w=fixture();w['evidence']['costs']['status']='VERIFIED_BOUNDED'
        self.assertTrue(evaluate(w)['backtest_allowed'])

if __name__=='__main__':unittest.main()
