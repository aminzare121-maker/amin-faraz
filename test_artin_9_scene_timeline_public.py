#!/usr/bin/env python3
"""Public synthetic safety tests for time-indexed video change evidence.

No proprietary voices, screenshots, course text or trade instructions here.
"""
import copy
import unittest
from artin_9_scene_timeline import build_decision_context,source_gate,SOURCE_DURATIONS


def fixture():
    groups=[];pairs=[]
    for sess,(a,b) in SOURCE_DURATIONS.items():
        count=4 if sess==19 else 5
        speech=[]
        for i in range(count):
            t=a+7+i*10 if sess==19 else a+4+i*8
            speech.append({'session':sess,'segment_id':f'test-{sess}-{i}',
                           'start_seconds':float(t),'end_seconds':float(t+2)})
        groups.append({'session':sess,'chart':'TEST','clip_seconds':[a,b],
                       'machine_speech':speech,'video_excerpt_sha256':'synthetic-sha'})
    s19=[f'test-19-{i}' for i in range(4)]
    s21=[f'test-21-{i}' for i in range(5)]
    for pair,ids,sess in [(2,[s19[0],s19[2]],19),(3,[s19[0],s19[3]],19),
                          (5,[s19[1],s19[2]],19),(7,[s19[1],s19[3]],19),
                          (9,[s21[2],s21[3]],21),(10,[s21[2],s21[4]],21),
                          (12,[s21[1],s21[2]],21),(13,[s21[0],s21[3]],21),
                          (14,[s21[0],s21[1]],21)]:
        pairs.append({'pair':pair,'session':sess,'utterance_ids':ids})
    source={'source_groups':groups,'pairs':pairs,
            'original_Persian_words_independently_heard':False,
            'speaker_identity_independently_verified':False,
            'teacher_semantics_verified':False,
            'same_chart_trade_situation_verified_for_any_pair':False,
            'XAUUSD_transfer_from_EURUSD_authorized':False,
            'mt5_orders_authorized':0}
    scan={}
    for sess,(a,b) in SOURCE_DURATIONS.items():
        scan[sess]=[{'second':t,'changed_fraction':0.0} for t in range(a,b)]
    return source,scan


class SceneTimelineTest(unittest.TestCase):
    def test_happy_path_is_not_semantic_validation(self):
        report,scans=fixture();out=build_decision_context(report,scans)
        self.assertEqual(len(out['pairs']),9)
        self.assertEqual([x['sampled_frames'] for x in out['episodes']],[55,48])
        self.assertFalse(out['teacher_rules_semantically_certified'])
        self.assertEqual(out['mt5_orders_authorized'],0)
        self.assertTrue(all(not p['teacher_semantics_verified'] for p in out['pairs']))
    def test_screen_event_only_when_fraction_at_least_8_percent(self):
        report,scans=fixture()
        scans[19][25]['changed_fraction']=0.079
        scans[19][26]['changed_fraction']=0.08
        out=build_decision_context(report,scans)
        self.assertEqual([x['second'] for x in out['episodes'][0]['candidate_changes']],[4302])
    def test_intervening_event_linked_to_matching_pair_only(self):
        report,scans=fixture();scans[19][20]['changed_fraction']=0.3
        d=build_decision_context(report,scans)
        p={i['pair']:i for i in d['pairs']}
        self.assertIn(4296,p[2]['intervening_sampled_screen_changes'])
        self.assertNotIn(4296,p[9]['intervening_sampled_screen_changes'])
        self.assertFalse(p[2]['visually_identical_chart_state_verified'])
    def test_no_event_never_certifies_identical_state(self):
        report,scans=fixture();out=build_decision_context(report,scans)
        self.assertTrue(all(not p['visually_identical_chart_state_verified'] for p in out['pairs']))
    def test_reject_cross_video_pair(self):
        r,s=fixture();r['pairs'][0]['utterance_ids'][0]='test-21-1'
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_duplicate_utterance(self):
        r,s=fixture();r['source_groups'][1]['machine_speech'][0]['segment_id']='test-19-0'
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_teacher_certification(self):
        r,s=fixture();r['teacher_semantics_verified']=True
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_trade_permission(self):
        r,s=fixture();r['mt5_orders_authorized']=1
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_missing_one_second(self):
        r,s=fixture();del s[19][5]
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_out_of_order_frames(self):
        r,s=fixture();s[19][5],s[19][6]=s[19][6],s[19][5]
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_nan_delta(self):
        r,s=fixture();s[21][3]['changed_fraction']=float('nan')
        with self.assertRaises(ValueError):build_decision_context(r,s)
    def test_reject_out_of_range_delta(self):
        r,s=fixture();s[19][0]['changed_fraction']=1.1
        with self.assertRaises(ValueError):build_decision_context(r,s)

if __name__=='__main__':unittest.main()