import csv,json,tempfile,unittest
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
from context_inputs import Context
from entry_engine import Engine,Fact,Observation
from raw_geometry import Candle
from raw_pipeline import RawPipeline
from run_raw import run
from monthly_execution import MonthlyExecutor

def context(side='BUY',unresolved=False):
    facts=dict(sentiment_permission='UNKNOWN' if unresolved else 'TWO_SIDED',current_setup=True,
        family_selection_context='ZONE_CONTEXT',trend_strength='NORMAL',break_strength='STRONG',
        level_kind='PIVOT',line_level=D(100))
    if unresolved:facts.update(direction_assessment='REVIEWED_INCONCLUSIVE',fixed_symbol_analysis=True,
        teacher_two_sided_branch_selected=True)
    return Context(0,2000,0,facts,'SYNTHETIC_SOURCE09_CONDITION_FIXTURE_NOT_HISTORICAL_ANALYSIS')

def execution(side='BUY',exit_price=None):
    if exit_price is None:exit_price='103' if side=='BUY' else '97'
    spec={'at':900,'known_at':0,'source':'SYNTHETIC_EXECUTION_FIXTURE','trade_id':'test1',
        'side':side,'rule_id':'BREAK_STRONG','entry_price':'100',
        'initial_stop':'99' if side=='BUY' else '101','target_price':'103' if side=='BUY' else '97',
        'instrument':{'money_per_price_unit_per_lot':'100','min_lot':'.01','lot_step':'.01'},
        'costs':{'round_trip_fee_per_lot':'10','adverse_price_allowance':'.1'},
        'box':{'box_id':'TEST','risk_budget':'25','target_definition':'SYNTHETIC_TARGET',
            'management_choices':[],'declared_before_box':True}}
    events=[{'trade_id':'test1','at':900,'known_at':900,'source':'SYNTHETIC_FILL',
             'event':'fill_entry','fill_price':'100'},
            {'trade_id':'test1','at':900,'known_at':900,'source':'SYNTHETIC_EXIT',
             'event':'close','exit_fill':exit_price,'actual_round_trip_fee':'.30'}]
    return {'specs':[spec],'events':events}

