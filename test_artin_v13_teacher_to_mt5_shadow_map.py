"""Tests include current original private queue only when mounted locally."""
import copy
import json
import unittest
from pathlib import Path
import artin_v13_teacher_to_mt5_shadow_map as m

PRIVATE=Path('/mnt/data/ARTIN_13_TEACHER_ACCEPTANCE_QUEUE_PRIVATE_20261110.json')

def fixture():
    d={'routes':[],'certified_routes':0,'orders_authorized':0}
    for i,name in enumerate(sorted(m.ROUTES)):
        n=2 if i<11 else 1
        citations=[]
        for j in range(n):
            k=sum(2 if t<11 else 1 for t in range(i))+j+1
            citations.append({'citation_index':k,'session':i+1,'interval_seconds':[100+k,102+k],
              'audio_words_independently_verified':False,'chart_visual_meaning_verified':False})
        d['routes'].append({'route_id':name,'source_sessions':[i+1],
            'citations':citations,'missing_required_reviews':list(m.REQUIRED_REVIEWS),
            'teacher_case_certified':False,'engine_decision_replay_certified':False,
            'orders_authorized':0})
    return d
class MapTests(unittest.TestCase):
 def test_synthetic_13_and_24_blocked(self):
    r=m.compile_shadow_evidence(fixture())
    self.assertEqual((r['distinct_legacy_entry_routes'],r['original_25_session_source_citations']),(13,24))
    self.assertEqual(r['teacher_certified_routes'],0)
    self.assertTrue(all(not x['orders_allowed'] for x in r['route_readiness']))
 def test_reject_claim_of_certification(self):
    d=fixture();d['routes'][0]['teacher_case_certified']=True
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 def test_reject_claim_of_order_authorization(self):
    d=fixture();d['routes'][0]['orders_authorized']=1
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 def test_reject_missing_route(self):
    d=fixture();d['routes'].pop()
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 def test_reject_missing_citation(self):
    d=fixture();d['routes'][0]['citations'].pop()
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 def test_reject_fake_review_completion(self):
    d=fixture();d['routes'][0]['missing_required_reviews'].pop()
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 def test_reject_changed_speech_anchor(self):
    d=fixture();d['routes'][0]['citations'][0]['audio_words_independently_verified']=True
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 def test_reject_cross_lesson_citation(self):
    d=fixture();d['routes'][0]['citations'][0]['session']=20
    with self.assertRaises(ValueError):m.compile_shadow_evidence(d)
 @unittest.skipUnless(PRIVATE.exists(),'private Behr source absent in public CI')
 def test_real_13_teacher_routes_24_citations(self):
    r=m.compile_shadow_evidence(json.loads(PRIVATE.read_text(encoding='utf8')))
    self.assertEqual(r['original_25_session_source_citations'],24)
    self.assertEqual(len(r['route_readiness']),13)
    self.assertEqual(sum(len(x['citation_numbers']) for x in r['route_readiness']),24)

if __name__=='__main__':unittest.main(verbosity=2)