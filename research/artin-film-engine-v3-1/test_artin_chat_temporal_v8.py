"""Synthetic temporal video samples: reliability of 1s chat change detection."""
import unittest
from artin_chat_temporal_v8 import FRAME_SIZE,score,collect_index

SHA='a'*64
def gray(v):return bytes([v])*FRAME_SIZE

class ChatTemporalTests(unittest.TestCase):
    def test_short_lived_message_detected_between_thirty_second_anchors(self):
        # A chat message appearing only at t=3 and gone by t=5 is missed
        # by 30s snapshots but observed at one-second sample resolution.
        frames=[gray(10)]*3+[gray(80)]*2+[gray(10)]*55
        x=collect_index(frames,source_sha256=SHA,duration_seconds=60)
        changes=[r['source_time_seconds'] for r in x['rows'] if r['reason']=='CHAT_CHANGED']
        self.assertIn(3,changes)
        self.assertIn(5,changes)
        self.assertEqual(x['sampled_source_frames'],60)
        self.assertFalse(x['ground_truth_all_chat_messages_found'])
        self.assertFalse(x['printed_persian_chat_recognized'])

    def test_unchanged_frames_keep_periodic_anchors(self):
        x=collect_index([gray(5)]*65,source_sha256=SHA,duration_seconds=65)
        choices=[r['source_time_seconds'] for r in x['rows'] if r['priority_capture']]
        self.assertEqual(choices,[0,30,60])
        self.assertEqual(x['changed_chat_frames'],0)

    def test_global_part_crosses_five_minutes(self):
        x=collect_index([gray(20)]*310,source_sha256=SHA,duration_seconds=310)
        self.assertEqual(x['rows'][299]['global_part'],1)
        self.assertEqual(x['rows'][300]['global_part'],2)

    def test_bad_source_hash_rejected(self):
        with self.assertRaises(ValueError):
            collect_index([gray(10)],source_sha256='abc',duration_seconds=10)

    def test_invalid_sample_luma_rejected(self):
        with self.assertRaisesRegex(ValueError,'Partial or corrupted'):
            collect_index([b'incomplete'],source_sha256=SHA,duration_seconds=1)

    def test_short_final_video_segment_is_not_error(self):
        x=collect_index([gray(10)]*13,source_sha256=SHA,duration_seconds=12.9)
        self.assertEqual(len(x['rows']),13)
        self.assertEqual(x['rows'][-1]['source_time_seconds'],12)


if __name__=='__main__':unittest.main()
