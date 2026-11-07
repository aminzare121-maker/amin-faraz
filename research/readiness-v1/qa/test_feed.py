import unittest
from feed_contract import dry_run,synthetic_receipt,future_gate,REQUIRED
class FeedTests(unittest.TestCase):
 def ticks(self):return [{'ts_ms':0,'bid':'100','ask':'100.3'},{'ts_ms':1,'bid':'101','ask':'101.3'}]
 def bar(self):return {'open_ms':0,'close_ms':900000,'available_ms':900000,'open':'100','high':'102','low':'99','close':'101','price_side':'BID'}
 def check_bad(self,rows,kind='TICK'):
  raw,r=synthetic_receipt(rows,kind);self.assertEqual(dry_run(raw,r)['status'],'BLOCKED')
 def test_valid_tick_hash_preserved(self):
  raw,r=synthetic_receipt(self.ticks());v=dry_run(raw,r);self.assertEqual(v['rows_processed'],2);self.assertEqual(v['sha256_before'],v['sha256_after'])
 def test_valid_bar_dry_run_only(self):
  raw,r=synthetic_receipt([self.bar()],'M15');v=dry_run(raw,r);self.assertEqual(v['status'],'SYNTHETIC_DRY_RUN_PASS');self.assertFalse(v['fit_allowed']);self.assertFalse(v['trade_allowed'])
 def test_real_scope_rejected_before_parse(self):self.assertEqual(dry_run(b'not json',{'scope':'REAL'})['rows_processed'],0)
 def test_hash_mismatch(self):
  raw,r=synthetic_receipt(self.ticks());r['sha256']='0'*64;self.assertEqual(dry_run(raw,r)['reasons'],['ORIGINAL_BYTE_HASH_MISMATCH'])
 def test_timezone_unknown(self):
  raw,r=synthetic_receipt(self.ticks());r['timezone']='UNKNOWN';self.assertEqual(dry_run(raw,r)['status'],'BLOCKED')
 def test_session_unknown(self):
  raw,r=synthetic_receipt(self.ticks());r['session']='UNKNOWN';self.assertEqual(dry_run(raw,r)['status'],'BLOCKED')
 def test_duplicate(self):self.check_bad([self.ticks()[0]]*2)
 def test_reverse_order(self):self.check_bad(self.ticks()[::-1])
 def test_crossed(self):self.check_bad([dict(self.ticks()[0],bid='200')])
 def test_nan(self):self.check_bad([dict(self.ticks()[0],bid='NaN')])
 def test_boolean_time(self):self.check_bad([dict(self.ticks()[0],ts_ms=True)])
 def test_empty(self):self.check_bad([])
 def test_ohlc(self):self.check_bad([dict(self.bar(),high='99')],'M15')
 def test_unclosed_bar(self):self.check_bad([dict(self.bar(),available_ms=899999)],'M15')
 def test_unknown_price_side(self):self.check_bad([dict(self.bar(),price_side='UNKNOWN')],'M15')
 def test_gap_is_not_filled(self):self.check_bad([self.bar(),dict(self.bar(),open_ms=1800000,close_ms=2700000,available_ms=2700000)],'M15')
 def test_all_unknown_blocks(self):self.assertEqual(len(future_gate({})['missing_or_unverified']),len(REQUIRED))
 def test_self_asserted_verified_not_permission(self):
  g=future_gate({k:{'status':'VERIFIED','evidence_id':'synthetic-assertion'} for k in REQUIRED});self.assertFalse(g['real_data_authorized']);self.assertFalse(g['fit_allowed']);self.assertEqual(g['status'],'BLOCKED_CURRENT_SCOPE')
 def test_extra_columns_rejected(self):self.check_bad([dict(self.ticks()[0],account='not-needed')])
if __name__=='__main__':unittest.main()
