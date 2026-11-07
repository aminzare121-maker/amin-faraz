"""Original-audio + typed-chat joining: never certify teacher answers."""
import unittest
from artin_ocr_asr_join_v8 import join_original_chat_qa

HASH='a'*64
CHAT='b'*64

def data():
    rows=[
      {'frame_id':f'f{i}','global_chunk':1,'batch':1,'slot':1,
       'time_seconds':i*30.,'chat':{'sha256':CHAT},
       'board':{'sha256':'c'*64}} for i in (1,2,3)]
    index={'schema':'artin_classroom_visual_v6',
           'source_video_sha256':HASH,'rows':rows}
    result=[]
    for i,r in enumerate(rows):
        result.append({'frame_id':r['frame_id'],
             'time_original_video_seconds':r['time_seconds'],
             'source_frame_sha256':CHAT,
             'state':'OCR_TEXT_CANDIDATES',
             'possible_typed_questions':[{'possible_question_text':
                     'چرا این عدد همیشه بیشتر از یک است؟'}]})
    ocr={'schema':'artin_full_original_chat_ocr_v7',
        'source_video_sha256':HASH,
        'frames_attempted':3,'complete':True,'results':result}
    speech={'schema':'artin_teacher_av_review_v5',
            'source_video_sha256':HASH,
            'speech_lines':[{'id':'asr01','start':60.,'end':65.,
                             'text':'باید درس رو ببینیم'}]}
    return index,ocr,speech


class OCRSpeechJoinTests(unittest.TestCase):
    def test_same_question_seen_three_frames_one_provisional_group(self):
        v,o,s=data()
        safe,private=join_original_chat_qa(v,o,s)
        self.assertEqual(safe['original_chat_frames'],3)
        self.assertEqual(safe['provisional_question_observations'],3)
        self.assertEqual(safe['provisional_distinct_question_groups'],1)
        group=private['question_groups'][0]
        self.assertEqual(group['frames_observed'],3)
        self.assertFalse(group['student_question_verified'])
        self.assertFalse(group['teacher_answer_verified'])
        self.assertEqual(safe['verified_trading_rules'],0)

    def test_different_audio_source_rejected(self):
        v,o,s=data();s['source_video_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'source SHA mismatch'):
            join_original_chat_qa(v,o,s)

    def test_partial_ocr_fails_closed(self):
        v,o,s=data();o['complete']=False
        with self.assertRaisesRegex(ValueError,'not fully completed'):
            join_original_chat_qa(v,o,s)

    def test_swapped_frame_hash_rejected(self):
        v,o,s=data();o['results'][0]['source_frame_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'relabeled'):
            join_original_chat_qa(v,o,s)

    def test_unreadable_frame_remains_counted_not_question(self):
        v,o,s=data();o['results'][0]['state']='OCR_NO_READABLE_TEXT'
        safe,private=join_original_chat_qa(v,o,s)
        self.assertEqual(safe['OCR_failed_or_blank_frames'],1)
        self.assertEqual(safe['provisional_question_observations'],2)
        self.assertEqual(private['ocr_missing_or_failed'][0]['frame_id'],'f1')

    def test_unexpected_status_rejected(self):
        v,o,s=data();o['results'][2]['state']='FAKE_VERIFIED'
        with self.assertRaisesRegex(ValueError,'Unknown OCR source state'):
            join_original_chat_qa(v,o,s)


if __name__=='__main__':unittest.main()
