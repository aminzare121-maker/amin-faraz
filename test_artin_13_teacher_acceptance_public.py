"""Self-contained synthetic tests. Not original teacher evidence."""
import copy
import unittest
from artin_13_teacher_acceptance_matrix import evaluate, EXPECTED_ROUTES

def synthetic():
    routes=sorted(EXPECTED_ROUTES)
    docs=[{'route_id':r,'source_sessions':[19], 'citation_intervals':[]} for r in routes]
    citations=[]; visual=[]
    for n in range(24):
        i=n+1;r=routes[n%13];t=float(i*100)
        docs[n%13]['citation_intervals'].append({'index':i})
        e={'asr_segment_id':f'segment_{i}','original_audio_sha256':f'synthetic_sha_{i}'}
        citations.append({'citation_index':i,'route_id':r,'session':19,'start_seconds':t,
          'end_seconds':t+10,'overlap_asr_rows':1,'excerpts':[e]})
        visual.append({'citation_index':i,'route_id':r,'session':19,'source_start_seconds':t,
          'source_end_seconds':t+10,'reviewed_66_images_in_window':[]})
    return {'routes':docs},{'citations':citations},{'citations':visual}

class TestPublicSynthetic(unittest.TestCase):
    def test_no_certification_from_metadata(self):
        result=evaluate(*synthetic())
        self.assertEqual((result['source_routes'],result['source_citations']), (13,24))
        self.assertEqual(result['certified_routes'],0)
        self.assertTrue(all(r['release_status'].startswith('BLOCKED') for r in result['routes']))
    def test_duplicate_route_rejected(self):
        data=synthetic();data[0]['routes'][0]['route_id']=data[0]['routes'][1]['route_id']
        with self.assertRaises(ValueError):evaluate(*data)
    def test_omitted_asr_rejected(self):
        data=synthetic();data[1]['citations'][0]['excerpts']=[]
        with self.assertRaises(ValueError):evaluate(*data)
    def test_changed_audio_source_rejected(self):
        data=synthetic();data[1]['citations'][0]['excerpts'][0]['original_audio_sha256']=''
        with self.assertRaises(ValueError):evaluate(*data)
    def test_crossmodal_timestamp_rejected(self):
        data=synthetic();data[2]['citations'][0]['source_end_seconds']+=1
        with self.assertRaises(ValueError):evaluate(*data)
    def test_original_input_not_mutated(self):
        data=synthetic();original=copy.deepcopy(data);evaluate(*data)
        self.assertEqual(data,original)
if __name__=='__main__':unittest.main()