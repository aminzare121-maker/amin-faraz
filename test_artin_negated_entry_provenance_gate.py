import unittest
from artin_negated_entry_provenance_gate import audit
def example(text='ورود نمی کنیم'):
    return {'citations':[{'session':21,'route_id':'R','excerpts':[{
        'asr_segment_id':'seg1','start':10.0,'end':11.0,'text_unverified':text,
        'original_audio_sha256':'abc'}]}]}, {'routes':[{'route_id':'R','cases':[{
        'session':21,'segment_id':'seg1','start_seconds':10.0,
        'polarity_triage':'POSSIBLE_NEGATED_ENTRY'}]}]}
class TestGate(unittest.TestCase):
    def test_negative_is_no_trade(self):
        a,b=example()
        d=audit(a,b)
        self.assertEqual(d['unique_cases'],1)
        self.assertEqual(d['cases'][0]['action'],'NO_TRADE')
        self.assertFalse(d['teacher_semantics_verified'])
    def test_positive_rejected(self):
        a,b=example('ورود کنید')
        with self.assertRaises(ValueError):audit(a,b)
    def test_mismatch_rejected(self):
        a,b=example()
        b['routes'][0]['cases'][0]['start_seconds']=12.0
        with self.assertRaises(ValueError):audit(a,b)
if __name__=='__main__': unittest.main()
