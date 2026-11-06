import unittest
from copy import deepcopy
from decimal import Decimal as D
from examples import demo_document
from run_engine import run_document
from entry_engine import Engine,Fact,Observation
from monthly_execution import MonthlyExecutor
from test_monthly_execution import execution
import test_trade_machine as trade_fixtures
from trade_machine import execution_event

class ExecutionRepairs(unittest.TestCase):
    def observation(self,at):
        values=dict(sentiment_permission='TWO_SIDED',current_setup=True,family_selection_context='ZONE_CONTEXT',trend_strength='NORMAL',break_strength='STRONG',fullbody_or_marubozu=True,decision_candle_closed=True,level_kind='PIVOT',decision_close=D(101),line_level=D(100))
        return Observation('BUY',at,{k:Fact(v,at,'SYNTHETIC') for k,v in values.items()})

    def test_overbudget_fill_reserves_actual_and_blocks_new_entries_until_closed(self):
        e=Engine('test',('BREAK_STRONG',));doc=execution()
        spec=doc['specs'][0];spec['box']['risk_budget']='40'
        second=deepcopy(spec);second['at']=1800;second['trade_id']='test2';doc['specs'].append(second)
        doc['events']=[dict(trade_id='test1',at=900,known_at=900,source='SYNTHETIC_FILL',event='fill_entry',fill_price='102')]
        m=MonthlyExecutor(e,'100','.30',doc)
        first=self.observation(900);m.accept(e.evaluate('BREAK_STRONG',first),first);m.advance(900)
        self.assertEqual(m.trades['test1'].state,'OPEN_REVIEW')
        self.assertEqual(m._reserved(),D('96'))
        later=self.observation(1800)
        self.assertEqual(m.accept(e.evaluate('BREAK_STRONG',later),later)['reason'],'OVERBUDGET_FILL_REQUIRES_EXPLICIT_RECONCILIATION')
        m.events=[dict(trade_id='test1',at=1800,known_at=1800,source='SYNTHETIC_ACTUAL_CLOSE',event='close',exit_fill='102',actual_round_trip_fee='0')]
        m.advance(1800)
        self.assertEqual(m._reserved(),D('0'))
        self.assertEqual(m.accept(e.evaluate('BREAK_STRONG',later),later)['result']['status'],'PAPER_ENTRY_INTENT')

    def test_annotated_events_require_clock_and_source_no_legacy_fabrication(self):
        for field in ('at','known_at','source'):
            doc=demo_document();del doc['cases'][0]['paper_trade']['events'][0][field]
            with self.assertRaises((ValueError,KeyError)):run_document(doc)
        doc=demo_document();doc['cases'][0]['paper_trade']['events'][0]['at']=99
        with self.assertRaises(ValueError):run_document(doc)

    def test_overbudget_pending_fee_keeps_gate_until_cash_reconciled(self):
        e=Engine('test',('BREAK_STRONG',));doc=execution()
        spec=doc['specs'][0];spec['box']['risk_budget']='40'
        second=deepcopy(spec);second['at']=1800;second['trade_id']='test2';doc['specs'].append(second)
        doc['events']=[dict(trade_id='test1',at=900,known_at=900,source='SYNTHETIC_FILL',event='fill_entry',fill_price='102'),
                       dict(trade_id='test1',at=901,known_at=901,source='SYNTHETIC_EXIT',event='close',exit_fill='101',actual_round_trip_fee=None)]
        m=MonthlyExecutor(e,'100','.30',doc)
        first=self.observation(900);m.accept(e.evaluate('BREAK_STRONG',first),first);m.advance(901)
        self.assertEqual(m.trades['test1'].state,'CLOSED_PENDING_COST')
        self.assertEqual(m.cash,D('100'))
        later=self.observation(1800)
        self.assertEqual(m.accept(e.evaluate('BREAK_STRONG',later),later)['reason'],'OVERBUDGET_FILL_REQUIRES_EXPLICIT_RECONCILIATION')
        m.events=[dict(trade_id='test1',at=1800,known_at=1800,source='SYNTHETIC_FEE_RECONCILIATION',event='close',exit_fill=None,actual_round_trip_fee='3')]
        m.advance(1800)
        self.assertEqual(m.cash,D('67'));self.assertEqual(m._reserved(),D('0'))
        self.assertEqual(m.accept(e.evaluate('BREAK_STRONG',later),later)['result']['status'],'PAPER_ENTRY_INTENT')

    def test_shared_dispatch_blocks_future_or_backdated_exit(self):
        helper=trade_fixtures.TradeMachineTests();m,_=helper.machine()
        execution_event(m,dict(event='fill_entry',fill_price='100',lots='.2',at=11,known_at=12,source='SYNTHETIC'),12)
        self.assertEqual(m.last_at,11)
        for at,known,now in [(10,12,12),(12,13,12),(13,12,13)]:
            with self.assertRaises(ValueError):execution_event(m,dict(event='close',exit_fill='103',actual_round_trip_fee='2',at=at,known_at=known,source='SYNTHETIC'),now)
        self.assertEqual(m.state,'OPEN')

    def test_fulltarget_is_structured_rejection_not_stop_move(self):
        m,_=trade_fixtures.TradeMachineTests().machine();m.fill_entry(D(100),D('.2'))
        r=m.manage('fulltarget',D(103),Fact(True,11,'SYNTHETIC'),11)
        self.assertEqual(r['reason'],'FULLTARGET_IS_EXIT_OUTCOME_NOT_STOP_MOVE')
        self.assertEqual(m.current_stop,D(99));self.assertEqual(m.state,'OPEN')

    def test_timed_demo_closes_with_trace_evidence(self):
        result=run_document(demo_document());trade=result['paper_trades'][0]
        self.assertEqual(trade['final_state'],'CLOSED')
        for r in trade['trace'][1:]:
            self.assertIn('event_at',r);self.assertIn('event_known_at',r);self.assertIn('event_source',r)

if __name__=='__main__':unittest.main()
