import unittest
from decimal import Decimal as D
from entry_engine import Engine,Fact,Observation
from capital import BoxPlan,Instrument,Costs
from trade_machine import TradeMachine

class TradeMachineTests(unittest.TestCase):
    def machine(self,side='BUY',remaining=D('25')):
        e=Engine('synthetic',('BREAK_STRONG',))
        m=TradeMachine(e,BoxPlan('b',D('25'),'explicit structural target',('reduce','riskfree','saveprofit'),True),Instrument(D('100'),D('.01'),D('.01')),Costs(D('10'),D('.1')))
        values=dict(sentiment_permission='TWO_SIDED',current_setup=True,family_selection_context='ZONE_CONTEXT',trend_strength='NORMAL',break_strength='STRONG',fullbody_or_marubozu=True,decision_candle_closed=True,level_kind='PIVOT',decision_close=D('101') if side=='BUY' else D('99'),line_level=D('100'))
        obs=Observation(side,10,{k:Fact(v,10,'synthetic_fixture') for k,v in values.items()})
        result=m.prepare('BREAK_STRONG',obs,D('100'),D('99') if side=='BUY' else D('101'),D('103') if side=='BUY' else D('97'),remaining)
        return m,result

    def test_long_gap_trigger_is_not_fill_or_pnl(self):
        m,r=self.machine();self.assertEqual(r['status'],'PAPER_ENTRY_INTENT')
        m.fill_entry(D('100'),D('.2'))
        r=m.quote(D('95'),D('95.2'),11)
        self.assertEqual(r['reason'],'STOP');self.assertFalse(r['fill_assumed'])
        self.assertIsNone(r['realized_pnl']);self.assertEqual(m.state,'OPEN')
        closed=m.close(D('94.9'),D('2'))
        self.assertEqual(closed['accounting']['net_pnl'],D('-104'))

    def test_short_exit_uses_ask_not_bid(self):
        m,_=self.machine('SELL');m.fill_entry(D('100'),D('.2'))
        self.assertEqual(m.quote(D('96.9'),D('97.1'),11)['status'],'NO_EXIT_TRIGGER')
        r=m.quote(D('96.8'),D('97'),12)
        self.assertEqual((r['reason'],r['quote_side']),('TARGET','ASK'))

    def test_unfavorable_fill_stays_recorded_for_review(self):
        m,_=self.machine();r=m.fill_entry(D('102'),D('.2'))
        self.assertEqual(r['status'],'OPEN_REVIEW');self.assertEqual(m.fill['entry'],D('102'))
        self.assertGreater(r['modeled_loss'],m.plan['risk_budget'])
        self.assertEqual(m.close(D('101'),D('2'))['accounting']['net_pnl'],D('-22'))

    def test_management_sourced_trigger_costs_and_no_realization(self):
        m,_=self.machine();m.fill_entry(D('100'),D('.2'))
        self.assertEqual(m.manage('riskfree',D('100.2'),Fact(True,12,'synthetic'),11)['status'],'REVIEW')
        r=m.manage('riskfree',D('100.2'),Fact(True,11,'synthetic'),11)
        self.assertEqual(r['status'],'ACCEPT');self.assertIsNone(r['realized_pnl'])
        self.assertEqual(m.fill['lots'],D('.2'));self.assertEqual(m.state,'OPEN')
        self.assertEqual(r['management']['modeled_exit_net'],D('0'))

    def test_unknown_exit_fee_does_not_close_or_realize(self):
        m,_=self.machine();m.fill_entry(D('100'),D('.2'))
        for fill,fee in [(None,D('2')),(D('103'),None)]:
            r=m.close(fill,fee);self.assertEqual(r['status'],'UNKNOWN')
            self.assertEqual(m.state,'OPEN' if fill is None else 'CLOSED_PENDING_COST')
        with self.assertRaises(ValueError):m.quote(D('103'),D('103.2'),12)
        with self.assertRaises(ValueError):m.close(D('104'),D('2'))
        self.assertEqual(m.close(D('103'),D('2'))['accounting']['net_pnl'],D('58'))

    def test_trade_data_and_contract_cannot_silently_change(self):
        m,_=self.machine()
        with self.assertRaises(TypeError):m.plan['stop']=D('98')
        m.fill_entry(D('100'),D('.2'))
        with self.assertRaises(TypeError):m.fill['entry']=D('99')
        m.costs=Costs(D('0'),D('0'))
        with self.assertRaises(ValueError):m.quote(D('100'),D('100.1'),11)

    def test_remaining_budget_grid_fixed_plan_and_no_global_position_rule(self):
        exhausted,result=self.machine(remaining=D('0'))
        self.assertEqual(result['reason'],'AGGREGATE_RISK_EXHAUSTED')
        self.assertEqual(exhausted.state,'NEW')
        m,r=self.machine(remaining=D('12'));other,_=self.machine()
        self.assertEqual(r['plan']['lots'],D('.10'))
        with self.assertRaises(ValueError):m.fill_entry(D('100'),D('.11'))
        m.fill_entry(D('100'),D('.1'));other.fill_entry(D('100'),D('.2'))
        self.assertEqual((m.state,other.state),('OPEN','OPEN'))
        m.box=BoxPlan('b',D('30'),'explicit structural target',('reduce',),True)
        with self.assertRaises(ValueError):m.quote(D('100'),D('100.2'),11)

if __name__=='__main__':unittest.main()
