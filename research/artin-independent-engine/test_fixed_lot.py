import unittest
from decimal import Decimal as D
from capital import Instrument,Costs,BoxPlan
from context_inputs import Context
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from entry_engine import Fact,Observation
from trade_machine import TradeMachine

class FixedLotTests(unittest.TestCase):
    def prepare(self,side='BUY',lots=D('.03'),budget=D('25')):
        ctx=Context(0,10000,0,dict(sentiment_permission='TWO_SIDED',current_setup=True,
            family_selection_context='ZONE_CONTEXT',trend_strength='NORMAL',break_strength='STRONG',
            level_kind='PIVOT',line_level=D('100')),'SYNTHETIC_TEST_CONTEXT')
        p=RawPipeline('TEST',('BREAK_STRONG',),900,'f'*64,[ctx])
        bar=Candle(0,900,D('99'),D('101'),D('99'),D('101')) if side=='BUY' else Candle(0,900,D('101'),D('101'),D('99'),D('99'))
        result=p.step(bar)
        obs=p.latest_observation(side)
        self.assertEqual(next(d for d in result['decisions'] if d['side']==side)['status'],'ELIGIBLE')
        t=TradeMachine(p.engine,BoxPlan('TEST_BOX',budget,'SYNTHETIC_STRUCTURAL_TARGET',(),True),
            Instrument(D('100'),D('.01'),D('.01')),Costs(D('10'),D('.1')))
        r=t.prepare('BREAK_STRONG',obs,D('100'),D('99') if side=='BUY' else D('101'),
            D('103') if side=='BUY' else D('97'),budget,fixed_lots=lots)
        return t,r

    def test_fixed_lot_buy_sell_raw_to_accounting(self):
        for side,exit_price in [('BUY',D('103')),('SELL',D('97'))]:
            t,r=self.prepare(side)
            self.assertEqual(r['status'],'PAPER_ENTRY_INTENT')
            self.assertEqual(t.plan['lots'],D('.03'))
            self.assertEqual(r['sizing']['modeled_loss'],D('3.60'))
            t.fill_entry(D('100'),D('.03'))
            closed=t.close(exit_price,D('.30'))
            self.assertEqual(closed['accounting']['net_pnl'],D('8.70'))
            self.assertEqual(D('1000')+closed['accounting']['net_pnl'],D('1008.70'))

    def test_fixed_lot_not_silently_resized_for_budget(self):
        t,r=self.prepare(budget=D('1'))
        self.assertEqual(r['reason'],'MIN_LOT_EXCEEDS_RISK_BUDGET')
        t,r=self.prepare(budget=D('2'))
        self.assertEqual(r['reason'],'REQUESTED_FIXED_LOT_EXCEEDS_DECLARED_RISK_BUDGET')
        self.assertEqual(t.state,'NEW')

    def test_fixed_lot_contract_and_fill_mismatch(self):
        t,r=self.prepare(lots=D('.035'))
        self.assertEqual(r['reason'],'FIXED_LOT_OUTSIDE_CONTRACT_GRID')
        t,r=self.prepare()
        with self.assertRaises(ValueError):t.fill_entry(D('100'),D('.02'))
        self.assertEqual(t.state,'PREPARED')

if __name__=='__main__':unittest.main()
