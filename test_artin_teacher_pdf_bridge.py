import unittest
from decimal import Decimal as D
from fxm_teacher_policy import AccountRisk
from artin_fxm_teacher_motor import evaluate_fxmgates

class PdfBridgeTests(unittest.TestCase):
 def evidence(self):
    def f(v):return dict(value=v,known_at=900,source='captured-chart-id:sample-scene@900')
    return dict(entry_family=f('REVERSAL'),teacher_scene_meaning_confirmed=f(True),
                prz_context=f('TREND'),prz_teacher_confirmed=f(True),
                stop_anchor_kind=f('PIVOT'),structural_stop_price=f('3995'),entry_price=f('4000'))
 def scenario(self,eligible='ELIGIBLE'):
    prior={'pinned_motor_commit':'TEST','all_13_route_implementations_loaded':True,
          'cases':[dict(case_id='teacher-scene',route_id='REVERSAL_CLASSIC',
                        motor_status=eligible,teacher_choice_independently_verified=False,
                        teacher_visual_verified=False,teacher_choice_in_record=None)]}
    cases=[dict(case_id='teacher-scene',side='BUY',paper_trade={
      'entry_price':'4000','initial_stop':'3995',
      'instrument':{'money_per_price_unit_per_lot':'100','min_lot':'0.01','lot_step':'0.01'},
      'costs':{'round_trip_fee_per_lot':'0','adverse_price_allowance':'0'}},
      teacher_pdf_plan={'target_mode':'THREE_TP','target_mode_source':'FXM.pdf#page=4',
                        'decision_at':901,'chart_evidence':self.evidence()})]
    return prior,cases
 def run_bridge(self,eligible='ELIGIBLE',enabled=True):
    a,b=self.scenario(eligible)
    return evaluate_fxmgates(a,b,AccountRisk(D('1000'),D('1000'),D('1')),
       risk_style='DAY_TRADE',technical_pdf_enabled=enabled,
       winrate='55',winrate_evidence='verified-journal')
 def test_pdf_branch_accepts_rule_without_claiming_video_certification(self):
    result=self.run_bridge()
    p=result['results'][0]['teacher_pdf_trade_plan']
    self.assertEqual(p['status'],'PAPER_TEACHER_PDF_TRADE_PLAN')
    self.assertEqual(p['targets']['tp2'],'4006.5')
    self.assertEqual(result['teacher_pdf_plans_satisfied'],1)
    self.assertEqual(result['orders_sent'],0)
    self.assertNotIn('position',p)
 def test_pdf_mode_does_not_override_existing_classroom_veto(self):
    p=self.run_bridge(eligible='REVIEW')['results'][0]['teacher_pdf_trade_plan']
    self.assertEqual(p['status'],'WAIT_PINNED_13_ROUTE_ENTRY_CORE')
 def test_no_pdf_does_not_change_previous_fxmgate(self):
    r=self.run_bridge(enabled=False)
    self.assertIsNone(r['results'][0]['teacher_pdf_trade_plan'])
    self.assertEqual(r['teacher_pdf_plans_satisfied'],0)
    self.assertEqual(r['results'][0]['fxm_status'],'WAIT_TEACHER_ENTRY_SEMANTICS_AND_CHART_FACTS')

if __name__=='__main__': unittest.main()