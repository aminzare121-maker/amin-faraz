import copy
import unittest
from artin_negated_entry_provenance_gate_v2 import audit
def fixture(text='ورود نمی کنیم'):
    return ({'citations':[{'session':21,'route_id':'R','excerpts':[{
       'asr_segment_id':'s1','start':10.0,'end':11.0,'text_unverified':text,
       'original_audio_sha256':'source'}]}]},
       {'routes':[{'route_id':'R','cases':[{'session':21,'segment_id':'s1',
       'start_seconds':10.0,'polarity_triage':'POSSIBLE_NEGATED_ENTRY'}]}]})
class Tests(unittest.TestCase):
    def test_no_trade(self):
        a,b=fixture();r=audit(a,b)
        self.assertEqual(r['unique_cases'],1)
        self.assertEqual(r['cases'][0]['action'],'NO_TRADE')
        self.assertEqual(r['orders_authorized'],0)
    def test_positive_rejected(self):
        a,b=fixture('ورود کنید')
        with self.assertRaises(ValueError):audit(a,b)
    def test_time_change(self):
        a,b=fixture();b['routes'][0]['cases'][0]['start_seconds']=12
        with self.assertRaises(ValueError):audit(a,b)
    def test_route_swap(self):
        a,b=fixture();b['routes'][0]['route_id']='wrong'
        with self.assertRaises(ValueError):audit(a,b)
    def test_fabricated_id(self):
        a,b=fixture();b['routes'][0]['cases'][0]['segment_id']='fake'
        with self.assertRaises(ValueError):audit(a,b)
    def test_empty_candidates(self):
        a,b=fixture();b['routes'][0]['cases']=[]
        with self.assertRaises(ValueError):audit(a,b)
    def test_conflicting_id(self):
        a,b=fixture();c=copy.deepcopy(a['citations'][0]);c['route_id']='other'
        c['excerpts'][0]['text_unverified']='ورود نکنید';a['citations'].append(c)
        with self.assertRaises(ValueError):audit(a,b)
    def test_invalid_numeric(self):
        a,b=fixture();a['citations'][0]['excerpts'][0]['end']=float('nan')
        with self.assertRaises(ValueError):audit(a,b)
    def test_immutable(self):
        a,b=fixture();orig=(copy.deepcopy(a),copy.deepcopy(b));audit(a,b)
        self.assertEqual((a,b),orig)
    def test_duplicate_deduplication(self):
        a,b=fixture();a['citations'].append(copy.deepcopy(a['citations'][0]))
        b['routes'].append(copy.deepcopy(b['routes'][0]))
        self.assertEqual(audit(a,b)['unique_cases'],1)
if __name__=='__main__':unittest.main()
