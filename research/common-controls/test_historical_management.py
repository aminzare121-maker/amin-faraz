import sys,unittest
from dataclasses import replace
from decimal import Decimal as D
from unittest.mock import patch
from historical_engine import canonical_bars,simulate
from historical_management import Management,train_past,Exposure

def bars(n=20):
    return canonical_bars([dict(time=1800000000+i*900,open='100',high='101',low='99',close='100') for i in range(n)],offset_seconds=0,offset_evidence='CONDITIONAL')
def setup(h):return dict(side='buy',stop_loss='95',signal_time=h[-1]['time'])
def run(data,m,signal=setup):
    return simulate(data,signal,spread='.3',slippage='.1',commission_roundtrip_per_lot='0',management=m)

class Tests(unittest.TestCase):
    def test_no_broker_module_loaded(self):
        self.assertNotIn('amin_mt5.mt5',sys.modules);self.assertNotIn('MetaTrader5',sys.modules)
    def test_variable_volume_from_capital(self):
        b=bars();a=Management('10000');c=Management('5000')
        x=a.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3'))
        y=c.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3'))
        self.assertLess(D(y['volume']),D(x['volume']))
        self.assertLessEqual(D(x['initial_risk_usd']),D('50'))
    def test_exposure_budget_veto(self):
        b=bars();m=Management();m.exposure=Exposure(notional='20000')
        self.assertIsNone(m.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3')))
    def test_daily_loss_and_stage_reduction(self):
        b=bars();m=Management();m.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3'))
        m.settle(D('-300'),b[2]['time'])
        self.assertEqual(m.stage.stage_index,1)
        self.assertEqual(D(m.stage.active_capital),D('4850'))
        self.assertIsNone(m.prepare(setup(b[:2]),D('100.4'),b[2],b[:2],D('.3')))
        self.assertIn('DAILY_DRAWDOWN_LIMIT',m.failures[-1]['reasons'])
    def test_daily_order_cap(self):
        b=bars();m=Management();m.policy=replace(m.policy,max_daily_orders=1)
        self.assertIsNotNone(m.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3')))
        self.assertIsNone(m.prepare(setup(b[:2]),D('100.4'),b[2],b[:2],D('.3')))
    def test_total_loss_limit(self):
        b=bars();m=Management();m.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3'))
        # Isolate total-reference veto without first exhausting stage sizing.
        m.stage=replace(m.stage,total_reference_equity='12000')
        self.assertIsNone(m.prepare(setup(b[:2]),D('100.4'),b[2],b[:2],D('.3')))
        self.assertIn('TOTAL_DRAWDOWN_LIMIT',m.failures[-1]['reasons'])
    def test_spread_and_stop_distance_vetoes(self):
        b=bars();m=Management()
        self.assertIsNone(m.prepare(setup(b[:1]),D('101.1'),b[1],b[:1],D('1')))
        self.assertIn('SPREAD_LIMIT',m.failures[-1]['reasons'])
        s=dict(setup(b[:1]),stop_loss='99.99')
        self.assertIsNone(m.prepare(s,D('100.4'),b[1],b[:1],D('.3')))
        self.assertIn('STOP_DIRECTION_OR_DISTANCE',m.failures[-1]['reasons'])
    def test_unprotected_exposure(self):
        b=bars();m=Management();m.exposure=Exposure(all_protected=False)
        self.assertIsNone(m.prepare(setup(b[:1]),D('100.4'),b[1],b[:1],D('.3')))
    def test_no_forced_horizon_or_gap_reentry(self):
        b=bars();b+= [dict(x,time=x['time']+900*40,raw_time=x['raw_time']+900*40) for x in bars(3)]
        r=run(b,Management())
        self.assertEqual(r['positions'],1);self.assertEqual(r['unresolved'],1)
        self.assertIsNone(r['scenario_net_usd']);self.assertIsNone(r['rows'][0]['target'])
    def test_trailing_effective_next_bar_not_same_bar(self):
        b=bars(16);m=Management()
        # A forced safe test double isolates the engine scheduling contract.
        b[14].update(high=D('110'),low=D('99'),close=D('109'))
        b[15].update(open=D('104'),high=D('105'),low=D('103'),close=D('104'))
        def close(*args):return dict(should_modify=args[5][-1]['time']==b[14]['time'],stop_loss='105')
        with patch.object(m,'on_close',side_effect=close):r=run(b,m)
        self.assertEqual(r['rows'][0]['reason'],'STOP_OPEN_GAP')
        self.assertGreater(r['rows'][0]['exit_time'],b[14]['time'])
        self.assertEqual(D(r['rows'][0]['exit']),D('103.9'))
    def test_real_trailing_never_weakens_stop(self):
        m=Management();m.peak=D('100');b=bars()
        x=m.on_close(D('100'),D('95'),'buy',D('120'),D('115'),b[-14:],D('.01'),D('0'),D('.1'))
        self.assertGreaterEqual(D(x['stop_loss']),D('115'))
    def test_unknown_rollover_blocks_new_position(self):
        b=bars(3)
        for i,x in enumerate(b):x['raw_time']=86400*20000+84600+i*900
        b[-1]['low']=D('94')
        r=run(b,Management())
        self.assertIsNone(r['scenario_net_usd'])
        self.assertEqual(r['rows'][0]['reason'],'ROLLOVER_COST_UNKNOWN')
    def test_training_excludes_future_and_insufficient(self):
        rows=[dict(time=10+i,net=D(i%2*2-1),learning_features=[float(i%3)]*7) for i in range(60)]
        a=train_past(rows,20);self.assertEqual(a['train_rows'],10)
        self.assertEqual(a['status'],'NO_TRAIN/INSUFFICIENT_SAMPLE')
        b=train_past(rows,40);self.assertEqual(b['model']['training_latest_exit'],39)
        rows[-1]['learning_features']=[999.0]*7
        self.assertEqual(b,train_past(rows,40))

if __name__=='__main__':unittest.main()
