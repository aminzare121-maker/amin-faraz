"""The high resolution crop planner must preserve exact 1s source timing."""
import unittest
from artin_chat_change_highres_v8 import selected_times


def data():
    return {'schema':'artin_source_chat_temporal_index_v8',
            'source_video_sha256':'a'*64,'video_duration_seconds':97*60,
            'rows':[{'source_time_seconds':t,'priority_capture':True,
                     'reason':'CHAT_CHANGED'} for t in (0,30,5400,5700,5819)]}


class HighResPlannerTests(unittest.TestCase):
    def test_cross_eighteen_slots_maintains_unique_id(self):
        p=selected_times(data())
        self.assertEqual(len({x['frame_id'] for x in p}),5)
        self.assertEqual(p[2]['global_chunk'],19)
        self.assertEqual(p[2]['batch'],2)
        self.assertEqual(p[2]['slot'],1)
        self.assertEqual(p[-1]['global_chunk'],20)
        self.assertEqual(p[-1]['slot'],2)

    def test_not_selected_frames_do_not_get_expensive_ffmpeg_crop(self):
        m=data()
        m['rows'].insert(1,{'source_time_seconds':1,
                'priority_capture':False,'reason':'NOT_SELECTED'})
        self.assertEqual(len(selected_times(m)),5)

    def test_out_of_order_source_rejected(self):
        m=data();m['rows'][2]['source_time_seconds']=15
        with self.assertRaisesRegex(ValueError,'Unordered'):
            selected_times(m)

    def test_unknown_source_schema_rejected(self):
        m=data();m['schema']='unknown'
        with self.assertRaisesRegex(ValueError,'original 1-second'):
            selected_times(m)


if __name__=='__main__':unittest.main()
