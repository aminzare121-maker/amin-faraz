"""Standalone synthetic test suite; no actual MT5 or teacher decision certified."""
import csv
import io
import unittest
from pathlib import Path
import artin_mt5_shadow_bridge as m

ROOT=Path(__file__).parent

def fixture(rows=2):
    out=io.StringIO(newline='')
    writer=csv.writer(out,lineterminator='\n'); writer.writerow(m.HEADER)
    for i in range(rows):
        writer.writerow([m.LABEL,str(1800000000+900*i),'2027.01.15 12:%02d:00'%(15*i),
            'XAUUSD','M15','4010.1','4012.2','4009.2','4011.7','38','14','0','0','0'])
    return out.getvalue().encode()

def mutate(raw,column,val,which=1):
    rows=list(csv.reader(io.StringIO(raw.decode())))
    rows[which][rows[0].index(column)]=val
    out=io.StringIO(newline='');wr=csv.writer(out,lineterminator='\n');wr.writerows(rows)
    return out.getvalue().encode()

class TestShadowBridge(unittest.TestCase):
 def test_valid_source_13_blocked_no_orders(self):
    r=m.build_blocked_report(fixture());self.assertEqual(r['source_rows'],2)
    self.assertEqual(len(r['route_statuses']),13)
    self.assertEqual(r['market_entry_signals'],0);self.assertEqual(r['broker_orders_sent'],0)
    self.assertTrue(all(not x['order_authorized'] for x in r['route_statuses']))
 def test_all_route_identifiers_unique(self):
    self.assertEqual(len(set(m.ROUTES)),13)
 def test_route_registry_matches_existing_git_hub_route_contract(self):
    contract=ROOT/'artin_13_teacher_acceptance_matrix.py'
    if not contract.exists():
        self.skipTest('GitHub source contract is not mounted locally')
    import ast
    tree=ast.parse(contract.read_text(encoding='utf8'))
    vals=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id=='EXPECTED_ROUTES':
                    vals.append(node.value)
    self.assertEqual(len(vals),1)
    expression=vals[0]
    self.assertIsInstance(expression,ast.Call)
    original=next(x.value for x in ast.walk(expression) if isinstance(x,ast.Constant) and isinstance(x.value,str))
    self.assertEqual(set(original.split()),set(m.ROUTES))

 def test_broker_source_not_authenticated_by_csv_claim(self):
    self.assertTrue(m.build_blocked_report(fixture())['source_claim_not_independently_authenticated'])
 def test_bad_header(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(fixture().replace(b'source_label',b'unknown_label'))
 def test_duplicate(self):
    raw=mutate(fixture(),'broker_epoch','1800000000',2)
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(raw)
 def test_wrong_symbol(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'symbol','EURUSD'))
 def test_wrong_timeframe(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'timeframe','M5'))
 def test_order_claim_rejected(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'trade_authorized','1'))
 def test_teacher_certification_claim_rejected(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'teacher_semantics_verified','1'))
 def test_invalid_ohlc(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'high','4000.0'))
 def test_nonfinite_ohlc(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'close','nan'))
 def test_wrong_interval(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'broker_epoch','1800000001'))
 def test_negative_volume(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'tick_volume','-2'))
 def test_not_proof_of_semantic_teacher_match(self):
    r=m.build_blocked_report(fixture());self.assertFalse(r['teacher_meaning_verified'])
    self.assertFalse(r['teacher_original_speech_independently_verified'])
 def test_missing_rows(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(','.join(m.HEADER).encode())
 def test_read_only_mql5_source_has_no_trade_capability(self):
    src=(ROOT/'ArtinV13_ShadowProbe_DemoOnly.mq5').read_text(encoding='utf-8')
    # Strip comments before asserting no trade-capable imports/calls.
    import re
    s=re.sub(r'//[^\n]*','',src)
    s=re.sub(r'/\*.*?\*/','',s,flags=re.S)
    for forbidden in ('CTrade','OrderSend','OrderCheck','OrderCalcMargin','PositionOpen','Buy(','Sell(','Trade.mqh','WebRequest','FILE_WRITE|FILE_BIN'):
        self.assertNotIn(forbidden,s)
    self.assertIn('ACCOUNT_TRADE_MODE_DEMO',s)
    self.assertIn('CopyRates(_Symbol,PERIOD_M15,1,1,rates)',s)
 def test_bad_line_or_binary(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(fixture()+b'\x00')
 def test_mixed_symbols_disallowed(self):
    with self.assertRaises(m.SourceRejected):m.parse_csv_bytes(mutate(fixture(),'symbol','XAUUSD.m',2))
 def test_unclassified_market_gap_allowed(self):
    raw=mutate(fixture(),'broker_epoch','1800001800',2)
    self.assertEqual(m.parse_csv_bytes(raw)['gaps_unclassified'],1)

if __name__=='__main__':unittest.main(verbosity=2)