class MonthlyExecutionTests(unittest.TestCase):
    def monthly(self,side='BUY',doc=None,ctx=None):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bars.csv'
            with p.open('w',newline='',encoding='utf8') as f:
                w=csv.writer(f);w.writerow(['time_raw_epoch','open','high','low','close'])
                w.writerow([0,99,101,99,101] if side=='BUY' else [0,101,101,99,99])
            s=run(p,Path(tmp)/'out',900,contexts=[context(side)] if ctx is None else ctx,
                  execution_document=doc)
            e=json.loads((Path(tmp)/'out/PRIVATE_execution.json').read_text(encoding='utf8'))
            return s,e

    def test_real_monthly_runner_raw_buy_and_sell_reach_fill_and_ledger(self):
        for side in ('BUY','SELL'):
            with self.subTest(side=side):
                s,e=self.monthly(side,execution(side))
                self.assertEqual(s['paper_trades_opened'],1)
                self.assertEqual(s['closed_trades'],1)
                self.assertEqual(s['bookkeeping_cash_end_usd'],'1008.70')
                self.assertEqual(s['eligible_decisions_routed'],1)
                self.assertTrue(s['actual_lot_applied'])
                self.assertEqual(s['paper_buy_trades'],int(side=='BUY'))
                self.assertEqual(s['paper_sell_trades'],int(side=='SELL'))
                self.assertEqual(e['events'][0]['result']['plan']['lots'],'0.03')

    def test_monthly_runner_records_losses_both_sides(self):
        for side,price in [('BUY','99'),('SELL','101')]:
            s,e=self.monthly(side,execution(side,price))
            self.assertEqual(s['bookkeeping_cash_end_usd'],'996.70')
            self.assertEqual(s['closed_trades'],1)

    def test_missing_execution_inputs_are_reported_not_fake_fills(self):
        s,e=self.monthly()
        self.assertEqual(s['eligible_decisions_routed'],1)
        self.assertEqual(s['execution_blocked'],1)
        self.assertEqual(s['paper_trades_opened'],0)
        self.assertEqual(e['events'][0]['reason'],'MISSING_SOURCE_BACKED_EXECUTION_SPEC')

    def test_unknown_branch_is_executable_only_with_explicit_source_conditions(self):
        s,e=self.monthly(doc=execution(),ctx=[context(unresolved=True)])
        self.assertEqual(s['paper_trades_opened'],1)
        self.assertEqual(s['bookkeeping_cash_end_usd'],'1008.70')

    def test_missing_economics_is_not_automatically_two_sided(self):
        c=context(unresolved=True)
        f=dict(c.facts);f['direction_assessment']='MISSING_DATA'
        c=Context(0,2000,0,f,'SYNTHETIC_MISSING_INPUT')
        s,e=self.monthly(ctx=[c])
        self.assertEqual(s['eligible_decisions_routed'],0)
        self.assertEqual(s['paper_trades_opened'],0)

    def test_unreviewed_or_unselected_branch_never_silently_permits_trade(self):
        for key,value in [('direction_assessment','NOT_REVIEWED'),('fixed_symbol_analysis',False),
                          ('teacher_two_sided_branch_selected',False)]:
            f=dict(context(unresolved=True).facts);f[key]=value
            s,e=self.monthly(ctx=[Context(0,2000,0,f,'SYNTHETIC_NEGATIVE_BRANCH')])
            self.assertEqual(s['eligible_decisions_routed'],0)

    def test_future_execution_spec_is_blocked(self):
        doc=execution();doc['specs'][0]['known_at']=901;doc['events']=[]
        s,e=self.monthly(doc=doc)
        self.assertEqual(s['paper_trades_opened'],0)
        self.assertEqual(e['events'][0]['reason'],'FUTURE_EXECUTION_SPEC')

    def test_future_execution_events_not_consumed_at_month_cutoff(self):
        doc=execution();doc['events'][1]['known_at']=901
        s,e=self.monthly(doc=doc)
        self.assertEqual(s['paper_trades_opened'],1)
        self.assertEqual(s['closed_trades'],0)
        self.assertEqual(s['unresolved_trades'],1)
        self.assertEqual(s['filled_open_trades'],1)
        self.assertEqual(s['closed_pending_cost'],0)
        self.assertEqual(s['pending_events_after_cutoff'],1)
        self.assertEqual(s['bookkeeping_cash_end_usd'],'1000.00')

    def test_late_event_cannot_precede_entry_and_fake_earlier_fill(self):
        doc=execution();doc['events'][0]['at']=899
        with self.assertRaises(ValueError):self.monthly(doc=doc)

    def test_one_way_sentiment_still_excludes_other_side(self):
        f=dict(context().facts);f['sentiment_permission']='SHORT_ONLY'
        s,e=self.monthly(ctx=[Context(0,2000,0,f,'SYNTHETIC_SHORT_ONLY')])
        self.assertEqual(s['eligible_decisions_routed'],0)

    def registry_case(self,change):
        p=RawPipeline('TEST',('BREAK_STRONG',),900,'a'*64,[context()])
        first=p.step(Candle(0,900,D(99),D(101),D(99),D(101)))
        obs=p.latest_observation('BUY');decision=p.engine.evaluate('BREAK_STRONG',obs)
        doc=execution();a=doc['specs'][0];b=deepcopy(a);b['at']=1800;b['trade_id']='test2'
        change(b);doc['specs'].append(b);doc['events']=[]
        m=MonthlyExecutor(p.engine,'1000','.03',doc);m.accept(decision,obs)
        p.step(Candle(900,1800,D(99),D(101),D(99),D(101)))
        return m,p.engine.evaluate('BREAK_STRONG',p.latest_observation('BUY')),p.latest_observation('BUY')

    def test_same_box_cannot_change_rules_between_trades(self):
        m,d,o=self.registry_case(lambda b:b['box'].update(target_definition='CHANGED_WITHIN_SAME_BOX'))
        with self.assertRaises(ValueError):m.accept(d,o)
        self.assertEqual(len(m.trades),1)

    def test_same_contract_or_cost_identity_cannot_silently_change(self):
        for change in [lambda b:b['instrument'].update(money_per_price_unit_per_lot='200'),
                       lambda b:b['costs'].update(round_trip_fee_per_lot='20')]:
            m,d,o=self.registry_case(change)
            with self.assertRaises(ValueError):m.accept(d,o)

    def test_explicit_new_cost_version_and_new_box_permitted(self):
        def change(b):
            b['box']['box_id']='NEW_BOX';b['box']['target_definition']='NEW_NEXT_BOX_POLICY'
            b['cost_model_id']='NEW_COST_VERSION';b['costs']['round_trip_fee_per_lot']='20'
        m,d,o=self.registry_case(change)
        self.assertEqual(m.accept(d,o)['result']['status'],'PAPER_ENTRY_INTENT')

    def test_known_exit_unknown_cost_is_not_an_open_position_or_realized_profit(self):
        doc=execution();doc['events'][1]['actual_round_trip_fee']=None
        s,e=self.monthly(doc=doc)
        self.assertEqual(s['filled_open_trades'],0)
        self.assertEqual(s['closed_pending_cost'],1)
        self.assertEqual(s['closed_trades'],0)
        self.assertEqual(s['bookkeeping_cash_end_usd'],'1000.00')

if __name__=='__main__':unittest.main()
