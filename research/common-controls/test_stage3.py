import unittest,tempfile
from pathlib import Path
from evidence_gates import server_to_utc,classify_gap,final_gate
from execution_scenarios import replay,spread_at
from engine_bridge import replay_registered
from registry import Registry,digest

REG={'official':{'reviewed':True,'issuer':'Eplanet','sha256':'a'*64,'historical':True}}
def period(a,b,o=7200):return dict(utc_start=a,utc_end=b,offset_seconds=o,status='VERIFIED',evidence_id='official')
def bar(t=0,o=100,h=102,l=98,c=100):return dict(time=t,open=o,high=h,low=l,close=c,final=True,available=t+900)
ORDER=dict(side='buy',signal_available=0,lots='.01',contract=100,stop=99,target=101)
COST=dict(assumed_spread='.1',slippage='.1',commission=0,swap=None,assumed_swap='-.2')

class TimeTests(unittest.TestCase):
    def test_actual_2026_transition_weeks_disagree(self):
        from datetime import datetime,timezone
        from zoneinfo import ZoneInfo
        ny,eu=ZoneInfo('America/New_York'),ZoneInfo('Europe/Athens')
        for day in ('2026-03-15','2026-10-28'):
            t=datetime.fromisoformat(day+'T12:00:00+00:00')
            self.assertTrue(t.astimezone(ny).dst().total_seconds());self.assertFalse(t.astimezone(eu).dst().total_seconds())
        for zone,before,after in ((ny,'2026-03-08T06:59:59+00:00','2026-03-08T07:00:00+00:00'),(eu,'2026-03-29T00:59:59+00:00','2026-03-29T01:00:00+00:00')):
            self.assertFalse(datetime.fromisoformat(before).astimezone(zone).dst().total_seconds())
            self.assertTrue(datetime.fromisoformat(after).astimezone(zone).dst().total_seconds())
    def test_unreviewed_rejected(self):
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):server_to_utc(7200,[period(0,900)],{})
    def test_exact_half_open(self):
        self.assertEqual(server_to_utc(7200,[period(0,900)],REG),0)
        with self.assertRaises(ValueError):server_to_utc(8100,[period(0,900)],REG)
    def test_spring_missing_local_time(self):
        with self.assertRaises(ValueError):server_to_utc(17200,[period(0,10000),period(10000,20000,10800)],REG)
    def test_fall_fold_ambiguous(self):
        with self.assertRaises(ValueError):server_to_utc(18000,[period(0,10000,10800),period(10000,20000)],REG)
    def test_duplicate_evidence_ambiguous(self):
        with self.assertRaises(ValueError):server_to_utc(7200,[period(0,900)]*2,REG)
    def test_verified_closed(self):self.assertEqual(classify_gap(0,900,[dict(start=0,end=900,state='CLOSED',evidence_id='official')],REG)['classification'],'SCHEDULED_CLOSED')
    def test_verified_open_missing(self):self.assertEqual(classify_gap(0,900,[dict(start=0,end=900,state='OPEN',evidence_id='official')],REG)['classification'],'OPEN_MISSING')
    def test_unknown_without_calendar(self):self.assertEqual(classify_gap(0,900,[],REG)['classification'],'UNKNOWN')
    def test_conflict_not_closed(self):self.assertEqual(classify_gap(0,900,[dict(start=0,end=900,state=s,evidence_id='official') for s in ('OPEN','CLOSED')],REG)['classification'],'UNKNOWN')
    def test_partial_schedule_unknown(self):self.assertEqual(classify_gap(0,1800,[dict(start=0,end=900,state='CLOSED',evidence_id='official')],REG)['classification'],'UNKNOWN')
    def test_unknown_gate_blocks(self):self.assertFalse(final_gate([period(0,1800)],[{'classification':'UNKNOWN'}],True,REG,0,1800)['final_backtest_allowed'])
    def test_incomplete_year_blocks(self):self.assertFalse(final_gate([period(0,900)],[],True,REG,0,1800)['final_backtest_allowed'])
    def test_asserted_mapping_not_trusted(self):self.assertFalse(final_gate([dict(period(0,1800),mapping_checked=True)],[],True,{},0,1800)['final_backtest_allowed'])
    def test_only_full_verified_gate(self):self.assertTrue(final_gate([period(0,1800)],[{'classification':'SCHEDULED_CLOSED'}],{'status':'VERIFIED','evidence_id':'official'},REG,0,1800)['final_backtest_allowed'])
    def test_boolean_cost_claim_is_not_evidence(self):self.assertFalse(final_gate([period(0,1800)],[],True,REG,0,1800)['final_backtest_allowed'])

