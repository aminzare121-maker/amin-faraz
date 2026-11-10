"""Public synthetic regressions for permutation-safe source segment pairing."""
import copy,unittest
from artin_14_pair_time_identity import bind_pair
H='a'*64
A={'source_audio_sha256':H,'start_seconds':40.1,'end_seconds':42.2}
B={'source_audio_sha256':H,'start_seconds':50.3,'end_seconds':53.4}
def sample():return {'segment_ids':['b','a'],'phrases':[[40.1,42.2],[50.3,53.4]],'source_audio_sha256':H}
class Checks(unittest.TestCase):
    def test_shuffled_ids_not_zipped_by_position(self):
        r=bind_pair(sample(),{'a':A,'b':B});self.assertEqual([v['source_segment_id'] for v in r],['a','b'])
    def test_wrong_source_sha_rejected(self):
        p=sample();p['source_audio_sha256']='f'*64
        with self.assertRaises(ValueError):bind_pair(p,{'a':A,'b':B})
    def test_bad_interval_rejected(self):
        p=sample();p['phrases'][0]=[40.1,44.9]
        with self.assertRaises(ValueError):bind_pair(p,{'a':A,'b':B})
    def test_duplicate_identifier_rejected(self):
        p=sample();p['segment_ids']=['a','a']
        with self.assertRaises(ValueError):bind_pair(p,{'a':A,'b':B})
    def test_missing_source_rejected(self):
        with self.assertRaises(ValueError):bind_pair(sample(),{'a':A})
    def test_nan_rejected(self):
        p=sample();p['phrases'][0]=[float('nan'),42.2]
        with self.assertRaises(ValueError):bind_pair(p,{'a':A,'b':B})
    def test_nonfinite_source_rejected(self):
        a=dict(A,start_seconds=float('inf'))
        with self.assertRaises(ValueError):bind_pair(sample(),{'a':a,'b':B})
if __name__=='__main__':unittest.main()