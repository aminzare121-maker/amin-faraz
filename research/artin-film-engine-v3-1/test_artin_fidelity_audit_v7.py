"""Regression tests for full-source teacher fidelity AUDIT; synthetic only."""
import copy
import unittest

from artin_batch_slots import batch_summary
from artin_fast_av_v4 import plan_fast
from artin_teacher_av_review_v5 import review_real_asr
from artin_fidelity_audit_v7 import audit_original_teacher_evidence


def fixture(duration=720):
    parts=plan_fast(duration,1)
    for i,p in enumerate(parts):
        p['audio_sha256']=f'{i+1:064x}'
        p['frames'][0]['sha256']=f'{i+101:064x}'
    manifest={'schema':'artin_fast_av_v4','video_sha256':'a'*64,
              'duration_seconds':duration,'frames_per_part':1,
              'overlap_s':12,'batches':batch_summary(parts),'parts':parts}
    rows=[]
    for i in range(len(parts)):
        t=min(duration-2,i*300+40.0)
        rows.append({'frame_id':f"source_frame_{i+1}",
             'time_seconds':t,'global_chunk':i+1,'batch':parts[i]['batch'],
             'slot':parts[i]['slot'],
             'video_frame':{'sha256':f'{200+i:064x}'},
             'board':{'sha256':f'{300+i:064x}'},
             'chat':{'sha256':f'{400+i:064x}'}})
    vis={'schema':'artin_classroom_visual_v6',
         'source_video_sha256':'a'*64,'rows':rows}
    shards=[]
    for i,p in enumerate(parts):
        u={'start':i*300+35.0,'end':min(duration,i*300+45.0),
            'text':'اگر کندل بسته شد و مقاومت شکست خرید می‌کنیم' if i==0
                   else 'الان ما آموزش بازار را می‌دهیم',
            'speaker':'UNKNOWN','speaker_verified':False}
        if u['end']<=u['start']:
            u['start']=p['core_start']+1
            u['end']=p['core_end']-.1
        shards.append({'schema':'artin_asr_shard_v5','global_chunk':i+1,
            'source_video_sha256':'a'*64,'source_audio_sha256':p['audio_sha256'],
            'timebase':'absolute_original_video_seconds','model':'synthetic',
            'speaker_human_verified':False,'teacher_rules_verified':False,
            'segments':[u]})
    return review_real_asr(manifest,shards),vis


class FullFidelityAuditTests(unittest.TestCase):
    def test_full_sentence_never_becomes_executable(self):
        r,v=fixture()
        summary,private=audit_original_teacher_evidence(r,v)
        self.assertGreaterEqual(summary['legacy_rule_candidate_count'],1)
        self.assertEqual(summary['verified_trading_rules'],0)
        self.assertIsNone(summary['teacher_rule_precision'])
        self.assertEqual(summary['status'],'NOT_RELIABLE_FOR_EXECUTABLE_RULES')
        self.assertFalse(summary['paper_orders_authorized'])
        self.assertFalse(summary['real_orders_authorized'])
        self.assertFalse(private['candidate_review_packets'][0]['teacher_quote_audio_verified'])

    def test_every_rule_has_time_and_real_audio_hash(self):
        r,v=fixture()
        summary,private=audit_original_teacher_evidence(r,v)
        p=private['candidate_review_packets'][0]
        self.assertEqual(p['video_sha256'],'a'*64)
        self.assertEqual(p['global_part'],1)
        self.assertEqual(p['audio_sha256'],r['speech_lines'][0]['source_audio_sha256'])
        self.assertGreater(len(p['nearby_unverified_asr']),0)
        self.assertGreater(len(p['source_video_frames']),0)
        self.assertEqual(p['status'],'REVIEW_REQUIRED')

    def test_absent_visuals_block_quality_completeness(self):
        r,v=fixture()
        summary,private=audit_original_teacher_evidence(r)
        self.assertEqual(summary['visual_frames_source_checked'],0)
        self.assertIn('NO_MATCHING_SOURCE_VISUAL_INDEX',summary['critical_quality_gaps'])

    def test_wrong_video_visuals_fail(self):
        r,v=fixture()
        v['source_video_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'another video'):
            audit_original_teacher_evidence(r,v)

    def test_fake_rule_quote_reference_fails(self):
        r,v=fixture()
        r['rule_candidates'][0]['source_utterance_id']='made_up'
        with self.assertRaisesRegex(ValueError,'Invented rule'):
            audit_original_teacher_evidence(r,v)

    def test_duplicate_rule_id_fails(self):
        r,v=fixture()
        r['rule_candidates'].append(copy.deepcopy(r['rule_candidates'][0]))
        with self.assertRaisesRegex(ValueError,'Repeated rule'):
            audit_original_teacher_evidence(r,v)

    def test_fake_answer_source_fails(self):
        r,v=fixture()
        r['possible_questions_and_following_utterances']=[
         {'question_line_id':'u_imagined','possible_following_utterances':[]}]
        with self.assertRaisesRegex(ValueError,'Question is not anchored'):
            audit_original_teacher_evidence(r,v)

    def test_missing_asr_parts_fail(self):
        r,v=fixture()
        r['parts_missing_asr']=[2]
        with self.assertRaisesRegex(ValueError,'Incomplete source'):
            audit_original_teacher_evidence(r,v)

    def test_changed_audio_hash_fails(self):
        r,v=fixture()
        r['speech_lines'][0]['source_audio_sha256']='invalid_hash'
        with self.assertRaisesRegex(ValueError,'audio SHA256'):
            audit_original_teacher_evidence(r,v)

    def test_missing_frame_hash_fails(self):
        r,v=fixture()
        v['rows'][0]['chat']['sha256']=None
        with self.assertRaisesRegex(ValueError,'Frame evidence'):
            audit_original_teacher_evidence(r,v)

    def test_cross_batch_processing_keeps_single_source(self):
        r,v=fixture(97*60)
        summary,private=audit_original_teacher_evidence(r,v)
        self.assertEqual(summary['all_global_audio_parts'],20)
        self.assertEqual(summary['speech_lines_source_checked'],20)
        self.assertFalse(summary['real_orders_authorized'])

    def test_summary_does_not_leak_transcript_text(self):
        r,v=fixture()
        summary,private=audit_original_teacher_evidence(r,v)
        self.assertNotIn('کندل بسته',str(summary))
        self.assertIn('کندل بسته',str(private))

    def test_unsupported_context_seconds_fails(self):
        r,v=fixture()
        with self.assertRaisesRegex(ValueError,'Context'):
            audit_original_teacher_evidence(r,v,context_seconds=2)


if __name__=="__main__":
    unittest.main()
