import copy
import hashlib
import io
import json
import unittest
import wave
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from artin_conflict_media_provenance import evaluate, verify_audio_zip


def sample():
    e={'session':21,'source_segment_id':'a','record_id':'rec1','start_seconds':1900.,'end_seconds':1902.,
       'source_audio_sha256':'abcd','text_unverified':'ورود نکن'}
    f={**e,'source_segment_id':'b','record_id':'rec2','start_seconds':1905.,'end_seconds':1907.,
       'text_unverified':'ورود کن'}
    pair={'session':21,'first_segment_id':'a','second_segment_id':'b','time_gap_seconds':3,
          'status':'NEEDS_ORIGINAL_AV_SPEAKER_AND_CHART_REPLAY_NO_TRADE'}
    r={'routes':[{'route_id':'R','events':[e,f],'candidate_polarity_flips':[pair]}]}
    c={'citations':[{'route_id':'R','session':21,'reviewed_66_images_in_window':[]}]}
    return r,c

class Tests(unittest.TestCase):
    def test_unverified_source_remains_blocked(self):
        r,c=sample(); v=evaluate(r,c,[{'sha256':'different','start':1890.,'end':2000.,'member':'m'}])
        self.assertEqual((v['source_audio_sha_matched_pairs'],v['orders_authorized']),(0,0))
    def test_matching_sha_is_not_semantic_certification(self):
        r,c=sample(); v=evaluate(r,c,[{'sha256':'abcd','start':1890.,'end':2000.,'member':'m'}])
        self.assertEqual(v['source_audio_sha_matched_pairs'],1)
        self.assertFalse(v['teacher_semantics_certified'])
        self.assertFalse(v['cases'][0]['teacher_decision_verified'])
    def test_matching_time_only_not_enough(self):
        r,c=sample();v=evaluate(r,c,[{'sha256':'bad','start':1890.,'end':2000.,'member':'m'}])
        self.assertFalse(v['cases'][0]['verified_original_wav_sha_match'])
    def test_tampered_source_id_fails(self):
        r,c=sample();r['routes'][0]['candidate_polarity_flips'][0]['second_segment_id']='fake'
        with self.assertRaises(ValueError):evaluate(r,c,[])
    def test_contradicting_audio_sha_pair_fails(self):
        r,c=sample();r['routes'][0]['events'][1]['source_audio_sha256']='other'
        with self.assertRaises(ValueError):evaluate(r,c,[])
    def test_route_duplication_is_not_independent(self):
        r,c=sample();r['routes'].append({**copy.deepcopy(r['routes'][0]),'route_id':'R2'})
        v=evaluate(r,c,[])
        self.assertEqual((v['occurrence_pairs'],v['unique_session_segment_pairs'],v['repeated_pairs_across_routes']),(2,1,1))
    def test_original_wav_sha_and_manifest(self):
        with TemporaryDirectory() as t:
            p=Path(t)/'src.zip';b=io.BytesIO()
            with wave.open(b,'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(b'\0\0'*8000)
            wav=b.getvalue();sha=hashlib.sha256(wav).hexdigest()
            data={'video_sha256':'dummy','parts':[{'audio':'audio/batch_001/part_07.wav',
                'cut_start':10,'cut_end':11,'audio_sha256':sha}]}
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('audio/batch_001/part_07.wav',wav)
                z.writestr('fast_av_manifest.json',json.dumps(data))
            x=verify_audio_zip(p,'audio/batch_001/part_07.wav')
            self.assertEqual(x['sha256'],sha)
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('audio/batch_001/part_07.wav',wav)
                data['parts'][0]['audio_sha256']='0'*64
                z.writestr('fast_av_manifest.json',json.dumps(data))
            with self.assertRaises(ValueError):verify_audio_zip(p,'audio/batch_001/part_07.wav')

if __name__=='__main__':unittest.main()