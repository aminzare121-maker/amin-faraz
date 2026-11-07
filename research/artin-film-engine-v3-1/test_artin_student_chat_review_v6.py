"""Fail-closed student chat and speech correlation with fake source data."""
import copy
import unittest

from artin_student_chat_review_v6 import (
  probable_question,validate_visual_model_candidates,reconcile_chat_asr
)

H='a'*64
CHAT='b'*64
BOARD='c'*64


def fixtures():
    visual={'schema':'artin_classroom_visual_v6',
            'source_video_sha256':H,
            'rows':[{'frame_id':'b001_s01_g000001_t0000000120',
              'global_chunk':1,'batch':1,'slot':1,'time_seconds':120.0,
              'chat':{'path':'chat/a.png','sha256':CHAT},
              'board':{'path':'board/a.png','sha256':BOARD}}]}
    proposal={'frame_id':visual['rows'][0]['frame_id'],'channel':'chat',
              'frame_sha256':CHAT,'visible_text_candidate':'اگر قیمت برگشت، باید خرید کنیم؟',
              'legibility':'MEDIUM'}
    speech={'schema':'artin_teacher_av_review_v5','source_video_sha256':H,
            'speech_lines':[{'id':'asr001','start':123.0,'end':127.0,'text':'باید ببینیم'}]}
    return visual,proposal,speech


class ChatEvidenceTests(unittest.TestCase):
    def test_real_question_detection(self):
        self.assertTrue(probable_question('اگر برگشت، خرید کنیم؟'))
        self.assertTrue(probable_question('چرا این کندل؟'))
        self.assertFalse(probable_question('یکی از کندل‌ها را نشان می‌دهیم'))
        self.assertFalse(probable_question('این یعنی بازار فارکس'))

    def test_valid_visual_candidate_cannot_be_rule(self):
        v,p,s=fixtures()
        got=validate_visual_model_candidates(v,[p])
        self.assertEqual(got['candidate_count'],1)
        self.assertTrue(got['candidates'][0]['question_candidate'])
        self.assertIsNone(got['candidates'][0]['message_sent_at_seconds'])
        self.assertFalse(got['candidates'][0]['can_change_artin_engine'])

    def test_wrong_image_hash_rejected(self):
        v,p,s=fixtures();p['frame_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'another or altered'):
            validate_visual_model_candidates(v,[p])

    def test_missing_frame_rejected(self):
        v,p,s=fixtures();p['frame_id']='not_real'
        with self.assertRaisesRegex(ValueError,'unknown frame'):
            validate_visual_model_candidates(v,[p])

    def test_hallucinated_speaker_rejected(self):
        v,p,s=fixtures();p['student_verified']=True
        with self.assertRaisesRegex(ValueError,'identity'):
            validate_visual_model_candidates(v,[p])

    def test_hallucinated_rule_authority_rejected(self):
        v,p,s=fixtures();p['rule_authorized']=True
        with self.assertRaisesRegex(ValueError,'trade rules'):
            validate_visual_model_candidates(v,[p])

    def test_no_false_student_question_from_board(self):
        v,p,s=fixtures();p['channel']='board';p['frame_sha256']=BOARD
        result=validate_visual_model_candidates(v,[p])
        self.assertFalse(result['candidates'][0]['question_candidate'])

    def test_typed_question_links_to_audio_for_review_only(self):
        v,p,s=fixtures()
        chat=validate_visual_model_candidates(v,[p])
        result=reconcile_chat_asr(chat,s)
        self.assertEqual(len(result['question_candidates']),1)
        link=result['question_candidates'][0]
        self.assertEqual(link['possible_spoken_replies'][0]['speech_line_id'],'asr001')
        self.assertFalse(link['answer_verified'])
        self.assertFalse(link['actual_question_post_time_known'])
        self.assertEqual(result['executable_rules'],0)

    def test_different_video_rejected(self):
        v,p,s=fixtures()
        s['source_video_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'different videos'):
            reconcile_chat_asr(validate_visual_model_candidates(v,[p]),s)

    def test_duplicate_within_one_image_deduplicated(self):
        v,p,s=fixtures()
        chat=validate_visual_model_candidates(v,[p,p])
        self.assertEqual(chat['candidate_count'],1)

    def test_nonquestion_does_not_generate_fake_answers(self):
        v,p,s=fixtures()
        p['visible_text_candidate']='فایل دانلود شد'
        chat=validate_visual_model_candidates(v,[p])
        self.assertEqual(reconcile_chat_asr(chat,s)['question_candidates'],[])


if __name__=='__main__':unittest.main()
