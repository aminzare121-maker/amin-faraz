import json,tempfile,unittest
from pathlib import Path
from video001_v13_text_archive_ready import package

class ArchiveTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
  self.sha='f'*64
  self.s=self.root/'source.json';self.p=self.root/'proof.json'
  self.s.write_text(json.dumps({'source_video_sha256':self.sha,'source_integrity_verified':True,
     'original_chat_images_selected':2,'original_board_frames':1,
     'original_ocr_workers':1,'source_global_audio_chunks':1}))
  self.p.write_text(json.dumps({'original_source_video_sha256':self.sha,'source_evidence_loss':0,
   'independent_hash_and_time_evidence_complete':True,'original_five_minute_audio_parts':1}))
  self.asr=self.root/'asr';self.ocr=self.root/'ocr';self.board=self.root/'board';self.export=self.root/'export'
  for p in [self.asr,self.ocr,self.board,self.export]:p.mkdir()
  (self.asr/'raw.json').write_text('{"segments":[{"text":"سلام"}]}')
  (self.ocr/'full_chat_ocr_candidates_PRIVATE.json').write_text(json.dumps({'complete':True,'results':[{'frame_id':'a'},{'frame_id':'b'}]}))
  (self.board/'board_ocr_candidates_PRIVATE.json').write_text(json.dumps({'source_video_sha256':self.sha,'frames_processed':1,'missing_frames':0,'results':[{}]}))
  (self.export/'notes.json').write_text('{}')
 def runit(self):return package(self.root/'result.zip','artin-course-001','video-q-0004-artin-clip-02',self.s,self.p,self.asr,self.ocr,self.board,self.export)
 def test_safely_archives_all_machine_text(self):
  x=self.runit();self.assertTrue(x['archive_text_only']);self.assertLess(x['archive_pack_and_local_verification_seconds'],60)
  with self.assertRaises(FileExistsError):self.runit()
 def test_refuse_missing_chat(self):
  (self.ocr/'full_chat_ocr_candidates_PRIVATE.json').unlink()
  with self.assertRaises(ValueError):self.runit()
 def test_reject_missing_board(self):
  (self.board/'board_ocr_candidates_PRIVATE.json').unlink()
  with self.assertRaises(FileNotFoundError):self.runit()
if __name__=='__main__':unittest.main()