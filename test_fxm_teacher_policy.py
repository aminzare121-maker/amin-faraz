import unittest
from dataclasses import replace
from decimal import Decimal as D
from core.capital import Instrument, Costs
from fxm_teacher_policy import (AccountRisk, FXMError, PaperPosition,
    risk_sized_plan, winrate_target_policy, timeframe_notes,
    proposed_multi_targets, day_trade_permission)

class FXMTeacherPolicyTests(unittest.TestCase):
    def contract(self):
        return Instrument(D('100'),D('0.01'),D('0.01')),Costs(D('0'),D('0'))

    def paper(self,side='BUY'):
        if side=='BUY':
            return PaperPosition('BUY',D('4000'),D('3995'),D('3995'),D('4004'),D('4006.5'),D('4009'),D('0.02'))
        return PaperPosition('SELL',D('4000'),D('4005'),D('4005'),D('3996'),D('3993.5'),D('3991'),D('0.02'))

    def test_teacher_1000_one_percent_is_10_dollars(self):
        self.assertEqual(AccountRisk(D('1000'),D('1000'),D('1')).assess()['per_trade_risk_budget'],'10')
    def test_teacher_1000_two_percent_is_20_dollars(self):
        self.assertEqual(AccountRisk(D('1000'),D('1000'),D('2')).assess()['per_trade_risk_budget'],'20')
    def test_drawdown_20_percent_halts(self):
        self.assertEqual(AccountRisk(D('800'),D('1000'),D('1')).assess()['status'],
                         'STOP_FXM_20_PERCENT_BALANCE_DRAWDOWN')
    def test_drawdown_just_under_20_does_not_halt(self):
        self.assertEqual(AccountRisk(D('800.01'),D('1000'),D('1')).assess()['status'],'RISK_BUDGET_AVAILABLE')
    def test_invalid_risk_percent_fails(self):
        self.assertIn('REJECT',AccountRisk(D('1000'),D('1000'),D('2.5')).assess()['status'])
    def test_nonfinite_fails(self):
        with self.assertRaises(FXMError):AccountRisk(D('NaN'),D('1000'),D('1'))
    def test_invalid_bool_input_fails(self):
        with self.assertRaises(FXMError):AccountRisk(True,D('1000'),D('1'))
    def test_sizing_uses_existing_legacy_capital_core(self):
        i,c=self.contract()
        r=risk_sized_plan(AccountRisk(D('1000'),D('1000'),D('1')),'BUY','4000','3995',i,c,
             entry_source='class:19:timestamp',stop_source='class:24:timestamp')
        self.assertEqual(r['status'],'PAPER_SIZED_ONLY')
        self.assertEqual(r['lots'],'0.02')
        self.assertEqual(r['structural_stop_unchanged'],'3995')
        self.assertEqual(r['modeled_max_loss'],'10.00')
        self.assertFalse(r['orders_enabled'])
    def test_min_lot_breach_rejected_without_moving_stop(self):
        i,c=self.contract()
        r=risk_sized_plan(AccountRisk(D('1000'),D('1000'),D('1')),'BUY','4000','3950',i,c,
              entry_source='class:19',stop_source='class:24')
        self.assertTrue(r['status'].startswith('NO_TRADE_'))
    def test_sizing_missing_provenance_blocks(self):
        i,c=self.contract()
        r=risk_sized_plan(AccountRisk(D('1000'),D('1000'),D('1')),'BUY','4000','3995',i,c,
              entry_source='',stop_source='class:24')
        self.assertEqual(r['status'],'REVIEW_TEACHER_ENTRY_AND_STOP_SOURCES_REQUIRED')
    def test_winrate_0_to_33_cancels(self):
        self.assertEqual(winrate_target_policy('33',evidence_source='journal:1')['status'],'NO_TRADE_WINRATE_0_TO_33')
    def test_winrate_clear_35_to_rr_2(self):
        self.assertEqual(winrate_target_policy('35',evidence_source='journal:1')['rr'],'2')
    def test_winrate_clear_43_to_rr_1_8(self):
        self.assertEqual(winrate_target_policy('43',evidence_source='journal:1')['rr'],'1.8')
    def test_winrate_clear_75_to_rr_0_8(self):
        self.assertEqual(winrate_target_policy('75',evidence_source='journal:1')['rr'],'0.8')
    def test_conflicting_middle_table_is_review_not_invented(self):
        for pct in ['45','50','55','60','65','66','40']:
            self.assertEqual(winrate_target_policy(pct,evidence_source='journal')['status'],
                             'REVIEW_CONFLICTING_OR_UNSPECIFIED_RR_BAND')
    def test_winrate_unaudited(self):
        self.assertEqual(winrate_target_policy('35',evidence_source='')['status'],'REVIEW_WINRATE_EVIDENCE_REQUIRED')
    def test_winrate_above_100(self):
        with self.assertRaises(FXMError):winrate_target_policy('101',evidence_source='journal')
    def test_timeframes_grounded(self):
        self.assertEqual(timeframe_notes('DAY_TRADE')['stop_reference_mins'],15)
        self.assertEqual(timeframe_notes('SCALP')['target_reference_mins'],30)
        self.assertEqual(timeframe_notes('FAST_SCALP')['entry_reference_mins'],1)
    def test_three_targets_gate_requires_explicit_branch(self):
        self.assertTrue(proposed_multi_targets('BUY','4000','3995',teacher_branch_confirmed=False)['status'].startswith('WAIT'))
    def test_three_targets_price_distance_buy_sell(self):
        b=proposed_multi_targets('BUY','4000','3995',teacher_branch_confirmed=True, teacher_branch_source='class:p4:multi-target')
        s=proposed_multi_targets('SELL','4000','4005',teacher_branch_confirmed=True, teacher_branch_source='class:p4:multi-target')
        self.assertEqual((b['tp1'],b['tp2'],b['tp3']),('4004.0','4006.5','4009.0'))
        self.assertEqual((s['tp1'],s['tp2'],s['tp3']),('3996.0','3993.5','3991.0'))
    def test_buy_tp1_to_entry_only_when_quote_touches(self):
        p=self.paper()
        p,one=p.observe_quote('4003.9','4004',900)
        self.assertEqual(one['status'],'PAPER_HOLD')
        p,one=p.observe_quote('4004','4004.2',901)
        self.assertEqual((one['status'],p.current_stop,p.stage),('PAPER_MOVE_STOP_TO_ENTRY',D('4000'),1))
        self.assertEqual(one['lots_before'],one['lots_after'])
    def test_buy_tp2_moves_stop_to_tp1(self):
        p=self.paper();p,_=p.observe_quote('4004','4004.2',900)
        p,r=p.observe_quote('4006.5','4006.6',901)
        self.assertEqual((p.current_stop,p.stage),(D('4004'),2))
        self.assertEqual(r['status'],'PAPER_MOVE_STOP_TO_TP1')
    def test_buy_direct_jump_to_tp2(self):
        p,r=self.paper().observe_quote('4007','4007.2',900)
        self.assertEqual((p.current_stop,p.stage,r['status']),(D('4004'),2,'PAPER_MOVE_STOP_TO_TP1'))
    def test_buy_tp3_requires_fill_and_does_not_claim_profit(self):
        p,r=self.paper().observe_quote('4009','4009.3',900)
        self.assertEqual((p.pending_exit,r['status']),('TP3_TOUCH','PAPER_TP3_CLOSE_ALL_TRIGGER'))
        self.assertIsNone(r['realized_pnl'])
    def test_buy_stop_touch_uses_bid(self):
        p,r=self.paper().observe_quote('3995','3996',900)
        self.assertEqual((p.pending_exit,r['status']),('STOP_TOUCH','PAPER_STOP_TOUCH'))
    def test_sell_stop_uses_ask(self):
        p,r=self.paper('SELL').observe_quote('4004.5','4005',900)
        self.assertEqual(p.pending_exit,'STOP_TOUCH')
    def test_sell_tp1_and_tp2(self):
        p,r=self.paper('SELL').observe_quote('3995.8','3996',900)
        self.assertEqual((p.current_stop,r['status']),(D('4000'),'PAPER_MOVE_STOP_TO_ENTRY'))
        p,r=p.observe_quote('3993.4','3993.5',901)
        self.assertEqual((p.current_stop,r['status']),(D('3996'),'PAPER_MOVE_STOP_TO_TP1'))
    def test_sell_tp3(self):
        p,r=self.paper('SELL').observe_quote('3990.5','3991',900)
        self.assertEqual(r['status'],'PAPER_TP3_CLOSE_ALL_TRIGGER')
    def test_no_repeat_move_after_tp1(self):
        p,_=self.paper().observe_quote('4004','4004.1',900)
        p,r=p.observe_quote('4004.5','4004.7',901)
        self.assertEqual(r['status'],'PAPER_HOLD')
    def test_reject_out_of_order_time(self):
        p,_=self.paper().observe_quote('4004','4004.1',900)
        with self.assertRaises(FXMError):p.observe_quote('4005','4005.1',899)
    def test_ladder_no_stop_regression(self):
        p=replace(self.paper(),current_stop=D('4005'))
        p,r=p.observe_quote('4006.5','4006.6',900)
        self.assertEqual(p.current_stop,D('4005'))
    def test_wrong_target_structure_fails(self):
        with self.assertRaises(FXMError):replace(self.paper(),tp2=D('4002'))
    def test_awaiting_fill_no_reopen(self):
        p,_=self.paper().observe_quote('4009','4009.1',900)
        q,r=p.observe_quote('4009','4009.1',901)
        self.assertEqual(q,p)
        self.assertEqual(r['status'],'AWAITING_BROKER_OR_PAPER_EXIT_FILL')
    def test_day_three_sl_stop(self):
        self.assertEqual(day_trade_permission(['SL','SL','SL'])['status'],'STOP_FXM_DAY_TRADE_SEQUENCE')
    def test_day_one_tp_two_sl_stop(self):
        self.assertEqual(day_trade_permission(['TP','SL','SL'])['status'],'STOP_FXM_DAY_TRADE_SEQUENCE')
    def test_day_two_tp_one_sl_fourth_sl_stop(self):
        self.assertEqual(day_trade_permission(['TP','SL','TP','SL'])['status'],'STOP_FXM_DAY_TRADE_SEQUENCE')
    def test_day_two_tp_one_sl_fourth_tp_continue(self):
        self.assertEqual(day_trade_permission(['TP','SL','TP','TP'])['status'],'PAPER_DAY_SEQUENCE_CONTINUE')
    def test_day_three_tp_until_first_sl(self):
        self.assertEqual(day_trade_permission(['TP','TP','TP','TP'])['status'],'PAPER_DAY_SEQUENCE_CONTINUE')
        self.assertEqual(day_trade_permission(['TP','TP','TP','TP','SL'])['status'],'STOP_FXM_DAY_TRADE_SEQUENCE')
    def test_day_unknown_outcome_review(self):
        self.assertTrue(day_trade_permission(['TP','UNKNOWN'])['status'].startswith('REVIEW_'))

if __name__ == '__main__': unittest.main()