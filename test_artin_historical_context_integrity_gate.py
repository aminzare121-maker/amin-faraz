"""Offline fail-closed control tests. Fixtures are synthetic, not teacher evidence."""
import copy
import unittest
from artin_historical_context_integrity_gate import ROUTES, CLOCK, check_row


def fixture():
    decisions=[]
    for r in ROUTES:
        for s in ('BUY','SELL'):
            decisions.append({'rule_id':r,'side':s,'status':'REVIEW',
                              'order_created':False,
                              'missing_dependencies':['sentiment_permission','current_setup'],
                              'future_dependencies':[], 'supplied_context_keys':[],
                              'context_required_keys':[],
                              'dependency_facts':{'decision_close':{
                                  'known_at':900,'origin':'DERIVED_FROM_RAW',
                                  'source':'CSV_SHA256:fixture:0'}}})
    return {'at':900,'bar_opened_at':0,'broker_connected':False,'orders_sent':0,
            'original_direction_evidence':None,'direction_plan':None,
            'active_context_windows':[],'decisions':decisions}

class ContextIntegrityTests(unittest.TestCase):
    def test_baseline_26_branches_causal(self):
        a,b,c=check_row(fixture())
        self.assertEqual(sum(a.values()),26)
        self.assertEqual(sum(b.values()),52)
        self.assertEqual(sum(c.values()),26)
    def test_duplicate_rejected(self):
        f=fixture();f['decisions'][1]=copy.deepcopy(f['decisions'][0])
        with self.assertRaisesRegex(ValueError,'duplicate'):check_row(f)
    def test_hidden_sentiment_rejected(self):
        f=fixture();f['decisions'][0]['missing_dependencies'].remove('sentiment_permission')
        with self.assertRaisesRegex(ValueError,'direction missingness'):check_row(f)
    def test_future_price_rejected(self):
        f=fixture();f['decisions'][0]['dependency_facts']['decision_close']['known_at']=901
        with self.assertRaisesRegex(ValueError,'LOOKAHEAD'):check_row(f)
    def test_supplied_unverified_context_rejected(self):
        f=fixture();f['active_context_windows']=[{'source':'invented'}]
        with self.assertRaisesRegex(ValueError,'supplied context'):check_row(f)
    def test_broker_connected_rejected(self):
        f=fixture();f['broker_connected']=True
        with self.assertRaisesRegex(ValueError,'broker'):check_row(f)
    def test_trade_claim_rejected(self):
        f=fixture();f['decisions'][0]['status']='ELIGIBLE'
        with self.assertRaisesRegex(ValueError,'remain REVIEW'):check_row(f)
    def test_source_missing_rejected(self):
        f=fixture();f['decisions'][0]['dependency_facts']['decision_close']['source']=''
        with self.assertRaisesRegex(ValueError,'provenance'):check_row(f)
    def test_negative_known_at_rejected(self):
        f=fixture();f['decisions'][0]['dependency_facts']['decision_close']['known_at']=-1
        with self.assertRaisesRegex(ValueError,'LOOKAHEAD'):check_row(f)
    def test_negative_open_time_rejected(self):
        f=fixture();f['bar_opened_at']=-900;f['at']=0
        with self.assertRaisesRegex(ValueError,'closed candle'):check_row(f)
    def test_clock_not_actual_utc(self):
        self.assertEqual(CLOCK,'RAW_BROKER_LABELS_NOT_VERIFIED_UTC')
    def test_time_regression_rejected(self):
        with self.assertRaisesRegex(ValueError,'non-ascending'):check_row(fixture(),900)
    def test_wrong_route_count_rejected(self):
        f=fixture();f['decisions'].pop()
        with self.assertRaisesRegex(ValueError,'13 rules'):check_row(f)

if __name__=='__main__':unittest.main()