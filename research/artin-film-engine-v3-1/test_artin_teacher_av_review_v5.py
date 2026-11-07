"""V5 evidence review: all tests use synthetic text; no teacher rule is auto-approved."""
import copy
import unittest
from artin_batch_slots import batch_summary
from artin_fast_av_v4 import plan_fast
from artin_teacher_av_review_v5 import review_real_asr

SHA='a'*64


def fixture():
    parts=plan_fast(720,1)
    for i,p in enumerate(parts):
        p['audio_sha256']=f'{i+1:064x}'
        p['frames'][0]['sha256']=f'{i+501:064x}'
    m={'schema':'artin_fast_av_v4','video_sha256':SHA,
       'duration_seconds':720,'frames_per_part':1,'overlap_s':12,
       'batches':batch_summary(parts),'parts':parts}
    def shard(part,segments):
        return {'schema':'artin_asr_shard_v5','global_chunk':part,
                'source_video_sha256':SHA,
                'source_audio_sha256':parts[part-1]['audio_sha256'],
                'timebase':'absolute_original_video_seconds',
                'model':'large-v3-turbo','speaker_human_verified':False,
                'teacher_rules_verified':False,'segments':segments}
    def seg(t,e,s):
        return {'start':t,'end':e,'text':s,'speaker':'UNKNOWN',
                'speaker_verified':False}
    return m,shard,seg


