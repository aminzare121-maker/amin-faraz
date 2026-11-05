import copy,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from carry_costs import carry
from data_validity import gate,validate
from research_protocol import freeze,reserve_trial,expose_holdout
from registry import Registry
from execution_scenarios import replay
from test_stage3 import bar,ORDER,COST

def contract():
    e=dict(schema='faraz-data-v1',source='Synthetic',version='1',raw_sha256='a'*64,kind='M15',evidence={'fixture':{'reviewed':True,'sha256':'b'*64}})
    for name in ('price_side','time','candle_completeness','session','bid_ask','provenance'):
        e[name]=dict(status='VERIFIED',evidence_ids=['fixture'])
    e['time']['value']='UTC';e['price_side']['value']='BID'
    return e
def schedule():return dict(coverage_start=0,coverage_end=90000,basis='ASSUMPTION',complete_event_calendar=True,events=[dict(time=900,long_per_lot=-10,short_per_lot=2,multiplier=3)])
PROTOCOL=dict(schema='faraz-protocol-v2',max_trials=12,seeds=[1729,2718,31415,42017,65537],split={'train':[0,100],'validation':[108,200],'holdout':[208,300]},primary='worst-case-net-minus-drawdown',market_status='BLOCKED',holdout_fingerprint='a'*64)

class ContractTests(unittest.TestCase):
    def test_unknown_clock_blocks(self):
        e=contract();e['time']['status']='UNKNOWN';self.assertFalse(gate(e,'price_comparison')['allowed'])
    def test_conditional_not_verified(self):
        e=contract();e['time']['status']='CONDITIONAL';self.assertFalse(gate(e,'strategy_research')['allowed'])
    def test_session_unknown_blocks_strategy(self):
        e=contract();e['session']['status']='UNKNOWN';self.assertFalse(gate(e,'strategy_research')['allowed'])
    def test_unreviewed_receipt_rejected(self):
        e=contract();e['evidence']['fixture']['reviewed']=False
        with self.assertRaisesRegex(ValueError,'UNREVIEWED'):validate(e)
    def test_fingerprint_changes_with_interpretation(self):
        e=contract();a=validate(e);e['time']['note']='changed';self.assertNotEqual(a,validate(e))
    def test_known_contract_does_not_authorize_trade(self):self.assertFalse(gate(contract(),'strategy_research')['trade_allowed'])

class CarryTests(unittest.TestCase):
    def test_lot_scaling_001_01_1(self):
        for lot in ('.01','.1','1'):
            self.assertEqual(Decimal(carry(0,900,lot,'buy',schedule())['cashflow']),Decimal('-30')*Decimal(lot))
    def test_positive_short_credit(self):self.assertEqual(carry(0,900,'.01','sell',schedule())['cashflow'],'0.06')
    def test_unknown_not_zero(self):self.assertIsNone(carry(0,900,'.01','buy',None)['cashflow'])
    def test_partial_coverage_unknown(self):self.assertIsNone(carry(0,100000,'.01','buy',schedule())['cashflow'])
    def test_start_excluded_end_included(self):self.assertEqual(carry(900,1800,'.01','buy',schedule())['cashflow'],'0')
    def test_incomplete_calendar_unknown(self):
        s=schedule();s['complete_event_calendar']=False;self.assertIsNone(carry(0,900,'.01','buy',s)['cashflow'])
    def test_unattested_verified_rejected(self):
        s=schedule();s['basis']='VERIFIED';self.assertEqual(carry(0,900,'.01','buy',s)['status'],'UNKNOWN')
    def test_duplicate_events_rejected(self):
        s=schedule();s['events']*=2
        with self.assertRaisesRegex(ValueError,'ORDER'):carry(0,900,'.01','buy',s)
    def test_invalid_lot_grid(self):
        with self.assertRaisesRegex(ValueError,'GRID'):carry(0,900,'.015','buy',schedule())
    def test_replay_carry_assumption_not_known_net(self):
        out=replay([bar()],ORDER,**dict(COST,assumed_swap=None),swap_schedule=schedule())
        self.assertIsNone(out['net_with_known_costs']);self.assertEqual(out['carry']['status'],'ASSUMPTION');self.assertIsNotNone(out['scenario_net_usd'])
    def test_no_double_swap(self):
        with self.assertRaisesRegex(ValueError,'CONFLICTING'):replay([bar()],ORDER,**COST,swap_schedule=schedule())
    def test_contract_pnl_scales_all_lots(self):
        for lot in ('.01','.1','1'):
            r=replay([bar()],dict(ORDER,lots=lot),**dict(COST,swap=0,assumed_swap=None))
            self.assertEqual(Decimal(r['gross_usd']),Decimal('-130')*Decimal(lot))

class ProtocolTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.bank=Registry(Path(self.tmp.name)/'bank.db');freeze(self.bank,'p',PROTOCOL)
    def tearDown(self):self.tmp.cleanup()
    def test_budget_no_cherry_pick(self):
        for i in range(12):reserve_trial(self.bank,'p',{'trial':i})
        with self.assertRaisesRegex(ValueError,'BUDGET'):reserve_trial(self.bank,'p',{'trial':12})
    def test_reuse_does_not_spend_trial(self):
        reserve_trial(self.bank,'p',{'trial':1});self.assertEqual(reserve_trial(self.bank,'p',{'trial':1})['action'],'EXISTING_TRIAL_CHECK_RESULT_CACHE')
    def test_holdout_blocks_new_tuning(self):
        expose_holdout(self.bank,'p')
        with self.assertRaisesRegex(ValueError,'HOLDOUT'):reserve_trial(self.bank,'p',{'trial':1})
    def test_protocol_cannot_mutate(self):
        with self.assertRaisesRegex(ValueError,'IMMUTABLE'):freeze(self.bank,'p',dict(PROTOCOL,primary='new'))
    def test_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError,'OVERLAP'):freeze(self.bank,'q',dict(PROTOCOL,split={'train':[0,100],'validation':[100,200],'holdout':[208,300]}))
    def test_rename_does_not_refresh_holdout(self):
        expose_holdout(self.bank,'p')
        with self.assertRaisesRegex(ValueError,'RENAMED'):freeze(self.bank,'another',PROTOCOL)
    def test_actual_runner_seals_holdout(self):
        from test_selector import bars,CONTEXTS,PROTOCOL as execution_protocol
        from engine_bridge import evaluate_strategies
        from registry import digest
        data=bars();self.bank.artifact('fixture',digest(data),{},True)
        split={'train':[44,160],'validation':[168,240],'holdout':[248,320]}
        body=dict(PROTOCOL,split=split,holdout_fingerprint=digest({'dataset':digest(data),'range':split['holdout']}))
        p=dict(execution_protocol,preregistered={'id':'runner-test','body':body})
        result=evaluate_strategies(self.bank,data,'fixture',CONTEXTS,p)
        self.assertEqual(result['action'],'EXECUTED')
        self.assertEqual(evaluate_strategies(self.bank,data,'fixture',CONTEXTS,p)['action'],'REUSE')
        changed=copy.deepcopy(CONTEXTS);changed['stress']['slippage']=.3
        with self.assertRaisesRegex(ValueError,'HOLDOUT'):evaluate_strategies(self.bank,data,'fixture',changed,p)

if __name__=='__main__':unittest.main()
