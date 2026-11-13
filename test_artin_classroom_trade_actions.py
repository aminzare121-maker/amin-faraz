"""No-order motor regression tests for class-sourced entry, stop and risk actions.

Synthetic utterances and prices are never evidence of real historical orders.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from artin_classroom_trade_actions import TeacherActionError, execute

ROOT=Path(__file__).resolve().parent
CORE=Path(os.environ.get('ARTIN_PINNED_LEGACY_DIR', ROOT/'core'))


def source(session, marker, words, second):
    return {'session':session,'source_segment_id':marker,'machine_text_unverified':words,
            'start_seconds':second,'end_seconds':second+2.0,
            'source_audio_sha256':'1'*64}


def frame_position(side='BUY',current_stop='3990',new_stop='3995'):
    entry='4000'; initial_stop='3990'
    if side=='SELL':
        initial_stop='4010'
        if current_stop=='3990':current_stop='4010'
        if new_stop=='3995':new_stop='4005'
    return {'side':side,'entry':entry,'initial_stop':initial_stop,
            'current_stop':current_stop,'new_stop':new_stop,'lots':'0.01',
            'money_per_price_unit_per_lot':'100','min_lot':'0.01','lot_step':'0.01',
            'round_trip_fee_per_lot':'0','adverse_price_allowance':'0'}


class ClassTradeActionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.rows={
           19:[source(19,'three','سه تا کندل زیر یک دوم لگ حتما یکی در جهت سنتیمنت باید کندل شک باشد ورود روی کلوز کندل سوم',100.0)],
           21:[source(21,'before','اینجا ورود نمی کنیم',10.0),
               source(21,'after','رو کلوز تاییده ورود میکنیم',20.0)],
           24:[source(24,'reduce','دو درصد ریسک را یک درصد می کنیم، معامله رو نمیبنده',100.0),
               source(24,'half-speech','استاپلاسم میارم جایی که نصفشه',150.0),
               source(24,'half-risk','نصف ریسکتون رو کم کنید',160.0),
               source(24,'profit','5 دلار سیوه سود میکنم، استاپلاس هم اینجاست',200.0),
               source(24,'stop-reference','برگرده استاپلاس من رو بزنه',300.0),
               source(24,'stop-exit','خودش معامله رو میبنده',325.0)],
           25:[source(25,'riskfree','استاپلاس رو برداری بیاری بذاری نقطه ورود',300.0),
               source(25,'structure','استاپ نزدیک تر کار اشتباه میشه',400.0)],
        }
        for session,rows in self.rows.items():
            (self.folder/f'session_{session:02d}_all_machine_speech_review.jsonl').write_text(
                ''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf8')

    def run_events(self, events):
        return execute({'schema':'artin_classroom_trade_actions_v1','events':events},self.folder,CORE)

    def base(self, kind, session, segment, **kwargs):
        return {'event_id':'case-'+kind,'kind':kind,'session':session,
                'source_segment_ids':[segment],**kwargs}

    def test_nonobject_classroom_event_rejected_before_source_loading(self):
        for bad in (None, 'bad', 17, []):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(TeacherActionError,'CLASS_EVENT_OBJECT_REQUIRED'):
                    self.run_events([self.base('NO_ENTRY',21,'before'),bad])

    def test_future_quote_cannot_trigger_paper_stop(self):
        e=self.base('STOP_EXIT_TRIGGER',24,'stop-reference',
                    position={'side':'BUY','entry':'4000','current_stop':'3995','lots':'0.01'},
                    quote={'bid':'3994','ask':'3995','source':'SYNTHETIC_QUOTE',
                           'known_at':2000},
                    decision_at=1000)
        # The class exit words are split across two sourced segments.
        e['source_segment_ids']=['stop-reference','stop-exit']
        result=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'WAIT_FOR_CAUSAL_QUOTE')
        self.assertFalse(result['order_created'])
        self.assertFalse(result['position_closed'])

    def test_empty_pinned_manifest_cannot_authorize_classroom_actions(self):
        from shutil import copytree
        with tempfile.TemporaryDirectory() as directory:
            core=Path(directory)/'pinned'
            copytree(CORE,core)
            manifest=core/'LEGACY_SHA_MANIFEST.json'
            doc=json.loads(manifest.read_text(encoding='utf8'))
            doc['files_sha256']={}
            manifest.write_text(json.dumps(doc),encoding='utf8')
            event=self.base('NO_ENTRY',21,'before')
            with self.assertRaisesRegex(TeacherActionError,'PINNED_ENGINE_HASH_COVERAGE_MISSING'):
                execute({'schema':'artin_classroom_trade_actions_v1','events':[event]},self.folder,core)

    def test_no_entry_then_wait_then_scoped_chart_review(self):
        before=self.base('NO_ENTRY',21,'before')
        after=self.base('ENTRY_AFTER_CONFIRMATION',21,'after',chart={'closed':False})
        doc=self.run_events([before,after]);a,b=[x['execution'] for x in doc['classroom_decision_actions']]
        self.assertEqual(a['decision'],'NO_TRADE_IN_CITED_CLASS_SCENE')
        self.assertEqual(b['decision'],'WAIT_FOR_CONFIRMATION_CLOSE')
        after['chart']={'closed':True,'source_verified':False,'source_frame_sha256':'f'*64}
        self.assertEqual(self.run_events([after])['classroom_decision_actions'][0]['execution']['decision'],'WAIT_FOR_CHART_REFERENCE')
        after['chart']['source_verified']=True
        r=self.run_events([after]);self.assertEqual(r['classroom_decision_actions'][0]['execution']['decision'],'CLASSROOM_CONFIRMATION_OBSERVED_ENTRY_REVIEW')
        self.assertEqual(r['orders_sent'],0)

    def test_risk_reduction_buy_does_not_close_position(self):
        e=self.base('REDUCE_RISK_STOP',24,'reduce',position=frame_position(),
                    observed_management_trigger=True,trigger_source='SYNTHETIC_UNIT_EVENT')
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'PAPER_STOP_MOVE_ACCEPTED')
        self.assertEqual(x['label'],'reduce')
        self.assertEqual(x['lots_before'],x['lots_after'])
        self.assertEqual(x['old_stop'],'3990')
        self.assertEqual(x['new_stop'],'3995')
        self.assertEqual(x['modeled_exit_net'],'-5.00')
        self.assertFalse(x['position_closed'])
        self.assertIsNone(x['realized_pnl'])
        self.assertEqual(x['source_trigger_class'],'PAPER_ASSUMPTION')

    def test_risk_reduction_sell(self):
        e=self.base('REDUCE_RISK_STOP',24,'reduce',position=frame_position('SELL'),
                    observed_management_trigger=True,trigger_source='SYNTHETIC_UNIT_EVENT')
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'PAPER_STOP_MOVE_ACCEPTED')
        self.assertEqual(x['new_stop'],'4005')
        self.assertEqual(x['modeled_exit_net'],'-5.00')

    def test_saveprofit_protects_gross_not_realized(self):
        p=frame_position(current_stop='4000',new_stop='4005')
        e=self.base('SAVE_PROFIT_STOP',24,'profit',position=p,
                    observed_management_trigger=True,trigger_source='SYNTHETIC_UNIT_EVENT')
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'PAPER_STOP_MOVE_ACCEPTED')
        self.assertEqual(x['label'],'saveprofit')
        self.assertEqual(x['modeled_exit_net'],'5.00')
        self.assertIsNone(x['realized_pnl'])
        self.assertEqual(x['lots_after'],p['lots'])

    def test_no_trigger_waits_instead_of_changing_stop(self):
        e=self.base('REDUCE_RISK_STOP',24,'reduce',position=frame_position(),
                    observed_management_trigger=False,trigger_source='SYNTHETIC_UNIT_EVENT')
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'WAIT_FOR_CLASSROOM_TRIGGER')
        self.assertEqual(x['current_stop_unchanged'],'3990')

    def test_stop_cannot_be_loosened_or_mislabeled(self):
        p=frame_position(new_stop='3985')
        e=self.base('REDUCE_RISK_STOP',24,'reduce',position=p,
                    observed_management_trigger=True,trigger_source='SYNTHETIC_UNIT_EVENT')
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'REJECT_PAPER_STOP_MOVE')
        self.assertEqual(x['reason'],'STOP_NOT_STRICTLY_RISK_REDUCING')
        p['new_stop']='4005'
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['reason'],'LABEL_DOES_NOT_MATCH_STOP')

    def test_negative_costs_and_unsourced_contract_rejected(self):
        p=frame_position();p.pop('lot_step')
        e=self.base('REDUCE_RISK_STOP',24,'reduce',position=p,observed_management_trigger=True,trigger_source='SYNTHETIC_UNIT_EVENT')
        with self.assertRaisesRegex(TeacherActionError,'EXPLICIT_STOP_CONTRACT_REQUIRED'):self.run_events([e])
        p['lot_step']='0.01';p['round_trip_fee_per_lot']='-1'
        with self.assertRaisesRegex(TeacherActionError,'NONNEGATIVE_DECIMAL_REQUIRED'):self.run_events([e])

    def test_riskfree_moves_to_entry_without_closing(self):
        pos={'side':'BUY','entry':'4000','current_stop':'3995','lots':'0.01'}
        e=self.base('RISKFREE_TO_ENTRY',25,'riskfree',position=pos,
                    observed_management_trigger=True,trigger_source='SYNTHETIC_UNIT_EVENT')
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'MOVE_STOP_TO_ENTRY_PAPER')
        self.assertFalse(x['position_closed'])
        self.assertEqual(x['new_stop'],'4000')
        self.assertFalse(x['net_break_even_guaranteed'])

    def test_synthetic_source_keyword_cannot_force_entry(self):
        e=self.base('ENTRY_AFTER_CONFIRMATION',21,'before',chart={'closed':True,'source_verified':True,'source_frame_sha256':'c'*64})
        with self.assertRaisesRegex(TeacherActionError,'CONFIRMATION_ENTRY_WORDS_NOT_PRESENT'):self.run_events([e])

    def test_cross_session_splice_rejected(self):
        e=self.base('NO_ENTRY',25,'before')
        with self.assertRaisesRegex(TeacherActionError,'SOURCE_SEGMENT_MISSING'):self.run_events([e])

    def test_source_not_replaced_by_hashed_label(self):
        e=self.base('NO_ENTRY',21,'before')
        r=self.run_events([e]);self.assertEqual(r['original_25_video_source_file_hashes']['21'],
                                                   hashlib.sha256((self.folder/'session_21_all_machine_speech_review.jsonl').read_bytes()).hexdigest())
        self.assertFalse(r['live_strategy_certified']);self.assertFalse(r['broker_connected'])

    def test_reversed_teacher_speech_sequence_rejected(self):
        first=self.base('ENTRY_AFTER_CONFIRMATION',21,'after')
        second=self.base('NO_ENTRY',21,'before')
        with self.assertRaisesRegex(TeacherActionError,'CLASSROOM_SEQUENCE_REVERSED'):
            self.run_events([first,second])

    def test_stop_trigger_paper_exit_buy_and_hold(self):
        e=self.base('STOP_EXIT_TRIGGER',24,'stop-reference',
                    position={'side':'BUY','entry':'4000','current_stop':'4005','lots':'0.01'},
                    quote={'bid':'4004','ask':'4004.1','source':'SYNTHETIC_TEST_PRICE'})
        e['source_segment_ids']=['stop-reference','stop-exit']
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'STOP_EXIT_TRIGGER_PAPER_NOT_A_FILL')
        self.assertFalse(x['broker_fill_verified'])
        self.assertIsNone(x['realized_pnl'])
        self.assertFalse(x['position_closed'])
        e['quote']['bid']='4006';e['quote']['ask']='4006.1'
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'PAPER_POSITION_HELD_STOP_NOT_HIT')

    def test_stop_trigger_paper_exit_sell_and_quote_side(self):
        e=self.base('STOP_EXIT_TRIGGER',24,'stop-reference',
                    position={'side':'SELL','entry':'4000','current_stop':'3995','lots':'0.01'},
                    quote={'bid':'3994','ask':'3996','source':'SYNTHETIC_TEST_PRICE'})
        e['source_segment_ids']=['stop-reference','stop-exit']
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'STOP_EXIT_TRIGGER_PAPER_NOT_A_FILL')
        self.assertEqual(x['quote_side'],'ASK')
        e['quote']['ask']='3994.5'
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'PAPER_POSITION_HELD_STOP_NOT_HIT')

    def test_stop_exit_needs_real_source_and_bid_ask(self):
        e=self.base('STOP_EXIT_TRIGGER',24,'stop-reference',
                    position={'side':'BUY','entry':'4000','current_stop':'4005','lots':'0.01'})
        e['source_segment_ids']=['stop-reference','stop-exit']
        x=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(x['decision'],'WAIT_FOR_SOURCED_QUOTE')
        e['quote']={'bid':'4004','ask':'4003','source':'SYNTHETIC_TEST_PRICE'}
        with self.assertRaisesRegex(TeacherActionError,'STOP_EXIT_BID_EXCEEDS_ASK'):self.run_events([e])
        e['source_segment_ids']=['stop-exit']
        with self.assertRaisesRegex(TeacherActionError,'STOP_EXIT_CLASS_WORDS_NOT_PRESENT'):self.run_events([e])


    def test_teacher_half_risk_auto_computes_stop_for_buy_and_sell(self):
        for side,initial,expected in [('BUY','3990','3995'),('SELL','4010','4005')]:
            with self.subTest(side=side):
                pos=frame_position(side)
                pos.pop('new_stop')  # Unlike the old event, user never chooses half-stop.
                event=self.base('HALVE_RISK_STOP',24,'half-speech',position=pos,
                    observed_management_trigger=True,trigger_source='SYNTHETIC_CLASS_EVENT')
                event['source_segment_ids']=['half-speech','half-risk']
                result=self.run_events([event])['classroom_decision_actions'][0]['execution']
                self.assertEqual(result['decision'],'PAPER_STOP_MOVE_ACCEPTED')
                self.assertEqual(result['new_stop'],expected)
                self.assertEqual(result['lots_before'],result['lots_after'])
                self.assertTrue(result['teacher_half_stop_distance_rule_applied'])
                self.assertFalse(result['position_closed'])
                self.assertIsNone(result['realized_pnl'])

    def test_half_risk_does_not_loosen_existing_better_stop(self):
        pos=frame_position(current_stop='3997');pos.pop('new_stop')
        event=self.base('HALVE_RISK_STOP',24,'half-speech',position=pos,
            observed_management_trigger=True,trigger_source='SYNTHETIC_CLASS_EVENT')
        event['source_segment_ids']=['half-speech','half-risk']
        result=self.run_events([event])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'ALREADY_HALF_RISK_OR_BETTER')
        self.assertEqual(result['current_stop_unchanged'],'3997')

    def test_half_risk_waits_for_trigger_not_claim_classroom_fill(self):
        pos=frame_position();pos.pop('new_stop')
        event=self.base('HALVE_RISK_STOP',24,'half-speech',position=pos,
            observed_management_trigger=False,trigger_source='SYNTHETIC_CLASS_EVENT')
        event['source_segment_ids']=['half-speech','half-risk']
        result=self.run_events([event])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'WAIT_FOR_CLASSROOM_TRIGGER')
        self.assertEqual(result['current_stop_unchanged'],'3990')

    def test_half_risk_rejects_wrong_initial_stop_side(self):
        pos=frame_position();pos.pop('new_stop');pos['initial_stop']='4010'
        event=self.base('HALVE_RISK_STOP',24,'half-speech',position=pos,
            observed_management_trigger=True,trigger_source='SYNTHETIC_CLASS_EVENT')
        event['source_segment_ids']=['half-speech','half-risk']
        with self.assertRaisesRegex(TeacherActionError,'INITIAL_STOP_WRONG_SIDE'):
            self.run_events([event])

    def test_half_risk_requires_both_original_class_concepts(self):
        pos=frame_position();pos.pop('new_stop')
        event=self.base('HALVE_RISK_STOP',24,'half-speech',position=pos,
            observed_management_trigger=True,trigger_source='SYNTHETIC_CLASS_EVENT')
        with self.assertRaisesRegex(TeacherActionError,'HALVE_RISK_CLASS_WORDS_NOT_PRESENT'):
            self.run_events([event])


    def three_candle_event(self, **changes):
        bars=[{'time':t,'open':o,'high':h,'low':l,'close':c,'source':'SYNTHETIC_TEST_M15'}
              for t,o,h,l,c in [(900,'100','102','99','101'),(1800,'101','103','100','102'),
                                 (2700,'102','104','101','103')]]
        event=self.base('THREE_CANDLE_CLOSE_ENTRY',19,'three',side='BUY',
              candles=bars,decision_at=3600,
              teacher_chart_facts={**{k:{'value':True,'known_at':3500,'source':'SYNTHETIC_TEST_CLASS_FACT'}
                 for k in ('pivot_confirmed','half_leg_location_confirmed',
                           'doubt_candle_present','sentiment_permitted')},
                 'doubt_candle_index':{'value':0,'known_at':3500,'source':'SYNTHETIC_TEST_CHART_FACT'}})
        event.update(changes)
        return event

    def test_three_candle_teacher_close_replay_candidate_only(self):
        e=self.three_candle_event()
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'CLASSROOM_THIRD_CLOSE_SETUP_CANDIDATE')
        self.assertEqual(r['bar_3_close_time'],3600)
        self.assertFalse(r['order_created'])
        self.assertFalse(r['trade_authorized'])
        self.assertFalse(r['teacher_chart_meaning_independently_verified'])

    def test_three_candle_must_wait_exact_closed_bar(self):
        e=self.three_candle_event(decision_at=3500)
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'WAIT_FOR_THIRD_CANDLE_CLOSE')
        e['decision_at']=4500
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'REJECT_NOT_AT_THIRD_CANDLE_CLOSE')

    def test_three_candle_gap_or_wrong_direction_blocks(self):
        e=self.three_candle_event();e['candles'][1]['time']=1900
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'REJECT_THREE_CANDLE_SEQUENCE_GAP')
        e=self.three_candle_event()
        for c in e['candles']:
            c['open'],c['close']='102','101'
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'REJECT_NO_CANDLE_IN_SENTIMENT_DIRECTION')

    def test_three_candle_mixed_directions_allowed_when_doubt_matches_sentiment(self):
        e=self.three_candle_event()
        # The class says one candle in sentiment direction must be a doubt
        # candle; it does NOT say each of three candles must match sentiment.
        e['candles'][1]['open'],e['candles'][1]['close']='102','101'
        result=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'CLASSROOM_THIRD_CLOSE_SETUP_CANDIDATE')
        self.assertEqual(result['observed_bar_directions'],['BUY','SELL','BUY'])
        self.assertEqual(result['doubt_candle_index'],0)

    def test_three_candle_doubt_must_really_be_sentiment_candle(self):
        e=self.three_candle_event()
        e['candles'][1]['open'],e['candles'][1]['close']='102','101'
        e['teacher_chart_facts']['doubt_candle_index']['value']=1
        result=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'REJECT_TEACHER_DOUBT_CANDLE_OPPOSES_SENTIMENT')
        e['teacher_chart_facts']['doubt_candle_index']['value']=3
        result=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'WAIT_FOR_PRIOR_KNOWN_CLASS_FACTS')

    def test_three_candle_missing_doubt_chart_index_never_claims_candidate(self):
        e=self.three_candle_event();del e['teacher_chart_facts']['doubt_candle_index']
        result=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(result['decision'],'WAIT_FOR_CLASS_CHART_CONTEXT')

    def test_three_candle_unknown_or_future_chart_fact_never_enters(self):
        e=self.three_candle_event();e['teacher_chart_facts'].pop('pivot_confirmed')
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'WAIT_FOR_CLASS_CHART_CONTEXT')
        e=self.three_candle_event();e['teacher_chart_facts']['half_leg_location_confirmed']['known_at']=3601
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'WAIT_FOR_PRIOR_KNOWN_CLASS_FACTS')
        e=self.three_candle_event();e['teacher_chart_facts']['doubt_candle_present']['value']=False
        r=self.run_events([e])['classroom_decision_actions'][0]['execution']
        self.assertEqual(r['decision'],'REJECT_TEACHER_THREE_CANDLE_CONDITION_FALSE')

    def test_three_candle_malformed_ohlc_rejected(self):
        e=self.three_candle_event();e['candles'][2]['high']='101'
        with self.assertRaisesRegex(TeacherActionError,'INVALID_THREE_CANDLE_OHLC'):
            self.run_events([e])

    def test_duplicate_class_event_rejected(self):
        e=self.base('NO_ENTRY',21,'before')
        with self.assertRaisesRegex(TeacherActionError,'EVENT_ID_DUPLICATE_OR_MISSING'):self.run_events([e,e])

if __name__=='__main__':unittest.main(verbosity=2)