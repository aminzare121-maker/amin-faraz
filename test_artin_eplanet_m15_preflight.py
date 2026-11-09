"""Purely synthetic fixture tests for read-only Eplanet-M15 input gate."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from artin_eplanet_m15_preflight import inspect_csv_text,main,read_source

HEADER='time_raw_epoch,open,high,low,close\n'
# Literal synthetic price data, not Eplanet and not teacher trading decisions.
def bars(rows):
    return HEADER+'\n'.join(','.join(str(x) for x in r) for r in rows)+'\n'

class M15Tests(unittest.TestCase):
    def test_valid_ohlc_does_not_authorize_trade(self):
        d=inspect_csv_text(bars([[0,100,102,99,101],[900,101,103,100,102]]),'a'*64,'synthetic.csv')
        self.assertEqual(d['status'],'PASS_STRUCTURAL_WITH_LIMITATIONS')
        self.assertEqual(d['rows'],2)
        self.assertFalse(d['teacher_rules_independently_verified'])
        self.assertFalse(d['mt5_orders_authorized'])
        self.assertIsNone(d['backtest_profit_usd'])
    def test_duplicate_rejected(self):
        r=inspect_csv_text(bars([[0,100,101,99,100],[0,100,101,99,100]]),'a'*64,'synthetic.csv')
        self.assertEqual(r['duplicate_bars'],1)
        self.assertEqual(r['status'],'FAIL_STRUCTURAL')
    def test_order_failure(self):
        r=inspect_csv_text(bars([[900,100,101,99,100],[0,100,101,99,100]]),'a'*64,'synthetic.csv')
        self.assertEqual(r['out_of_order_bars'],1)
        self.assertEqual(r['status'],'FAIL_STRUCTURAL')
    def test_hl_invalid_rejected(self):
        r=inspect_csv_text(bars([[0,100,99,99,101]]),'a'*64,'synthetic.csv')
        self.assertEqual(r['status'],'FAIL_STRUCTURAL')
        self.assertEqual(r['invalid_rows_sample'][0]['reason'],'invalid_ohlc')
    def test_unknown_session_gaps_not_fabricated(self):
        r=inspect_csv_text(bars([[0,100,101,99,100],[3600,100,101,99,100]]),'a'*64,'synthetic.csv')
        self.assertEqual(r['status'],'PASS_STRUCTURAL_WITH_LIMITATIONS')
        self.assertEqual(r['missing_calendar_slots_unclassified'],3)
        self.assertEqual(r['gap_events'],1)
    def test_reject_non_quarter_alignment(self):
        r=inspect_csv_text(bars([[61,100,101,99,100]]),'a'*64,'synthetic.csv')
        self.assertEqual(r['status'],'FAIL_STRUCTURAL')
        self.assertEqual(r['invalid_rows_sample'][0]['reason'],'not_m15_aligned')
    def test_native_mt5_tab_delimited_and_naive_clock(self):
        t='<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n2026.11.06\t10:00:00\t100\t101\t99\t100\n2026.11.06\t10:15:00\t100\t101\t99\t100\n'
        r=inspect_csv_text(t,'a'*64,'mt5_export.txt')
        self.assertEqual(r['rows'],2)
        self.assertEqual(r['status'],'PASS_STRUCTURAL_WITH_LIMITATIONS')
        self.assertIn('UNVERIFIED',r['time_interpretation'])
    def test_source_utf8_zip_single_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'actual_source.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('M15.csv',bars([[0,100,101,99,100]]))
            txt, digest, name=read_source(p)
            self.assertEqual(name,'M15.csv');self.assertEqual(txt[:5],'time_')
            self.assertEqual(len(digest),64)
    def test_zip_multiple_sources_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'ambiguous.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('M15.csv',HEADER);z.writestr('M5.csv',HEADER)
            with self.assertRaisesRegex(ValueError,'exactly_one'):read_source(p)
    def test_absent_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report.json'
            rc=main(['--csv',str(Path(tmp)/'missing.csv'),'--out',str(out)])
            self.assertEqual(rc,2)
            r=json.loads(out.read_text())
            self.assertEqual(r['status'],'FAIL_INPUT')
            self.assertFalse(r['mt5_orders_authorized'])
    def test_nonfinite_price_is_rejected(self):
        r=inspect_csv_text(bars([[0,100,float('nan'),99,100]]),'a'*64,'synthetic.csv')
        self.assertEqual(r['status'],'FAIL_STRUCTURAL')
        self.assertEqual(r['invalid_rows_sample'][0]['reason'],'invalid_ohlc')
    def test_23k_synthetic_rows_are_not_real_eplanet_or_teacher_backtest(self):
        rows=[[1700000100+900*i,100,101,99,100] for i in range(23735)]
        # Align start to a quarter hour to satisfy bar-open-grid test.
        for row in rows:row[0]=1700000100-1700000100%900+900*((row[0]-1700000100)//900)
        out=inspect_csv_text(bars(rows),'b'*64,'synthetic_23k.csv')
        self.assertEqual(out['rows'],23735)
        self.assertEqual(out['status'],'PASS_STRUCTURAL_WITH_LIMITATIONS')
        self.assertFalse(out['broker_provenance_independently_verified'])
        self.assertEqual(out['backtest_trades'],0)
        self.assertIsNone(out['backtest_profit_usd'])
        self.assertFalse(out['mt5_orders_authorized'])
    def test_dont_infer_one_year_coverage_from_row_count(self):
        r=inspect_csv_text(bars([[0,100,101,99,100],[900,100,101,99,100]]),'a'*64,'synthetic.csv')
        self.assertFalse(r['calendar_year_span_at_least_330_days'])

if __name__=='__main__':unittest.main()