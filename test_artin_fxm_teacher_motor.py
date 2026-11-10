import unittest
from decimal import Decimal as D
from fxm_teacher_policy import AccountRisk
from artin_fxm_teacher_motor import evaluate_fxmgates

class FXMClassroomBridgeTests(unittest.TestCase):
    def original(self, *, visual=False, meaning=False, status='ELIGIBLE'):
        return {'pinned_motor_commit':'PINNED',
                'all_13_route_implementations_loaded':True,
                'cases':[{'case_id':'scene1','route_id':'REVERSAL_THREE',
                          'motor_status':status,
                          'teacher_choice_independently_verified':meaning,
                          'teacher_visual_verified':visual,
                          'teacher_choice_in_record':'ENTER'}]}

    def case(self):
        return [{'case_id':'scene1','side':'BUY',
                 'paper_trade_teacher_source':'video-session19@3623:verified',
                 'paper_trade':{'entry_price':'4000','initial_stop':'3995',
                     'instrument':{'money_per_price_unit_per_lot':'100',
                                   'min_lot':'0.01','lot_step':'0.01'},
                     'costs':{'round_trip_fee_per_lot':'0',
                              'adverse_price_allowance':'0'}}}]

    def invoke(self, *args, **kwargs):
        return evaluate_fxmgates(*args,
              AccountRisk(D('1000'),D('1000'),D('1')),risk_style='DAY_TRADE',
              winrate='35',winrate_evidence='journal:verified',**kwargs)

    def test_verified_and_entry_engine_eligible_sizes_paper_not_order(self):
        r=self.invoke(self.original(visual=True, meaning=True),self.case())
        self.assertEqual(r['fxm_paper_intents'],1)
        self.assertEqual(r['results'][0]['fxm_sizing']['lots'],'0.02')
        self.assertEqual(r['orders_sent'],0)

    def test_unverified_visual_blocks_even_if_engine_eligible(self):
        r=self.invoke(self.original(visual=False,meaning=True),self.case())
        self.assertEqual(r['fxm_paper_intents'],0)
        self.assertEqual(r['results'][0]['fxm_status'],'WAIT_TEACHER_ENTRY_SEMANTICS_AND_CHART_FACTS')

    def test_unverified_semantics_blocks_even_if_chart_seen(self):
        r=self.invoke(self.original(visual=True,meaning=False),self.case())
        self.assertEqual(r['fxm_paper_intents'],0)

    def test_review_in_entry_engine_blocks_even_when_all_bool_flags_true(self):
        r=self.invoke(self.original(visual=True,meaning=True,status='REVIEW'),self.case())
        self.assertEqual(r['fxm_paper_intents'],0)

    def test_missing_paper_contract_blocks(self):
        r=self.invoke(self.original(visual=True,meaning=True),[{'case_id':'scene1','side':'BUY'}])
        self.assertEqual(r['results'][0]['fxm_status'],'WAIT_SOURCED_ENTRY_STOP_AND_CONTRACT')

    def test_missing_rr_evidence_blocks(self):
        r=evaluate_fxmgates(self.original(visual=True,meaning=True),self.case(),
                AccountRisk(D('1000'),D('1000'),D('1')),risk_style='DAY_TRADE')
        self.assertEqual(r['results'][0]['fxm_status'],'WAIT_FXM_TARGET_POLICY')

    def test_account_loss_blocks_even_if_all_entry_rules_true(self):
        r=evaluate_fxmgates(self.original(visual=True,meaning=True),self.case(),
                AccountRisk(D('800'),D('1000'),D('1')),risk_style='DAY_TRADE',
                winrate='35',winrate_evidence='journal:verified')
        self.assertEqual(r['results'][0]['fxm_status'],'STOP_FXM_20_PERCENT_BALANCE_DRAWDOWN')

if __name__ == '__main__': unittest.main()