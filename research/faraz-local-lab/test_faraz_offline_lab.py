import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from faraz_offline_lab import Candle,load_csv,split_segments,one_trade,screen,main

class FarazTests(unittest.TestCase):
    def test_stop_long_with_spread_slip(self):
        bars=[Candle(900*k,100,101,97,100,1) for k in range(12)]
        t,s=one_trade(bars,0,1,1.0)
        self.assertEqual(s,'RESOLVED')
        self.assertEqual(t[2],'STOP')
        self.assertAlmostEqual(t[0], -2.5)  # (98.5-0.2)-(100+0.7)-0.1
    def test_stop_short_with_spread_slip(self):
        bars=[Candle(900*k,100,103,99,100,1) for k in range(12)]
        t,s=one_trade(bars,0,-1,1.0)
        self.assertEqual(t[2],'STOP')
        self.assertAlmostEqual(t[0], -2.5)
    def test_unresolved_end(self):
        bars=[Candle(900*k,100,100.1,99.9,100,1) for k in range(4)]
        self.assertEqual(one_trade(bars,0,1,1.)[1],'UNRESOLVED_NEXT_GAP_OR_END')
    def test_time_exit(self):
        bars=[Candle(900*k,100+k*.1,100+k*.1+.1,100+k*.1-.1,100+k*.1,1) for k in range(12)]
        trade,status=one_trade(bars,0,1,1.)
        self.assertEqual(trade[2],'TIME')
        self.assertEqual(trade[1],8*900)
    def test_split_no_lookahead_across_gap(self):
        bars=[Candle(900*k,1,2,0.5,1,1) for k in range(80)] + [Candle(900*k,1,2,.5,1,1) for k in range(82,180)]
        self.assertEqual(len(split_segments(bars)),2)
        self.assertEqual(len(screen(bars)[1]),3)
    def test_csv_schema_and_aggregate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'price.csv'; output=Path(tmp)/'out.json'
            with path.open('w',encoding='utf-8',newline='') as f:
                w=csv.writer(f)
                w.writerow(['time_raw_epoch','open','high','low','close','tick_volume','spread','real_volume'])
                for k in range(500):
                    v=1000+0.02*k+math.sin(k/8)*5
                    w.writerow([900*k,f'{v:.4f}',f'{v+1:.4f}',f'{v-1:.4f}',f'{v:.4f}',10,15,0])
            self.assertEqual(main(['--csv',str(path),'--out',str(output)]),0)
            a=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(a['candles_observed'],500)
            self.assertEqual(len(a['methods']),3)
            self.assertNotIn('1000.0',output.read_text())
            self.assertNotIn(str(path),output.read_text())
    def test_reject_bad_ohlc(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.csv'
            p.write_text('time_raw_epoch,open,high,low,close\n0,100,90,99,100\n',encoding='utf8')
            with self.assertRaises(ValueError):load_csv(p)

if __name__=='__main__': unittest.main()
