"""Read-only M15 source checks, real input available locally, absent in public CI."""
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_real_m15_observation_replay import read_verified_bars,scan,build

ROOT=Path(__file__).parent
PRIVATE=Path('/mnt/data/EPLANET_M15_FOR_ARTIN_PRIVATE_UPLOAD.zip')

class SyntheticTests(unittest.TestCase):
    def test_basic_wick_body_and_never_a_trade(self):
        rows=[(900,10.,12.,9.,11.),(1800,11.,11.5,10.5,10.5)]
        r,t,g=scan(rows)
        self.assertEqual(len(r),2)
        self.assertEqual(t['bullish'],1)
        self.assertEqual(t['bearish'],1)
        self.assertEqual(r[0]['teacher_trade_decision'],'NOT_VERIFIED')
        self.assertIsNone(r[0]['trade_or_profit_result'])
    def test_gap_never_imputed(self):
        r,t,g=scan([(900,10,11,9,10),(2700,10,11,9,10)])
        self.assertEqual(len(r),2)
        self.assertEqual(g[0]['missing_calendar_slots'],1)
        self.assertEqual(t['bars_following_gap'],1)
        self.assertEqual(t['consecutive_pairs'],0)
    def test_outside_previous_is_not_entry(self):
        r,t,g=scan([(900,10,11,9,10),(1800,10,12,8,10)])
        self.assertEqual(t['outside_previous_range'],1)
        self.assertEqual(r[1]['teacher_trade_decision'],'NOT_VERIFIED')

@unittest.skipUnless(PRIVATE.is_file(),'Private original Eplanet M15 upload not present on public GitHub runner')
class ActualUploadTests(unittest.TestCase):
    def test_source_all_parts_hash_and_count(self):
        rows,m,h=read_verified_bars(PRIVATE)
        self.assertEqual(len(rows),23643)
        self.assertEqual(m['source_chunks'],20)
    def test_all_real_bars_replayed_without_strategy(self):
        with tempfile.TemporaryDirectory() as d:
            r=build(PRIVATE,Path(d)/'report.json')
            self.assertTrue(r['source_complete_bar_replay'])
            self.assertEqual(r['gap_events_unclassified'],260)
            self.assertEqual(r['semantic_teacher_rules_verified'],0)
            self.assertIsNone(r['backtest_profit_usd'])
    def test_reject_modified_m15_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)/'changed.zip'
            with zipfile.ZipFile(PRIVATE) as src, zipfile.ZipFile(dst,'w') as out:
                for x in src.namelist():
                    b=src.read(x)
                    if x.endswith('.csv') and b'1762340400' in b:
                        b=b.replace(b'3979.8',b'3979.9',1)
                    out.writestr(x,b)
            with self.assertRaisesRegex(ValueError,'hash or byte count mismatch'):
                read_verified_bars(dst)
if __name__=='__main__':unittest.main()