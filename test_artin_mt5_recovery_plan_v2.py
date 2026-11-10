"""Synthetic-only regression of a safe closed-bar recovery algorithm.

Not an execution or compilation test of MQL5; never broker/teacher certification.
"""
import csv
import io
import unittest
from datetime import datetime, timezone
from pathlib import Path

from artin_mt5_recovery_plan_v2 import RecoveryBlocked, next_closed_batch
from artin_mt5_shadow_bridge import HEADER, LABEL, parse_csv_bytes, SourceRejected, build_blocked_report

BASE = 1760000400  # exactly divisible by 900, synthetic, NOT live market data


def bars(n=60):
    return [BASE + 900 * i for i in range(n)]


def encode_csv(epochs, symbol='XAUUSD.ecn', bad_flags=False):
    file = io.StringIO(newline='')
    w = csv.writer(file, lineterminator='\r\n')
    w.writerow(HEADER)
    for i,t in enumerate(epochs):
        # Walltime derived for test only, not a claimed Eplanet time-zone.
        ts = datetime.fromtimestamp(t, timezone.utc).strftime('%Y.%m.%d %H:%M:%S')
        p = 3000 + i/10
        w.writerow([LABEL, str(t), ts, symbol, 'M15', str(p), str(p+2), str(p-2),
                    str(p+1), '10', '20', '0', '1' if bad_flags else '0','0'])
    return file.getvalue().encode('utf8')