class RealAVReviewTests(unittest.TestCase):
    def test_two_neighbors_link_question_to_possible_reply_only(self):
        m,sh,seg=fixture()
        a=sh(1,[seg(294,298,'اگر کندل برگشت کند آیا بخریم؟')])
        b=sh(2,[seg(301,305,'این حالت رو بررسی می‌کنیم')])
        r=review_real_asr(m,[b,a])
        self.assertEqual(len(r['possible_questions_and_following_utterances']),1)
        q=r['possible_questions_and_following_utterances'][0]
        self.assertEqual(len(q['possible_following_utterances']),1)
        self.assertFalse(q['teacher_answer_verified'])
        self.assertFalse(r['real_orders_allowed'])
        self.assertEqual(r['parts_with_asr'],2)
        self.assertEqual(r['parts_missing_asr'],[3])

    def test_short_final_chunk_source_offset(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(3,[seg(701,707,'معامله اینجا نیست')])])
        self.assertEqual(r['parts_with_asr'],1)
        self.assertEqual(r['speech_lines'][0]['part_global'],3)
        self.assertFalse(r['complete_original_video_review'])

    def test_boundary_conflicting_buy_sell_preserved_for_review(self):
        m,sh,seg=fixture()
        a=sh(1,[seg(300.1,302.1,'خرید')])
        b=sh(2,[seg(300.1,302.1,'فروش')])
        r=review_real_asr(m,[a,b])
        self.assertEqual(len(r['speech_lines']),1)
        self.assertEqual(r['speech_lines'][0]['text'],'فروش')
        self.assertEqual(r['cross_boundary_conflicts'],1)
        self.assertEqual(r['cross_boundary_asr_review'][0]['text_candidate'],'خرید')
        self.assertEqual(r['cross_boundary_asr_review'][0]['review_status'],
                         'CONFLICTING_ASR_TEXT_REQUIRES_AUDIO_REVIEW')
        self.assertEqual(r['rules_executable'],0)

    def test_boundary_agreement_is_not_proof_of_teacher(self):
        m,sh,seg=fixture()
        a=sh(1,[seg(300.1,302.1,'خرید')])
        b=sh(2,[seg(300.1,302.1,'خرید')])
        r=review_real_asr(m,[a,b])
        self.assertEqual(r['cross_boundary_conflicts'],0)
        self.assertEqual(r['cross_boundary_asr_review'][0]['review_status'],
                         'AGREEMENT_ONLY_NOT_TEACHER_VERIFICATION')
        self.assertFalse(r['cross_boundary_asr_review'][0]['teacher_rule_verified'])

    def test_partial_transcript_retains_overlapping_neighbor_words(self):
        m,sh,seg=fixture()
        a=sh(1,[seg(300.1,302.1,'خرید')])
        r=review_real_asr(m,[a])
        self.assertEqual(len(r['speech_lines']),0)
        self.assertEqual(r['cross_boundary_conflicts'],1)
        self.assertEqual(r['cross_boundary_asr_review'][0]['review_status'],
                         'OWNER_PART_ASR_MISSING')

    def test_overlap_text_uses_time_owner(self):
        m,sh,seg=fixture()
        a=sh(1,[seg(300.1,302.1,'معامله')])
        b=sh(2,[seg(300.1,302.1,'معامله')])
        r=review_real_asr(m,[a,b])
        self.assertEqual(len(r['speech_lines']),1)
        self.assertEqual(r['speech_lines'][0]['part_global'],2)

    def test_detects_possible_late_correction_without_replacing_old_rule(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(5,8,'خرید اینجا')]),
                           sh(3,[seg(700,704,'اشتباه گفتم منظورم فروش بود')])])
        self.assertTrue(r['possible_later_corrections'])
        self.assertIsNone(r['possible_later_corrections'][0]['superseded_rule_id'])
        self.assertEqual(r['rules_executable'],0)

    def test_technical_problem_does_not_enter_active_rules(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(10,15,'اینترنت قطع شد')])])
        self.assertEqual(len(r['classroom_noise_or_mixed_review']),1)
        self.assertEqual(len(r['rule_candidates']),0)

    def test_frame_note_requires_actual_image_sha(self):
        m,sh,seg=fixture()
        u=sh(1,[seg(10,13,'کندل')])
        frame=m['parts'][0]['frames'][0]
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):
            review_real_asr(m,[u],[{'path':frame['path'],
                                    'frame_sha256':'f'*64,'description':'نمودار'}])
        r=review_real_asr(m,[u],[{'path':frame['path'],
                                   'frame_sha256':frame['sha256'],'description':'نمودار'}])
        self.assertFalse(r['unverified_vision_candidates'][0]['chart_rule_verified'])

    def test_wrong_video_sha_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(1,3,'خرید')]);t['source_video_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'different video'):
            review_real_asr(m,[t])

    def test_wrong_audio_hash_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(1,3,'خرید')]);t['source_audio_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'different or unchecked audio'):
            review_real_asr(m,[t])

    def test_wrong_timebase_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(1,3,'خرید')]);t['timebase']='relative'
        with self.assertRaisesRegex(ValueError,'timebase'):
            review_real_asr(m,[t])

    def test_time_outside_clip_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(450,453,'خرید')])
        with self.assertRaisesRegex(ValueError,'outside original'):
            review_real_asr(m,[t])

    def test_claim_of_teacher_verified_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(1,3,'خرید')]);t['teacher_rules_verified']=True
        with self.assertRaisesRegex(ValueError,'cannot verify teacher'):
            review_real_asr(m,[t])

    def test_claim_of_speaker_verified_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(1,3,'خرید')]);t['segments'][0]['speaker_verified']=True
        with self.assertRaisesRegex(ValueError,'cannot claim'):
            review_real_asr(m,[t])

    def test_duplicate_source_part_rejected(self):
        m,sh,seg=fixture();t=sh(1,[seg(1,3,'خرید')])
        with self.assertRaisesRegex(ValueError,'duplicate or unknown'):
            review_real_asr(m,[t,t])

    def test_invalid_frame_hash_rejected(self):
        m,sh,seg=fixture();m['parts'][0]['frames'][0]['sha256']=None
        with self.assertRaisesRegex(ValueError,'Frame missing'):
            review_real_asr(m,[sh(1,[seg(1,3,'خرید')])])

    def test_long_asr_hallucination_is_not_candidate_rule(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(25,88,'خرید خرید خرید خرید خرید خرید')])])
        self.assertTrue(r['suspect_asr_lines'])
        self.assertEqual(r['rule_candidates'],[])

    def test_actual_class_screen_record_is_offtopic(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(16,20,'اسکرین رکورد رو بزنید')])])
        self.assertEqual(len(r['classroom_noise_or_mixed_review']),1)
        self.assertEqual(r['rule_candidates'],[])

    def test_generic_forex_topic_not_considered_trading_rule(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(115,124,'ما نیاز داریم بشناسیم بازار فارکس چیه')])])
        self.assertEqual(len(r['rule_candidates']),0)
        self.assertEqual(len(r['teaching_topics_not_rules']),1)

    def test_declarative_yani_not_a_real_question(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(1,5,'یعنی به معنای واقعی کار کنیم')])])
        self.assertEqual(len(r['possible_questions_and_following_utterances']),0)

    def test_word_ki_inside_yeki_not_question(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(1,5,'یکی از کارها را ادامه میدهیم')])])
        self.assertEqual(len(r['possible_questions_and_following_utterances']),0)

    def test_no_rules_even_with_complete_synthetic_transcripts(self):
        m,sh,seg=fixture()
        r=review_real_asr(m,[sh(1,[seg(1,3,'اگر کندل بسته شد خرید کنیم')]),
            sh(2,[seg(305,307,'وقتی مقاومت شکست فروش انجام بده')]),sh(3,[seg(705,707,'حد ضرر')])])
        self.assertEqual(r['parts_with_asr'],3)
        self.assertGreaterEqual(len(r['rule_candidates']),2)
        self.assertEqual(r['rules_executable'],0)
        self.assertFalse(r['paper_orders_allowed'])


if __name__=='__main__': unittest.main()
