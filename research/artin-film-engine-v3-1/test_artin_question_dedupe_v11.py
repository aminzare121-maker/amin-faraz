import unittest
from artin_question_dedupe_v11 import clustered_review

SHA='b'*64
FRAME='a'*64

def group(text,at=10,index=1,verified=False):
    return {'candidate_text':text,'first_seen':at,'last_seen':at,
            'frame_sources':[{'frame_id':'frame'+str(index),'chat_frame_sha256':FRAME,
                              'observed_at_seconds':at}],
            'teacher_answer_verified':verified,'student_question_verified':False,
            'provisional_nearby_speech':[]}

def review(groups):
    return {'schema':'artin_private_typed_chat_audio_candidates_v8',
            'source_video_sha256':SHA,'question_groups':groups}

class DedupeTests(unittest.TestCase):
    def test_same_question_with_persian_digits_spaces_and_ui_clock_clusters(self):
        x=clustered_review(review([
            group('۱۱:۱۹ تا چه قد ذاتیه؟ یا تا چه قد میتونه به دست بیاد؟',10,1),
            group('11:19 تاچه قدذاتیه؟یا تاچه قد میتونه به دست بیاد؟',35,2)]))
        self.assertEqual(x['conservative_near_duplicate_clusters'],1)
        self.assertEqual(x['original_review_groups'],2)
        self.assertEqual(len(x['review_clusters'][0]['member_groups']),2)
        self.assertEqual(x['review_clusters'][0]['original_chat_frame_observations'],2)
        self.assertEqual(x['verified_teacher_answers'],0)

    def test_buy_and_no_buy_never_combined(self):
        x=clustered_review(review([
            group('وقتی که شکست این ناحیه تایید شد بخر',10,1),
            group('وقتی که شکست این ناحیه تایید شد نخر',20,2)]))
        self.assertEqual(x['conservative_near_duplicate_clusters'],2)

    def test_sell_and_no_sell_never_combined(self):
        x=clustered_review(review([
            group('اگر قیمت به ناحیه رسید بفروش',10,1),
            group('اگر قیمت به ناحیه رسید نفروش',20,2)]))
        self.assertEqual(x['conservative_near_duplicate_clusters'],2)

    def test_far_apart_same_question_remains_distinct(self):
        x=clustered_review(review([group('آیا باید حد ضرر را به نقطه ورود انتقال بدهیم؟',10,1),
                                   group('آیا باید حد ضرر را به نقطه ورود انتقال بدهیم؟',500,2)]))
        self.assertEqual(x['conservative_near_duplicate_clusters'],2)

    def test_uncertain_short_chat_does_not_merge(self):
        x=clustered_review(review([group('صدا دارید؟',10,1),group('صدا دارید؟',25,2)]))
        self.assertEqual(x['conservative_near_duplicate_clusters'],2)

    def test_reject_unverified_teacher_claim(self):
        with self.assertRaisesRegex(ValueError,'cannot assert'):
            clustered_review(review([group('آیا میشه همیشه خرید کرد؟',10,1,True)]))

    def test_source_hash_required(self):
        r=review([group('آیا میشه همیشه خرید کرد؟')]);r['source_video_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'SHA256'):
            clustered_review(r)

if __name__=='__main__': unittest.main()