class RecoveryPlannerTests(unittest.TestCase):
    def test_initial_bootstrap_has_oldest_first_across_batches(self):
        history=bars(30)
        first=next_closed_batch(history,None,initial_closed_bars=7,batch_bars=3)
        self.assertEqual(first.epochs, tuple(history[-7:-4]))
        self.assertEqual(first.pending_after_batch,4)
        second=next_closed_batch(history,first.epochs[-1],initial_closed_bars=7,batch_bars=3)
        self.assertEqual(second.epochs, tuple(history[-4:-1]))
        third=next_closed_batch(history,second.epochs[-1],batch_bars=3)
        self.assertEqual(third.epochs, (history[-1],))
        self.assertTrue(third.exhausted)

    def test_recover_14_closed_bars_in_oldest_first_chunks(self):
        source=bars(60); last=source[35]; recovered=[]
        for _ in range(8):
            batch=next_closed_batch(source,last,batch_bars=4)
            recovered.extend(batch.epochs)
            if not batch.epochs: break
            last=batch.epochs[-1]
        self.assertEqual(recovered,source[36:])
        self.assertEqual(len(set(recovered)),len(recovered))

    def test_no_work_when_checkpoint_is_latest_closed(self):
        h=bars(16)
        self.assertEqual(next_closed_batch(h,h[-1]).epochs, ())

    def test_closed_bar_zero_is_never_inserted_into_batch(self):
        h=bars(24)
        newest_forming=h[-1]+900
        self.assertNotIn(newest_forming,next_closed_batch(h,h[12],batch_bars=10).epochs)

    def test_weekend_gap_is_not_filled_with_fake_candles(self):
        h=[BASE,BASE+900,BASE+300*900,BASE+301*900]
        batch=next_closed_batch(h,BASE,batch_bars=5)
        self.assertEqual(batch.epochs,tuple(h[1:]))
        self.assertNotIn(BASE+2*900,batch.epochs)

    def test_missing_exact_anchor_refused(self):
        with self.assertRaisesRegex(RecoveryBlocked,'EXACT_LAST_COMMITTED_BAR'):
            next_closed_batch(bars(15),BASE+30*900)

    def test_wrong_anchor_lag_cap_refused(self):
        with self.assertRaisesRegex(RecoveryBlocked,'CATCHUP_BAR_COUNT_EXCEEDS_CAP'):
            next_closed_batch(bars(50),BASE,max_catchup_bars=6,batch_bars=2)

    def test_invalid_batch_configuration_refused(self):
        for args in ({'batch_bars':0},{'initial_closed_bars':0},
                     {'batch_bars':300,'max_catchup_bars':5}):
            with self.subTest(args=args),self.assertRaises(RecoveryBlocked):
                next_closed_batch(bars(10),None,**args)

    def test_reversed_or_duplicated_history_refused(self):
        for data in ([BASE,BASE],[BASE+900,BASE],[BASE,BASE+1]):
            with self.subTest(data=data),self.assertRaises(RecoveryBlocked):
                next_closed_batch(data,None)

    def test_invalid_or_boolean_checkpoint_refused(self):
        for cp in (True,-10,BASE+1,'fake'):
            with self.subTest(cp=cp),self.assertRaises(RecoveryBlocked):
                next_closed_batch(bars(10),cp)

    def test_caught_up_stream_integrates_with_existing_python_parser(self):
        h=bars(70); last=h[20]; collected=h[:21]
        while True:
            b=next_closed_batch(h,last,batch_bars=7)
            if not b.epochs:break
            collected.extend(b.epochs)
            last=b.epochs[-1]
        self.assertEqual(collected,h)
        raw=encode_csv(collected)
        audit=build_blocked_report(raw)
        self.assertEqual(audit['source_rows'],70)
        self.assertEqual(audit['route_count'],13)
        self.assertEqual(audit['broker_orders_sent'],0)
        self.assertEqual(audit['market_entry_signals'],0)
        self.assertTrue(all(not r['order_authorized'] for r in audit['route_statuses']))

    def test_parser_rejects_forged_semantic_authorization(self):
        with self.assertRaisesRegex(SourceRejected,'FALSE_SEMANTIC_OR_ORDER_AUTHORIZATION'):
            parse_csv_bytes(encode_csv(bars(1),bad_flags=True))

    def test_parser_rejects_wrong_symbol(self):
        with self.assertRaisesRegex(SourceRejected,'UNEXPECTED_SYMBOL'):
            parse_csv_bytes(encode_csv(bars(1),symbol='EURUSD'))

    def test_parser_rejects_truncated_row(self):
        bad=encode_csv(bars(2)).rstrip(b'\r\n').rsplit(b',',2)[0]+b'\r\n'
        with self.assertRaises(SourceRejected):
            parse_csv_bytes(bad)

    def test_v2_mql_source_remains_read_only_and_fail_closed(self):
        source=Path(__file__).with_name('ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.mq5').read_text()
        for term in ('CopyRates(_Symbol,PERIOD_M15,start_pos,count,rates)',
                     'iBarShift(_Symbol,PERIOD_M15,g_last_bar,true)',
                     'start_pos=anchor_shift-count',
                     'FILE_SHARE_READ',
                     'ACCOUNT_TRADE_MODE_DEMO',
                     'g_last_bar=0;',
                     'FileFlush(g_file)',
                     'g_file=FileOpen('):
            with self.subTest(term=term):self.assertIn(term,source)
        for forbidden in ('OrderSend(', 'CTrade(', 'Buy(', 'Sell(', 'WebRequest(',
                          'GlobalVariableGet(', 'GlobalVariableSet(', 'FILE_SHARE_WRITE'):
            with self.subTest(forbidden=forbidden):self.assertNotIn(forbidden,source)

    def test_v2_mql_checks_prior_csv_price_and_walltime_before_append(self):
        source=Path(__file__).with_name('ArtinV13_ShadowProbe_RecoveryV2_DemoOnly.mq5').read_text()
        self.assertIn('row[2]!=TimeToString(current,TIME_DATE|TIME_SECONDS)',source)
        self.assertIn('corrupt OHLC in persisted CSV',source)
        self.assertIn('ValidDecimalCell(row[p])',source)
        self.assertIn('DigitsOnly(row[v])',source)
        self.assertIn('FileClose(g_file);g_file=INVALID_HANDLE;return INIT_FAILED;',source)
        bad=encode_csv(bars(1)).replace(b'3002.0',b'2000.0')
        with self.assertRaises(SourceRejected):
            parse_csv_bytes(bad)

    def test_stream_stays_blocked_after_partial_recovery(self):
        history=bars(20); pending=next_closed_batch(history,history[4],batch_bars=3)
        self.assertEqual(len(pending.epochs),3)
        ledger=build_blocked_report(encode_csv(history[:5]+list(pending.epochs)))
        self.assertEqual(ledger['source_rows'],8)
        self.assertEqual(ledger['demo_orders_sent'],0)
        self.assertFalse(ledger['teacher_meaning_verified'])


if __name__=='__main__':unittest.main(verbosity=2)