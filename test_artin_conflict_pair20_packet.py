import hashlib, io, json, tempfile, unittest, wave, zipfile
from pathlib import Path
from artin_conflict_pair20_packet import render, SOURCE_SHA, EVENT_IDS, EXCERPT_START, EXCERPT_END

ROOT=Path('/mnt/data')
class TestOriginalPair20(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=ROOT/'ARTIN_VIDEO20_3371_3383_SOURCE_AUDIO_REVIEW_20261110.zip'
  with zipfile.ZipFile(cls.path) as z:
   cls.names=z.namelist();cls.m=json.loads(z.read('manifest.json'));cls.wav=z.read('source_video20_part12_excerpt.wav');cls.html=z.read('index.html').decode('utf-8')
 def test_original_identity(self):
  self.assertEqual(self.m['source_audio_sha256'],SOURCE_SHA)
  self.assertEqual(self.m['excerpt_sha256'],hashlib.sha256(self.wav).hexdigest())
 def test_actual_pcm_31_seconds(self):
  with wave.open(io.BytesIO(self.wav)) as w:
   self.assertEqual(w.getframerate(),16000)
   self.assertEqual(w.getnframes(),31*16000)
   self.assertEqual(len(w.readframes(w.getnframes())),31*16000*2)
 def test_exact_pair_members(self):
  self.assertEqual(set(e['source_segment_id'] for e in self.m['events']),set(EVENT_IDS))
 def test_buttons_match_offsets(self):
  for e in self.m['events']:
   self.assertIn('data-start="%.3f"'%(e['start_seconds']-EXCERPT_START),self.html)
   self.assertIn('data-end="%.3f"'%(e['end_seconds']-EXCERPT_START),self.html)
 def test_no_frame_is_inside_either_statement(self):
  for f in self.m['reference_frames']:
   self.assertEqual(f['position'],'OUTSIDE_BOTH_ASR')
   self.assertFalse(any(e['start_seconds']<=f['second']<=e['end_seconds'] for e in self.m['events']))
 def test_original_frames_sha(self):
  with zipfile.ZipFile(self.path) as z:
   for f in self.m['reference_frames']:
    self.assertEqual(hashlib.sha256(z.read(f['file'])).hexdigest(),f['sha256'])
 def test_invalid_archive_audio_source_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'bad.zip'
   with zipfile.ZipFile(ROOT/'files/AUDIO_11.zip') as source,zipfile.ZipFile(p,'w') as dest:
    for name in source.namelist():
     raw=source.read(name)
     if name.endswith('.wav'):raw=raw[:-2]+b'ZZ'
     dest.writestr(name,raw)
   with self.assertRaisesRegex(ValueError,'SHA'):
    render(p,ROOT/'files/BOARD_IMAGES.zip',ROOT/'files/ARTIN_13_DECISION_CONFLICT_REVIEW_PRIVATE_20261110.json',Path(tmp)/'out.zip')
 def test_no_semantic_certification_or_orders(self):
  self.assertFalse(self.m['original_words_verified'])
  self.assertFalse(self.m['teacher_chart_decision_verified'])
  self.assertFalse(self.m['semantic_conflict_resolved'])
  self.assertEqual(self.m['orders_authorized'],0)
if __name__=='__main__':unittest.main()