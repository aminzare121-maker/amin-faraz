"""Synthetic regression tests for complete private source-hash split/merge."""
import json
import tempfile
import unittest
from pathlib import Path
from artin_batch_slots import batch_summary
from artin_fast_av_v4 import plan_fast
from artin_parallel_asr_merge_v5 import merge_private_shards


class PartitionMergeTests(unittest.TestCase):
    def make(self,root):
        parts=plan_fast(720,1)
        for i,p in enumerate(parts):
            p['audio_sha256']=f'{i+1:064x}'
            p['frames'][0]['sha256']=f'{i+101:064x}'
        m={'schema':'artin_fast_av_v4','video_sha256':'a'*64,
           'duration_seconds':720,'frames_per_part':1,'overlap_s':12,
           'batches':batch_summary(parts),'parts':parts}
        (root/'manifest_redacted.json').write_text(json.dumps(m))
        for i,p in enumerate(parts):
            doc={'schema':'artin_asr_shard_v5','global_chunk':i+1,
                 'source_video_sha256':'a'*64,
                 'source_audio_sha256':p['audio_sha256'],
                 'timebase':'absolute_original_video_seconds',
                 'model':'large-v3-turbo','speaker_human_verified':False,
                 'teacher_rules_verified':False,
                 'segments':[{'id':f't{i}','start':i*300+1,
                              'end':min(i*300+3,720),
                              'text':'توضیح درس'}]}
            (root/f'part_{i+1:03d}_unverified.json').write_text(json.dumps(doc))
        for i,done in enumerate(([1,3],[2])):
            status={'shard_index':i,'partition_count':2,'source_video_sha256':'a'*64,
                    'expected_global_parts':done,'completed_global_parts':done}
            (root/f'partition_{i}_status.json').write_text(json.dumps(status))
        return root

    def test_complete_three_parts(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make(Path(d))
            r=merge_private_shards(root,root/'final')
            self.assertTrue(r['audio_transcript_coverage_complete'])
            self.assertEqual(r['global_parts'],3)
            self.assertEqual(r['rules_executable'],0)
            self.assertFalse(r['full_original_audio_human_reviewed'])

    def test_missing_global_chunk_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make(Path(d))
            (root/'part_003_unverified.json').unlink()
            with self.assertRaisesRegex(ValueError,'Missing or unexpected'):
                merge_private_shards(root,root/'final')

    def test_tampered_source_hash_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make(Path(d))
            p=root/'part_002_unverified.json';x=json.loads(p.read_text())
            x['source_video_sha256']='f'*64;p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,'different video'):
                merge_private_shards(root,root/'final')

    def test_partition_wrong_owner_rejected_even_if_union_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make(Path(d))
            p0=root/'partition_0_status.json'
            p1=root/'partition_1_status.json'
            a=json.loads(p0.read_text());b=json.loads(p1.read_text())
            a['expected_global_parts']=[1,2]
            a['completed_global_parts']=[1,2]
            b['expected_global_parts']=[3]
            b['completed_global_parts']=[3]
            p0.write_text(json.dumps(a))
            p1.write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,'assignment'):
                merge_private_shards(root,root/'final')

    def test_duplicate_partition_ownership_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.make(Path(d))
            p=root/'partition_1_status.json';x=json.loads(p.read_text())
            x['expected_global_parts']=[1,2]
            x['completed_global_parts']=[1,2];p.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,'assignment|ownership'):
                merge_private_shards(root,root/'final')


if __name__=='__main__':unittest.main()
