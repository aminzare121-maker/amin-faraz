"""Tests for source identity, image hashes, timing and strict non-trading result."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from artin_teacher_case_provenance import audit

class CandidateEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.frames=self.root/'frames';self.frames.mkdir()
        self.index=self.root/'source';self.index.mkdir()
        self.image=self.frames/'session_15'/'frame.png';self.image.parent.mkdir()
        self.image.write_bytes(b'FAKE IMAGE FOR TEST ONLY')
        self.sha=hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.audio_sha='a'*64
        self.row={'session':15,'start_seconds':20.0,'end_seconds':22.0,
                  'machine_text_unverified':'اگر قیمت مقاومت را شکست',
                  'source_audio_sha256':self.audio_sha, 'source_segment_id':'asr-1',
                  'visual_source_nearby':[{'frame_sha256':self.sha,'time_seconds':21.0}]}
        self.case={'case_id':'X15','session':15,'speech_start_seconds':20.0,
                  'machine_quote':self.row['machine_text_unverified'],
                  'source_audio_sha256':self.audio_sha, 'source_segment_id':'asr-1',
                  'original_image_path':'session_15/frame.png',
                  'original_image_sha256':self.sha}
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):
        self.cases=self.root/'cases.json'
        self.cases.write_text(json.dumps([self.case]),encoding='utf-8')
        (self.index/'session_15_all_machine_speech_review.jsonl').write_text(json.dumps(self.row)+'\n',encoding='utf-8')
    def run_audit(self):return audit(self.cases,self.index,self.frames)
    def test_valid_evidence_keeps_teacher_unverified(self):
        o=self.run_audit()
        self.assertEqual((o['speech_exact_count'],o['original_image_match_count'],o['same_segment_visual_count']), (1,1,1))
        self.assertFalse(o['teacher_semantics_certified'])
        self.assertFalse(o['mt5_trading_allowed'])
    def test_original_png_tamper_detected(self):
        self.image.write_bytes(b'TAMPERED FILE')
        self.assertEqual(self.run_audit()['original_image_match_count'],0)
    def test_exact_speech_identity_mismatch_detected(self):
        self.row['source_segment_id']='another'
        self.save()
        self.assertEqual(self.run_audit()['speech_exact_count'],0)
    def test_proximity_mismatch_not_treated_as_teacher_error(self):
        self.row['visual_source_nearby']=[]
        self.save()
        o=self.run_audit()
        self.assertEqual((o['speech_exact_count'],o['original_image_match_count'],o['same_segment_visual_count']),(1,1,0))
        self.assertFalse(o['items'][0]['trade_authorized'])
        self.assertIn('FRAME_NOT_IN_NEARBY_SPEECH_VISUAL_REFERENCES',o['items'][0]['source_integrity_issues'])
    def test_invalid_digest_rejected(self):
        self.case['original_image_sha256']='notsha';self.save()
        self.assertEqual(self.run_audit()['original_image_match_count'],0)
    def test_duplicate_case_id_flagged(self):
        self.cases.write_text(json.dumps([self.case,self.case]),encoding='utf-8')
        o=self.run_audit()
        self.assertEqual(o['case_count'],2)
        self.assertIn('BAD_OR_DUPLICATE_CASE_ID',o['items'][1]['source_integrity_issues'])
    def test_hypothetical_stays_valid_evidence_without_historical_claim(self):
        self.case['scenario_type']='BREAKOUT';self.case['hypothetical_example_is_educationally_valid']=True
        self.save()
        o=self.run_audit()
        self.assertTrue(o['items'][0]['machine_speech_source_exact'])
        self.assertFalse(o['teacher_semantics_certified'])

if __name__=='__main__':unittest.main()