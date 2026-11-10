import copy
import hashlib
import io
import json
import unittest
import zipfile
from artin_video20_scene_boundary import verify_boundary


def fixture():
    items = [('frames/a_t0004215000_original.jpg',b'schematic fake image','educational_schematic',4215),
             ('frames/a_t0004245000_original.jpg',b'chart fake image','historical_price_chart',4245)]
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for name,data,_,_ in items:z.writestr(name,data)
    buf.seek(0)
    labels=[{'archive_member':n,'sha256':hashlib.sha256(d).hexdigest(),
             'observed_scene':category,'time_seconds':t} for n,d,category,t in items]
    return buf,labels

class TestSceneBoundary(unittest.TestCase):
    def test_interval_not_exact_timestamp(self):
        z,l=fixture();v=verify_boundary(z,l)
        self.assertEqual(v['transition_observation'],{'after_seconds':4215,'at_or_before_seconds':4245,'exact_transition_time_known':False})
        self.assertEqual(v['trade_orders_authorized'],0)
    def test_changed_hash_rejected(self):
        z,l=fixture();l[0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SHA'):verify_boundary(z,l)
    def test_duplicate_timestamp_rejected(self):
        z,l=fixture();l[1]['time_seconds']=l[0]['time_seconds']
        with self.assertRaises(ValueError):verify_boundary(z,l)
    def test_forged_member_rejected(self):
        z,l=fixture();l[1]['archive_member']='fake'
        with self.assertRaisesRegex(ValueError,'identity'):verify_boundary(z,l)
    def test_inverted_observations_rejected(self):
        z,l=fixture();l[0]['observed_scene'],l[1]['observed_scene']=l[1]['observed_scene'],l[0]['observed_scene']
        with self.assertRaises(ValueError):verify_boundary(z,l)
    def test_single_kind_rejected(self):
        z,l=fixture();l[1]['observed_scene']='educational_schematic'
        with self.assertRaisesRegex(ValueError,'transition'):verify_boundary(z,l)
    def test_optimized_no_assert_bypass(self):
        z,l=fixture();l[1]['sha256']='0'*64
        with self.assertRaises(ValueError):verify_boundary(z,l)
if __name__=='__main__':unittest.main()