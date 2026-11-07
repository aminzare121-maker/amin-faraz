"""Video evidence tests: chronology, full frame, typed chat crop, tamper rejection."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from artin_fast_av_v4 import fast_prepare,plan_fast
from artin_visual_timeline_v6 import frame_times,extract_visual_timeline,validate_visual_index


class VisualTimelineUnitTests(unittest.TestCase):
    def test_twelve_minute_short_tail_has_all_parts(self):
        p=plan_fast(720,0)
        times=frame_times(p,20)
        self.assertEqual([len([r for r in times if r['global_chunk']==n]) for n in (1,2,3)],
                         [15,15,6])
        self.assertLess(times[-1]['time_seconds'],720)

    def test_seventeen_parts_and_twenty_second_tail(self):
        p=plan_fast(4820.545,0)
        rows=frame_times(p,20)
        self.assertEqual(len(p),17)
        self.assertEqual(len([r for r in rows if r['global_chunk']==17]),2)
        self.assertEqual(rows[-1]['global_chunk'],17)
        self.assertLess(rows[-1]['time_seconds'],4820.545)

    def test_cross_batch_global_id_never_reused(self):
        p=plan_fast(97*60,0)
        rows=frame_times(p,30)
        self.assertEqual(len({r['frame_id'] for r in rows}),len(rows))
        self.assertTrue(any(r['global_chunk']==19 and r['batch']==2 and r['slot']==1 for r in rows))
        self.assertTrue(any(r['global_chunk']==1 and r['batch']==1 and r['slot']==1 for r in rows))

    def test_invalid_spacing(self):
        with self.assertRaises(ValueError): frame_times(plan_fast(60,0),4)
        with self.assertRaises(ValueError): frame_times(plan_fast(60,0),121)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),"FFmpeg unavailable")
class VisualEvidenceRealMp4Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.video=self.root/'original.mp4'
        proc=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',
                '-f','lavfi','-i','testsrc=size=640x360:rate=2',
                '-f','lavfi','-i','sine=frequency=300:sample_rate=16000',
                '-t','12','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',
                '-c:a','aac',str(self.video)],capture_output=True,text=True,timeout=50)
        if proc.returncode:raise RuntimeError(proc.stderr[-1000:])
        self.manifest=fast_prepare(self.video,self.root/'preprocessed',workers=2,frames_per_part=1)
        self.out=self.root/'visual'

    def test_actual_mp4_contains_original_and_two_derived_viewports(self):
        index=extract_visual_timeline(self.video,self.out,self.manifest,
                            sample_seconds=5,workers=2)
        self.assertEqual(index['schema'],'artin_classroom_visual_v6')
        self.assertGreaterEqual(index['frame_count'],2)
        self.assertEqual(index['frame_count'],len(index['rows']))
        self.assertTrue(validate_visual_index(self.out,self.manifest,index))
        for row in index['rows']:
            for key in ('video_frame','board','chat'):
                self.assertTrue((self.out/row[key]['path']).exists())
                self.assertEqual(len(row[key]['sha256']),64)
            self.assertFalse(row['typed_student_question_verified'])
            self.assertFalse(row['any_rule_executable'])
        self.assertFalse(index['vision_model_ran'])

    def test_corrupt_chat_crop_rejected(self):
        index=extract_visual_timeline(self.video,self.out,self.manifest,
                            sample_seconds=8,workers=2)
        first=self.out/index['rows'][0]['chat']['path']
        first.write_bytes(b'not-actual-image')
        with self.assertRaisesRegex(ValueError,'corrupted'):
            validate_visual_index(self.out,self.manifest,index)

    def test_frame_sequence_swapped_is_rejected(self):
        index=extract_visual_timeline(self.video,self.out,self.manifest,
                            sample_seconds=8,workers=2)
        index['rows']=index['rows'][::-1]
        with self.assertRaisesRegex(ValueError,'time/identity'):
            validate_visual_index(self.out,self.manifest,index)

    def test_source_video_change_aborts_before_sampling(self):
        corrupt=self.root/'different.mp4'
        corrupt.write_bytes(self.video.read_bytes()+b'different source')
        with self.assertRaisesRegex(ValueError,'content differs'):
            extract_visual_timeline(corrupt,self.out,self.manifest,sample_seconds=10,workers=1)

    def test_regions_must_remain_within_original_frame(self):
        with self.assertRaisesRegex(ValueError,'screen region'):
            extract_visual_timeline(self.video,self.out,self.manifest,chat_bounds=(.9,0,1.1,1))


if __name__=='__main__':unittest.main()
