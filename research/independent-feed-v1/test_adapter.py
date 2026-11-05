import copy
import json
import unittest
from adapter import aggregate, receipt, utc_ms, quote_spread

START = utc_ms('2026-11-01T00:00:00Z')  # Sunday: no globally assumed weekend rule.

def fixture(count=15):
    rows = []
    for i in range(count):
        rows.append({'open_ms': START+i*60000, 'close_ms': START+(i+1)*60000,
                     'available_ms': START+(i+1)*60000,
                     'bid': {'open': '100', 'high': str(102+i), 'low': '99', 'close': '101'},
                     'ask': {'open': '101', 'high': str(103+i), 'low': '100', 'close': '102'}})
    return rows

def run(rows=None, calendar=None, decision=None, mutate_meta=None):
    rows = fixture() if rows is None else rows
    raw = json.dumps(rows, sort_keys=True).encode()
    meta = receipt(raw)
    if mutate_meta: mutate_meta(meta)
    cal = {START+i*60000: 'OPEN' for i in range(15)} if calendar is None else calendar
    return aggregate(raw, meta, START, START+900000, START+900000 if decision is None else decision, cal)

class ContractTests(unittest.TestCase):
    def blocked(self, result, reason):
        self.assertEqual(result['status'], 'BLOCKED'); self.assertIn(reason, result['quality_flags'])
        self.assertEqual(result['bars'], [])
    def test_exact_aggregation(self):
        r = run(); self.assertEqual(r['status'], 'SYNTHETIC_PASS')
        self.assertEqual(r['bars'][0]['bid'], {'open':'100','high':'116','low':'99','close':'101'})
        self.assertEqual(r['bars'][0]['ask']['high'], '117')
        self.assertEqual(r['coverage']['ratio'], 1)
    def test_raw_preserved(self):
        r = run(); self.assertEqual(r['raw_sha256_before'], r['raw_sha256_after'])
    def test_hash_mismatch(self):
        self.blocked(run(mutate_meta=lambda m:m.update(sha256='0'*64)), 'HASH_MISMATCH')
    def test_real_scope_rejected(self):
        self.blocked(run(mutate_meta=lambda m:m.update(scope='REAL')), 'SYNTHETIC_ONLY')
    def test_mapping_unknown(self):
        self.blocked(run(mutate_meta=lambda m:m.update(instrument='XAUUSD.st')), 'SOURCE_OR_PROVENANCE_SCHEMA')
    def test_timezone_unknown(self):
        self.blocked(run(mutate_meta=lambda m:m.update(timezone='UNKNOWN')), 'SOURCE_OR_PROVENANCE_SCHEMA')
    def test_licence_missing(self):
        self.blocked(run(mutate_meta=lambda m:m.pop('licence_evidence')), 'SOURCE_OR_PROVENANCE_SCHEMA')
    def test_future_available(self):
        rows=fixture(); rows[-1]['available_ms']+=1
        self.blocked(run(rows), 'LOOKAHEAD_OR_UNCLOSED')
    def test_early_available(self):
        rows=fixture(); rows[0]['available_ms']-=1
        self.blocked(run(rows), 'LOOKAHEAD_OR_UNCLOSED')
    def test_decision_inside_bar(self):
        self.blocked(run(decision=START+899999), 'LOOKAHEAD_OR_UNCLOSED')
    def test_exact_duplicate(self):
        rows=fixture(); rows.insert(1,copy.deepcopy(rows[0]))
        self.blocked(run(rows), 'DUPLICATE')
    def test_conflicting_duplicate(self):
        rows=fixture(); duplicate=copy.deepcopy(rows[0]); duplicate['bid']['high']='150'; rows.insert(1,duplicate)
        self.blocked(run(rows), 'DUPLICATE')
    def test_unsorted(self):
        rows=fixture(); rows[0],rows[1]=rows[1],rows[0]
        self.blocked(run(rows), 'UNSORTED')
    def test_missing_not_filled(self):
        r=run(fixture()[1:]); self.blocked(r, 'MISSING_OPEN_MINUTES_NO_FILL')
        self.assertEqual(r['coverage']['missing_minutes'],1)
    def test_weekend_explicit_closed(self):
        r=run([], {START+i*60000:'CLOSED' for i in range(15)})
        self.assertEqual(r['status'],'SYNTHETIC_PASS'); self.assertEqual(r['bars'],[])
        self.assertIsNone(r['coverage']['ratio'])
    def test_weekend_not_assumed(self):
        self.assertEqual(run()['coverage']['expected_open_minutes'],15)
    def test_calendar_unknown(self):
        cal={START+i*60000:'OPEN' for i in range(15)}; cal[START]='UNKNOWN'
        self.blocked(run(calendar=cal),'SESSION_UNKNOWN')
    def test_calendar_missing(self):
        self.blocked(run(calendar={}), 'CALENDAR_SCHEMA')
    def test_record_in_closed(self):
        self.blocked(run(calendar={START+i*60000:'CLOSED' for i in range(15)}), 'RECORD_IN_CLOSED_SESSION')
    def test_partial_session(self):
        cal={START+i*60000:'OPEN' for i in range(15)}; cal[START]='CLOSED'
        self.blocked(run(fixture()[1:],cal), 'PARTIAL_SESSION_BUCKET')
    def test_invalid_ohlc(self):
        rows=fixture(); rows[0]['bid']['low']='105'
        self.blocked(run(rows),'OHLC_RANGE')
    def test_nan(self):
        rows=fixture(); rows[0]['bid']['open']='NaN'
        self.blocked(run(rows),'NONFINITE_OR_NONPOSITIVE_PRICE')
    def test_numeric_not_decimal_string(self):
        rows=fixture(); rows[0]['bid']['open']=100
        self.blocked(run(rows),'DECIMAL_STRING_REQUIRED')
    def test_crossed(self):
        rows=fixture(); rows[0]['bid']['high']='1000'
        self.blocked(run(rows),'CROSSED_SIDE_ENVELOPE')
    def test_m1_duration(self):
        rows=fixture(); rows[0]['close_ms']+=1
        self.blocked(run(rows),'M1_TIME')
    def test_schema_extra(self):
        rows=fixture(); rows[0]['volume']=0
        self.blocked(run(rows),'M1_SCHEMA')
    def test_utc_offsets(self):
        self.assertEqual(utc_ms('2026-11-01T03:30:00+03:30'),START)
    def test_naive_time(self):
        with self.assertRaises(ValueError): utc_ms('2026-11-01T00:00:00')
    def test_dst_fold_explicit_offsets(self):
        self.assertEqual(utc_ms('2026-11-01T01:30:00-05:00')-utc_ms('2026-11-01T01:30:00-04:00'),3600000)
    def test_precision_not_silently_lost(self):
        with self.assertRaises(ValueError): utc_ms('2026-11-01T00:00:00.000001Z')
    def test_spread_unknown_on_bars(self):
        self.assertIsNone(run()['bars'][0]['spread']['value'])
    def test_synchronous_spread(self):
        self.assertEqual(quote_spread('100','100.3',START,START),'0.3')
    def test_asynchronous_spread_rejected(self):
        with self.assertRaises(ValueError): quote_spread('100','100.3',START,START+1)
    def test_no_authority_escalation(self):
        r=run(); self.assertFalse(r['trade_allowed']); self.assertFalse(r['fit_allowed'])
        self.assertFalse(r['gate']['real_data_authorized'])
    def test_two_buckets(self):
        rows=fixture(30); raw=json.dumps(rows).encode()
        r=aggregate(raw,receipt(raw),START,START+1800000,START+1800000,{START+i*60000:'OPEN' for i in range(30)})
        self.assertEqual(len(r['bars']),2); self.assertEqual(r['bars'][1]['bid']['high'],'131')

if __name__=='__main__': unittest.main(verbosity=2)
