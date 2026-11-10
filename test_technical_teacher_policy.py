import unittest
from technical_teacher_policy import apply_technical_handout

def f(value,at=9,src='real-chart-capture:clip:9'):
    return {'value':value,'known_at':at,'source':src}

class TechnicalHandoutGeometryTest(unittest.TestCase):
    def case(self,route='REVERSAL_CLASSIC',side='BUY'):
        evidence={'entry_family':f('REVERSAL' if route.startswith('REVERSAL_') else 'BREAK'),
                  'teacher_scene_meaning_confirmed':f(True),
                  'stop_anchor_kind':f('PIVOT'),
                  'entry_price':f('4000'),
                  'structural_stop_price':f('3995' if side=='BUY' else '4005')}
        if route.startswith('REVERSAL_'):
            evidence['prz_context']=f('FVG');evidence['prz_teacher_confirmed']=f(True)
        else:
            evidence['break_line_price']=f('3998' if side=='BUY' else '4002')
            evidence['break_teacher_confirmed']=f(True)
            evidence['decision_close']=f('4000')
        size={'status':'PAPER_SIZED_ONLY','entry':'4000','structural_stop_unchanged':
              '3995' if side=='BUY' else '4005','lots':'0.02'}
        return {'route':route,'side':side,'at':10,'evidence':evidence,'fxm_sizing':size,
                'rr':{'status':'RR_CANDIDATE_FROM_HANDOUT','rr':'2'}}
    def test_reversal_buy_stop_and_tp(self):
        r=apply_technical_handout(**self.case())
        self.assertEqual((r['stop'],r['target']),('3995','4010'))
    def test_break_sell_stop_and_tp(self):
        r=apply_technical_handout(**self.case('BREAK_STRONG','SELL'))
        self.assertEqual((r['stop'],r['target']),('4005','3990'))
    def test_missing_chart_stop_blocks(self):
        c=self.case();del c['evidence']['structural_stop_price']
        self.assertEqual(apply_technical_handout(**c)['status'],'MISSING_SOURCED_CHART_FACT:structural_stop_price')
    def test_future_quote_blocks(self):
        c=self.case();c['evidence']['entry_price']['known_at']=11
        self.assertEqual(apply_technical_handout(**c)['status'],'FUTURE_OR_UNTIMED_CHART_FACT:entry_price')
    def test_stop_side_blocks(self):
        c=self.case();c['evidence']['structural_stop_price']['value']='4005'
        self.assertEqual(apply_technical_handout(**c)['status'],'STOP_NOT_ON_LOSS_SIDE')
    def test_sized_stop_cannot_be_substituted(self):
        c=self.case();c['fxm_sizing']['structural_stop_unchanged']='3990'
        self.assertEqual(apply_technical_handout(**c)['status'],'STOP_ENTRY_NOT_IDENTICAL_TO_FXM_RISK_PLAN')
    def test_break_close_must_be_beyond_sourced_line(self):
        c=self.case('BREAK_STRONG');c['evidence']['break_line_price']['value']='4001'
        self.assertEqual(apply_technical_handout(**c)['status'],'CLOSE_NOT_BEYOND_TEACHER_BREAK_LINE')
    def test_pullback_variants_are_not_derived_from_pdf_entry_families(self):
        c=self.case('PULLBACK_STANDARD')
        self.assertEqual(apply_technical_handout(**c)['status'],'WAIT_SOURCE_MAPPING_FOR_THIS_ENTRY_FAMILY')
    def test_pdf_as_market_source_rejected(self):
        c=self.case();c['evidence']['prz_context']['source']='Technical(1).pdf#page=13'
        self.assertEqual(apply_technical_handout(**c)['status'],'CHART_SOURCE_REQUIRED:prz_context')
    def test_missing_risk_gate_blocks(self):
        c=self.case();c['fxm_sizing']['status']='NO_TRADE'
        self.assertEqual(apply_technical_handout(**c)['status'],'WAIT_PREVIOUS_ENGINE_OR_FXM_RISK_GATES')

if __name__=='__main__':unittest.main()