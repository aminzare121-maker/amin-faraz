import copy
import hashlib
import io
import unittest
import zipfile
from artin_video20_citation_scene_guard import build_audit


def fixture():
    frames = [(4215, 'educational_schematic'), (4245, 'historical_price_chart')]
    buf = io.BytesIO()
    pins = []
    with zipfile.ZipFile(buf, 'w') as z:
        for t, label in frames:
            name = f'frames/frame_t{t*1000:010d}_original.jpg'
            data = f'test frame {t}'.encode()
            z.writestr(name, data)
            pins.append({'time_seconds':t, 'observed_scene':label,
                        'archive_member':name,'sha256':hashlib.sha256(data).hexdigest()})
    buf.seek(0)
    citations = {'citations': [
        {'session':20,'citation_index':1,'route_id':'A','source_start_seconds':4210.14,'source_end_seconds':4214.52},
        {'session':20,'citation_index':2,'route_id':'B','source_start_seconds':4214.52,'source_end_seconds':4223.26},
        {'session':20,'citation_index':3,'route_id':'C','source_start_seconds':4245,'source_end_seconds':4246},
        {'session':20,'citation_index':4,'route_id':'D','source_start_seconds':4180,'source_end_seconds':4185},
    ]}
    return buf, {'frames':pins}, citations


class Tests(unittest.TestCase):
    def test_citation_no_inside_frame(self):
        z,p,c=fixture(); r=build_audit(z,p,c)
        self.assertEqual(r['cases'][0]['classification'],'NO_DIRECT_FRAME')
        self.assertEqual(r['cases'][0]['nearby_later_frame_seconds_not_evidence'],4215)
        self.assertEqual(r['mt5_orders_authorized'],0)
    def test_transition_ambiguous_even_with_in_window_frame(self):
        z,p,c=fixture();r=build_audit(z,p,c)
        self.assertEqual(r['cases'][1]['classification'],'SCENE_AMBIGUOUS')
        self.assertTrue(r['cases'][1]['touches_unknown_transition_interval'])
    def test_after_transition_sample_is_not_decision(self):
        z,p,c=fixture();r=build_audit(z,p,c)
        self.assertEqual(r['cases'][2]['classification'],'SAMPLED_FRAME_ONLY')
        self.assertFalse(r['cases'][2]['observed_trade_sequence_verified'])
    def test_no_nearby_frame_does_not_create_evidence(self):
        z,p,c=fixture();r=build_audit(z,p,c)
        self.assertEqual(r['cases'][3]['classification'],'NO_DIRECT_FRAME')
    def test_tampered_hash_rejected(self):
        z,p,c=fixture();p['frames'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'digest'):build_audit(z,p,c)
    def test_fake_transition_anchor_rejected(self):
        z,p,c=fixture();p['frames'][0]['observed_scene']='historical_price_chart'
        with self.assertRaisesRegex(ValueError,'anchor'):build_audit(z,p,c)
    def test_repeated_time_rejected(self):
        z,p,c=fixture();p['frames'].append(copy.deepcopy(p['frames'][0]))
        with self.assertRaisesRegex(ValueError,'repeated'):build_audit(z,p,c)

if __name__=='__main__':unittest.main()