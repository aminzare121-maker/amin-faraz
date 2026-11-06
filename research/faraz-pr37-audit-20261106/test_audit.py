import importlib.util,sys,unittest,tempfile,os,math
from pathlib import Path
from unittest.mock import patch
from pr37_audit import load_reference,metrics,friction_usd,costs,reconstruct
from metric_revision_v2 import snap_net
from safe_outputs_v2 import reject_aliases,write_json_atomic

SOURCE=Path(os.environ.get('FARAZ_PR37_REFERENCE',str(Path(__file__).resolve().parents[1]/'faraz-local-lab/faraz_offline_lab.py')))
lab=load_reference(SOURCE)

class AuditTests(unittest.TestCase):
    def test_theoretical_zero_before_after(self):
        bars=[lab.Candle(900*k,100,101.1,99.9,101 if k==68 else 100,1) for k in range(70)]
        trade,status=lab.one_trade(bars,60,1,1.)
        self.assertEqual(status,'RESOLVED');self.assertLess(trade[0],0);self.assertLess(abs(trade[0]),1e-12)
        row={'pnl':trade[0],'segment':0}
        before=metrics([row]);after=metrics([row],normalize=True)
        self.assertEqual(before['losing_closed'],1);self.assertEqual(before['closed_pf'],0)
        self.assertEqual(after['breakeven_closed'],1);self.assertEqual(after['losing_closed'],0);self.assertIsNone(after['closed_pf'])
    def test_missing_is_never_zero(self):
        self.assertIsNone(snap_net(None));self.assertEqual(metrics([{'pnl':None,'segment':0}],normalize=True)['unresolved'],1)
    def test_material_loss_not_erased(self):
        self.assertEqual(snap_net(-.01),-.01);self.assertEqual(snap_net(.01),.01)
    def test_hardlink_before_after(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'source.csv';b=Path(td)/'output.json';a.write_text('source sentinel');os.link(a,b)
            with self.assertRaises(ValueError):write_json_atomic(b,{'would':'overwrite'},[a])
            self.assertEqual(a.read_text(),'source sentinel')
    def test_same_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'x';a.write_text('protected')
            with self.assertRaises(ValueError):reject_aliases([a],[a])
    def test_two_outputs_alias_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'x';b=Path(td)/'y';a.write_text('sentinel');os.link(a,b)
            with self.assertRaises(ValueError):reject_aliases([],[a,b])
    def test_safe_atomic_write_preserves_input(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'source';b=Path(td)/'out';a.write_text('protected');write_json_atomic(b,{'ok':True},[a]);self.assertEqual(a.read_text(),'protected');self.assertIn('true',b.read_text())
    def test_cost_overlay_same_entry_same_exit(self):
        bars=[lab.Candle(k*900,100,100.1,99.9,100,1) for k in range(12)]
        base={'spread_price':.5,'slippage_each_side_price':.2,'commission_usd_per_lot_roundtrip':10}
        env={'spread_price':1.,'slippage_each_side_price':.4,'commission_usd_per_lot_roundtrip':10}
        for direction in (-1,1):
            with costs(lab,base):a,status=lab.one_trade(bars,0,direction,1.)
            with costs(lab,env):b,status=lab.one_trade(bars,0,direction,1.)
            self.assertEqual(a[1:],b[1:]);self.assertAlmostEqual(a[0]-b[0],.9)
    def test_cost_context_restores_globals(self):
        old=lab.SPREAD_PRICE
        with self.assertRaises(RuntimeError):
            with costs(lab,{'spread_price':9,'slippage_each_side_price':1,'commission_usd_per_lot_roundtrip':2}):raise RuntimeError()
        self.assertEqual(lab.SPREAD_PRICE,old)
    def test_short_ask_convention_contrast(self):
        bars=[lab.Candle(k*900,100,100.1,99.9,100,1) for k in range(12)]
        trade,status=lab.one_trade(bars,0,-1,.1)
        self.assertEqual(trade[2],'TIME');self.assertLess(100.1,100+.15);self.assertGreater(100.1+.5,100+.15)
    def test_short_bid_and_transformed_ask_stop_equivalent(self):
        stop_bid=100.15;spread=.5;stop_ask=stop_bid+spread
        for bid_high in (100.,100.1,100.15,100.3):
            self.assertEqual(bid_high>=stop_bid,bid_high+spread>=stop_ask)
        self.assertLess(100.1+spread,stop_ask)
    def test_future_prefix_invariance(self):
        pre=[lab.Candle(k*900,100+k*.1,101+k*.1,99+k*.1,100+k*.1,1) for k in range(80)]
        future=pre+[lab.Candle(k*900,10000,11000,9000,10000,1) for k in range(80,100)]
        a,aa=lab.signals(pre);b,bb=lab.signals(future)
        self.assertEqual(aa,bb[:80]);self.assertTrue(all(a[f]==b[f][:80] for f in lab.FAMILIES))
    def test_gap_and_sample_end_unknown_distinguished(self):
        bars=[lab.Candle(k*900,100,100.1,99.9,100,1) for k in range(64)]
        bars+= [lab.Candle(k*900,100,100.1,99.9,100,1) for k in range(66,130)]
        def fake(seg):
            signals={f:[0]*len(seg) for f in lab.FAMILIES};signals['compression_expansion'][60]=1
            atr=[None]*len(seg)
            for i in range(60,len(seg)):atr[i]=.2
            return signals,atr
        with patch.object(lab,'signals',side_effect=fake):
            segs,traces,*rest=reconstruct(lab,bars)
        self.assertEqual([r['reason'] for r in traces['compression_expansion']],['HISTORY_GAP_BEFORE_HORIZON','SAMPLE_END_BEFORE_HORIZON'])
    def test_dd_resets_only_in_independent_segment_metric(self):
        rows=[{'segment':0,'pnl':-5.},{'segment':1,'pnl':-7.}]
        self.assertEqual(metrics(rows)['max_independent_segment_closed_dd_usd'],7.)
    def test_unfavourable_gap_can_exceed_nominal_risk(self):
        bars=[lab.Candle(k*900,100,100.1,99.9,100,1) for k in range(12)]
        bars[2]=lab.Candle(1800,70,71,69,70,1)
        trade,status=lab.one_trade(bars,0,1,1.)
        self.assertEqual(trade[2],'STOP');self.assertLess(trade[0],-25)

if __name__=='__main__':unittest.main(verbosity=2)
