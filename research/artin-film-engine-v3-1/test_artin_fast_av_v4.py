import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from artin_fast_av_v4 import plan_fast,fast_prepare,validate_fast,SourceEvidenceError


class FastAVTests(unittest.TestCase):
    def test_12minute_last_two_minutes(self):
        p=plan_fast(720)
        self.assertEqual(len(p),3)
        self.assertEqual(p[-1]['core_end']-p[-1]['core_start'],120)
        self.assertEqual(p[-1]['batch'],1)

    def test_80minutes_20seconds_final_short_part(self):
        p=plan_fast(4820.545)
        self.assertEqual(len(p),17)
        self.assertAlmostEqual(p[-1]['core_end']-p[-1]['core_start'],20.545)

    def test_97minutes_unique_batched_audio_and_frame_paths(self):
        p=plan_fast(5820)
        self.assertEqual(len(p),20)
        self.assertEqual(p[18]['unique_id'],'b002_s01_g000019')
        self.assertNotEqual(p[0]['audio'],p[18]['audio'])
        self.assertNotEqual(p[0]['frames'][0]['path'],p[18]['frames'][0]['path'])
        self.assertEqual(len(set(x['audio'] for x in p)),20)

    def test_source_video_no_recompression_and_real_wav_jpeg_hashes(self):
        if not shutil.which('ffmpeg'):self.skipTest('no ffmpeg')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            vid=p/'clip.mp4'
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
             '-f','lavfi','-i','testsrc2=size=160x90:rate=1',
             '-f','lavfi','-i','sine=frequency=450:sample_rate=16000',
             '-t','12','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(vid)],
              check=True)
            result=fast_prepare(vid,p/'out',workers=2,frames_per_part=2)
            self.assertEqual(result['parts_ready'],1)
            self.assertTrue(validate_fast(p/'out',result))
            self.assertTrue((p/'out'/result['parts'][0]['audio']).is_file())
            self.assertEqual(len(result['parts'][0]['frames']),2)
            self.assertFalse(result['audio_transcribed'])
            self.assertEqual(result['teacher_rules_verified'],0)
            self.assertEqual(len(list((p/'out').rglob('*.mp4'))),0)
            result['parts'][0]['frames'][0]['sha256']='incorrect'
            with self.assertRaisesRegex(SourceEvidenceError,'hash mismatch'):
                validate_fast(p/'out',result)

if __name__=='__main__':unittest.main()