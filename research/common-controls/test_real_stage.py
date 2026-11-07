import unittest,tempfile,copy
from unittest.mock import patch
from pathlib import Path
from datetime import datetime,timezone
from registry import Registry,digest
from real_overlap import aggregate
from engine_bridge import execute,existing_engine

def minutes(n=15):
    start=1793740500
    return [dict(**{'Etc/UTC':datetime.fromtimestamp(start+i*60,timezone.utc).isoformat()},Open=str(100+i),High=str(102+i),Low=str(99+i),Close=str(101+i),Volume='1') for i in range(n)]

class AggregationTests(unittest.TestCase):
    def test_exact_ohlc(self):
        bars,excluded=aggregate(minutes(),1793740500,1793741400,1793741400)
        self.assertEqual(bars[0],dict(time=1793740500,open='100',high='116',low='99',close='115'));self.assertFalse(excluded)
    def test_missing_not_filled(self):
        bars,excluded=aggregate(minutes(14),1793740500,1793741400,1793741400)
        self.assertFalse(bars);self.assertEqual(excluded[0]['missing_m1'],1)
    def test_duplicate(self):
        with self.assertRaises(ValueError):aggregate(minutes()+minutes(),1793740500,1793741400,1793741400)
    def test_unclosed(self):
        with self.assertRaises(ValueError):aggregate(minutes(),1793740500,1793741400,1793741399)
    def test_zero_volume_rejected(self):
        rows=minutes();rows[0]['Volume']='0'
        with self.assertRaises(ValueError):aggregate(rows,1793740500,1793741400,1793741400)
    def test_bad_ohlc(self):
        rows=minutes();rows[0]['Close']='999'
        with self.assertRaises(ValueError):aggregate(rows,1793740500,1793741400,1793741400)
    def test_wrong_timezone(self):
        rows=minutes();rows[0]['Etc/UTC']='2026-11-04T00:00:00+02:00'
        with self.assertRaises(ValueError):aggregate(rows,1793740500,1793741400,1793741400)

def fixture():
    # Explicit synthetic sawtooth, no market data and no strategy claims.
    start=1760000400//900*900;out=[]
    for i in range(320):
        p=2000+(i%35)*.5
        out.append(dict(time=start+i*900,open=p,high=p+1,low=p-1,close=p+.2,tick_volume=100,final=True,observed_at=start+(i+1)*900))
    return out

COSTS=dict(spread=.5,slippage=.2,commission_per_lot=0,contract=100,volume=.01,swap_long_per_lot=-70,swap_short_per_lot=-70)
PROTOCOL=dict(cost_basis='HYPOTHETICAL_EXPLICIT',variable_spread=False,holdout='diagnostic-not-fresh',scenario='conservative-fixed-cost')

class EngineBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.bank=Registry(Path(self.tmp.name)/'bank.db');self.bars=fixture()
        self.bank.artifact('synthetic-320',digest(self.bars),{'synthetic':True},True)
    def tearDown(self):self.tmp.cleanup()
    def test_actual_engine_then_cached(self):
        first=execute(self.bank,self.bars,'synthetic-320',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
        self.assertEqual(first['action'],'EXECUTED');self.assertFalse(first['result']['market_profitability_verified'])
        second=execute(self.bank,self.bars,'synthetic-320',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
        self.assertEqual(second['action'],'REUSE');self.assertEqual(first['result'],second['result'])
        self.assertEqual(first['result']['split']['embargo_bars'],8)
        self.assertFalse(first['result']['selection_uses_holdout'])
    def test_unknown_cost_rejected(self):
        c=dict(COSTS,swap_long_per_lot=None)
        with self.assertRaisesRegex(ValueError,'COSTS'):execute(self.bank,self.bars,'synthetic-320',c,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
    def test_variable_spread_not_falsely_supported(self):
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED'):execute(self.bank,self.bars,'synthetic-320',COSTS,dict(PROTOCOL,variable_spread=True),scope='SYNTHETIC_DIAGNOSTIC')
    def test_invalid_dataset_blocks_actual_runner(self):
        self.bank.invalidate('synthetic-320','test invalidation')
        with self.assertRaisesRegex(ValueError,'DATA_NOT_VALIDATED'):execute(self.bank,self.bars,'synthetic-320',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
    def test_future_availability(self):
        self.bars[0]['observed_at']=self.bars[0]['time']
        with self.assertRaisesRegex(ValueError,'AVAILABILITY'):execute(self.bank,self.bars,'synthetic-320',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
    def test_unknown_raw_time(self):
        self.bars[0]['time_basis']='broker-server'
        with self.assertRaisesRegex(ValueError,'TIME'):execute(self.bank,self.bars,'synthetic-320',COSTS,PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
    def test_xau_contract_enforced(self):
        with self.assertRaisesRegex(ValueError,'CONTRACT'):execute(self.bank,self.bars,'synthetic-320',dict(COSTS,contract=1),PROTOCOL,scope='SYNTHETIC_DIAGNOSTIC')
    def test_existing_engine_contract_spread_slippage_arithmetic(self):
        existing_engine()
        from amin_mt5.research import evaluate_segment,Costs
        from amin_mt5.strategy import Candidate
        bars=[dict(b,open=100,high=102,low=98,close=100) for b in self.bars[:48]]
        setup=dict(side='buy',learning_features=[0]*7,features={'trend':'up'})
        # Controlled trigger isolates actual engine execution/PnL arithmetic.
        with patch('amin_mt5.research.plan',return_value=setup),patch('amin_mt5.research.size_and_target',return_value={'volume':'.01','stop_loss':'99'}):
            rows=evaluate_segment(bars,44,47,Costs(**COSTS),Candidate())
        self.assertTrue(rows);self.assertAlmostEqual(rows[0]['entry_price'],100.7)
        self.assertAlmostEqual(rows[0]['exit_price'],98.8)
        self.assertAlmostEqual(rows[0]['gross'],-1.9)
        self.assertEqual(rows[0]['exit_reason'],'stop')
    def test_existing_statistics_retain_losses_and_wins(self):
        existing_engine()
        from amin_mt5.research import statistics
        r=statistics([{'net':2},{'net':-3},{'net':1}])
        self.assertEqual(r['trades'],3);self.assertEqual(r['net_usd'],0);self.assertEqual(r['max_drawdown_usd'],3)

if __name__=='__main__':unittest.main(verbosity=2)