class ExecutionTests(unittest.TestCase):
    def test_optimistic_is_only_scenario(self):
        r=replay([bar()],ORDER,**dict(COST,intrabar_policy='target_first'))
        self.assertEqual(r['exit'],'100.9');self.assertTrue(r['ambiguous_sl_tp']);self.assertFalse(r['profitability_verified'])
    def test_unknown_path_has_no_selected_pnl(self):
        r=replay([bar()],ORDER,**dict(COST,intrabar_policy='unknown'))
        self.assertIsNone(r['exit']);self.assertIsNone(r['gross_usd']);self.assertIsNone(r['scenario_net_usd'])
    def test_path_policy_changes_cache_identity(self):
        with tempfile.TemporaryDirectory() as d:
            bank=Registry(Path(d)/'bank.db');bars=[bar()];bank.artifact('fixture',digest(bars),{},True)
            a=replay_registered(bank,bars,'fixture',ORDER,COST)
            b=replay_registered(bank,bars,'fixture',ORDER,dict(COST,intrabar_policy='target_first'))
            self.assertNotEqual(a['id'],b['id']);self.assertEqual(b['action'],'EXECUTED')
    def test_sl_tp_stop_first_unknown(self):
        r=replay([bar()],ORDER,**COST);self.assertTrue(r['ambiguous_sl_tp']);self.assertEqual(r['exit_reason'],'STOP_FIRST_AMBIGUOUS')
        self.assertEqual(r['entry'],'100.2');self.assertEqual(r['exit'],'98.9');self.assertIsNone(r['net_with_known_costs']);self.assertEqual(r['scenario_net_usd'],'-1.500')
    def test_missing_swap_not_zero(self):
        r=replay([bar()],ORDER,**dict(COST,assumed_swap=None));self.assertIsNone(r['scenario_net_usd']);self.assertEqual(r['swap_status'],'UNKNOWN')
    def test_future_signal(self):
        with self.assertRaisesRegex(ValueError,'LOOKAHEAD'):replay([bar()],dict(ORDER,signal_available=1),**COST)
    def test_stop_gap_adverse_fill(self):
        r=replay([bar(h=100.5,l=99.5),bar(900,o=98,h=98.5,l=97,c=98)],ORDER,**COST);self.assertEqual(r['exit'],'97.9')
    def test_target_no_gap_bonus(self):
        r=replay([bar(h=100.5,l=99.5),bar(900,o=103,h=104,l=102,c=103)],ORDER,**COST);self.assertEqual(r['exit'],'100.9')
    def test_variable_real_quote_spread(self):
        q={0:dict(time=0,bid=100,ask=100.2,receipt_id='r',status='VERIFIED'),900:dict(time=900,bid=100,ask=100.8,receipt_id='r',status='VERIFIED')}
        r=replay([bar(h=100.5,l=99.5),bar(900)],ORDER,**dict(COST,quotes=q,receipt_ids=['r']))
        self.assertEqual([t['spread'] for t in r['spread_trace']],['0.2','0.8']);self.assertFalse(r['profitability_verified']);self.assertEqual(r['cost_basis'],'ASSUMPTION')
    def test_unverified_quote_fallback(self):self.assertEqual(spread_at(0,{0:dict(time=0,receipt_id='r',status='VERIFIED')},'.5',[])[1],'ASSUMPTION')
    def test_no_spread_reject(self):
        with self.assertRaises(ValueError):spread_at(0,{},None,[])
    def test_no_slippage_default(self):
        with self.assertRaises(ValueError):replay([bar()],ORDER,**dict(COST,slippage=None))
    def test_no_session_gap_bridge(self):
        with self.assertRaisesRegex(ValueError,'SESSION'):replay([bar(),bar(1800)],ORDER,**COST)
    def test_short_ask_stop(self):
        r=replay([bar()],dict(ORDER,side='sell',stop=101,target=99),**COST);self.assertEqual(r['entry'],'99.9');self.assertEqual(r['exit'],'101.1')
    def test_no_double_cost(self):
        r=replay([bar()],ORDER,**dict(COST,swap=0));self.assertEqual(r['net_with_known_costs'],'-1.300')
    def test_register_reuse_negative_scenario(self):
        with tempfile.TemporaryDirectory() as d:
            bank=Registry(Path(d)/'bank.db');bars=[bar()];bank.artifact('fixture',digest(bars),{'synthetic':True},True)
            first=replay_registered(bank,bars,'fixture',ORDER,COST);second=replay_registered(bank,bars,'fixture',ORDER,COST)
            self.assertEqual(first['action'],'EXECUTED');self.assertEqual(second['action'],'REUSE');self.assertEqual(first['result'],second['result'])

if __name__=='__main__':unittest.main(verbosity=2)
