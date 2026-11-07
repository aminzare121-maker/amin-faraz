"""Synthetic tests for variable-length videos and 18-slot collision-free batches."""
import tempfile
import unittest
from pathlib import Path

from artin_batch_slots import batch_slot, artifact_path, batch_frames_dir, batch_summary
from artin_semantic_context import adjacent_context
from artin_film_pipeline import (
    chunk_plan, canonical_chunk_order, validate_manifest_order,
    atomic_json, chapters_for_ffmpeg
)


class BatchSlotsTests(unittest.TestCase):
    def test_twelve_minutes_has_three_slots_and_short_tail(self):
        p=chunk_plan(720)
        self.assertEqual(len(p),3)
        self.assertEqual([(x['core_start'],x['core_end']) for x in p],
                         [(0,300),(300,600),(600,720)])
        self.assertEqual([(x['batch'],x['slot']) for x in p],[(1,1),(1,2),(1,3)])
        self.assertEqual(p[-1]['cut_start'],588)
        self.assertEqual(p[-1]['cut_end'],720)
        self.assertEqual(p[-1]['clip'],'clips/part_03.mp4')

    def test_ninety_minute_exactly_one_full_batch(self):
        p=chunk_plan(5400)
        self.assertEqual(len(p),18)
        self.assertEqual(len(batch_summary(p)),1)
        self.assertEqual(batch_summary(p)[0]['slots_in_order'],list(range(1,19)))
        self.assertEqual(p[-1]['unique_id'],'b001_s18_g000018')

    def test_ninety_seven_minute_video_has_two_batches_with_short_tail(self):
        p=chunk_plan(97*60)
        self.assertEqual(len(p),20)
        self.assertEqual([(c['chunk'],c['batch'],c['slot']) for c in p[17:]],
                         [(18,1,18),(19,2,1),(20,2,2)])
        self.assertEqual(p[18]['unique_id'],'b002_s01_g000019')
        self.assertEqual(p[18]['clip'],'clips/batch_002/part_01.mp4')
        self.assertEqual(p[18]['transcript'],'transcripts/batch_002/part_01.json')
        self.assertEqual(p[18]['analysis'],'analyses/batch_002/part_01.json')
        self.assertEqual(p[19]['core_start'],5700)
        self.assertEqual(p[19]['core_end'],5820)
        self.assertEqual(p[19]['clip'],'clips/batch_002/part_02.mp4')
        self.assertEqual(batch_summary(p)[1]['slots_in_order'],[1,2])
        self.assertEqual(batch_summary(p)[1]['global_indices'],[19,20])
        self.assertEqual(len({c['clip'] for c in p}),20)
        self.assertEqual(len({c['unique_id'] for c in p}),20)

    def test_long_video_third_batch_starts_at_global_thirty_seven(self):
        p=chunk_plan(181*60)
        self.assertEqual(len(p),37)
        self.assertEqual(p[36]['chunk'],37)
        self.assertEqual(p[36]['batch'],3)
        self.assertEqual(p[36]['slot'],1)
        self.assertEqual(p[36]['core_end'],181*60)
        self.assertEqual(p[36]['unique_id'],'b003_s01_g000037')
        self.assertEqual(p[36]['clip'],'clips/batch_003/part_01.mp4')

    def test_out_of_order_parallel_completion_keeps_global_order(self):
        expected=chunk_plan(97*60)
        complete=canonical_chunk_order(expected[::-1],expected)
        self.assertEqual([c['chunk'] for c in complete],list(range(1,21)))
        self.assertEqual([c['slot'] for c in complete[18:]],[1,2])
        self.assertEqual([c['batch'] for c in complete[18:]],[2,2])

    def test_reused_slot_from_previous_batch_cannot_pass(self):
        expected=chunk_plan(97*60)
        result=[dict(c) for c in expected]
        result[18]['batch']=1
        with self.assertRaisesRegex(ValueError,'batch/slot identity'):
            canonical_chunk_order(result,expected)

    def test_global_id_reassignment_cannot_pass(self):
        expected=chunk_plan(97*60)
        result=[dict(c) for c in expected]
        result[18]['unique_id']=result[0]['unique_id']
        with self.assertRaisesRegex(ValueError,'batch/slot identity'):
            canonical_chunk_order(result,expected)

    def test_duplicate_slot_files_are_rejected(self):
        p=chunk_plan(97*60)
        changed=[dict(c) for c in p]
        changed[18]['clip']=changed[0]['clip']
        with self.assertRaisesRegex(ValueError,'wrong numbered file'):
            canonical_chunk_order(changed,p)

    def test_missing_second_batch_part_is_rejected(self):
        p=chunk_plan(97*60)
        with self.assertRaisesRegex(ValueError,'Missing five-minute chunk'):
            canonical_chunk_order(p[:-1],p)

    def test_neighbor_context_crosses_batch_boundary(self):
        c={18:{'anchors':[{'id':'last_batch_1'}]},19:{'anchors':[{'id':'first_batch_2'}]}}
        self.assertEqual(adjacent_context(18,c)['next']['anchors'][0]['id'],'first_batch_2')
        self.assertEqual(adjacent_context(19,c)['previous']['anchors'][0]['id'],'last_batch_1')

    def test_vision_and_capsule_paths_are_collision_free(self):
        p=chunk_plan(97*60)
        self.assertEqual(artifact_path('visual_scans',p[0]),'visual_scans/part_01.json')
        self.assertEqual(artifact_path('visual_scans',p[18]),'visual_scans/batch_002/part_01.json')
        self.assertEqual(batch_frames_dir(p[18]),'vision_frames/batch_002/part_01')
        self.assertEqual(batch_slot(19),(2,1))

    def test_manifest_rejects_swapped_batch_two_mapping(self):
        p=chunk_plan(97*60)
        m={'source_duration':97*60,'strict_chunk_order':True,'chunk_seconds':300,
           'overlap_seconds':12,'chunks':p}
        self.assertEqual(len(validate_manifest_order(m)),20)
        changed=[dict(c) for c in p]
        changed[18]['slot']=3
        m['chunks']=changed
        with self.assertRaisesRegex(ValueError,'batch/slot identity'):
            validate_manifest_order(m)

    def test_manifest_tampered_batch_index_is_rejected(self):
        p=chunk_plan(97*60)
        groups=batch_summary(p)
        m={'source_duration':97*60,'strict_chunk_order':True,'chunk_seconds':300,
           'overlap_seconds':12,'batch_schema':'EIGHTEEN_SLOTS_WITH_GLOBAL_ID_V1',
           'batch_count':2,'batches':groups,'chunks':p}
        self.assertEqual(len(validate_manifest_order(m)),20)
        m['batches'][1]['global_indices']=[1,2]
        with self.assertRaisesRegex(ValueError,'batch index'):
            validate_manifest_order(m)

    def test_chapters_include_batch_and_global_numbers(self):
        p=chunk_plan(97*60)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            atomic_json(root/'manifest.json',{'schema':'artin_video_manifest_v1',
                'source_duration':97*60,'chunk_seconds':300,'overlap_seconds':12,
                'strict_chunk_order':True,'chunks':p})
            output=chapters_for_ffmpeg(root).read_text(encoding='utf8')
            self.assertEqual(output.count('[CHAPTER]'),20)
            self.assertIn('Batch 002 Slot 01 Global 0019',output)
            self.assertIn('END=5820000',output)


if __name__=='__main__': unittest.main()
