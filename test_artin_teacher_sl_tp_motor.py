import unittest
from decimal import Decimal as D
from core.capital import Instrument,Costs
from fxm_teacher_policy import AccountRisk
from artin_teacher_sl_tp_motor import (SingleTargetPaperPosition,build_plan,replay_quotes)

class TeacherSLTPTest(unittest.TestCase):
    def setUp(self):
        self.account=AccountRisk(D('1000'),D('1000'),D('1'))
        self.ins=Instrument(D('100'),D('0.01'),D('0.01'))
        self.cost=Costs(D('0'),D('0'))
    def obs(self,side='BUY',family='REVERSAL'):
        def fact(value):return {'value':value,'known_at':900,'source':'actual-chart:fixture:900'}
        e={'entry_family':fact(family),'teacher_scene_meaning_confirmed':fact(True),
           'stop_anchor_kind':fact('PIVOT'), 'entry_price':fact('4000'),
           'structural_stop_price':fact('3995' if side=='BUY' else '4005')}
        if family=='REVERSAL':e.update(prz_context=fact('FVG'),prz_teacher_confirmed=fact(True))
        else:e.update(break_line_price=fact('3999' if side=='BUY' else '4001'),break_teacher_confirmed=fact(True),decision_close=fact('4000'))
        return e
    def plan(self,side='BUY',route='REVERSAL_THREE',mode='SINGLE_RR',**kw):
        return build_plan(route=route,side=side,decision_at=901,
         chart_evidence=self.obs(side,'BREAK' if route.startswith('BREAK') else 'REVERSAL'),
         account=self.account,instrument=self.ins,costs=self.cost,target_mode=mode,
         target_mode_source='FXM.pdf#page=4',winrate=('55' if mode=='THREE_TP' else '35'),winrate_evidence='journal-closed-100-trades',
         teacher_core_eligible=True,**kw)
    def test_buy_one_target_from_teacher_rr_and_structural_stop(self):
        p=self.plan()
        self.assertEqual(p['status'],'PAPER_TEACHER_PDF_TRADE_PLAN')
        self.assertEqual((p['initial_stop'],p['targets']['tp'],p['lots']),('3995','4010','0.02'))
        self.assertEqual(p['modeled_max_loss'],'10.00')
        self.assertFalse(p['orders_enabled'])
    def test_sell_one_target_from_teacher_rr(self):
        p=self.plan(side='SELL')
        self.assertEqual((p['initial_stop'],p['targets']['tp']),('4005','3990'))
    def test_buy_multi_tp_and_teacher_stop_ladder(self):
        p=self.plan(mode='THREE_TP')
        self.assertEqual(p['targets'],{'tp1':'4004.0','tp2':'4006.5','tp3':'4009.0'})
        result=replay_quotes(p,[{'at':902,'bid':'4004','ask':'4004.1','source':'observed-1'},
           {'at':903,'bid':'4006.5','ask':'4006.6','source':'observed-2'},
           {'at':904,'bid':'4009','ask':'4009.2','source':'observed-3'}])
        self.assertEqual([x['status'] for x in result['events']],
              ['PAPER_MOVE_STOP_TO_ENTRY','PAPER_MOVE_STOP_TO_TP1','PAPER_TP3_CLOSE_ALL_TRIGGER'])
        self.assertEqual(result['latest_stop'],'4004.0')
        self.assertIsNone(result['realized_profit'])
    def test_sell_multi_tp_ladder(self):
        p=self.plan(side='SELL',mode='THREE_TP')
        r=replay_quotes(p,[{'at':902,'bid':'3995.8','ask':'3996','source':'q1'},
           {'at':903,'bid':'3993','ask':'3993.5','source':'q2'},
           {'at':904,'bid':'3990.8','ask':'3991','source':'q3'}])
        self.assertEqual(r['latest_stop'],'3996.0')
        self.assertEqual(r['exit_trigger'],'TP3_TOUCH')
    def test_single_target_stop_touch_not_filled(self):
        p=self.plan()
        r=replay_quotes(p,[{'at':902,'bid':'3994','ask':'3994.3','source':'q1'}])
        self.assertEqual(r['exit_trigger'],'STOP_TOUCH')
        self.assertFalse(r['exit_fill_verified'])
    def test_single_target_tp_touch_not_filled(self):
        p=self.plan()
        r=replay_quotes(p,[{'at':902,'bid':'4010','ask':'4010.1','source':'q1'}])
        self.assertEqual(r['exit_trigger'],'TARGET_TOUCH')
        self.assertFalse(r['exit_fill_verified'])
    def test_no_video_does_not_prevent_pdf_rule_but_core_eligible_is_required(self):
        data=self.plan()
        self.assertEqual(data['status'],'PAPER_TEACHER_PDF_TRADE_PLAN')
        args=dict(route='REVERSAL_THREE',side='BUY',decision_at=901,
          chart_evidence=self.obs(),account=self.account,instrument=self.ins,
          costs=self.cost,target_mode='THREE_TP',target_mode_source='FXM.pdf#page=4')
        self.assertEqual(build_plan(**args)['status'],'WAIT_PINNED_13_ROUTE_ENTRY_CORE')
    def test_missing_teacher_scene_flag_blocks(self):
        e=self.obs();del e['teacher_scene_meaning_confirmed']
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,target_mode='THREE_TP',
          target_mode_source='FXM.pdf#page=4',winrate='55',winrate_evidence='journal',
          teacher_core_eligible=True)
        self.assertEqual(r['status'],'TECHNICAL_ENTRY_OR_STOP_REJECTED')
    def test_teacher_pdf_cannot_be_fake_market_source(self):
        e=self.obs();e['structural_stop_price']['source']='Technical(1).pdf#page=17'
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,target_mode='THREE_TP',
          target_mode_source='FXM.pdf#page=4',teacher_core_eligible=True)
        self.assertEqual(r['status'],'ACTUAL_CHART_PRICE_SOURCE_REQUIRED')
    def test_cancel_under_33_even_if_multitarget_requested(self):
        e=self.obs()
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,target_mode='THREE_TP',
          target_mode_source='FXM.pdf#page=4',winrate='20',winrate_evidence='journal',
          teacher_core_eligible=True)
        self.assertEqual(r['status'],'FXM_CANCEL_LOW_WINRATE')
    def test_multitarget_band_must_be_grounded(self):
        e=self.obs()
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,target_mode='THREE_TP',
          target_mode_source='FXM.pdf#page=4',winrate='35',winrate_evidence='journal',
          teacher_core_eligible=True)
        self.assertEqual(r['status'],'FXM_THREE_TARGET_BAND_UNCONFIRMED')
    def test_unverified_balance_drawdown_blocks(self):
        e=self.obs()
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=AccountRisk(D('800'),D('1000'),D('1')),instrument=self.ins,costs=self.cost,
          target_mode='THREE_TP',target_mode_source='FXM.pdf#page=4',teacher_core_eligible=True)
        self.assertEqual(r['status'],'FXM_RISK_GATE_REJECTED')
    def test_no_guess_rr_on_ambiguous_winrate(self):
        e=self.obs()
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,
          target_mode='SINGLE_RR',target_mode_source='FXM.pdf#page=4',
          winrate='55',winrate_evidence='journal',teacher_core_eligible=True)
        self.assertEqual(r['status'],'FXM_RR_UNRESOLVED')
    def test_buy_break_requires_observed_close_beyond_teacher_line(self):
        r=self.plan(route='BREAK_STRONG')
        self.assertEqual(r['status'],'PAPER_TEACHER_PDF_TRADE_PLAN')
    def test_future_chart_fact_blocks(self):
        e=self.obs();e['entry_price']['known_at']=9999
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,target_mode='THREE_TP',
          target_mode_source='FXM.pdf#page=4',winrate='55',winrate_evidence='journal',
          teacher_core_eligible=True)
        self.assertEqual(r['status'],'TECHNICAL_ENTRY_OR_STOP_REJECTED')
    def test_stop_price_does_not_change_to_force_minimum_lot(self):
        e=self.obs();e['structural_stop_price']['value']='3900'
        r=build_plan(route='REVERSAL_THREE',side='BUY',decision_at=901,chart_evidence=e,
          account=self.account,instrument=self.ins,costs=self.cost,target_mode='THREE_TP',
          target_mode_source='FXM.pdf#page=4',teacher_core_eligible=True)
        self.assertEqual(r['status'],'FXM_RISK_GATE_REJECTED')
    def test_source_events_required(self):
        p=self.plan()
        with self.assertRaises(ValueError):replay_quotes(p,[{'at':902,'bid':'4010','ask':'4011'}])
    def test_monotonic_quotes_required(self):
        p=self.plan()
        with self.assertRaises(ValueError):replay_quotes(p,[{'at':902,'bid':'4001','ask':'4001.2','source':'q1'},
                           {'at':901,'bid':'4002','ask':'4002.2','source':'q2'}])
    def test_sell_stop_uses_ask_target_uses_ask(self):
        p=self.plan(side='SELL')
        r=replay_quotes(p,[{'at':902,'bid':'3990','ask':'3991','source':'q1'},
                           {'at':903,'bid':'3990','ask':'3990','source':'q2'}])
        self.assertEqual(len(r['events']),2)
        self.assertEqual(r['exit_trigger'],'TARGET_TOUCH')

if __name__=='__main__':unittest.main()