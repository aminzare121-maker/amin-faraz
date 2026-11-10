"""Pure synthetic tests; no classroom speech, private original videos or credentials."""
import copy
import unittest
from artin_9_episode_validation import validate_report

def fixture():
    groups=[]
    for session,start,end,count in ((19,4276.,4331.,4),(21,1896.,1944.,5)):
        speech=[]
        for i in range(count):
            a=start+1+i*4; b=a+1
            speech.append(dict(segment_id=f's{session}_{i}',session=session,start_seconds=a,end_seconds=b,
                source_frame_time=a+.5,audio_relative_from_seconds=a-start,audio_relative_until_seconds=b-start,
                machine_text_unverified='نمونه ساختگی غیرواقعی',independently_heard=False,speaker_identity_verified=False))
        groups.append(dict(session=session,clip_seconds=[start,end],machine_speech=speech))
    arr19=[f's19_{i}' for i in range(4)];arr21=[f's21_{i}' for i in range(5)]
    pairs=[]
    options=[(2,19,arr19[0],arr19[2]),(3,19,arr19[0],arr19[3]),(5,19,arr19[1],arr19[2]),(7,19,arr19[1],arr19[3]),
        (9,21,arr21[0],arr21[1]),(10,21,arr21[0],arr21[2]),(12,21,arr21[1],arr21[3]),(13,21,arr21[0],arr21[4]),(14,21,arr21[2],arr21[4])]
    for n,s,a,b in options:
        g=next(x for x in groups if x['session']==s)
        us={x['segment_id']:x for x in g['machine_speech']}
        pairs.append(dict(pair=n,session=s,utterance_ids=[a,b],relative_timing_seconds=[us[x]['audio_relative_from_seconds'] for x in (a,b)],
            trade_authorized=False,semantic_verdict='UNRESOLVED_NOT_A_CONFIRMED_CONTRADICTION'))
    result=dict(source_groups=groups,pairs=pairs,source_group_count=2,nine_unique_speech_segments=9,candidate_pairs=9,
        total_duration_seconds=103,original_Persian_words_independently_heard=False,speaker_identity_independently_verified=False,
        teacher_semantics_verified=False,same_chart_trade_situation_verified_for_any_pair=False,
        XAUUSD_transfer_from_EURUSD_authorized=False,mt5_orders_authorized=0)
    return result

class PublicNineEpisodeTests(unittest.TestCase):
    def test_positive_synthetic_pair_index(self):
        self.assertEqual(validate_report(fixture())['unique_speech_count'],9)
    def test_refuse_trade_authorization(self):
        x=fixture();x['mt5_orders_authorized']=1
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_unearned_teacher_certification(self):
        x=fixture();x['teacher_semantics_verified']=True
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_claim_of_heard_words(self):
        x=fixture();x['original_Persian_words_independently_heard']=True
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_pair_crossing_video(self):
        x=fixture();x['pairs'][0]['utterance_ids'][1]='s21_2'
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_misbound_playback_offset(self):
        x=fixture();x['source_groups'][0]['machine_speech'][0]['audio_relative_from_seconds']=99
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_wrong_frame_time(self):
        x=fixture();x['source_groups'][0]['machine_speech'][0]['source_frame_time']=9000
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_rewritten_utterance_id(self):
        x=fixture();x['source_groups'][1]['machine_speech'][0]['segment_id']='s19_0'
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_replayed_wrong_pair(self):
        x=fixture();x['pairs'][0]['utterance_ids']=['s19_3','s19_0']
        with self.assertRaises(ValueError):validate_report(x)
    def test_refuse_unearned_pair_semantics(self):
        x=fixture();x['pairs'][0]['semantic_verdict']='TEACHER_CONTRADICTION_CERTIFIED'
        with self.assertRaises(ValueError):validate_report(x)

if __name__=='__main__':unittest.main()