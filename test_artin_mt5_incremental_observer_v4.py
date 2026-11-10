"""Synthetic and a previously archived M15-shaped fixture, NOT DEMO runtime/teacher tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta

from artin_mt5_incremental_observer_v4 import ObserverBlocked, process_snapshot, run
from artin_mt5_shadow_bridge import HEADER, ROUTES

ROOT = Path(__file__).resolve().parent


def fixture():
    """Use immutable synthetic rows, no fabricated broker provenance claims."""
    raw = (ROOT / 'SYNTHETIC_M15_RECOVERY_FIXTURE.csv').read_bytes()
    lines = raw.splitlines(keepends=True)
    assert len(lines)>10
    return lines


def source(lines, count):
    return b''.join(lines[:count+1])


class TestIncrementalObserverV4(unittest.TestCase):
    def setUp(self):
        self.lines=fixture()
        self.first=source(self.lines,5)
        self.next=source(self.lines,8)
        self.last=source(self.lines,len(self.lines)-1)

    def test_bootstrap_5_new_closed_bars_no_trade(self):
        s,r=process_snapshot(self.first)
        self.assertEqual(r['new_closed_bars_processed'],5)
        self.assertEqual(len(r['raw_market_observations_not_teacher_signals']),5)
        self.assertEqual(r['route_count'],13)
        self.assertEqual(set(x['route_id'] for x in r['route_states']),set(ROUTES))
        self.assertEqual(r['orders_sent'],0)
        self.assertFalse(r['teacher_engine_example_match_certified'])
        self.assertTrue(all(not x['broker_order_permitted'] for x in r['route_states']))
        self.assertEqual(s['rows_seen'],5)
        self.assertFalse(s['trading_authorized'])

    def test_three_new_rows_only_after_checkpoint(self):
        prior,_=process_snapshot(self.first)
        later,report=process_snapshot(self.next,prior)
        self.assertEqual(report['previous_rows_seen'],5)
        self.assertEqual(report['new_closed_bars_processed'],3)
        self.assertEqual(later['rows_seen'],8)
        self.assertEqual(report['raw_market_observations_not_teacher_signals'][0]['broker_bar_epoch'], int(self.lines[6].split(b',')[1]))

    def test_idempotent_against_same_snapshot(self):
        checkpoint,_=process_snapshot(self.first)
        again,report=process_snapshot(self.first,checkpoint)
        self.assertEqual(checkpoint,again)
        self.assertEqual(report['status'],'READ_ONLY_OBSERVATION_NO_NEW_BARS')
        self.assertEqual(report['raw_market_observations_not_teacher_signals'],[])

    def test_historical_mutation_rejected_even_if_csv_valid(self):
        s,_=process_snapshot(self.first)
        modified=self.next.replace(b'3000.0,3002.0',b'3000.1,3002.0',1)
        with self.assertRaisesRegex(ObserverBlocked,'HISTORY_REWRITTEN'):
            process_snapshot(modified,s)

    def test_truncated_old_snapshot_rejected(self):
        s,_=process_snapshot(self.next)
        with self.assertRaisesRegex(ObserverBlocked,'SOURCE_TRUNCATED'):
            process_snapshot(self.first,s)

    def test_bad_checkpoint_row_count_rejected(self):
        s,_=process_snapshot(self.first)
        s['rows_seen']=4
        with self.assertRaisesRegex(ObserverBlocked,'CHECKPOINT_ROW_IDENTITY_MISMATCH'):
            process_snapshot(self.first,s)

    def test_bad_checkpoint_symbol_rejected(self):
        s,_=process_snapshot(self.first)
        s['symbol']='XAUUSD.OTHER'
        with self.assertRaisesRegex(ObserverBlocked,'SYMBOL_CHANGED'):
            process_snapshot(self.next,s)

    def test_invalid_sha_format_rejected(self):
        s,_=process_snapshot(self.first)
        s['source_sha256']='unknown'
        with self.assertRaisesRegex(ObserverBlocked,'INVALID_CHECKPOINT_DIGEST'):
            process_snapshot(self.next,s)

    def test_invalid_checkpoint_bool_rejected(self):
        s,_=process_snapshot(self.first)
        s['rows_seen']=True
        with self.assertRaisesRegex(ObserverBlocked,'INVALID_CHECKPOINT_ROW_COUNT'):
            process_snapshot(self.next,s)

    def test_extended_source_with_no_new_bar_refused(self):
        s,_=process_snapshot(self.first)
        with self.assertRaisesRegex(ObserverBlocked,'SOURCE_EXTENDED_WITHOUT_CLOSED_BAR'):
            process_snapshot(self.first+b'\r\n',s)

    def test_gap_is_recorded_never_interpolated(self):
        s,_=process_snapshot(self.first)
        previous=self.lines[5].decode().strip().split(',')
        old_epoch=int(previous[1]);old_dt=datetime.strptime(previous[2],'%Y.%m.%d %H:%M:%S')
        previous[1]=str(old_epoch+1800)
        previous[2]=(old_dt+timedelta(minutes=30)).strftime('%Y.%m.%d %H:%M:%S')
        new=self.first+(','.join(previous)+'\r\n').encode()
        _,r=process_snapshot(new,s)
        self.assertEqual(r['new_closed_bars_processed'],1)
        self.assertEqual(len(r['unclassified_gap_events_in_new_batch']),1)
        self.assertEqual(r['unclassified_gap_events_in_new_batch'][0]['interval_seconds'],1800)
        self.assertEqual(r['orders_sent'],0)

    def test_source_authorization_1_rejected(self):
        bogus=self.first.replace(b',0,0\r\n',b',0,1\r\n',1)
        with self.assertRaisesRegex(ObserverBlocked,'FALSE_SEMANTIC_OR_ORDER_AUTHORIZATION'):
            process_snapshot(bogus)

    def test_other_symbol_rejected(self):
        bogus=self.first.replace(b'XAUUSD.ecn',b'EURUSD',1)
        with self.assertRaisesRegex(ObserverBlocked,'UNEXPECTED_SYMBOL'):
            process_snapshot(bogus)

    def test_non_numeric_invalid_ohlc_rejected(self):
        bogus=self.first.replace(b'3002.0',b'INVALID',1)
        with self.assertRaisesRegex(ObserverBlocked,'NONNUMERIC'):
            process_snapshot(bogus)

    def test_duplicate_closed_bar_rejected(self):
        bogus=self.first+self.lines[5]
        with self.assertRaisesRegex(ObserverBlocked,'DUPLICATE_OR_NONMONOTONIC'):
            process_snapshot(bogus)

    def test_batch_size_limit_fail_closed(self):
        with self.assertRaisesRegex(ObserverBlocked,'TOO_MANY_NEW_BARS'):
            process_snapshot(self.next,max_new_bars=6)

    def test_invalid_batch_limit_rejected(self):
        with self.assertRaisesRegex(ObserverBlocked,'INVALID_BATCH_LIMIT'):
            process_snapshot(self.first,max_new_bars=True)

    def test_zero_body_observation_is_raw_subset_only(self):
        modified=self.lines.copy()
        row=modified[3].decode().strip().split(',')
        row[8]=row[5]
        modified[3]=(','.join(row)+'\r\n').encode()
        _,r=process_snapshot(source(modified,4))
        row=r['raw_market_observations_not_teacher_signals'][2]
        self.assertTrue(row['exact_zero_body_subset'])
        self.assertFalse(row['teacher_rule_verified'])

    def test_each_new_bar_has_individual_raw_source_hash(self):
        _,r=process_snapshot(self.first)
        rows=r['raw_market_observations_not_teacher_signals']
        self.assertEqual(len(set(x['source_row_raw_fields_sha256'] for x in rows)),5)
        self.assertTrue(all(x['closed_bar_known_no_earlier_than_broker_epoch']==x['broker_bar_epoch']+900 for x in rows))

    def test_checkpoint_atomic_write_and_resume(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);csv=d/'source.csv';state=d/'state.json'
            csv.write_bytes(self.first)
            r=run(csv,state)
            self.assertTrue(state.exists())
            self.assertEqual(r['new_closed_bars_processed'],5)
            csv.write_bytes(self.next)
            r=run(csv,state)
            self.assertEqual(r['new_closed_bars_processed'],3)
            self.assertEqual(json.loads(state.read_text())['rows_seen'],8)
            r=run(csv,state)
            self.assertEqual(r['new_closed_bars_processed'],0)
            self.assertFalse(list(d.glob('*.tmp')))

    def test_rejected_source_leaves_checkpoint_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);csv=d/'source.csv';state=d/'state.json'
            csv.write_bytes(self.first);run(csv,state)
            old=state.read_bytes()
            csv.write_bytes(self.next.replace(b'3000.0,3002.0',b'3000.1,3002.0',1))
            with self.assertRaises(ObserverBlocked):run(csv,state)
            self.assertEqual(old,state.read_bytes())

    def test_source_file_is_never_mutated(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);csv=d/'source.csv';state=d/'state.json'
            csv.write_bytes(self.first)
            before=csv.read_bytes();run(csv,state)
            self.assertEqual(csv.read_bytes(),before)

    def test_cannot_overwrite_source_with_checkpoint(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'source.csv';p.write_bytes(self.first)
            with self.assertRaisesRegex(ObserverBlocked,'MUST_NOT_OVERWRITE'):
                run(p,p)

    def test_full_synthetic_49_recovered_bars_no_trades(self):
        s,r=process_snapshot(self.last)
        self.assertGreater(r['new_closed_bars_processed'],49)
        self.assertEqual(s['rows_seen'],len(self.lines)-1)
        self.assertEqual(r['orders_sent'],0)
        self.assertEqual(len(r['route_states']),13)
        self.assertTrue(all(not x['trade_allowed'] for x in r['raw_market_observations_not_teacher_signals']))


if __name__ == '__main__':
    unittest.main(verbosity=2)