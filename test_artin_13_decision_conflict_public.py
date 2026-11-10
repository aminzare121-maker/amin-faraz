"""Public synthetic fixtures: no private ASR, teacher audio, or source SHA values."""
import copy
import unittest
from artin_13_decision_conflict_replay import EXPECTED_ROUTES, analyze, public_projection, classify_candidate


def fixture():
    routes=sorted(EXPECTED_ROUTES)
    data={'citations':[]}
    for i in range(24):
        route=routes[i%13]
        start=i*100.+1
        text= 'ورود نکنیم' if i==0 else ('ورود کنیم' if i==13 else 'مثال ساختگی و غیروابسته به آموزش')
        if i==13:
            # Same session as i=0, but deliberately close timestamps, to trigger candidate pair in one route.
            start=5.
        row={'start':start,'end':start+1,'record_id':'synthetic_'+str(i),
             'asr_segment_id':'synthetic_id_'+str(i),'text_unverified':text,
             'original_audio_sha256':'SYNTHETIC_SHA_'+str(i)}
        data['citations'].append({'citation_index':i+1,'route_id':route,'session':1,
              'start_seconds':start-0.1,'end_seconds':start+1.1,
              'expected_machine_asr_rows':1,'overlap_asr_rows':1,'excerpts':[row]})
    return data

class ReviewTests(unittest.TestCase):
    def test_synthetic_has_no_orders(self):
        r=analyze(fixture()); self.assertEqual(r['summary']['routes'],13)
        self.assertEqual(r['summary']['mt5_orders_authorized'],0)
        self.assertEqual(r['summary']['source_excerpt_occurrences'],24)
    def test_polarity_only_candidate(self):
        r=analyze(fixture())
        self.assertGreater(r['summary']['candidate_polarity_flip_pairs'],0)
        self.assertEqual(r['summary']['teacher_decisions_certified'],0)
    def test_no_private_text_in_public(self):
        r=public_projection(analyze(fixture()))
        self.assertNotIn('text_unverified',str(r))
        self.assertNotIn('SYNTHETIC_SHA',str(r))
    def test_duplicate_excerpt_rejected(self):
        d=fixture();d['citations'][0]['excerpts'].append(copy.deepcopy(d['citations'][0]['excerpts'][0]))
        d['citations'][0]['expected_machine_asr_rows']=2
        d['citations'][0]['overlap_asr_rows']=2
        with self.assertRaises(ValueError): analyze(d)
    def test_forged_route_rejected(self):
        d=fixture();d['citations'][0]['route_id']='INVENTED'
        with self.assertRaises(ValueError): analyze(d)
    def test_invalid_interval_rejected(self):
        d=fixture();d['citations'][0]['excerpts'][0]['start']=-5
        with self.assertRaises(ValueError):analyze(d)
    def test_question_is_not_certification(self):
        self.assertEqual(classify_candidate('استاد چرا باید وارد بشیم؟'),'ENTRY_MENTION_UNVERIFIED')
        self.assertEqual(analyze(fixture())['summary']['teacher_decisions_certified'],0)
if __name__=='__main__':unittest.main()